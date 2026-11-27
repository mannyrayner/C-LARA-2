"""Words-first guided pictures. One durable claim before each paid provider call."""
from datetime import timedelta
from copy import deepcopy
from decimal import Decimal
import uuid
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from projects.billing import credits_enabled, get_user_balance_usd
from . import capture, capture_ai, guided, image_generation as images, learning, photo_ai, tts, writing
from .models import ImageStudy, Participation, PictureCapture, VoicePreference
from .services import Conflict
from .storage import delete_file, path_for, write_upload

SALT = 'guided-words-1'


def quote_values(user, dictionary):
    model, _key, personal, allowance = images.configuration(user)
    return {'version': 'guided-words-1', 'guided': guided.consent_values(user, dictionary),
        'image_revision': dictionary.image_generation_revision, 'image_enabled': dictionary.image_generation_enabled,
        'image_model': model, 'personal': personal, 'allowance': str(allowance),
        'quality': images.QUALITY, 'size': images.SIZE, 'prompt_version': images.PROMPT_VERSION,
        'text_rate': str(images.TEXT_RATE), 'output_rate': str(images.OUTPUT_RATE),
        'asr_model': capture_ai.ASR_MODEL}


def context(user, dictionary):
    values, error = None, ''
    try:
        if dictionary.image_generation_enabled: values = quote_values(user, dictionary)
    except Conflict as exc: error = str(exc)
    return {'words_quote': signing.dumps(values, salt=SALT) if values else '',
        'words_estimate': estimate(values) if values else None, 'words_setup_error': error,
        'image_counts': images.daily_usage(dictionary, user)}


def estimate(values):
    # Configured image allowance plus the existing enrichment estimate and a
    # short recording allowance. Provider invoice remains authoritative.
    return Decimal(values['allowance']) + guided.estimate(values['guided']) + Decimal('0.01')


def approved_quote(form, user, dictionary):
    try:
        values = signing.loads(form.cleaned_data['words_quote'], salt=SALT, max_age=600)
    except signing.BadSignature:
        raise Conflict(_('Reload this page to see the current picture-generation estimate.'))
    if not dictionary.image_generation_enabled or values != quote_values(user, dictionary):
        raise Conflict(_('The AI settings changed. Reload this page and confirm the new estimate.'))
    return values


def permitted(study, payment=False):
    info = study.result.get('guided', {}).get('words')
    if not info or study.status == 'saved': return
    # Disabling generation invalidates unfinished work, including publication.
    if (not study.dictionary.image_generation_enabled or
            study.dictionary.image_generation_revision != info['quote']['image_revision']):
        raise Conflict(_('The image settings changed. Start a new preview.'))
    if payment and info['quote'] != quote_values(study.user, study.dictionary):
        raise Conflict(_('The AI settings changed. Start a new preview with the current estimate.'))


