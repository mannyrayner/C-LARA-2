"""Owner-selected lexical TTS and reversible, explicitly approved Google batches."""
from datetime import timedelta
from decimal import Decimal
import uuid

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from . import audio_review as review, google_tts, photo_ai, porting, tts, word_audio
from .evaluation_views import page
from .collections import content_digest
from .models import (Contribution, Dictionary, DictionaryWordAudioSettings, LanguagePort,
                     Participation, PortItem, PortRun)
from .permissions import require_owner
from .services import Conflict, event
from .storage import delete_file
from .views import context

VERSION = 'google-word-batch-1'
MAX_GROUPS = 2000


def prices(dictionary):
    return google_tts.comparison_prices(dictionary)


def check_run(run):
    google_tts.require_access(run.port.user)
    word_audio.validate(run.port.source, run.options.get('word_audio_policy'))
    if (run.options.get('google_batch') != VERSION or
            any(run.prices.get(k) != v for k, v in prices(run.port.source).items())):
        raise Conflict('Google settings changed. Prepare a fresh batch estimate.')


@page(['GET', 'POST'])
def settings(request, pk):
    dictionary = review.owner(request, pk)
    current = DictionaryWordAudioSettings.objects.filter(dictionary=dictionary).first()
    key = f'google-voices:{pk}:{dictionary.language}'
    names = sorted(set([*google_tts.voices_for(dictionary).values(), *request.session.get(key, [])]))
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'discover':
            request.session[key] = google_tts.discover(request.user, dictionary.language)
            messages.success(request, 'Available Google voices loaded. No audio was generated.')
        elif action == 'save':
            selected = request.POST.get('voice', '')
            if selected:
                if selected not in names or not google_tts.matches_language(selected, dictionary.language):
                    raise Conflict('Select a listed voice for this language.')
                if request.POST.get('consent') != 'on':
                    raise Conflict('Confirm Google project billing and permission to send word text.')
                google_tts.check_access(request.user, dictionary.language, selected_voice=selected)
            with transaction.atomic():
                locked = Dictionary.objects.select_for_update().get(pk=pk)
                require_owner(request.user, locked)
                if locked.language != dictionary.language:
                    raise Conflict('The dictionary language changed. Reload settings.')
                row, _ = DictionaryWordAudioSettings.objects.get_or_create(dictionary=locked,
                    defaults={'authorised_by':request.user, 'language':locked.language})
                row.voice, row.language, row.authorised_by = selected, locked.language, request.user
                row.revision += 1
                row.save()
                event(locked, request.user, 'word_audio_settings', detail=f'Voice: {selected or "OpenAI"}')
            messages.success(request, 'Future word and sentence-form audio updated. Existing recordings are unchanged. Renew any saved picture-workflow consent when prompted.')
        else:
            raise Conflict('Unknown settings action.')
        return redirect('community_dictionary:word-audio-settings', pk=pk)
    return render(request, 'community_dictionary/word_audio_settings.html', context(request, dictionary,
        voices=names, selected=current.voice if current else '', google_project=google_tts.project(),
        can_google=request.user.is_staff or request.user.is_superuser))


def groups(dictionary, *, include_reviewed=False, include_matching=False):
    from .audio_review_data import ReviewData
    chosen = word_audio.policy(dictionary)
    if not chosen:
        raise Conflict('Choose a Google voice under Word audio settings first.')
    rows, skipped = [], 0
    loaded = ReviewData(dictionary)
    for part in loaded.selected.values():
        row = review.row_for(part, all_words=True, loaded=loaded)
        if not row:
            continue
        audio = [loaded.audio[a['id']] for a in row['audio']]
        if (review.protected(row) or
                (not include_reviewed and any(a.provenance.get('pronunciation_approved') for a in audio)) or
                (not include_matching and audio and all(a.provenance.get('provider') == 'google' and
                    a.provenance.get('voice') == chosen['voice'] and
                    a.provenance.get('instructions_version') == google_tts.VERSION for a in audio))):
            skipped += 1
        else:
            rows.append(row)
    return review.group_words(dictionary, rows, loaded=loaded), skipped


