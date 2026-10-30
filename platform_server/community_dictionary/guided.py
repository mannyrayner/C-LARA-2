"""Private picture -> approved meaning -> existing sentence/word/audio pipeline."""
from decimal import Decimal
import logging
from django.contrib.auth import get_user_model
from django.db import close_old_connections, transaction
from django.http import Http404
from django.utils import timezone
from . import capture, capture_limits, guided_ai, learning, photo_ai
from .models import PictureCapture
from .permissions import get_dictionary
from .services import Conflict
from .storage import path_for

log = logging.getLogger(__name__)


def consent_values(user, dictionary):
    model, key, personal, prices = photo_ai.configuration(user)
    from . import tts
    # No credential values are stored. Changing provider rates/payer or policy
    # requires renewed consent before a further request.
    return {'version': guided_ai.VERSION, 'user': user.pk, 'dictionary': dictionary.pk,
        'revision': dictionary.capture_revision, 'language': dictionary.language,
        'explanation_language': dictionary.explanation_language or 'English',
        'model': model, 'personal': personal,
        'rates': {k: str(prices[k]) for k in ['input', 'output']},
        'speech_model': tts.MODEL, 'speech_recipe': tts.INSTRUCTIONS_VERSION}


def estimate(values):
    rates = values['rates']
    return capture_limits.unit_estimate(rates) + (
        Decimal(3000) * Decimal(rates['input']) + Decimal(1200) * Decimal(rates['output'])) / 1_000_000


def permitted(study, payment=False):
    capture.allowed(study, payment=payment)
    if study.input_mode != 'guided': raise Http404


def own(user, dictionary, pk):
    from django.shortcuts import get_object_or_404
    study = get_object_or_404(PictureCapture, pk=pk, dictionary=dictionary, user=user,
        input_mode='guided', expires_at__gt=timezone.now())
    permitted(study)
    return study


def queue(pk):
    try:
        from django_q.tasks import async_task
        async_task('community_dictionary.guided.run', str(pk),
            q_options={'task_name': f'guided-{pk}', 'timeout': 900, 'ack_failure': True})
    except Exception:
        log.warning('Could not enqueue guided picture %s; explicit continuation is available', pk)


def begin(pk):
    with transaction.atomic():
        capture.locks()
        study = capture.fetch(pk, True)
        if study.input_mode != 'guided' or study.status != 'draft': return
        get_user_model().objects.select_for_update().get(pk=study.user_id)
        permitted(study, payment=True)
        capture_limits.enforce(study.dictionary, study.user)
        study.status = 'waiting'
        study.created_at = timezone.now()
        study.usage['guided_request'] = {'cost_usd': '0', 'tokens': {}}
        study.save(update_fields=['status', 'created_at', 'usage'])
        transaction.on_commit(lambda: queue(pk))


def describe(pk):
    with transaction.atomic():
        capture.locks(); study = capture.fetch(pk, True)
        if study.input_mode != 'guided' or study.status != 'waiting': return
        permitted(study, payment=True)
        key = photo_ai.api_credentials(study.user)[0]
        study.status = 'processing'; study.save(update_fields=['status'])
    try:
        response = guided_ai.describe(path_for(study.file_path).read_bytes(), {
            'explanation_language': study.explanation_language,
            'generation_level': study.result['guided']['level']}, model=study.model, api_key=key)
        capture.account(pk, 'guided_description', response)
        result = guided_ai.parse(response)
        with transaction.atomic():
            capture.locks(); current = capture.fetch(pk, True); permitted(current)
            if current.status != 'processing': return
            current.result['guided']['suggestion'] = result
            current.status = 'feedback'
            current.save(update_fields=['result', 'status'])
    except Exception as exc:
        log.warning('Guided picture %s failed (%s)', pk, type(exc).__name__)
        PictureCapture.objects.filter(pk=pk, status='processing').update(status='failed')


def approve(pk, user, description):
    description = description.strip()
    if not description or len(description) > 255:
        raise Conflict('Write a short description of what you want to say (up to 255 characters).')
    with transaction.atomic():
        capture.locks(); study = capture.fetch(pk, True)
        if study.user_id != user.pk: raise Http404
        permitted(study)
        info = study.result['guided']
        if study.status in {'approved', 'processing', 'ready', 'saved'} and info.get('approved_description'):
            if info['approved_description'] != description:
                raise Conflict('This version is already approved. Open its result before editing again.')
            return
        if study.status != 'feedback': raise Conflict('Wait for the picture description before confirming.')
        get_user_model().objects.select_for_update().get(pk=study.user_id)
        permitted(study, payment=True)
        if 'guided_request' not in study.usage:
            capture_limits.enforce(study.dictionary, study.user)
            study.created_at = timezone.now()
            study.usage['guided_request'] = {'cost_usd': '0', 'tokens': {}}
        size = 0
        for entry in study.dictionary.entries.filter(entry_type='word', archived=False).exclude(word='').select_related(
                'current_text', 'current_meaning').order_by('-created_at')[:200]:
            if not entry.current_text or entry.current_text.status != 'accepted' or len(entry.meaning) > 300: continue
            size += len(entry.word) + len(entry.meaning)
            if size > 24000: break
            study.sources.add(*[p.pk for p in [entry.current_text, entry.current_meaning] if p and p.status == 'accepted'])
        info.update(approved_description=description, approved_at=timezone.now().isoformat())
        study.description = description
        study.status = 'approved'
        study.save(update_fields=['result', 'description', 'status', 'usage', 'created_at'])
        transaction.on_commit(lambda: queue(pk))


def run(pk):
    close_old_connections()
    try:
        study = capture.fetch(pk)
        if study.input_mode != 'guided': return
        if study.status == 'waiting':
            describe(pk); return
        if study.status == 'approved':
            permitted(study, payment=True)
            capture.prepare(pk)
        study = capture.fetch(pk)
        if study.status == 'ready' and study.result.get('guided', {}).get('approved_description'):
            capture.publish(pk, study.user)
        if PictureCapture.objects.filter(pk=pk, status='saved').exists():
            capture.run_audio(pk)
    except Exception as exc:
        log.warning('Guided picture %s stopped (%s)', pk, type(exc).__name__)
        PictureCapture.objects.filter(pk=pk, input_mode='guided', status__in=['waiting', 'approved', 'ready']).update(status='failed')
    finally:
        close_old_connections()
