"""Opt-in publication and a prepaid continuation of the existing batch stages.

The first reservation includes a separate vocabulary allowance. Sentence-item
refunds cannot release that allowance. At the stage boundary, settlement and the
child reservation happen in one database transaction, under the dictionary locks.
No browser visit, second approval, or additional unapproved debit is needed.
"""
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN

from django.db import transaction
from django.http import Http404
from django.utils import timezone

from . import porting, port_vocabulary as vocabulary, port_costs, tts
from .models import Entry, PortRun, PortItem, PortSpeech, PortEntryLink, VocabularyState, SentenceWord
from .services import Conflict

VERSION = 'automatic-dictionary-1'
ZERO = Decimal('0')


def metadata(run):
    return {'automatic_publication': True, 'publication_authorized_by': run.port.user_id,
            'automatic_run': str(run.options.get('automatic_root', run.pk))}


def missing_audio(entry):
    from .lexicon import recordings
    words = Entry.objects.filter(pk__in=SentenceWord.objects.filter(
        sentence_text_id=entry.current_text_id).values('word_entry_id'), archived=False,
        current_text__status='accepted').select_related('dictionary', 'current_text', 'current_meaning')
    return [e for e in [entry, *words] if e.word and not recordings(e, entry.dictionary)]


def followup(entry, prices, extra=0):
    """Never replace vocabulary that somebody edited after its last generation."""
    # Retrying missing work is not a linguistic review of an unchanged warning.
    # Keep a flagged automatic sentence out of later bulk derivation until its
    # wording is edited, its flag is cleared, or that wording is checked.
    from .models import LanguageCheck
    checked = LanguageCheck.objects.filter(entry=entry, text=entry.current_text,
        meaning=entry.current_meaning).exists()
    if not checked:
        snapshot = vocabulary.sentence_snapshot(entry)
        for item in PortItem.objects.filter(saved_entry=entry, needs_attention=True,
                run__options__automatic=True):
            if item.review_values.get('automatic_sentence') == snapshot:
                return None
    state = VocabularyState.objects.filter(sentence=entry).first()
    if state and not vocabulary.current_state(entry, state):
        return None
    audio = missing_audio(entry)
    if state and not audio:
        return None
    estimate = ZERO if state else vocabulary.estimate(entry, prices, extra)[0]
    # New words are included in vocabulary.estimate; add only already-known
    # missing clips. This is an explicit retry estimate, not a silent paid retry.
    estimate += sum((port_costs.speech(e.word, e.dictionary.language, prices,
        sentence=e.entry_type == 'sentence') for e in audio), ZERO)
    return {'entry': entry.pk, 'sentence': vocabulary.sentence_snapshot(entry),
            'audio_only': bool(state), 'retry_audio': True,
            'estimated': str(porting.money(estimate)),
            'allowance': str(port_costs.allowance(estimate))}


