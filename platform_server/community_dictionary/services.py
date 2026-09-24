import hashlib
import json
import uuid

from django.db import IntegrityError, transaction
from django.urls import reverse

from .models import Contribution, Entry, Event, Submission
from .permissions import require_editor
from .storage import delete_file, write_upload


class Conflict(Exception):
    pass


def event(dictionary, user, action, entry=None, detail=''):
    Event.objects.create(dictionary=dictionary, actor=user, action=action, entry=entry, detail=detail[:400])


def digest_request(request):
    digest = hashlib.sha256()
    fields = [(key, request.POST.getlist(key)) for key in sorted(request.POST) if key not in {'csrfmiddlewaretoken', 'submission_id'}]
    digest.update(json.dumps(fields, ensure_ascii=False).encode())
    for key in sorted(request.FILES):
        for upload in request.FILES.getlist(key):
            digest.update(key.encode())
            for chunk in upload.chunks():
                digest.update(chunk)
            upload.seek(0)
    return digest.hexdigest()


def submit_once(request, dictionary, scope, callback):
    """The receipt and all database writes commit together. Rollbacks remove new files."""
    try:
        token = uuid.UUID(request.POST.get('submission_id', ''))
    except (ValueError, AttributeError):
        raise Conflict('The submission identifier is missing. Reload the form and try again.')
    digest = digest_request(request)

    def replay():
        receipt = Submission.objects.get(token=token)
        if (receipt.user_id, receipt.dictionary_id, receipt.scope, receipt.digest) != (request.user.pk, dictionary.pk, scope, digest):
            raise Conflict('This saved submission has changed. Open a fresh form to submit different content.')
        return receipt.result_url

    if Submission.objects.filter(token=token).exists():
        return replay()
    created_paths = []
    try:
        with transaction.atomic():
            receipt = Submission.objects.create(token=token, user=request.user, dictionary=dictionary, scope=scope, digest=digest)
            result = callback(created_paths)
            receipt.result_url = result
            receipt.save(update_fields=['result_url'])
        return result
    except IntegrityError:
        for path in created_paths:
            delete_file(path)
        if Submission.objects.filter(token=token).exists():
            return replay()
        raise
    except Exception:
        for path in created_paths:
            delete_file(path)
        raise


@transaction.atomic
def accept(contribution, user):
    entry = Entry.objects.select_for_update().select_related('dictionary').get(pk=contribution.entry_id)
    require_editor(user, entry.dictionary)
    contribution = Contribution.objects.select_for_update().get(pk=contribution.pk)
    if contribution.status == 'accepted':
        return
    if contribution.status != 'pending' or contribution.kind == 'note':
        raise Conflict('This contribution is no longer awaiting review.')
    if contribution.kind == 'text':
        if contribution.base_version != entry.text_version:
            raise Conflict('The accepted wording changed after this proposal was made. Open “Edit words” to propose a combined revision.')
        entry.word, entry.meaning, entry.category = contribution.word, contribution.meaning, contribution.category
        entry.text_version += 1
        entry.current_text = contribution
    elif contribution.kind == 'image' and not entry.selected_image_id:
        entry.selected_image = contribution
    entry.save()
    contribution.status = 'accepted'
    contribution.save(update_fields=['status'])
    if contribution.request_id:
        req = contribution.request
        if not req.withdrawn and not req.completed_with_id:
            req.completed_with = contribution
            req.save(update_fields=['completed_with'])
    event(entry.dictionary, user, 'accept', entry, f'Contribution {contribution.pk}')


def add_contributions(entry, user, data, created_paths, *, publish=False, response_to=None):
    made = []
    if data.get('edit_text') or any(data.get(k) for k in ['word', 'meaning', 'category']):
        if response_to:
            raise Conflict('Use the response form for the requested media; edit wording separately.')
        made.append(Contribution.objects.create(entry=entry, author=user, kind='text', word=data.get('word', ''), meaning=data.get('meaning', ''), category=data.get('category', ''), base_version=data.get('base_version') or 0))
    for key, kind in [('photo', 'image'), ('audio', 'audio')]:
        if data.get('prepared_' + key):
            if response_to and kind != response_to.kind:
                raise Conflict('Please supply the kind of media requested by your partner.')
            media = write_upload(data['prepared_' + key], entry.dictionary_id, created_paths)
            made.append(Contribution.objects.create(entry=entry, author=user, kind=kind, label=data.get('label', ''), request=response_to, **media))
    for contribution in made:
        event(entry.dictionary, user, 'contribute', entry, f'{contribution.kind} {contribution.pk}; media permission confirmed' if contribution.file_path else f'{contribution.kind} {contribution.pk}')
        if publish:
            accept(contribution, user)
    return made


def entry_url(entry):
    return reverse('community_dictionary:entry', args=[entry.dictionary_id, entry.pk])
