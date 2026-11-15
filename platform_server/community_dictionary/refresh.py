"""Refresh one accepted sentence without translating or replacing its text.

PictureCapture/CaptureSpeech provide durable claims and accounting. No provider
call runs under a transaction, and every publication rechecks the frozen input.
"""
from datetime import timedelta
import logging

from django.db import close_old_connections, transaction
from django.http import Http404
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import capture, capture_limits, photo_ai, port_vocabulary, port_vocabulary_ai, tts, word_audio
from .models import CaptureSpeech, Entry, PictureCapture, SentenceWord, VocabularyState
from .permissions import is_editor
from .services import Conflict, event
from .storage import path_for

VERSION = 'sentence-refresh-1'
SALT = 'community-sentence-refresh-1'
log = logging.getLogger(__name__)


def available(user, entry):
    d = entry.dictionary
    return bool(is_editor(user, d) and entry.entry_type == 'sentence' and not entry.archived
        and entry.word and entry.current_text and entry.current_text.status == 'accepted'
        and d.sentence_capture_enabled and d.tts_enabled
        and tts.language_code(d.language) and tts.language_code(d.explanation_language or 'English'))


def values(user, entry):
    if not available(user, entry):
        raise Conflict('This action needs an accepted sentence, editing permission and supported audio languages.')
    model, key, personal, prices = photo_ai.configuration(user)
    return {'version': VERSION, 'user': user.pk, 'entry': entry.pk,
        'snapshot': port_vocabulary.sentence_snapshot(entry), 'model': model,
        'personal': personal, 'rates': {k: str(prices[k]) for k in ('input', 'output')},
        'revision': entry.dictionary.capture_revision,
        'membership': entry.dictionary.membership_revision,
        'speech_recipe': tts.INSTRUCTIONS_VERSION, 'speech_model': tts.MODEL,
        'vocabulary_recipe': port_vocabulary.VERSION,
        'word_audio_policy': word_audio.policy(entry.dictionary)}


def validate(study, *, payment=False):
    """Also called by the shared audio worker, including after text publication."""
    info = study.result.get('refresh', {})
    entry = Entry.objects.select_related('dictionary', 'current_text', 'current_meaning').filter(pk=study.saved_entry_id).first()
    if not entry: raise Conflict('This sentence is no longer available.')
    if (info.get('version') != VERSION or not available(study.user, entry)
            or port_vocabulary.sentence_snapshot(entry) != info.get('consent', {}).get('snapshot')):
        raise Conflict('The sentence, translation, picture or editing permission changed. Start a fresh update.')
    if payment and info['consent'] != values(study.user, entry):
        raise Conflict('The prices or settings changed. Review a fresh update estimate.')
    return entry


def queue(pk):
    try:
        from django_q.tasks import async_task
        async_task('community_dictionary.refresh.run', str(pk),
            q_options={'task_name': f'sentence-refresh-{pk}', 'timeout': 900, 'ack_failure': True})
    except Exception:
        log.warning('Could not enqueue sentence refresh %s; explicit continuation is available', pk)


def audio_complete(entry):
    from .lexicon import recordings
    from . import sentence_forms
    if not recordings(entry, entry.dictionary): return False
    for link in sentence_forms.links(entry):
        if not recordings(link.word_entry, entry.dictionary): return False
        form = sentence_forms.find(link)
        if form and not sentence_forms.separated(form.word) and not sentence_forms.audio(form): return False
    return True


def plan_audio(study, entry, targets=None):
    from . import sentence_forms
    targets = targets if targets is not None else [link.word_entry for link in sentence_forms.links(entry)]
    for target in [*targets, entry]: capture.plan_speech(study, target)
    for link in sentence_forms.links(entry):
        form = sentence_forms.find(link)
        if form and not sentence_forms.separated(form.word) and not sentence_forms.audio(form):
            CaptureSpeech.objects.create(capture=study, kind='form', entry=entry,
                text_id=form.pk, text=form.word, meaning=form.meaning, language=study.language)


def input_data(study):
    entry = validate(study)
    words = [{'id': p.entry_id, 'lemma': p.word, 'meaning': p.entry.meaning}
             for p in study.sources.filter(text_field='word', entry__entry_type='word').select_related('entry')]
    return {'target_language': study.language, 'explanation_language': study.explanation_language,
        'sentence': entry.word, 'translation': entry.meaning, 'vocabulary': words}


def prepare(pk):
    with transaction.atomic():
        capture.locks(); study = capture.fetch(pk, True)
        if study.input_mode != 'refresh' or study.status != 'waiting':
            return
        key = capture.allowed(study, payment=True)
        data = input_data(study)
        study.result['refresh']['started_at'] = timezone.now().isoformat()
        study.status = 'processing'; study.save(update_fields=['status', 'result'])
    try:
        photo = path_for(study.source_image.file_path).read_bytes() if study.source_image_id else None
        response = port_vocabulary_ai.analyse(data, photo, model=study.model, api_key=key)
        capture.account(pk, 'refresh_vocabulary', response)
        result = port_vocabulary_ai.parse(response, data)
        with transaction.atomic():
            capture.locks(); current = capture.fetch(pk, True)
            capture.allowed(current)
            if current.status != 'processing':
                return
            current.result = {**current.result, 'words': result['words']}
            current.status = 'ready'; current.save(update_fields=['result', 'status'])
    except Exception as exc:
        log.warning('Sentence refresh %s failed (%s)', pk, type(exc).__name__)
        PictureCapture.objects.filter(pk=pk, status='processing').update(status='failed')