def new_attempt(request, dictionary, paths, form, quote):
    data = form.cleaned_data
    extra = data.get('extra_image_allowance', False)
    images.approve_capacity(dictionary, request.user, extra)
    choices = dict(learning.preference(request, dictionary).get('choices', {}))
    styles = dict(choices.get('styles', {}))
    style_key = data['picture_style']
    if style_key == 'custom':
        style_key = next((key for key, value in styles.items()
            if value['name'].casefold() == data['style_name'].casefold()), None)
        if style_key is None:
            if len(styles) >= 20: raise Conflict(_('You can save up to 20 picture styles per dictionary.'))
            style_key = 'saved-' + uuid.uuid4().hex
        styles[style_key] = {'name': data['style_name'], 'description': data['style_description']}
    choices.update(start_with='words', words_mode=data['words_mode'], words_language=data['words_language'],
        picture_style=style_key, styles=styles, style_seen=True)
    learning.save_guided_choices(request, dictionary, choices)
    audio = write_upload(data['prepared_audio'], dictionary.pk, paths) if data['words_mode'] == 'voice' else {}
    text = data.get('words', '')
    info = {'method': data['words_mode'], 'text': text, 'stage': 'transcribe' if audio else 'image',
        'style_name': data['style_name'], 'style_description': data['style_description'], 'quote': quote}
    study = PictureCapture.objects.create(dictionary=dictionary, user=request.user, status='draft',
        input_mode='guided', input_language=data['words_language'], language=dictionary.language,
        explanation_language=dictionary.explanation_language or 'English', description=text,
        recording_path=audio.get('file_path', ''), model=quote['guided']['model'],
        personal_key=quote['guided']['personal'],
        voice=VoicePreference.objects.filter(user=request.user, dictionary=dictionary).values_list('voice', flat=True).first() or tts.VOICE,
        expires_at=timezone.now() + timedelta(days=writing.RETENTION_DAYS), revision=dictionary.capture_revision,
        membership_revision=dictionary.membership_revision,
        participation_revision=Participation.objects.filter(dictionary=dictionary, user=request.user).values_list('revision', flat=True).first() or 0,
        result={'guided': {'version': quote['guided']['version'], 'level': learning.level(dictionary),
            'consent': {**quote['guided'], 'words_version': quote['version']}, 'words': info}})
    if extra:
        info['image_allowance'] = images.allowance_token(dictionary, request.user, study.pk)
        study.save(update_fields=['result'])
    return study


def generate_from_transcript(pk, user, text):
    with transaction.atomic():
        capture.locks(); study = capture.fetch(pk, True)
        if study.user_id != user.pk: raise Conflict(_('This preview belongs to another user.'))
        guided.permitted(study, payment=True)
        info = study.result['guided']['words']
        if study.status in {'waiting', 'processing'} and info['stage'] == 'image' and info['text'] == text: return
        if study.status != 'feedback' or info['stage'] != 'confirm':
            raise Conflict(_('Open the current preview before continuing.'))
        info.update(text=text, stage='image')
        study.description, study.status = text, 'waiting'
        study.save(update_fields=['description', 'status', 'result'])
        transaction.on_commit(lambda: guided.queue(pk))


def admit_image(study):
    model, _key, personal, allowance = images.configuration(study.user)
    if not personal and credits_enabled() and get_user_balance_usd(study.user) < allowance:
        raise Conflict(_('Your balance is too low to generate this picture.'))
    recent = images.started_studies().filter(created_at__gte=timezone.now()-timedelta(days=1))
    info = study.result['guided']['words']
    extra = images.approved_allowance(info.get('image_allowance'), study.dictionary, study.user, study.pk)
    images.approve_capacity(study.dictionary, study.user, extra)
    if recent.filter(user=study.user, status='processing',
            created_at__gte=timezone.now()-timedelta(seconds=images.TIMEOUT+60)).exists():
        raise Conflict(_('Your previous image is still being generated. Open its recent attempt before starting another.'))
    info = study.result['guided']['words']
    return ImageStudy.objects.create(dictionary=study.dictionary, user=study.user, kind='entry',
        expires_at=study.expires_at, subject=info['text'], style_description=info['style_description'],
        membership_revision=study.membership_revision, participation_revision=study.participation_revision,
        policy_revision=study.dictionary.image_generation_revision, model=model, quality=images.QUALITY,
        personal_key=personal, prompt=images.prompt_for(info['text'], info['style_description']),
        usage={'owner_allowance': {'approved_by': study.user_id, 'source_attempt': str(study.pk)}} if extra else {})


