"""Private, bounded picture practice. No contribution or enrichment stage."""
import logging
from decimal import Decimal
from django.db import close_old_connections, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from projects.billing import has_minimum_balance_for_compile
from . import capture, capture_ai, photo_ai, tts, writing_ai
from .models import Contribution, ContributionPreference, PictureCapture, Participation
from .permissions import get_dictionary
from .services import Conflict
from .storage import path_for

log = logging.getLogger(__name__)
VERSION = 'picture-practice-1'
SCHEMA = {**writing_ai.SCHEMA, 'properties': {**writing_ai.SCHEMA['properties'],
    'understood': writing_ai.string(600)}, 'required': [*writing_ai.SCHEMA['required'], 'understood']}
INSTRUCTIONS = writing_ai.INSTRUCTIONS.replace('The learner writes', 'The learner practises').replace(
    'to try writing in target_language', 'to try again in target_language') + '''
This is speaking or writing practice, not a caption-matching test. A few words, an
interpretation, an imagined situation or dialogue are all valid. Never require the
stored dictionary description (which you have not been given), or invent a visual
contradiction when the speaker may simply be imagining something. In understood,
briefly say what you understood, using feedback_language. Focus explanations on
one or two useful learning points; explain all edits, grouping related changes.
Keep feedback brief. Usually no optional suggestions, at most one.
For speech you see only a learner-confirmed transcript, NOT the recording: never
claim to assess pronunciation, accent, fluency, confidence or speaking ability.'''


def images(dictionary, category=''):
    qs = Contribution.objects.filter(entry__dictionary=dictionary, entry__archived=False,
        kind='image', status='accepted').exclude(file_path='').exclude(pk=dictionary.image_style_id)
    if category:
        qs = qs.filter(entry__current_category__status='accepted', entry__category=category)
    return qs.select_related('entry__current_text')


def available(dictionary):
    return dictionary.sentence_capture_enabled and bool(tts.language_code(dictionary.language))


def choices(user, dictionary):
    row = ContributionPreference.objects.filter(user=user, dictionary=dictionary).first()
    return row.consent.get('_picture_practice', {}) if row else {}


def save_choices(user, dictionary, values):
    from .learning import available as guided_available
    row, _ = ContributionPreference.objects.select_for_update().get_or_create(user=user, dictionary=dictionary,
        defaults={'mode': 'guided' if guided_available(dictionary) else 'manual'})
    row.consent = {**row.consent, '_picture_practice': values}
    row.updated_at = timezone.now()
    row.save(update_fields=['consent', 'updated_at'])


def quote(user, dictionary):
    model, _key, personal, prices = photo_ai.configuration(user)
    return {'version': VERSION, 'model': model, 'personal': personal,
        'input': str(prices['input']), 'output': str(prices['output']),
        'language': dictionary.language, 'explanation': dictionary.explanation_language or 'English',
        'revision': dictionary.capture_revision, 'membership': dictionary.membership_revision}


def estimate(values):
    # Image + short text + bounded output. Preview only; actual usage is charged.
    return (Decimal(3000)*Decimal(values['input']) + Decimal(2600)*Decimal(values['output'])) / 1000000


def own(user, dictionary, pk):
    study = get_object_or_404(PictureCapture, pk=pk, user=user, dictionary=dictionary,
        input_mode='practice', expires_at__gt=timezone.now())
    if study.status == 'discarded':
        raise Http404
    permitted(study)
    return study


def permitted(study, *, payment=False):
    dictionary = get_dictionary(study.user, study.dictionary_id)
    revision = Participation.objects.filter(user=study.user, dictionary=dictionary).values_list('revision', flat=True).first() or 0
    if (not available(dictionary) or study.status == 'discarded' or study.expires_at <= timezone.now() or
            dictionary.capture_revision != study.revision or dictionary.membership_revision != study.membership_revision or
            revision != study.participation_revision or dictionary.language != study.language or
            (dictionary.explanation_language or 'English') != study.explanation_language):
        raise Conflict('The practice settings or your participation changed. Start again from Practise.')
    if not study.source_image_id or not images(dictionary).filter(pk=study.source_image_id).exists():
        raise Conflict('The original picture is no longer available. Choose another picture.')
    if payment:
        if study.result['practice']['quote'] != quote(study.user, dictionary):
            raise Conflict('The AI settings or prices changed. Start a new practice attempt.')
        if not has_minimum_balance_for_compile(study.user):
            raise Conflict('Your balance is too low. Add credit before continuing practice.')
        return photo_ai.api_credentials(study.user)[0]


def queue(pk):
    try:
        from django_q.tasks import async_task
        async_task('community_dictionary.picture_practice.run', str(pk),
            q_options={'task_name': f'picture-practice-{pk}', 'timeout': 900, 'ack_failure': True})
    except Exception:
        log.warning('Could not enqueue picture practice %s; explicit continuation is available', pk)


def parse(response, original):
    import json
    from types import SimpleNamespace
    data = json.loads(response.output_text)
    if not isinstance(data, dict) or set(data) != set(SCHEMA['properties']):
        raise ValueError('practice_fields')
    understood = data.pop('understood')
    if not isinstance(understood, str) or not understood.strip() or len(understood) > 600:
        raise ValueError('understood')
    parsed = writing_ai.parse(SimpleNamespace(status=getattr(response, 'status', None),
        output_text=json.dumps(data)), original)
    return {**parsed, 'understood': understood}


def run(pk):
    """Commit a stage claim before network I/O; redelivery never repeats it."""
    close_old_connections()
    try:
        with transaction.atomic():
            capture.locks()
            study = capture.fetch(pk, True)
            if study.input_mode != 'practice':
                return
            if study.status != 'waiting':
                stage = None
            else:
                key = permitted(study, payment=True)
                stage = study.result['practice']['stage']
                study.status = 'processing'
                study.save(update_fields=['status'])
        if stage:
            if stage == 'transcribe':
                response = capture_ai.transcribe(path_for(study.recording_path), tts.language_code(study.language), key)
                capture.account(pk, 'practice_transcription', response, transcription=True)
                text = getattr(response, 'text', '').strip()
                if not text or len(text) > 255:
                    raise ValueError('transcript_length')
                update, status = {'transcript': text, 'original_text': text}, 'transcript'
            elif stage == 'review':
                info = study.result['practice']
                response = writing_ai.review(path_for(study.file_path).read_bytes(), text=info['original_text'],
                    language=study.language, feedback_language=info['feedback_language'], model=study.model,
                    api_key=key, instructions=INSTRUCTIONS, schema=SCHEMA)
                capture.account(pk, 'practice_feedback', response)
                update, status = {'feedback': parse(response, info['original_text'])}, 'feedback'
            else:
                raise ValueError('stage')
            with transaction.atomic():
                capture.locks()
                current = capture.fetch(pk, True)
                permitted(current)
                if current.status != 'processing':
                    return
                current.result = {'practice': {**current.result['practice'], **update}}
                current.status = status
                current.save(update_fields=['result', 'status'])
        for clip_id in study.speech.filter(kind='feedback', status='waiting').values_list('pk', flat=True):
            capture.speak(clip_id)  # Only explicitly requested private clips exist.
    except Exception as exc:
        log.warning('Picture practice %s stopped (%s)', pk, type(exc).__name__)
        PictureCapture.objects.filter(pk=pk, input_mode='practice', status__in=['waiting', 'processing']).update(status='failed')
        from .models import CaptureSpeech
        CaptureSpeech.objects.filter(capture_id=pk, status='waiting').update(status='failed')
    finally:
        close_old_connections()
