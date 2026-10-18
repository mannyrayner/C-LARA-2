"""Owner-approved regeneration of existing synthetic MWE audio, in place.

Reuse the durable audio queue and credit ledger. No source recording is sent to
OpenAI. Earlier audio remains in private storage, with a guarded restore action.
"""
from datetime import timedelta
from decimal import Decimal
import uuid

from django import forms
from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from projects.billing import get_user_balance_usd
from . import carrier, porting, port_audio, photo_ai, tts, port_budget
from .models import (Contribution, Dictionary, Entry, LanguagePort, Participation,
                     PortItem, PortRun, PortSpeech)
from .lexicon import recordings
from .permissions import get_dictionary, require_owner
from .services import Conflict, accept, event
from .storage import write_upload
from .evaluation_views import page
from .views import context


def authority(port):
    dictionary = Dictionary.objects.get(pk=port.source_id)
    require_owner(port.user, dictionary)
    if not dictionary.tts_enabled or tts.language_code(dictionary.language) not in carrier.SUPPORTED_LANGUAGES:
        raise Conflict(f'This pilot needs saved TTS enabled in {carrier.LANGUAGE_LABEL}.')
    if (dictionary.language, dictionary.explanation_language) != (port.language, port.explanation_language):
        raise Conflict('The dictionary languages changed. Prepare another estimate.')


def old_audio(entry):
    return recordings(entry, entry.dictionary)


def candidates(dictionary, *, explicit_selection=False):
    entries = dictionary.entries.filter(archived=False, entry_type='word', current_text__status='accepted').select_related(
        'dictionary', 'current_text', 'current_meaning').prefetch_related('contributions')
    result = []
    for entry in entries:
        if entry.current_text.entry_id != entry.pk or not carrier.eligible(
                entry.word, dictionary.language, explicit_selection=explicit_selection):
            continue
        audio = old_audio(entry)
        # Protect all human recordings, including ones whose wording is unknown.
        if not audio or any(c.provenance.get('origin') != 'synthetic' for c in audio):
            continue
        if any(c.provenance.get('instructions_version') == carrier.VERSION for c in audio):
            continue  # Completed replacements are not requested again on Retry.
        result.append(entry)
    return result


def fingerprint(entry):
    snap = port_audio.fingerprint(entry)
    audio = old_audio(entry)
    snap['audio_ids'] = [c.pk for c in audio]
    snap['voice'] = audio[0].provenance.get('voice', tts.VOICE) if audio else tts.VOICE
    if snap['voice'] not in tts.VOICE_NAMES:
        snap['voice'] = tts.VOICE
    snap['ids'] = sorted(set(snap['ids'] + snap['audio_ids']))
    return snap


def current_item(item):
    authority(item.run.port)
    entry = Entry.objects.select_related('dictionary', 'current_text', 'current_meaning').get(pk=item.source_entry_id)
    if (item.invalidated or entry.archived or entry.entry_type != 'word' or
            entry.dictionary_id != item.run.port.source_id or not entry.current_text or
            entry.current_text.status != 'accepted' or entry.current_text.entry_id != entry.pk or
            not carrier.eligible(entry.word, entry.dictionary.language,
                explicit_selection=item.run.options.get('carrier_explicit_selection', False)) or
            (entry.current_meaning and (entry.current_meaning.status != 'accepted' or entry.current_meaning.entry_id != entry.pk)) or
            fingerprint(entry) != item.snapshot or
            any(c.provenance.get('origin') != 'synthetic' for c in old_audio(entry)) or
            Contribution.objects.filter(pk__in=item.snapshot['ids'], withdrawal_holds__isnull=False).exists()):
        raise Conflict('The wording, recordings or access changed. The existing audio has been kept.')
    return entry