def run(pk):
    attempt = None
    paths = []
    try:
        with transaction.atomic():
            capture.locks(); study = capture.fetch(pk, True)
            if study.status != 'waiting': return
            key = capture.allowed(study, payment=True)
            info = study.result['guided']['words']
            if info['stage'] == 'image':
                get_user_model().objects.select_for_update().get(pk=study.user_id)
                attempt = admit_image(study)
                info['image_attempt'] = str(attempt.pk)
            study.status = 'processing'
            study.save(update_fields=['status', 'result'])
        if info['stage'] == 'transcribe':
            response = capture_ai.transcribe(path_for(study.recording_path), tts.language_code(study.input_language), key)
            capture.account(pk, 'transcription', response, transcription=True)
            text = getattr(response, 'text', '').strip()
            if not 0 < len(text) <= 255: raise ValueError('transcript_length')
            with transaction.atomic():
                capture.locks(); current = capture.fetch(pk, True); guided.permitted(current)
                if current.status != 'processing': return
                current.result['guided']['words'].update(text=text, stage='confirm')
                current.description, current.status = text, 'feedback'
                current.save(update_fields=['result', 'description', 'status'])
        else:
            prepared, usage, failure = images.generate(attempt, key)
            # Account the attempt even if membership/policy changed during the call.
            with transaction.atomic():
                row = ImageStudy.objects.select_for_update().get(pk=attempt.pk)
                images.account(row, usage)
                if row.status == 'processing':
                    row.status, row.failure_code = ('ready' if prepared else 'failed'), failure
                row.save()
            if not prepared: raise ValueError('image_generation_failed')
            with transaction.atomic():
                capture.locks(); current = capture.fetch(pk, True); guided.permitted(current)
                if current.status != 'processing': return
                media = write_upload(prepared, current.dictionary_id, paths)
                current.file_path, current.status = media['file_path'], 'feedback'
                current.result['guided']['words']['stage'] = 'ready'
                current.result['guided']['suggestion'] = {'outcome': 'ready', 'description': info['text'], 'question': ''}
                current.save(update_fields=['file_path', 'status', 'result'])
    except Exception as exc:
        for path in paths: delete_file(path)
        guided.log.warning('Words-first preview %s stopped (%s)', pk, type(exc).__name__)
        PictureCapture.objects.filter(pk=pk, status__in=['waiting', 'processing']).update(status='failed')
        if isinstance(exc, images.ImageAllowanceConflict):
            with transaction.atomic():
                current = capture.fetch(pk, True)
                current.result['guided']['words']['allowance_error'] = str(exc)
                current.save(update_fields=['result'])


def image_provenance(study):
    info = study.result['guided']['words']
    return {'origin': 'generated', 'provider': 'openai', 'model': info['quote']['image_model'],
        'quality': info['quote']['quality'], 'size': info['quote']['size'],
        'subject': info['text'], 'style_name': info['style_name'], 'style_description': info['style_description'],
        'prompt_version': info['quote']['prompt_version'], 'study_id': info.get('image_attempt'),
        'permission_confirmed': True, 'reviewed_by': study.user_id,
        'reviewed_at': timezone.now().isoformat()}


def retry_enrichment(study, paths):
    """Keep the already generated picture and words; never buy another image."""
    current = capture.fetch(study.pk, True)
    guided.permitted(current, payment=True)
    if current.status != 'failed' or not current.file_path:
        raise Conflict(_('Open the current preview before continuing.'))
    info = deepcopy(current.result['guided'])
    info.pop('approved_description', None)
    info.pop('approved_at', None)
    text = info['words']['text']
    info['suggestion'] = {'outcome': 'ready', 'description': text, 'question': ''}
    media = write_upload((path_for(current.file_path).read_bytes(), 'image/jpeg', '.jpg'), current.dictionary_id, paths)
    return PictureCapture.objects.create(dictionary=current.dictionary, user=current.user, status='feedback',
        input_mode='guided', input_language=current.input_language, language=current.language,
        explanation_language=current.explanation_language, description=text, file_path=media['file_path'],
        model=current.model, personal_key=current.personal_key, voice=current.voice,
        expires_at=timezone.now()+timedelta(days=writing.RETENTION_DAYS), revision=current.revision,
        membership_revision=current.membership_revision, participation_revision=current.participation_revision,
        result={'guided': info})