def prepare_quote(run):
    """Add the second stage to a local estimate; no network or credit mutation."""
    if run.stage not in {'sentences', 'descriptions', 'vocabulary'}:
        raise Conflict('Automatic processing is not available for this job.')
    if not tts.language_code(run.port.language):
        raise Conflict('Automatic processing needs a language with supported spoken audio.')
    run.options.update(automatic=True, automatic_recipe=VERSION)
    if run.stage == 'vocabulary':
        return
    run.options['automatic_vocabulary_recipe'] = vocabulary.VERSION
    estimate = reserve = ZERO
    extra = 0
    if run.port.target_id:
        refs = vocabulary.context(run.port.target)
        from .models import Contribution
        ids = [r[k] for r in refs for k in ['text', 'meaning'] if r[k]]
        extra = sum(len(p.word) + len(p.meaning) for p in Contribution.objects.filter(pk__in=ids))
    for item in run.items.select_related('source_entry'):
        if item.snapshot.get('entry_type') != 'sentence':
            continue
        entry = item.source_entry if run.stage != 'descriptions' else Entry(word='x'*180, meaning='x'*500)
        value, maximum = vocabulary.estimate(entry, run.prices, extra)
        estimate += value; reserve += maximum
    existing = []
    if run.port.target_id:
        # Include earlier accepted sentences whose vocabulary/audio is missing.
        # This also makes Retry useful after a partly successful automatic run.
        ids = (PortItem.objects.filter(run__port=run.port, status='saved').exclude(saved_entry=None)
               .values('saved_entry_id') if run.port.is_description_batch else
               PortEntryLink.objects.filter(port=run.port).values('destination_id'))
        changing = set(PortEntryLink.objects.filter(port=run.port,
            source_id__in=run.items.values('source_entry_id')).values_list('destination_id', flat=True))
        for entry in Entry.objects.filter(pk__in=ids, archived=False, entry_type='sentence',
                current_text__status='accepted').exclude(pk__in=changing).select_related(
                    'dictionary', 'current_text', 'current_meaning'):
            value = followup(entry, run.prices, extra)
            if value:
                existing.append(value)
                estimate += Decimal(value['estimated']); reserve += Decimal(value['allowance'])
    run.options.update(automatic_existing=existing, automatic_vocabulary_estimate=str(estimate),
        automatic_vocabulary_reserve=str(reserve))
    run.estimated_usd += estimate; run.allowance_usd += reserve


def check_quote(run):
    if not run.options.get('automatic'):
        return
    if run.options.get('automatic_recipe') != VERSION or (
            run.stage != 'vocabulary' and run.options.get('automatic_vocabulary_recipe') != vocabulary.VERSION):
        raise Conflict('Automatic processing changed. Prepare another estimate.')
    for record in run.options.get('automatic_existing', []):
        entry = Entry.objects.select_related('dictionary', 'current_text', 'current_meaning').get(pk=record['entry'])
        if entry.archived or vocabulary.sentence_snapshot(entry) != record['sentence']:
            raise Conflict('An accepted sentence changed. Prepare another estimate.')
    if run.port.target_id:
        vocabulary.authority(run.port)


def publish_ready(run):
    """Called under dispatch's locks, before settling or queuing more work."""
    if not run.options.get('automatic') or run.status != 'running':
        return
    for item in run.items.filter(status__in=['ready', 'unclear']).select_related('run__port'):
        item.run = run
        try:
            with transaction.atomic():
                if run.stage == 'vocabulary':
                    entry = vocabulary.save_item(run.port.user, item.pk, item.result['words'], automatic=True)
                else:
                    if not item.result.get('word', '').strip():
                        raise Conflict('No usable sentence or wording was returned.')
                    homographs = item.result.get('tts_synthesis',{}).get('english_homographs')
                    flagged = item.status == 'unclear' or item.needs_attention or bool(homographs)
                    if flagged:
                        item.needs_attention = True
                        item.attention_note = item.attention_note or (
                            'Check pronunciation: this wording can be read as English.' if homographs else
                            'The AI was uncertain about this suggestion.')
                        item.save(update_fields=['needs_attention', 'attention_note'])
                    entry = porting.save_item(run.port.user, item.pk, item.result, automatic=True)
                    item.refresh_from_db()
                    item.saved_entry = entry
                    item.review_values['automatic_sentence'] = vocabulary.sentence_snapshot(entry)
                    item.save(update_fields=['saved_entry', 'review_values'])
        except (Conflict, Http404, KeyError, ValueError, OSError):
            # Savepoint keeps partially created entries and files out of the DB.
            # Keep a usable preview for later inspection, but never loop on it.
            item.refresh_from_db()
            item.status = 'failed'; item.needs_attention = True
            item.message = 'Could not publish automatically. Existing work was kept; check this item or retry with a fresh estimate.'
            item.save(update_fields=['status', 'needs_attention', 'message'])