@transaction.atomic
def quote(user, dictionary, token, *, entry_ids=None):
    porting.locks()
    require_owner(user, dictionary)
    previous = PortRun.objects.filter(pk=token, port__source=dictionary, port__user=user, port__is_audio_batch=True).first()
    if previous:
        return previous
    if PortRun.objects.filter(pk=token).exists():
        raise Conflict('Reload this form before estimating.')
    port = LanguagePort.objects.filter(source=dictionary, user=user, is_audio_batch=True,
        language=dictionary.language, explanation_language=dictionary.explanation_language).first()
    if not port:
        port = LanguagePort.objects.create(source=dictionary, user=user, is_audio_batch=True,
            name='Regenerate AI expression audio', language=dictionary.language,
            explanation_language=dictionary.explanation_language, voice=tts.VOICE)
    authority(port)
    if PortRun.objects.filter(port__source=dictionary, port__is_audio_batch=True, status='running').exists():
        raise Conflict('Finish or cancel the current expression-audio job first.')
    japanese = tts.language_code(dictionary.language) == 'ja'
    entries = candidates(dictionary, explicit_selection=japanese)
    if japanese:
        if not isinstance(entry_ids, (list, tuple, set)) or not entry_ids or len(entry_ids) > 500:
            raise Conflict('Choose between 1 and 500 Japanese entries explicitly. Nothing is selected automatically.')
        try:
            selected = {int(pk) for pk in entry_ids}
        except (TypeError, ValueError):
            raise Conflict('Reload this form and choose eligible Japanese entries.')
        by_id = {entry.pk: entry for entry in entries}
        if not selected.issubset(by_id):
            raise Conflict('Some selected entries changed or are not eligible. Reload this form.')
        entries = [by_id[pk] for pk in sorted(selected)]
    elif entry_ids is not None:
        raise Conflict('Individual entry selection is currently only used for the Japanese pilot.')
    model, key, personal, prices = photo_ai.configuration(user)
    run = PortRun.objects.create(pk=token, port=port, stage='audio', model=model,
        source_language=dictionary.language, source_explanation_language=dictionary.explanation_language,
        prices={**{k:str(v) for k,v in prices.items()}, 'speech_recipe':tts.INSTRUCTIONS_VERSION,
                'carrier_recipe':carrier.VERSION}, options={'budget_version':1, 'mwe_regeneration':True,
                'carrier_explicit_selection':japanese},
        payer=porting.payer_now(user), expires_at=timezone.now()+timedelta(hours=1))
    for entry in entries:
        snap = fingerprint(entry)
        item = PortItem.objects.create(run=run, source_entry=entry, saved_entry=entry, snapshot=snap,
            estimated_usd=porting.money(carrier.estimate(entry.word, dictionary.language)),
            allowance_usd=porting.money(carrier.estimate(entry.word, dictionary.language, allowance=True)))
        item.sources.set(snap['ids'])
        run.estimated_usd += item.estimated_usd
        run.allowance_usd += item.allowance_usd
    run.save()
    return run


def prepare(run):
    # Called while dictionary and run locks are held, before dispatch.
    if PortRun.objects.filter(port__source=run.port.source, port__is_audio_batch=True, status='running').exclude(pk=run.pk).exists():
        raise Conflict('An expression-audio job is already running in this dictionary.')
    for item in run.items.all():
        item.run = run
        entry = current_item(item)
        item.status = 'saved'; item.save(update_fields=['status'])
        PortSpeech.objects.get_or_create(run=run, item=item, entry=entry, text=entry.current_text,
            defaults={'meaning':entry.current_meaning})


def publish(clip, prepared, paths, report):
    entry = current_item(clip.item)
    previous = old_audio(entry)
    part = Contribution.objects.create(entry=entry, author=clip.run.port.user, kind='audio',
        shared_from=clip.text, previous_revision=previous[0],
        provenance={'origin':'synthetic', 'provider':'openai', 'model':tts.MODEL,
            'voice':clip.item.snapshot['voice'], 'language':entry.dictionary.language,
            'source_text':clip.text.word, 'source_text_id':clip.text_id,
            'instructions_version':carrier.VERSION, 'synthesis':report,
            'mwe_regeneration_run':str(clip.run_id), 'replaces_audio_ids':[p.pk for p in previous],
            'automatic_publication':True, 'publication_authorized_by':clip.run.port.user_id},
        **write_upload(prepared, entry.dictionary_id, paths))
    accept(part, clip.run.port.user)
    # Old recordings keep attribution/files. Superseded audio remains available
    # to frozen evaluation results, but disappears from ordinary playback.
    Contribution.objects.filter(pk__in=[p.pk for p in previous], status='accepted').update(status='superseded')
    clip.item.result = {'replacement_audio_id':part.pk}
    clip.item.save(update_fields=['result'])
    event(entry.dictionary, clip.run.port.user, 'mwe_audio_replace', entry, f'Audio {part.pk}; run {clip.run_id}')


@transaction.atomic
def restore(user, run):
    porting.locks()
    run = PortRun.objects.select_for_update().select_related('port__source','port__user').get(pk=run.pk)
    require_owner(user, run.port.source)
    if not run.port.is_audio_batch or run.port.user_id != user.pk or not run.settled:
        raise Conflict('Finish or cancel this job before restoring earlier audio.')
    count = skipped = 0
    for item in run.items.all():
        replacement = Contribution.objects.filter(pk=item.result.get('replacement_audio_id'),
            entry__dictionary=run.port.source, entry__archived=False, status='accepted',
            withdrawal_holds__isnull=True).first()
        if not replacement:
            continue
        entry = replacement.entry
        from .lexicon import outdated_tts
        ids = item.snapshot['audio_ids']
        previous = list(Contribution.objects.filter(pk__in=ids, entry=entry, kind='audio',
            status='superseded', withdrawal_holds__isnull=True).distinct())
        controllers = [p.controlled_by_id or p.author_id for p in [replacement, *previous]]
        if (len(previous) != len(ids) or outdated_tts(replacement, entry, entry.dictionary) or
                any(outdated_tts(p, entry, entry.dictionary) for p in previous) or
                Participation.objects.filter(dictionary=run.port.source, user_id__in=controllers, withdrawn=True).exists() or
                [p.pk for p in old_audio(entry)] != [replacement.pk]):
            skipped += 1; continue
        Contribution.objects.filter(pk=replacement.pk).update(status='superseded')
        Contribution.objects.filter(pk__in=ids).update(status='accepted')
        item.result['restored'] = True; item.save(update_fields=['result'])
        event(entry.dictionary, user, 'mwe_audio_restore', entry, f'Run {run.pk}')
        count += 1
    return count, skipped