@transaction.atomic
def quote(user, dictionary, token, *, include_reviewed=False, include_matching=False):
    porting.locks(); require_owner(user, dictionary); google_tts.require_access(user)
    old = PortRun.objects.filter(pk=token, port__source=dictionary, port__user=user,
        options__google_batch=VERSION).first()
    if old:
        return old
    if PortRun.objects.filter(pk=token).exists():
        raise Conflict('Reload the batch page.')
    policy = word_audio.policy(dictionary)
    word_audio.validate(dictionary, policy)
    google_tts.credentials()  # Read configuration only; no API request or reservation.
    selected, skipped = groups(dictionary, include_reviewed=include_reviewed, include_matching=include_matching)
    if not selected or len(selected) > MAX_GROUPS:
        raise Conflict(f'Select between 1 and {MAX_GROUPS} eligible word/form groups.')
    model, _key, _personal, rates = photo_ai.configuration(user)
    port = LanguagePort.objects.create(source=dictionary, user=user, is_audio_batch=True,
        name='Google word audio', language=dictionary.language, explanation_language=dictionary.explanation_language)
    review.authority(port)
    run = PortRun.objects.create(pk=token, port=port, stage=review.STAGE, model=model,
        source_language=dictionary.language, source_explanation_language=dictionary.explanation_language,
        prices={**{k:str(v) for k,v in rates.items()}, 'speech_recipe':tts.INSTRUCTIONS_VERSION, **prices(dictionary)},
        options={'review_version':review.VERSION, 'google_batch':VERSION, 'word_audio_policy':policy,
            'skipped':skipped, 'include_reviewed':include_reviewed, 'include_matching':include_matching},
        payer=porting.payer_now(user), expires_at=timezone.now()+timedelta(hours=1))
    entries = {}
    for members in selected:
        entries.setdefault(members[0]['entry'], []).append(members)
    items = []
    for entry_id, entry_groups in entries.items():
        words, clips = [], []
        for members in entry_groups:
            words.extend(members)
            cost = porting.money(word_audio.estimate(members[0]['word'], policy))
            clips.append({'id':uuid.uuid4().hex, 'word_id':members[0]['id'], 'method':policy['method'],
                'candidate':1, 'status':'waiting', 'estimate':str(cost), 'allowance':str(cost), 'cost':'0', 'report':{}})
        total = sum((Decimal(c['estimate']) for c in clips), Decimal('0'))
        item = PortItem(run=run, source_entry_id=entry_id,
            snapshot={'words':words, 'audio_groups':{str(g[0]['id']):[r['id'] for r in g] for g in entry_groups}},
            result={'clips':clips}, estimated_usd=total, allowance_usd=total)
        items.append(item)
        run.estimated_usd += total; run.allowance_usd += total
    PortItem.objects.bulk_create(items)
    through = PortItem.sources.through
    through.objects.bulk_create([through(portitem_id=item.pk, contribution_id=pk)
        for item in items for pk in review.source_ids(item.snapshot['words'])])
    run.save()
    return run


def apply_all(user, run):
    """Each group is atomic; a changed group does not block unrelated groups."""
    require_owner(user, run.port.source)
    if run.options.get('google_batch') != VERSION:
        raise Conflict('Not a Google batch.')
    done, skipped = 0, 0
    for item in run.items.all():
        for clip in item.result.get('clips', []):
            if clip.get('decision') or clip['status'] != 'ready':
                continue
            paths = []
            try:
                review.choose(user, run.pk, item.pk, clip['id'], 'accept', paths, bulk=True)
                done += 1
            except Conflict:
                for path in paths: delete_file(path)
                skipped += 1
            except Exception:
                for path in paths: delete_file(path)
                raise
    return done, skipped


@transaction.atomic
def restore(user, run):
    porting.locks(); require_owner(user, run.port.source)
    if run.options.get('google_batch') != VERSION or not run.settled:
        raise Conflict('Wait for the Google batch to finish.')
    review.authority(run.port)
    done, skipped = 0, 0
    for item in run.items.select_for_update():
        item.run = run
        try: review.current_item(item)
        except Conflict:
            skipped += 1; continue
        for clip in item.result.get('clips', []):
            if clip.get('decision') != 'accept': continue
            old_rows = clip.get('previous_rows', [])
            old_ids = [a['id'] for row in old_rows for a in row['audio']]
            old = list(Contribution.objects.filter(pk__in=old_ids, status='superseded',
                withdrawal_holds__isnull=True).distinct())
            if (len(old) != len(old_ids) or any(a.provenance.get('origin') != 'synthetic' for a in old) or
                    any(content_digest(a) != next(x['digest'] for r in old_rows for x in r['audio'] if x['id']==a.pk) for a in old) or
                    Participation.objects.filter(dictionary=run.port.source, withdrawn=True,
                        user_id__in=[a.controlled_by_id or a.author_id for a in old]).exists()):
                skipped += 1; continue
            Contribution.objects.filter(pk__in=clip['accepted_audio_ids'], status='accepted').update(status='superseded')
            Contribution.objects.filter(pk__in=old_ids).update(status='accepted')
            for row in old_rows:
                updated = review.live_row(run.port.source, row['id'], all_words=True)
                item.snapshot['words'] = [updated if r['id']==row['id'] else r for r in item.snapshot['words']]
            clip['decision'] = 'restored'; done += 1
        item.save(update_fields=['snapshot','result'])
    event(run.port.source, user, 'google_audio_restore', detail=f'Run {run.pk}; groups {done}')
    return done, skipped


@page(['GET', 'POST'])
def start(request, pk):
    dictionary = review.owner(request, pk)
    if request.method == 'POST':
        try: token = uuid.UUID(request.POST.get('token', ''))
        except ValueError: raise Conflict('Reload the batch page.') from None
        run = quote(request.user, dictionary, token, include_reviewed=request.POST.get('reviewed')=='on',
            include_matching=request.POST.get('matching')=='on')
        return redirect('community_dictionary:audio-review-run', pk=pk, run_id=run.pk)
    policy = word_audio.policy(dictionary)
    return render(request, 'community_dictionary/google_word_batch.html', context(request, dictionary,
        policy=policy, token=uuid.uuid4(), runs=PortRun.objects.filter(port__source=dictionary,
            port__user=request.user, options__google_batch=VERSION)[:20]))
