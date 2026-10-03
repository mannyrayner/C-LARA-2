"""Generate once, privately preview, then explicitly save a synthetic recording."""
from datetime import timedelta
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from projects.billing import credits_enabled, has_minimum_balance_for_compile
from . import tts
from .forms import AudioGenerateForm, AudioSaveForm
from .models import AudioStudy, Dictionary, Entry, VoicePreference
from .permissions import get_dictionary, is_editor
from .services import Conflict, add_contributions, entry_url, event, submit_once
from .storage import delete_file, path_for, write_upload
from .views import context, fail, get_entry, private_media_response

logger = logging.getLogger(__name__)


def study_url(study):
    return reverse('community_dictionary:audio-study', args=[study.dictionary_id, study.pk])


def get_study(request, dictionary, study_id, lock=False):
    query = AudioStudy.objects.select_for_update() if lock else AudioStudy.objects.all()
    return get_object_or_404(query, pk=study_id, dictionary=dictionary, user=request.user,
                            entry__isnull=False, expires_at__gt=timezone.now())


def finish(study, api_key):
    prepared, duration = None, None
    try:
        prepared, duration = tts.synthesize(study.source_text, language=study.language_code,
            model=study.model, voice=study.voice, api_key=api_key)
    except Exception as exc:
        logger.warning('Audio study %s failed (%s)', study.pk, type(exc).__name__)
    paths = []
    try:
        with transaction.atomic():
            current = AudioStudy.objects.select_for_update().get(pk=study.pk)
            if prepared and current.cost_usd is None:
                current.duration_seconds = duration
                current.cost_usd = tts.estimate_cost(current.source_text, duration)
                tts.record_charge(current)
            if current.status == 'processing':
                if prepared and current.entry_id:
                    for key, value in write_upload(prepared, current.dictionary_id, paths).items():
                        setattr(current, key, value)
                    current.status = 'ready'
                else:
                    current.status = 'failed'
            current.save()
    except Exception:
        for path in paths:
            delete_file(path)
        raise


@login_required
def start(request, pk, entry_id):
    dictionary = get_dictionary(request.user, pk)
    entry = get_entry(dictionary, entry_id)
    if not dictionary.tts_enabled:
        return fail(request, 'The dictionary owner can enable saved spoken audio under Settings.', 403)
    config, setup_error = None, ''
    try:
        config = tts.configuration(request.user, dictionary)
        if not entry.word or not entry.current_text_id:
            raise Conflict('Add and accept the wording before creating audio. A dictionary editor can accept proposed words.')
    except Conflict as exc:
        setup_error = str(exc)
    preferred_voice = VoicePreference.objects.filter(user=request.user, dictionary=dictionary).values_list('voice', flat=True).first() or tts.VOICE
    form = AudioGenerateForm(request.POST or None, initial={
        'source_text_id': entry.current_text_id, 'source_text_version': entry.text_version, 'voice': preferred_voice})
    if request.method == 'POST' and not setup_error and form.is_valid():
        key, personal, code = config
        created = []

        def create(paths):
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            current_dictionary = Dictionary.objects.select_for_update().get(pk=pk)
            get_dictionary(request.user, pk)
            target = Entry.objects.select_for_update().get(pk=entry_id, dictionary=current_dictionary)
            if not current_dictionary.tts_enabled or current_dictionary.language != dictionary.language:
                raise Conflict('The dictionary audio settings changed. Reload the entry.')
            if not target.word or (target.current_text_id, target.text_version) != (
                    form.cleaned_data['source_text_id'], form.cleaned_data['source_text_version']):
                raise Conflict('The wording changed. Reload this page before generating audio.')
            if not has_minimum_balance_for_compile(request.user):
                raise Conflict('Your C-LARA balance is too low. Add credit or use your own OpenAI key.')
            recent = AudioStudy.objects.filter(created_at__gte=timezone.now()-timedelta(days=1))
            limit = settings.COMMUNITY_DICTIONARY_TTS_DAILY_LIMIT
            if recent.filter(user=request.user).count() >= limit or recent.filter(dictionary=dictionary).count() >= limit:
                raise Conflict('The daily audio-generation limit has been reached. Please try tomorrow.')
            if recent.filter(user=request.user, status='processing', created_at__gte=timezone.now()-timedelta(seconds=90)).exists():
                raise Conflict('Your previous recording is still being generated. Open the recent attempt below.')
            study = AudioStudy.objects.create(dictionary=dictionary, entry=target, user=request.user,
                expires_at=timezone.now()+timedelta(days=1), source_text=target.word,
                source_text_id=target.current_text_id, source_text_version=target.text_version,
                language=dictionary.language, language_code=code, model=tts.MODEL, voice=form.cleaned_data['voice'],
                personal_key=personal)
            VoicePreference.objects.update_or_create(user=request.user, dictionary=dictionary,
                defaults={'voice': study.voice})
            event(dictionary, request.user, 'audio_generation', target, f'OpenAI TTS consent; attempt {study.pk}')
            created.append(study)
            return study_url(study)
        try:
            url = submit_once(request, dictionary, f'entry-tts:{entry.pk}', create)
        except Conflict as exc:
            form.add_error(None, str(exc))
        else:
            if created:
                finish(created[0], key)
            return redirect(url)
    recent = AudioStudy.objects.filter(dictionary=dictionary, entry=entry, user=request.user,
        expires_at__gt=timezone.now()).exclude(status='discarded').order_by('-created_at')[:5]
    return render(request, 'community_dictionary/audio_start.html', context(request, dictionary,
        entry=entry, form=form, setup_error=setup_error, recent=recent, model=tts.MODEL,
        rate=tts.USD_PER_MINUTE, limit=settings.COMMUNITY_DICTIONARY_TTS_DAILY_LIMIT,
        personal=config[1] if config else False, charge_credits=credits_enabled(),
        submission_id=request.POST.get('submission_id') or context(request)['submission_id']))