def queue_existing_audio(run, item, entry, *, include_words=False):
    entries = missing_audio(entry) if include_words else [entry]
    from .lexicon import recordings
    for target in entries:
        if not recordings(target, run.port.target):
            PortSpeech.objects.get_or_create(run=run, entry=target, text=target.current_text,
                defaults={'item': item, 'meaning': target.current_meaning})


def continue_workflow(run):
    """Called by settle, in its transaction. Once-only and bounded by approval."""
    if (not run.options.get('automatic') or run.stage not in {'sentences', 'descriptions'} or
            run.status != 'complete' or not run.approved_at or run.options.get('automatic_continued')):
        return
    try:
        with transaction.atomic():
            _continue(run)
    except (Conflict, Http404, ValueError):
        # A setting/permission change must not roll back first-stage results or
        # refunds. Resume can retry the *unstarted* continuation after correction.
        run.refresh_from_db()
        run.options['automatic_error'] = 'Vocabulary could not start because inputs, permissions or configuration changed. Saved results are kept. Resume after correcting the settings, or request a fresh estimate.'
        run.save(update_fields=['options'])


def _continue(run):
    porting.authority(run.port)
    vocabulary.authority(run.port)
    # Frozen first approval: changed model, recipe, price or payer requires a
    # fresh estimate. Never silently approve a different provider configuration.
    from . import photo_ai
    model, _, _, prices = photo_ai.configuration(run.port.user)
    if (model != run.model or porting.payer_now(run.port.user) != run.payer or
            any(str(v) != run.prices.get(k) for k, v in prices.items()) or
            run.options.get('automatic_vocabulary_recipe') != vocabulary.VERSION or
            run.prices.get('speech_recipe') != tts.INSTRUCTIONS_VERSION or
            run.options.get('automatic_recipe') != VERSION):
        raise Conflict('Configuration changed.')
    records = list(run.options.get('automatic_existing', []))
    for item in run.items.filter(status='saved', invalidated=False, needs_attention=False).select_related('saved_entry'):
        if item.saved_entry and item.saved_entry.entry_type == 'sentence':
            records.append({'entry': item.saved_entry_id, 'sentence': item.review_values.get('automatic_sentence'),
                            'audio_only': False, 'retry_audio': False})
    refs = vocabulary.context(run.port.target)
    context_ids = [ref[k] for ref in refs for k in ['text', 'meaning'] if ref[k]]
    from .models import Contribution
    extra = sum(len(p.word) + len(p.meaning) for p in Contribution.objects.filter(pk__in=context_ids))
    plans = []
    for record in records:
        entry = Entry.objects.select_related('dictionary', 'current_text', 'current_meaning').get(pk=record['entry'])
        if entry.archived or vocabulary.sentence_snapshot(entry) != record['sentence']:
            continue  # an intervening human edit is preserved
        if record.get('retry_audio'):
            current = followup(entry, run.prices, extra)
            if not current:
                continue
            estimate, maximum = Decimal(current['estimated']), Decimal(current['allowance'])
            record['audio_only'] = current['audio_only']
        else:
            if vocabulary.current_state(entry):
                continue
            estimate, maximum = vocabulary.estimate(entry, run.prices, extra)
        plans.append((record, entry, estimate, maximum))
    if not plans:
        run.options.update(automatic_continued=True)
        run.options.pop('automatic_error', None)
        run.save(update_fields=['options'])
        return
    child = PortRun.objects.create(port=run.port, stage='vocabulary', model=run.model,
        source_language=run.port.language, source_explanation_language=run.port.explanation_language,
        prices={**{k:str(v) for k,v in prices.items()}, 'speech_recipe':tts.INSTRUCTIONS_VERSION,
                'vocabulary_recipe':vocabulary.VERSION}, payer=run.payer,
        options={'budget_version':1, 'automatic':True, 'automatic_recipe':VERSION,
                 'automatic_root':str(run.pk)}, expires_at=timezone.now()+timedelta(hours=1))
    total = sum((p[3] for p in plans), ZERO)
    cap = Decimal(run.options['automatic_vocabulary_reserve'])
    # Longer translations can change the forecast. Keep the approved cap;
    # existing budget guards pause individual requests before an overrun.
    scale = min(Decimal('1'), cap / total) if total else Decimal('0')
    for record, entry, estimate, maximum in plans:
        snap = record['sentence']
        item = PortItem.objects.create(run=child, source_entry=entry,
            snapshot={'entry_type':'sentence', 'sentence':snap, 'image':snap['image'], 'context':refs},
            estimated_usd=estimate, allowance_usd=(maximum*scale).quantize(Decimal('.0001'), rounding=ROUND_DOWN),
            review_values={'automatic_audio_only':record['audio_only'],
                           'automatic_retry_audio':record['retry_audio']})
        item.sources.set(snap['ids']+context_ids)
        child.estimated_usd += item.estimated_usd; child.allowance_usd += item.allowance_usd
    child.save()
    # The root refund and this smaller reservation commit together. The child
    # is not permitted to debit more than the already approved vocabulary pot.
    porting.approve(run.port.user, child.pk)
    run.options.update(automatic_continued=True, automatic_child=str(child.pk))
    run.options.pop('automatic_error', None)
    run.save(update_fields=['options'])