class QuoteForm(forms.Form):
    token = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, dictionary, **kwargs):
        super().__init__(*args, **kwargs)
        if tts.language_code(dictionary.language) == 'ja':
            entries = candidates(dictionary, explicit_selection=True)
            self.fields['entry_ids'] = forms.MultipleChoiceField(
                label='Choose Japanese entries to try',
                help_text='Nothing is selected by default. Select only recordings you want to experiment with; '
                          'compound words are not automatically treated as multi-word expressions.',
                choices=[(entry.pk, f'{entry.word} — {entry.meaning} (entry {entry.pk})') for entry in entries],
                widget=forms.CheckboxSelectMultiple)


@transaction.atomic
def baseline(user, run):
    """Freeze precisely the quoted words before an owner authorises replacement."""
    from .evaluation import create_set
    porting.locks()
    require_owner(user, run.port.source)
    if run.status != 'estimate':
        raise Conflict('Create the baseline before approving regeneration.')
    ids = []
    for item in run.items.all():
        item.run = run
        ids.append(current_item(item).pk)
    return create_set(user, run.port.source, {
        'token':uuid.uuid5(run.pk, 'carrier-audio-baseline'),
        'name':f'Before carrier audio: {run.port.source.name}'[:160],
        'scope':'word_audio', 'sampling':'all', 'size':len(ids), 'allow_visitors':False,
        'selected_entry_ids':ids,
    })


@page(['GET', 'POST'])
def start(request, pk):
    dictionary = get_dictionary(request.user, pk)
    require_owner(request.user, dictionary)
    form = QuoteForm(request.POST if request.method == 'POST' else None,
        dictionary=dictionary, initial={'token':uuid.uuid4()})
    if request.method == 'POST' and form.is_valid():
        run = quote(request.user, dictionary, form.cleaned_data['token'], entry_ids=form.cleaned_data.get('entry_ids'))
        return redirect('community_dictionary:mwe-audio-run', pk=pk, run_id=run.pk)
    return render(request, 'community_dictionary/mwe_audio_start.html', context(request, dictionary,
        form=form, supported=tts.language_code(dictionary.language) in carrier.SUPPORTED_LANGUAGES,
        japanese=tts.language_code(dictionary.language) == 'ja',
        runs=PortRun.objects.filter(port__source=dictionary, port__user=request.user, port__is_audio_batch=True)[:10]))


@page(['GET', 'POST'])
def detail(request, pk, run_id):
    dictionary = get_dictionary(request.user, pk)
    require_owner(request.user, dictionary)
    run = get_object_or_404(PortRun.objects.select_related('port__user','port__source'), pk=run_id,
        port__source=dictionary, port__user=request.user, port__is_audio_batch=True)
    if request.method == 'POST':
        if request.POST.get('action') == 'baseline':
            batch = baseline(request.user, run)
            return redirect('community_dictionary:evaluation-set', pk=pk, set_id=batch.pk)
        if request.POST.get('action') != 'restore':
            raise Conflict('Unknown action.')
        count, skipped = restore(request.user, run)
        messages.success(request, f'Restored earlier audio for {count} entries; {skipped} changed entries left unchanged.')
        return redirect('community_dictionary:mwe-audio-run', pk=pk, run_id=run.pk)
    rows = []
    for clip in run.speech.select_related('entry__dictionary', 'entry__current_text', 'item'):
        entry = clip.entry
        safe = (not entry.archived and entry.dictionary_id == pk and entry.current_text_id == clip.text_id
                and entry.current_text and entry.current_text.status == 'accepted' and not clip.item.invalidated
                and not Contribution.objects.filter(pk__in=clip.item.snapshot['ids'], status__in=['withdrawn','removed']).exists()
                and not Contribution.objects.filter(pk__in=clip.item.snapshot['ids'], withdrawal_holds__isnull=False).exists())
        rows.append({'clip':clip, 'entry':entry if safe else None, 'restored':clip.item.result.get('restored',False)})
    preview_rows = []
    if run.status == 'estimate':
        for item in run.items.all():
            item.run = run
            try:
                entry = current_item(item)
            except (Conflict, Entry.DoesNotExist):
                entry = None
            preview_rows.append(entry)
    balance = get_user_balance_usd(request.user) if run.payer == 'credits' else None
    budget_offer = port_budget.offer(run)
    return render(request, 'community_dictionary/mwe_audio_run.html', context(request, dictionary,
        run=run, rows=rows, preview_rows=preview_rows, budget_offer=budget_offer,
        enough_extra_funds=not budget_offer or balance is None or balance >= budget_offer['amount'], expired=run.expires_at <= timezone.now(), balance=balance,
        enough_funds=balance is None or balance >= run.allowance_usd,
        held=0 if run.settled else run.reserved_usd-run.released_usd,
        uncertain=run.items.filter(uncertain_cost=True).exists()))
