"""Saved homograph listening checklist and explicitly accepted audio repairs.

Review-only records use the existing batch storage with zero cost and no queue.
Each repair is a separate immutable quote. The shared private-clip worker settles
its generation cost before review; publication always requires a fresh POST.
"""
from collections import Counter
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import re
import uuid

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from projects.billing import get_user_balance_usd
from . import carrier, homograph_experiments as experiments, photo_ai, port_costs, porting, tts
from . import sentence_forms as sf
from .collections import content_digest
from .evaluation_views import page
from .lexicon import recordings
from .models import Contribution, ContributionDependency, Dictionary, LanguagePort, PortItem, PortRun, SentenceWord
from .permissions import get_dictionary, require_owner
from .public_browsing import contributions
from .services import Conflict, accept, event
from .storage import delete_file, path_for, write_upload
from .views import context, private_media_response

VERSION = 'homograph-review-1'
STAGE = 'audio_repair'
REVIEW = 'audio_review'
MAX_REPAIR = 100
DEFAULT_CANDIDATES = 3
MAX_CANDIDATES = 5
DECISIONS = {'': _('Not reviewed'), 'keep': _('Keep'), 'replace': _('Needs regeneration')}
GENERATION_METHODS = {'mixed': _('Both methods'), **experiments.METHODS}


def method_choices(dictionary):
    if tts.language_code(dictionary.language) in carrier.AUTOMATIC_LANGUAGES - {'en'}:
        return list(GENERATION_METHODS.items())
    return [('guidance', GENERATION_METHODS['guidance'])]


def candidate_methods(row, count, method):
    supported = carrier.homograph_eligible(row['word'], row['language'])
    if method == 'carrier' and not supported:
        raise Conflict(_('Carrier extraction is unavailable for some selected items. Choose Both methods or pronunciation guidance.'))
    if method == 'mixed' and supported:
        return ['guidance' if n % 2 == 0 else 'carrier' for n in range(count)]
    return [method if method != 'mixed' else 'guidance'] * count


def authority(port):
    dictionary = Dictionary.objects.get(pk=port.source_id)
    require_owner(port.user, dictionary)
    if not port.user.is_active or dictionary.archived:
        raise Http404
    if not dictionary.tts_enabled or not tts.language_code(dictionary.language):
        raise Conflict(_('Enable saved AI audio in dictionary settings before regenerating.'))
    if (dictionary.language, dictionary.explanation_language) != (port.language, port.explanation_language):
        raise Conflict(_('The dictionary languages changed. Prepare a new estimate.'))


def row_for(part):
    row = experiments.candidate(part, for_review=True)
    if not row:
        return None
    if part.kind == 'form':
        audio = [c for c in part.entry.contributions.filter(kind='audio', status='accepted', shared_from=part)
                 .exclude(file_path='') if c.provenance.get('origin') != 'synthetic' or sf.audio_current(c)]
    else:
        audio = recordings(part.entry, part.entry.dictionary)
    permitted = set(contributions(part.entry.dictionary).filter(pk__in=[a.pk for a in audio]).values_list('pk', flat=True))
    audio = sorted((a for a in audio if a.pk in permitted), key=lambda a:a.pk)
    row['audio'] = [{'id':a.pk, 'digest':content_digest(a), 'synthetic':a.provenance.get('origin') == 'synthetic'} for a in audio]
    row['language'] = part.entry.dictionary.language
    row['explanation_language'] = part.entry.dictionary.explanation_language
    voice = audio[0].provenance.get('voice') if audio else tts.VOICE
    row['voice'] = voice if voice in tts.VOICE_NAMES else tts.VOICE
    return row


def live_row(dictionary, part_id):
    part = Contribution.objects.select_related('entry__dictionary','entry__current_text','entry__current_meaning').filter(
        pk=part_id, entry__dictionary=dictionary).first()
    row = row_for(part) if part else None
    if not row:
        raise Conflict(_('This word or form is no longer available. Reload the review page.'))
    return row