def prepare_approved(run):
    if not run.options.get('automatic') or run.stage != 'vocabulary':
        return
    for item in run.items.filter(review_values__automatic_audio_only=True):
        entry = vocabulary.current_item(item)
        item.status = 'saved'; item.save(update_fields=['status'])
        queue_existing_audio(run, item, entry, include_words=True)


def related_runs(run):
    root = PortRun.objects.select_related('port__source', 'port__destination', 'port__user').get(
        pk=run.options['automatic_root']) if run.options.get('automatic_root') else run
    children = PortRun.objects.filter(options__automatic_root=str(root.pk)).select_related('port__user')
    return root, [root, *children]


def retry_quote(user, run, token):
    root, _ = related_runs(run)
    if (not root.options.get('automatic') and root.status != 'estimate') or root.port.user_id != user.pk:
        raise Conflict('This is not your automatic job.')
    if root.port.runs.filter(status='running').exists():
        raise Conflict('Finish or cancel the current job before estimating another attempt.')
    if root.stage == 'descriptions':
        from .batch_descriptions import quote
        return quote(user, root.port.source, token, root.options.get('image_status','both'),
                     root.port.voice, automatic=True)
    if root.stage == 'vocabulary':
        return vocabulary.quote(user, root.port, token, automatic=True)
    return porting.quote(user, root.port.source, {}, token, port=root.port, automatic=True,
                         sentence_updates=bool(root.options.get('sentence_updates')))


def summary(run):
    root, runs = related_runs(run)
    items = PortItem.objects.filter(run__in=runs)
    clips = PortSpeech.objects.filter(run__in=runs)
    active = next((r for r in runs if r.status == 'running'), None)
    attention = items.filter(needs_attention=True).count() + clips.filter(status__in=['failed','discarded']).count()
    attention += items.filter(status__in=['failed','discarded'],needs_attention=False).count()
    attention += items.filter(status='saved',needs_attention=False,message__contains='no usable audio').count()
    return {'root':root, 'runs':runs, 'active':active, 'finished':not active and root.status != 'estimate',
        'attention':attention, 'sentences':root.items.filter(status='saved').count() if root.stage != 'vocabulary' else 0,
        'vocabulary':items.filter(run__stage='vocabulary',status='saved').count(),
        'audio':clips.filter(status='ready').count(),
        'held':sum((r.reserved_usd-r.released_usd if not r.settled else ZERO for r in runs),ZERO),
        'charged':sum((r.charged_usd for r in runs if r.settled),ZERO)}