def render_study(request, dictionary, study, form):
    if not is_editor(request.user, dictionary):
        form.fields.pop('publish_now', None)
    stale = (study.entry.text_version != study.source_text_version or study.entry.word != study.source_text
             or dictionary.language != study.language)
    return render(request, 'community_dictionary/audio_study.html', context(request, dictionary,
        study=study, form=form, stale=stale, timed_out=study.created_at < timezone.now()-timedelta(seconds=90)))


@login_required
def detail(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    study = get_study(request, dictionary, study_id)
    if study.status == 'saved':
        return redirect(entry_url(study.entry))
    return render_study(request, dictionary, study,
                        AudioSaveForm(initial={'publish_now': is_editor(request.user, dictionary)}))


@login_required
def media(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    study = get_study(request, dictionary, study_id)
    if study.status != 'ready' or not study.file_path:
        from django.http import Http404
        raise Http404
    return private_media_response(request, study.file_path, study.mime_type, 'synthetic-preview')


@login_required
@require_POST
def action(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    paths = []
    try:
        with transaction.atomic():
            Dictionary.objects.select_for_update().get(pk=pk)
            get_dictionary(request.user, pk)
            study = get_study(request, dictionary, study_id, lock=True)
            choice = request.POST.get('action')
            if study.status == 'saved':
                return redirect(entry_url(study.entry))
            if choice == 'discard':
                old_path = study.file_path
                study.status, study.file_path = 'discarded', ''
                study.save(update_fields=['status', 'file_path'])
                transaction.on_commit(lambda: delete_file(old_path))
                return redirect(entry_url(study.entry))
            if choice != 'save' or study.status != 'ready':
                raise Conflict('This recording is not ready to save.')
            form = AudioSaveForm(request.POST)
            if not form.is_valid():
                return render_study(request, dictionary, study, form)
            target = Entry.objects.select_for_update().get(pk=study.entry_id)
            if (target.text_version != study.source_text_version or target.word != study.source_text
                    or dictionary.language != study.language):
                raise Conflict('The wording or language changed. Return to the entry and generate audio for the current wording.')
            data = {'prepared_audio': (path_for(study.file_path).read_bytes(), 'audio/wav', '.wav'),
                    'label': f'Synthetic voice: {study.source_text}'[:200]}
            contribution = add_contributions(target, request.user, data, paths,
                publish=is_editor(request.user, dictionary) and form.cleaned_data.get('publish_now', False))[0]
            contribution.provenance = {'origin': 'synthetic', 'provider': 'openai', 'model': study.model,
                'voice': study.voice, 'language': study.language, 'source_text': study.source_text,
                'source_text_id': study.source_text_id, 'source_text_version': study.source_text_version,
                'study_id': str(study.pk), 'generated_at': study.created_at.isoformat(),
                'reviewed_by': request.user.pk, 'reviewed_at': timezone.now().isoformat()}
            contribution.shared_from_id = target.current_text_id
            contribution.save(update_fields=['provenance', 'shared_from'])
            old_path = study.file_path
            study.status, study.file_path, study.saved_contribution = 'saved', '', contribution
            study.save(update_fields=['status', 'file_path', 'saved_contribution'])
            transaction.on_commit(lambda: delete_file(old_path))
        return redirect(entry_url(target))
    except Conflict as exc:
        for path in paths:
            delete_file(path)
        return fail(request, exc, 409)
    except Exception:
        for path in paths:
            delete_file(path)
        raise