def fingerprint(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def source_ids(rows):
    return {pk for row in rows for pk in row['ids'] + [a['id'] for a in row['audio']]}


def protected(row):
    return any(not a['synthetic'] for a in row['audio'])


def single_word(row):
    # The broad detector remains useful for synthesis guidance. The listening
    # checklist defaults to whole single words, not tokens inside expressions.
    return bool(re.fullmatch(r"[^\W\d_]+(?:['’][^\W\d_]+)*", row['word'].strip()))


def group_words(dictionary, rows):
    parts = Contribution.objects.filter(pk__in=[r['id'] for r in rows if r['kind']=='form'],
        entry__dictionary=dictionary).select_related('entry__dictionary').in_bulk()
    grouped = {}
    for row in rows:
        key = ('single', row['id'])
        if row['kind']=='form' and not protected(row):
            key = ('form', *sf.audio_key(parts[row['id']], row['voice']))
        grouped.setdefault(key, []).append(row)
    return [sorted(members, key=lambda r:r['id']) for members in grouped.values()]


def review_groups(user, dictionary, *, include_expressions=False, parts=None):
    rows = rows_for(user, dictionary, parts=parts, include_expressions=include_expressions)
    by_id = {r['word']['id']:r for r in rows}
    result = []
    for members in group_words(dictionary, [r['word'] for r in rows
            if include_expressions or single_word(r['word'])]):
        values = [by_id[r['id']]['decision'] for r in members]
        result.append({'word':members[0], 'members':members,
            'decision':values[0] if len(set(values))==1 else '', 'mixed':len(set(values))>1,
            'protected':any(protected(r) for r in members),
            'token':fingerprint({'members':members, 'decisions':values})})
    return sorted(result, key=lambda r:(r['word']['word'].casefold(), r['word']['meaning'], r['word']['id']))


def group_now(user, dictionary, part_id, token):
    part = get_object_or_404(Contribution, pk=part_id, entry__dictionary=dictionary)
    parts = Contribution.objects.filter(pk=part_id)
    if part.kind == 'form':
        parts = Contribution.objects.filter(kind='form',
            provenance__form_basis__word_entry=part.provenance.get('form_basis', {}).get('word_entry'))
    group = next((g for g in review_groups(user, dictionary, include_expressions=True, parts=parts)
                  if g['word']['id']==part_id), None)
    if not group or group['token'] != token:
        raise Conflict(_('The recording or its review changed. Reload before saving.'))
    return group


def record_decision(user, dictionary, row, decision):
    # Approval follows the exact recording; changing the decision removes it.
    for audio in Contribution.objects.filter(pk__in=[a['id'] for a in row['audio'] if a['synthetic']]):
        if bool(sf.pronunciation_approved(audio)) != (decision=='keep'):
            audio.provenance = {**audio.provenance, 'pronunciation_approved':decision=='keep',
                'reviewed_by':user.pk, 'reviewed_at':timezone.now().isoformat()}
            audio.save(update_fields=['provenance'])
    remember(user, dictionary, live_row(dictionary, row['id']), decision)


@transaction.atomic
def mark_group(user, dictionary, part_id, token, decision):
    porting.locks(); require_owner(user, dictionary)
    group = group_now(user, dictionary, part_id, token)
    if decision not in DECISIONS or (decision=='replace' and group['protected']):
        raise Conflict(_('Human recordings are protected. Use the entry page to discuss changes.'))
    if decision=='keep' and any(not r['audio'] for r in group['members']):
        raise Conflict(_('There is no current recording to keep.'))
    for row in group['members']:
        record_decision(user, dictionary, row, decision)


@transaction.atomic
def use_existing(user, dictionary, part_id, token, audio_id, paths):
    """One explicit choice repairs the displayed group without an API request."""
    porting.locks(); require_owner(user, dictionary)
    group = group_now(user, dictionary, part_id, token)
    if group['protected'] or audio_id not in source_ids(group['members']) or not any(
            a['id']==audio_id for row in group['members'] for a in row['audio']):
        raise Conflict(_('This recording is no longer available for reuse.'))
    source = Contribution.objects.get(pk=audio_id)
    # Make this reviewed clip a new reuse root, even if it was itself copied.
    source.provenance = {**source.provenance, 'pronunciation_approved':True,
        'reviewed_by':user.pk, 'reviewed_at':timezone.now().isoformat()}
    source.provenance.pop('audio_reuse_source', None)
    source.save(update_fields=['provenance'])
    for row in group['members']:
        old_ids = [a['id'] for a in row['audio']]
        if audio_id not in old_ids:
            part = Contribution.objects.select_related('entry__dictionary').get(pk=row['id'])
            new = sf.copy_audio(part, source, paths, provenance={'replaces_audio_ids':old_ids})
            event(dictionary, user, 'homograph_audio_reuse', part.entry, f'Audio {new.pk}; source {source.pk}')
        Contribution.objects.filter(pk__in=old_ids, status='accepted').exclude(pk=audio_id).update(status='superseded')
        remember(user, dictionary, live_row(dictionary, row['id']), 'keep')


def targets(item, part_id):
    ids = item.snapshot.get('audio_groups', {}).get(str(part_id), [part_id])
    return [r for r in item.snapshot['words'] if r['id'] in ids]


def form_labels(rows):
    """Display why identical spellings can still belong to different groups."""
    parts = Contribution.objects.filter(pk__in=[r['word']['id'] for r in rows if r['word']['kind']=='form']).in_bulk()
    bases = {pk:p.provenance.get('form_basis', {}) for pk,p in parts.items()}
    sources = Contribution.objects.filter(pk__in={b.get(k) for b in bases.values()
        for k in ('word_text','word_meaning') if b.get(k)}).in_bulk()
    for row in rows:
        basis = bases.get(row['word']['id'], {})
        lemma, meaning = sources.get(basis.get('word_text')), sources.get(basis.get('word_meaning'))
        row['lemma'] = lemma.word if lemma else ''
        row['lemma_meaning'] = meaning.meaning if meaning else ''


def review_run(user, dictionary):
    return PortRun.objects.filter(stage=REVIEW, port__source=dictionary, port__user=user,
        port__language=dictionary.language, port__explanation_language=dictionary.explanation_language,
        options__review_version=VERSION).first()


def decisions(user, dictionary):
    run = review_run(user, dictionary)
    return {row['id']:(row, item.review_values.get(str(row['id']), ''))
            for item in run.items.filter(invalidated=False) for row in item.snapshot.get('words', [])} if run else {}


def remember(user, dictionary, row, decision):
    """Caller holds the dictionary lock. Only current, versioned decisions count."""
    run = review_run(user, dictionary)
    if not run:
        port = LanguagePort.objects.create(source=dictionary, user=user, is_audio_batch=True,
            name='Homograph listening checklist', language=dictionary.language,
            explanation_language=dictionary.explanation_language)
        run = PortRun.objects.create(port=port, stage=REVIEW, status='complete', settled=True,
            source_language=dictionary.language, source_explanation_language=dictionary.explanation_language,
            model='', payer='server', expires_at=timezone.now(), options={'review_version':VERSION})
    item, _created = PortItem.objects.get_or_create(run=run, source_entry_id=row['entry'])
    rows = [r for r in item.snapshot.get('words', []) if r['id'] != row['id']]
    rows.append(row)
    item.snapshot, item.status, item.invalidated = {'words':rows}, 'ready', False
    item.review_values[str(row['id'])] = decision
    item.save(update_fields=['snapshot','status','invalidated','review_values'])
    item.sources.set(source_ids(rows))


@transaction.atomic
def mark(user, dictionary, part_id, token, previous, decision):
    porting.locks(); require_owner(user, dictionary)
    row = live_row(dictionary, part_id)
    old_row, old_decision = decisions(user, dictionary).get(row['id'], (None, ''))
    if old_row != row:
        old_decision = ''
    if token != fingerprint(row) or previous != old_decision:
        raise Conflict(_('The recording or its review changed. Reload before saving.'))
    if decision not in DECISIONS or (decision == 'replace' and protected(row)):
        raise Conflict(_('Human recordings are protected. Use the entry page to discuss changes.'))
    if decision == 'keep' and not row['audio']:
        raise Conflict(_('There is no current recording to keep.'))
    record_decision(user, dictionary, row, decision)


def rows_for(user, dictionary, *, parts=None, include_expressions=True):
    saved = decisions(user, dictionary)
    rows = []
    parts = (parts if parts is not None else Contribution.objects.all()).filter(entry__dictionary=dictionary, entry__archived=False,
        status='accepted', kind__in=['text','form']).select_related('entry__dictionary','entry__current_text','entry__current_meaning')
    for part in parts:
        if not include_expressions and not single_word({'word':part.word}):
            continue
        row = row_for(part)
        if row:
            old, decision = saved.get(row['id'], (None, ''))
            rows.append({'word':row, 'decision':decision if old == row else '',
                         'token':fingerprint(row), 'protected':protected(row)})
    return sorted(rows, key=lambda r:(r['word']['word'].casefold(),r['word']['meaning'],r['word']['id']))


def check_approval(run):
    if run.status == 'estimate' and PortRun.objects.filter(stage=STAGE, port__source=run.port.source,
            status='running').exclude(pk=run.pk).exists():
        raise Conflict(_('Finish or cancel the current audio repair before starting another.'))


@transaction.atomic
def quote(user, dictionary, token, candidate_count=DEFAULT_CANDIDATES, *, selected_ids=None, previous_run=None,
          include_expressions=False, generation_method='guidance'):
    porting.locks(); require_owner(user, dictionary)
    existing = PortRun.objects.filter(pk=token, port__source=dictionary, port__user=user, stage=STAGE).first()
    if existing:
        return existing
    if PortRun.objects.filter(pk=token).exists():
        raise Conflict(_('Reload the review page.'))
    if type(candidate_count) is not int or not 1 <= candidate_count <= MAX_CANDIDATES:
        raise Conflict(_('Choose between one and five candidates per word or form.'))
    if generation_method not in GENERATION_METHODS:
        raise Conflict(_('Choose a generation method.'))
    if generation_method == 'mixed' and candidate_count < 2:
        raise Conflict(_('Choose at least two candidates to use both methods.'))
    chosen = []
    for old, decision in decisions(user, dictionary).values():
        if decision != 'replace':
            continue
        if selected_ids is not None and old['id'] not in selected_ids:
            continue
        try:
            row = live_row(dictionary, old['id'])
        except Conflict:
            continue
        if row == old and not protected(row) and (include_expressions or single_word(row)):
            chosen.append(row)
    if not chosen:
        raise Conflict(_('Mark at least one current recording as Needs regeneration first.'))
    if selected_ids is not None and {row['id'] for row in chosen} != set(selected_ids):
        raise Conflict(_('The recording or its review changed. Reload before saving.'))
    audio_groups = group_words(dictionary, chosen)
    if len(audio_groups) > MAX_REPAIR:
        raise Conflict(_('Regenerate at most 100 marked words or forms in one batch.'))
    plans = {members[0]['id']:candidate_methods(members[0], candidate_count, generation_method)
             for members in audio_groups}
    has_carrier = any('carrier' in methods for methods in plans.values())
    model, _key, _personal, prices = photo_ai.configuration(user)
    port = LanguagePort.objects.create(source=dictionary, user=user, is_audio_batch=True,
        name='Review homograph audio', language=dictionary.language, explanation_language=dictionary.explanation_language)
    authority(port)
    run = PortRun.objects.create(pk=token, port=port, stage=STAGE, model=model,
        source_language=dictionary.language, source_explanation_language=dictionary.explanation_language,
        prices={**{k:str(v) for k,v in prices.items()}, 'speech_recipe':tts.INSTRUCTIONS_VERSION,
                **({'carrier_recipe':carrier.VERSION} if has_carrier else {})},
        options={'review_version':VERSION, 'candidate_count':candidate_count, 'generation_method':generation_method,
                 'previous_run':str(previous_run) if previous_run else ''}, payer=porting.payer_now(user),
        expires_at=timezone.now()+timedelta(hours=1))
    grouped = {}
    for members in audio_groups:
        grouped.setdefault(members[0]['entry'], []).append(members)
    for entry_id, groups in grouped.items():
        words = [row for members in groups for row in members]
        clips = []
        for members in groups:
            row = members[0]
            for number, method in enumerate(plans[row['id']], 1):
                if method == 'carrier':
                    estimated = porting.money(carrier.estimate(row['word'], dictionary.language))
                    allowance = experiments.clip_allowance(row['word'], dictionary.language, prices, method)
                else:
                    estimated = porting.money(port_costs.speech(row['word'], dictionary.language, prices))
                    allowance = port_costs.allowance(estimated)
                clips.append({'id':uuid.uuid4().hex, 'word_id':row['id'], 'method':method, 'candidate':number,
                    'status':'waiting', 'allowance':str(allowance), 'estimate':str(estimated), 'cost':'0', 'report':{}})
        item = PortItem.objects.create(run=run, source_entry_id=entry_id,
            snapshot={'words':words, 'audio_groups':{str(g[0]['id']):[r['id'] for r in g] for g in groups}}, result={'clips':clips},
            estimated_usd=sum(Decimal(c['estimate']) for c in clips),
            allowance_usd=sum(Decimal(c['allowance']) for c in clips))
        item.sources.set(source_ids(words))
        run.estimated_usd += item.estimated_usd
        run.allowance_usd += item.allowance_usd
    run.save()
    return run


@transaction.atomic
def quote_more(user, dictionary, run_id, item_id, part_id, token, candidate_count, *, generation_method='guidance'):
    """A new approved batch for one still-marked word; existing previews survive."""
    porting.locks(); require_owner(user, dictionary)
    item = get_object_or_404(PortItem.objects.select_related('run__port__source','run__port__user'),
        pk=item_id, run_id=run_id, run__stage=STAGE, run__port__source=dictionary, run__port__user=user)
    if not any(row['id'] == part_id for row in item.snapshot.get('words', [])):
        raise Http404
    # Retried submissions return their original estimate, even after later review.
    existing = PortRun.objects.filter(pk=token, stage=STAGE, port__source=dictionary,
        port__user=user, options__previous_run=str(run_id)).first()
    if existing:
        return existing
    current_item(item)
    if item.run.status != 'complete' or not item.run.settled:
        raise Conflict(_('Wait until generation finishes before requesting more candidates.'))
    if any(c['word_id'] == part_id and c.get('decision') == 'accept' for c in item.result.get('clips', [])):
        raise Conflict(_('A replacement was already accepted for this item. Return to the checklist to review it again.'))
    return quote(user, dictionary, token, candidate_count,
        selected_ids={r['id'] for r in targets(item, part_id)}, previous_run=run_id,
        include_expressions=True, generation_method=generation_method)


def current_item(item):
    authority(item.run.port)
    if item.invalidated or item.run.status == 'cancelled' or item.run.options.get('review_version') != VERSION:
        raise Conflict(_('This audio repair is no longer available.'))
    if any(c.get('method') == 'carrier' for c in item.result.get('clips', [])):
        if item.run.prices.get('carrier_recipe') != carrier.VERSION:
            raise Conflict(_('Carrier processing changed. Prepare and approve a fresh estimate.'))
    for expected in item.snapshot['words']:
        row = live_row(item.run.port.source, expected['id'])
        if protected(row) or row != expected:
            raise Conflict(_('The wording or recordings changed. Existing audio has been kept; start from the review page again.'))
    return item.source_entry


@transaction.atomic
def choose(user, run_id, item_id, clip_id, decision, paths):
    porting.locks()
    item = get_object_or_404(PortItem.objects.select_for_update().select_related('run__port__source','run__port__user'),
        pk=item_id, run_id=run_id, run__stage=STAGE, run__port__user=user)
    run = item.run
    require_owner(user, run.port.source)
    current_item(item)
    if run.status != 'complete' or not run.settled:
        raise Conflict(_('Wait until generation finishes before choosing recordings.'))
    clip = next((c for c in item.result.get('clips', []) if c['id']==clip_id), None)
    if not clip or clip['status'] != 'ready' or decision not in {'accept','reject'}:
        raise Conflict(_('This preview is not ready.'))
    if clip.get('decision'):
        return  # repeated submit is harmless
    if any(c['word_id'] == clip['word_id'] and c.get('decision') == 'accept' for c in item.result['clips']):
        raise Conflict(_('A replacement was already accepted for this item. Return to the checklist to review it again.'))
    row = next(r for r in item.snapshot['words'] if r['id']==clip['word_id'])
    members = targets(item, row['id'])
    if decision == 'reject':
        clip['decision'] = 'reject'
        for member in members:
            remember(user, run.port.source, member, 'replace')
    else:
        part = Contribution.objects.select_related('entry__dictionary','entry__current_meaning').get(pk=row['id'])
        prepared = (path_for(clip['path']).read_bytes(), 'audio/wav', '.wav')
        previous_ids = [a['id'] for a in row['audio']]
        provenance = {'origin':'synthetic', 'provider':'openai', 'model':tts.MODEL,
            'voice':row['voice'], 'language':row['language'], 'source_text':row['word'], 'source_text_id':part.pk,
            'instructions_version':clip['report'].get('instructions_version',
                carrier.VERSION if clip['method']=='carrier' else tts.INSTRUCTIONS_VERSION),
            'generation_method':clip['method'], 'synthesis':clip['report'],
            'homograph_repair_run':str(run.pk), 'replaces_audio_ids':previous_ids,
            'pronunciation_approved':True, 'reviewed_by':user.pk, 'reviewed_at':timezone.now().isoformat()}
        if row['kind'] == 'form':
            provenance['sentence_form'] = part.pk
        elif part.entry.current_meaning_id:
            provenance['source_meaning_id'] = part.entry.current_meaning_id
        new = Contribution.objects.create(entry=part.entry, author=user, kind='audio', shared_from=part,
            previous_revision_id=previous_ids[0] if previous_ids else None,
            status='accepted' if row['kind']=='form' else 'pending', provenance=provenance,
            **write_upload(prepared, part.entry.dictionary_id, paths))
        if row['kind'] != 'form':
            accept(new, user)
        ContributionDependency.objects.bulk_create([ContributionDependency(source_id=pk, derived=new) for pk in row['ids']])
        Contribution.objects.filter(pk__in=previous_ids, status='accepted').update(status='superseded')
        clip.update(decision='accept', accepted_audio_id=new.pk)
        item.sources.add(new)
        accepted_ids = [new.pk]
        for member in members:
            if member['id'] != row['id']:
                other = Contribution.objects.select_related('entry__dictionary').get(pk=member['id'])
                old_ids = [a['id'] for a in member['audio']]
                copied = sf.copy_audio(other, new, paths, provenance={'replaces_audio_ids':old_ids})
                Contribution.objects.filter(pk__in=old_ids, status='accepted').update(status='superseded')
                item.sources.add(copied); accepted_ids.append(copied.pk)
            updated = live_row(run.port.source, member['id'])
            item.snapshot['words'] = [updated if r['id']==member['id'] else r for r in item.snapshot['words']]
            remember(user, run.port.source, updated, 'keep')
        clip['accepted_audio_ids'] = accepted_ids
        event(run.port.source, user, 'homograph_audio_replace', part.entry, f'Audio {new.pk}; run {run.pk}')
    item.save(update_fields=['snapshot','result'])


def owner(request, pk):
    dictionary = get_dictionary(request.user, pk)
    require_owner(request.user, dictionary)
    return dictionary


def owner_run(request, pk, run_id):
    dictionary = owner(request, pk)
    run = get_object_or_404(PortRun.objects.select_related('port__source','port__user'), pk=run_id,
        stage=STAGE, port__source=dictionary, port__user=request.user)
    return dictionary, run


def quote_input(request):
    try:
        token = uuid.UUID(request.POST.get('token', ''))
        count = int(request.POST.get('candidates', str(DEFAULT_CANDIDATES)))
    except (ValueError, TypeError):
        raise Conflict(_('Choose between one and five candidates per word or form.'))
    if not 1 <= count <= MAX_CANDIDATES:
        raise Conflict(_('Choose between one and five candidates per word or form.'))
    # Old tabs did not send a method; preserve their guidance-only scope.
    method = request.POST.get('generation_method', 'guidance')
    if method not in GENERATION_METHODS:
        raise Conflict(_('Choose a generation method.'))
    return token, count, method


@page(['GET','POST'])
def home(request, pk):
    dictionary = owner(request, pk)
    include_expressions = (request.POST if request.method=='POST' else request.GET).get('expressions') == '1'
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'quote':
            token, count, method = quote_input(request)
            run = quote(request.user, dictionary, token, count, include_expressions=include_expressions,
                        generation_method=method)
            return redirect('community_dictionary:audio-review-run', pk=pk, run_id=run.pk)
        if action not in DECISIONS and action != 'reuse':
            raise Conflict(_('Choose Keep or Needs regeneration.'))
        try:
            part_id = int(request.POST.get('part', ''))
        except ValueError:
            raise Http404
        if action == 'reuse':
            paths = []
            try:
                try:
                    audio_id = int(request.POST.get('audio', ''))
                except ValueError:
                    raise Http404
                use_existing(request.user, dictionary, part_id, request.POST.get('token'), audio_id, paths)
            except Exception:
                for path in paths:
                    delete_file(path)
                raise
        elif request.POST.get('scope') == 'group':
            mark_group(request.user, dictionary, part_id, request.POST.get('token'), action)
        else:  # Old tabs can still submit their per-occurrence checklist decision.
            mark(request.user, dictionary, part_id, request.POST.get('token'), request.POST.get('previous', ''), action)
        messages.success(request, _('Review saved.'))
        # Only local numeric page and anchor values enter the redirect.
        number = request.POST.get('page','1')
        number = number if number.isdigit() else '1'
        return redirect(reverse('community_dictionary:audio-review', args=[pk])+f'?page={number}&expressions={int(include_expressions)}#word-{part_id}')
    rows = review_groups(request.user, dictionary, include_expressions=include_expressions)
    counts = Counter(r['decision'] for r in rows)
    paging = Paginator(rows, 20).get_page(request.GET.get('page'))
    pending_rows = [{'word':row['word'], 'page':index // paging.paginator.per_page + 1}
                    for index, row in enumerate(rows) if row['decision']=='replace']
    form_labels(paging)
    audio_by_id = Contribution.objects.filter(pk__in={a['id'] for r in paging
        for member in r['members'] for a in member['audio']}).in_bulk()
    # Lemma context is display-only, never included in a generation prompt.
    for row in paging:
        row['all_recorded'] = all(r['audio'] for r in row['members'])
        row['recordings'] = []
        seen = set()
        for member in row['members']:
            for clip in member['audio']:
                recording = audio_by_id[clip['id']]
                key = recording.provenance.get('audio_reuse_source', recording.pk)
                if key not in seen:
                    row['recordings'].append({**clip, 'part':member['id'], 'context':member['context']})
                    seen.add(key)
        row['context'] = row['word']['context']
        if not row['context']:
            links = SentenceWord.objects.filter(word_text_id=row['word']['id'],
                sentence_text__entry__dictionary=dictionary).select_related('sentence_text__entry')
            for link in links:
                sentence = link.sentence_text
                if sentence.entry.current_text_id == sentence.pk and contributions(dictionary).filter(pk=sentence.pk).exists():
                    row['context'] = sentence.word
                    break
    return render(request, 'community_dictionary/audio_review.html', context(request, dictionary,
        rows=paging, total=len(rows), kept=counts['keep'], marked=counts['replace'], unreviewed=counts[''], token=uuid.uuid4(),
        include_expressions=include_expressions, pending_rows=pending_rows,
        generation_methods=method_choices(dictionary), default_method=method_choices(dictionary)[0][0],
        candidate_choices=range(1, MAX_CANDIDATES + 1), default_candidates=DEFAULT_CANDIDATES,
        runs=PortRun.objects.filter(stage=STAGE, port__source=dictionary, port__user=request.user)[:10]))


@page(['GET','POST'])
def detail(request, pk, run_id):
    dictionary, run = owner_run(request, pk, run_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'more':
            token, count, method = quote_input(request)
            try:
                item_id, part_id = int(request.POST.get('item','0')), int(request.POST.get('part','0'))
            except ValueError:
                raise Http404
            next_run = quote_more(request.user, dictionary, run.pk, item_id, part_id, token, count,
                                  generation_method=method)
            return redirect('community_dictionary:audio-review-run', pk=pk, run_id=next_run.pk)
        elif action == 'approve':
            if request.POST.get('approve') != 'on':
                raise Conflict(_('Approve the estimate and permission to send selected text to OpenAI.'))
            porting.approve(request.user, run.pk)
        elif action == 'resume':
            experiments.resume(request.user, run.pk)
        elif action == 'cancel':
            porting.cancel(request.user, run.pk)
        elif action in {'accept','reject'}:
            try:
                item_id = int(request.POST.get('item','0'))
            except ValueError:
                raise Http404
            paths = []
            try:
                choose(request.user, run.pk, item_id, request.POST.get('clip'), action, paths)
            except Exception:
                for path in paths:
                    delete_file(path)
                raise
        else:
            raise Conflict(_('Unknown audio review action.'))
        return redirect('community_dictionary:audio-review-run', pk=pk, run_id=run.pk)
    rows, unavailable = [], 0
    for item in run.items.all():
        item.run = run
        try:
            current_item(item)
        except (Conflict, Http404):
            unavailable += 1; continue
        for row in item.snapshot['words']:
            clips = [dict(c) for c in item.result['clips'] if c['word_id']==row['id']]
            if not clips:
                continue  # Group members share their representative's candidates.
            for number, clip in enumerate(clips, 1):
                clip.setdefault('candidate', number)  # Existing single-preview jobs remain usable.
                clip['method_label'] = experiments.METHODS.get(clip['method'], clip['method'])
            rows.append({'word':row, 'members':targets(item, row['id']), 'clips':clips, 'item':item, 'token':uuid.uuid4(),
                         'accepted':any(c.get('decision')=='accept' for c in clips)})
    clips = [c for row in rows for c in row['clips']]
    form_labels(rows)
    progress = Counter(c['status'] for c in clips)
    methods = Counter(c['method'] for c in clips)
    balance = get_user_balance_usd(request.user) if run.payer=='credits' else None
    return render(request, 'community_dictionary/audio_review_run.html', context(request, dictionary,
        run=run, rows=rows, words=len(rows), total=len(clips), finished=progress['ready']+progress['failed'],
        failures=progress['failed'], unavailable=unavailable, balance=balance,
        candidate_choices=range(1, MAX_CANDIDATES + 1), default_candidates=DEFAULT_CANDIDATES,
        generation_methods=method_choices(dictionary),
        default_method=run.options.get('generation_method', method_choices(dictionary)[0][0]),
        guidance_count=methods['guidance'], carrier_count=methods['carrier'],
        previous_run=run.options.get('previous_run'),
        later_runs=PortRun.objects.filter(stage=STAGE, port__source=dictionary, port__user=request.user,
                                         options__previous_run=str(run.pk)).order_by('created_at'),
        enough_funds=balance is None or balance>=run.allowance_usd,
        expired=run.expires_at<=timezone.now(), held=0 if run.settled else run.reserved_usd-run.released_usd))


@page(['GET'])
def current_media(request, pk, part_id, audio_id):
    dictionary = owner(request, pk)
    row = live_row(dictionary, part_id)
    if audio_id not in [a['id'] for a in row['audio']]:
        raise Http404
    audio = get_object_or_404(Contribution, pk=audio_id)
    return private_media_response(request, audio.file_path, audio.mime_type, 'recording')


@page(['GET'])
def preview_media(request, pk, run_id, item_id, clip_id):
    _dictionary, run = owner_run(request, pk, run_id)
    item = get_object_or_404(PortItem, pk=item_id, run=run)
    item.run = run; current_item(item)
    clip = next((c for c in item.result.get('clips', []) if c['id']==clip_id), None)
    if not clip or clip.get('decision'):
        raise Http404
    if request.GET.get('full') == '1':
        if clip['method'] != 'carrier' or clip['status'] not in {'ready','failed'} or not clip.get('full_path'):
            raise Http404
        return private_media_response(request, clip['full_path'], 'audio/wav', 'carrier.wav')
    if clip['status'] != 'ready' or not clip.get('path'):
        raise Http404
    return private_media_response(request, clip['path'], 'audio/wav', 'preview.wav')
