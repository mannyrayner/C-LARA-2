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
VERSION = 'picture-practice-2'
from . import practice_review
SCHEMA = practice_review.SCHEMA
INSTRUCTIONS = practice_review.INSTRUCTIONS
LEVELS = ['unspecified', 'beginner', 'low_intermediate', 'high_intermediate', 'advanced']


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


def diagnostic(study, stage, state, *, elapsed_ms=None, **details):
    info = study.result['practice']
    diag = info.setdefault('diagnostics', {'schema': 1, 'prompt_version': practice_review.VERSION})
    events = diag.setdefault('events', [])
    events.append({'at': timezone.now().isoformat(), 'stage': stage, 'state': state,
                   **({'elapsed_ms': elapsed_ms} if elapsed_ms is not None else {}), **details})
    diag['events'] = events[-40:]
    # Content stays in the private attempt. Server logs contain no learner words.
    log.info('Picture practice %s stage=%s state=%s', study.pk, stage, state)


def parse(response, original, *, mode='text', confirmed=False):
    return practice_review.parse(response, original, mode=mode, confirmed=confirmed)


def run(pk):
    """ASR proceeds directly to review. Each stage is claimed before I/O.

    Two workers may race between stages; only one can claim the waiting row.
    No provider call is repeated on redelivery, including uncertain failures.
    """
    import time
    close_old_connections()
    try:
        for _ in range(2):
            with transaction.atomic():
                capture.locks()
                study = capture.fetch(pk, True)
                if study.input_mode != 'practice':
                    return
                if study.status != 'waiting':
                    break
                key = permitted(study, payment=True)
                info = study.result['practice']
                stage = info['stage']
                diagnostic(study, stage, 'started')
                study.status = 'processing'
                study.save(update_fields=['status', 'result'])
            began = time.monotonic()
            if stage == 'transcribe':
                response = capture_ai.transcribe(path_for(study.recording_path), tts.language_code(study.language), key)
                capture.account(pk, 'practice_transcription', response, transcription=True)
                text = getattr(response, 'text', '').strip()
                if not text or len(text) > 255:
                    raise ValueError('transcript_length')
                update, status = {'transcript': text, 'original_text': text, 'stage': 'review'}, 'waiting'
            elif stage == 'review':
                response = practice_review.review(path_for(study.file_path).read_bytes(), text=info['original_text'],
                    language=study.language, feedback_language=info['feedback_language'], model=study.model,
                    api_key=key, mode=info['mode'], level=info.get('level', 'unspecified'), confirmed=info.get('confirmed', False))
                charge_stage = 'practice_feedback_confirmed' if info.get('confirmed') else 'practice_feedback'
                capture.account(pk, charge_stage, response)
                # Retain bounded provider output privately even if validation fails.
                with transaction.atomic():
                    current = capture.fetch(pk, True)
                    permitted(current)
                    if current.status != 'processing':
                        return
                    current.result['practice'].setdefault('review_log', []).append({
                        'round': int(bool(info.get('confirmed'))), 'prompt_version': practice_review.VERSION,
                        'output': str(getattr(response, 'output_text', ''))[:16000]})
                    current.save(update_fields=['result'])
                parsed = parse(response, info['original_text'], mode=info['mode'], confirmed=info.get('confirmed', False))
                update = {'heard': parsed['heard'], 'review_decision': parsed['diagnostics']}
                if parsed['outcome'] == 'recognition':
                    update.update(original_text=parsed['heard'], recognition_question=parsed['question'])
                    status = 'transcript'
                    if info.get('confirmed'):
                        # At most one confirmation review per attempt. A further
                        # uncertainty is a request to revise, never an auto-loop.
                        status = 'feedback'
                        update['feedback'] = {'outcome': 'clarify', 'text': parsed['heard'],
                            'question': parsed['question'], 'understood': '', 'corrections': [], 'suggestions': []}
                else:
                    update.update(feedback=parsed['feedback'], recognition_question='')
                    status = 'feedback'
            else:
                raise ValueError('stage')
            with transaction.atomic():
                capture.locks()
                current = capture.fetch(pk, True)
                permitted(current)
                if current.status != 'processing':
                    return
                current.result['practice'].update(update)
                diagnostic(current, stage, 'finished', elapsed_ms=round((time.monotonic()-began)*1000),
                    decision=status)
                current.status = status
                current.save(update_fields=['result', 'status'])
            if status != 'waiting':
                break
        for clip_id in study.speech.filter(kind='feedback', status='waiting').values_list('pk', flat=True):
            capture.speak(clip_id)
    except Exception as exc:
        log.warning('Picture practice %s stopped (%s)', pk, type(exc).__name__)
        with transaction.atomic():
            current = PictureCapture.objects.select_for_update().filter(pk=pk, input_mode='practice',
                status__in=['waiting', 'processing']).first()
            if current:
                diagnostic(current, current.result['practice'].get('stage', ''), 'failed', error_type=type(exc).__name__)
                current.status = 'failed'
                current.save(update_fields=['result', 'status'])
        from .models import CaptureSpeech
        CaptureSpeech.objects.filter(capture_id=pk, status='waiting').update(status='failed')
    finally:
        close_old_connections()