def publish(pk):
    with transaction.atomic():
        capture.locks(); study = capture.fetch(pk, True)
        if study.input_mode != 'refresh' or study.status != 'ready':
            return
        capture.allowed(study)
        entry = validate(study)
        words = port_vocabulary.validated_words(study.result['words'], entry.word)
        # Keep existing manually corrected forms/links. Their glosses and custody
        # remain authoritative; old sentence revisions retain their own history.
        from . import sentence_forms
        protected = []
        for link in sentence_forms.links(entry):
            form = sentence_forms.find(link)
            if form and form.previous_revision_id:
                protected.append((link, form))
        protected_ids = {link.word_entry_id for link, form in protected}
        from .capture_vocabulary import identity
        protected_keys = {identity(link.word_entry.word, link.word_entry.meaning) for link, form in protected}
        words = [w for w in words if identity(w['lemma'], w['meaning']) not in protected_keys]
        # Remove relations, never shared dictionary entries or human recordings.
        SentenceWord.objects.filter(sentence_text=entry.current_text).exclude(word_entry_id__in=protected_ids).delete()
        from .models import ImageWordLink
        ImageWordLink.objects.filter(sentence_text__entry=entry).exclude(word_entry_id__in=protected_ids).delete()
        provenance = {'origin': 'sentence-vocabulary', 'sentence_refresh': str(study.pk),
            'recipe': VERSION, 'model': study.model, 'language': study.language,
            'vocabulary_generated_automatically': True}
        from .capture_vocabulary import publish_words
        images = list(entry.contributions.filter(kind='image', status='accepted').exclude(file_path=''))
        targets = publish_words(entry.current_text, words, study.user, provenance, images)
        targets += [link.word_entry for link, form in protected]
        plan_audio(study, entry, targets)
        VocabularyState.objects.update_or_create(sentence=entry, defaults={
            'snapshot': port_vocabulary.sentence_snapshot(entry), 'recipe': port_vocabulary.VERSION,
            'accepted_by': study.user, 'accepted_at': timezone.now(),
            'words': [{'entry': e.pk, 'text': e.current_text_id, 'meaning': e.current_meaning_id} for e in targets]})
        study.status = 'saved'; study.save(update_fields=['status'])
        event(entry.dictionary, study.user, 'sentence_refreshed', entry,
            'Updated vocabulary from fixed accepted wording; audio queued; no expert review claimed')


def run(pk):
    close_old_connections()
    try:
        study = capture.fetch(pk)
        if study.input_mode != 'refresh':
            return
        if study.status == 'waiting': prepare(pk)
        if capture.fetch(pk).status == 'ready': publish(pk)
        if capture.fetch(pk).status == 'saved': capture.run_audio(pk)
    except Exception as exc:
        log.warning('Sentence refresh %s stopped (%s)', pk, type(exc).__name__)
        PictureCapture.objects.filter(pk=pk, status__in=['waiting', 'ready']).update(status='failed')
    finally:
        close_old_connections()


def retry_audio(pk, user):
    with transaction.atomic():
        capture.locks(); study = capture.fetch(pk, True)
        if study.user_id != user.pk or study.input_mode != 'refresh': raise Http404
        if study.status != 'saved': raise Conflict('Finish the vocabulary update first.')
        capture.allowed(study, payment=True)
        for clip in capture.failed_audio(study):
            capture.speech_allowed(clip)
            if study.speech.filter(kind=clip.kind, text_id=clip.text_id, status__in=['waiting', 'running']).exists():
                continue
            CaptureSpeech.objects.create(capture=study, kind=clip.kind, entry=clip.entry,
                text=clip.text, meaning=clip.meaning, language=clip.language,
                text_id=clip.text_id, meaning_id=clip.meaning_id)
        transaction.on_commit(lambda: queue(pk))


def recover(study):
    """Uncertain requests are failed, never automatically sent a second time."""
    cutoff = timezone.now() - timedelta(minutes=15)
    started = parse_datetime(study.result.get('refresh', {}).get('started_at', '')) or study.created_at
    if started < cutoff:
        PictureCapture.objects.filter(pk=study.pk, status='processing').update(status='failed')
    for clip in study.speech.filter(status='running'):
        started = parse_datetime(clip.report.get('refresh_started_at', '')) or study.created_at
        if started < cutoff:
            CaptureSpeech.objects.filter(pk=clip.pk, status='running').update(status='failed')
    study.refresh_from_db()
