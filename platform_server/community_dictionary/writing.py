"""Writing practice uses private PictureCapture attempts and the shared publisher.

No new persistence model: input_mode identifies the workflow; result.writing
contains private feedback. Each revised draft is a new, idempotent attempt.
"""
import difflib
import logging
from django.db import close_old_connections, transaction
from django.utils import timezone
from . import capture, writing_ai
from .models import PictureCapture, CaptureSpeech
from .services import Conflict
from .storage import path_for

log = logging.getLogger(__name__)
RETENTION_DAYS = 30


def preference(request, dictionary):
    return getattr(request, 'session', {}).get(f'writing-{dictionary.pk}', {})


def enabled(request, dictionary):
    return bool(dictionary and dictionary.sentence_capture_enabled and dictionary.tts_enabled
                and preference(request, dictionary).get('enabled'))


def own(user, dictionary, pk):
    from django.shortcuts import get_object_or_404
    from django.http import Http404
    study = get_object_or_404(PictureCapture, pk=pk, dictionary=dictionary,
        user=user, input_mode='writing', expires_at__gt=timezone.now())
    if study.status == 'discarded':
        raise Http404
    capture.allowed(study)
    return study


def changes(original, corrected):
    """Plain strings rendered with template escaping, never model-supplied HTML."""
    return [{'changed': tag != 'equal', 'text': corrected[j1:j2]}
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, original, corrected, autojunk=False).get_opcodes() if j2 > j1]


def queue(pk):
    try:
        from django_q.tasks import async_task
        async_task('community_dictionary.writing.run', str(pk),
            q_options={'task_name': f'writing-{pk}', 'timeout': 900, 'ack_failure': True})
    except Exception:
        log.warning('Could not enqueue writing attempt %s; explicit continuation is available', pk)


def review(pk):
    with transaction.atomic():
        capture.locks()
        study = capture.fetch(pk, True)
        if study.input_mode != 'writing' or study.status != 'waiting':
            return
        key = capture.allowed(study, payment=True)
        study.status = 'processing'
        study.save(update_fields=['status'])
    try:
        original = study.result['writing']['original_text']
        response = writing_ai.review(path_for(study.file_path).read_bytes(), text=original,
            language=study.language, feedback_language=study.result['writing']['feedback_language'],
            model=study.model, api_key=key)
        capture.account(pk, 'writing_feedback', response)
        feedback = writing_ai.parse(response, original)
        with transaction.atomic():
            capture.locks()
            current = capture.fetch(pk, True)
            capture.allowed(current)
            if current.status != 'processing':
                return
            current.result = {'writing': {**current.result['writing'], 'feedback': feedback}}
            current.status = 'feedback'
            current.save(update_fields=['result', 'status'])
    except Exception as exc:
        log.warning('Writing feedback %s failed (%s)', pk, type(exc).__name__)
        PictureCapture.objects.filter(pk=pk, status='processing').update(status='failed')


def approve(pk, user):
    with transaction.atomic():
        capture.locks()
        study = capture.fetch(pk, True)
        if study.user_id != user.pk or study.input_mode != 'writing':
            from django.http import Http404
            raise Http404
        capture.allowed(study)
        if study.status in {'approved', 'processing', 'ready', 'saved'} and study.result['writing'].get('approved_text'):
            return  # Repeated button taps never schedule another paid attempt.
        feedback = study.result['writing'].get('feedback', {})
        if study.status != 'feedback' or feedback.get('outcome') != 'ready':
            raise Conflict('Read the writing feedback before approving a version.')
        capture.allowed(study, payment=True)
        # Reuse the same bounded vocabulary context as picture descriptions.
        size = 0
        for entry in study.dictionary.entries.filter(entry_type='word', archived=False).exclude(word='').select_related(
                'current_text', 'current_meaning').order_by('-created_at')[:200]:
            if not entry.current_text or entry.current_text.status != 'accepted' or len(entry.meaning) > 300:
                continue
            size += len(entry.word) + len(entry.meaning)
            if size > 24000: break
            study.sources.add(*[part.pk for part in [entry.current_text, entry.current_meaning]
                if part and part.status == 'accepted'])
        study.result = {'writing': {**study.result['writing'],
            'approved_text': feedback['text'], 'approved_at': timezone.now().isoformat()}}
        # Older capture publishers include description in shared provenance.
        # Keep only approved text there, including across a code rollback.
        study.description = feedback['text']
        study.status = 'approved'
        study.save(update_fields=['status', 'result', 'description'])
        transaction.on_commit(lambda: queue(pk))


def run(pk):
    """One bounded job; persisted claims prevent duplicate calls on redelivery."""
    close_old_connections()
    try:
        study = capture.fetch(pk)
        if study.input_mode != 'writing':
            return
        if study.status == 'waiting':
            review(pk)
            return
        if study.status == 'approved':
            capture.prepare(pk)
        study = capture.fetch(pk)
        if study.status == 'ready' and study.result.get('writing', {}).get('approved_text'):
            capture.publish(pk, study.user)
        if PictureCapture.objects.filter(pk=pk, status='saved').exists():
            capture.run_audio(pk)
    except Exception as exc:
        log.warning('Writing attempt %s stopped (%s)', pk, type(exc).__name__)
        PictureCapture.objects.filter(pk=pk, input_mode='writing', status__in=['waiting', 'approved', 'ready']).update(status='failed')
    finally:
        close_old_connections()


def retry_audio(pk, user):
    """Explicit, bounded retry of failed clips only; old attempts remain billed."""
    with transaction.atomic():
        capture.locks()
        study = capture.fetch(pk, True)
        if study.user_id != user.pk or study.input_mode != 'writing' or study.status != 'saved':
            raise Conflict('Open the completed writing attempt first.')
        capture.allowed(study, payment=True)
        from .lexicon import recordings
        for clip in study.speech.filter(kind='entry', status='failed').select_related('entry'):
            if study.speech.filter(entry_id=clip.entry_id, status__in=['waiting', 'running']).exists():
                continue
            capture.speech_allowed(clip)
            if recordings(clip.entry, study.dictionary):
                continue
            # A failed attempt is superseded locally, not retried with its old
            # accounting key. Do not revive a running/uncertain provider call.
            CaptureSpeech.objects.create(capture=study, kind='entry', entry=clip.entry,
                text=clip.text, meaning=clip.meaning, language=clip.language,
                text_id=clip.text_id, meaning_id=clip.meaning_id)
        transaction.on_commit(lambda: queue(pk))


def recent(user, dictionary):
    return PictureCapture.objects.filter(user=user, dictionary=dictionary, input_mode='writing',
        expires_at__gt=timezone.now()).exclude(status='discarded').order_by('-created_at')[:8]
