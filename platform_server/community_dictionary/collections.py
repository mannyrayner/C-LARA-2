"""Contribution custody, withdrawal and explicit sharing.

Withdrawal moves records, not merely links. A former project member's access to
these operations is checked against custody, independently of project membership.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import AudioStudy, Contribution, Dictionary, Entry, ImageWordLink, PhotoStudy, Request
from .permissions import get_dictionary, is_editor
from .services import Conflict, accept, event
from .storage import delete_file
from .text import FIELDS, current, version


def controller(item):
    return item.controlled_by_id or item.author_id


def personal_dictionary(user, source):
    if source.personal:
        return source
    collection, _ = Dictionary.objects.get_or_create(owner=user, personal=True, collection_source=source,
        defaults={'name': f'My collection · {source.name}'[:160], 'language': source.language,
                  'explanation_language': source.explanation_language, 'text_direction': source.text_direction,
                  'photo_ai_enabled': False, 'tts_enabled': False})
    return collection


def rebuild(entry):
    """Recalculate presentation after a move; never select a private contribution."""
    for field, (pointer, counter) in FIELDS.items():
        old_id = getattr(entry, pointer + '_id')
        part = None if entry.dictionary.personal else entry.contributions.filter(pk=old_id, kind='text', text_field=field, status='accepted').first()
        if part is None:
            part = entry.contributions.filter(kind='text', text_field=field, status='accepted').order_by('-created_at', '-pk').first()
        if old_id != (part.pk if part else None):
            setattr(entry, counter, getattr(entry, counter) + 1)
        setattr(entry, pointer, part)
        setattr(entry, field, getattr(part, field) if part else '')
    if not entry.contributions.filter(pk=entry.selected_image_id, kind='image', status='accepted').exists():
        entry.selected_image = entry.contributions.filter(kind='image', status='accepted').first()
    entry.save()


def dependent_ids(ids, *, dictionary_id=None):
    result = set(ids)
    frontier = set(ids)
    while frontier:
        query = Contribution.objects.filter(Q(shared_from_id__in=frontier) | Q(previous_revision_id__in=frontier))
        if dictionary_id:
            query = query.filter(entry__dictionary_id=dictionary_id)
        new = set(query.values_list('pk', flat=True)) - result
        result.update(new)
        frontier = new
    return result


def withdraw(user, ids, *, moderator_dictionary=None):
    """Move selected components and their shared descendants into custodians' collections.

    A contributor can revoke uses across dictionaries. A moderator can only
    stop sharing within the dictionary they manage.
    """
    with transaction.atomic():
        # All contribution mutations use this lock order. Stable dictionary locks
        # also protect export and membership changes against a withdrawal race.
        list(Dictionary.objects.select_for_update().order_by('pk').values_list('pk', flat=True))
        selected = list(Contribution.objects.select_for_update(of=('self',)).filter(pk__in=ids).select_related('entry__dictionary'))
        if not selected or len(selected) != len(set(ids)):
            raise Conflict('Select contributions that still exist.')
        if moderator_dictionary:
            from .permissions import require_editor
            require_editor(user, moderator_dictionary)
            if any(c.entry.dictionary_id != moderator_dictionary.pk for c in selected):
                raise Conflict('Choose contributions from this dictionary.')
        elif any(controller(c) != user.pk for c in selected):
            raise Conflict('You can withdraw only material entrusted to your account.')
        seeds = {c.pk for c in selected}
        # A text component includes its history: older versions must not restore
        # the withdrawn text to the project when the current revision moves.
        for item in selected:
            if item.kind == 'text' and item.text_field:
                seeds.update(Contribution.objects.filter(entry=item.entry, kind='text', text_field=item.text_field,
                    controlled_by_id=controller(item)).values_list('pk', flat=True))
        moving_ids = dependent_ids(seeds, dictionary_id=moderator_dictionary.pk if moderator_dictionary else None)
        moving = list(Contribution.objects.select_for_update(of=('self',)).filter(pk__in=moving_ids, entry__dictionary__personal=False).select_related('entry__dictionary', 'controlled_by', 'author'))
        if not moving:
            return 0
        original_entries = {c.entry_id for c in moving}
        destinations = set()
        moved_media_ids = [c.pk for c in moving if c.kind == 'image']
        word_ids = [c.pk for c in moving if c.kind == 'text' and c.text_field == 'word']
        for item in moving:
            old_entry = item.entry
            custodian = item.controlled_by or item.author
            collection = personal_dictionary(custodian, old_entry.dictionary)
            destination, _ = Entry.objects.get_or_create(dictionary=collection, collection_source=old_entry,
                defaults={'created_by': custodian})
            if item.kind == 'note' and item.request_id and item.request.created_by_id == controller(item):
                Request.objects.filter(pk=item.request_id).update(note='', withdrawn=True)
            item.withdrawn_from = old_entry
            item.withdrawn_at = timezone.now()
            item.entry = destination
            item.request = None
            # Private retention is not community approval; provenance keeps the
            # review status that applied when sharing stopped.
            item.provenance = {**item.provenance, 'status_before_withdrawal': item.status}
            item.status = 'accepted'
            item.save()
            destinations.add(destination.pk)
            event(old_entry.dictionary, user, 'withdraw_contribution', old_entry, f'Contribution {item.pk}; retained privately')
        ImageWordLink.objects.filter(image_id__in=moving_ids).delete()
        Request.objects.filter(completed_with_id__in=moving_ids).update(completed_with=None)
        # Private AI previews can contain a second copy of withdrawn media/text.
        for study in PhotoStudy.objects.select_for_update().filter(source_image_id__in=moved_media_ids).exclude(status='discarded'):
            path = study.file_path
            study.status, study.file_path, study.result = 'discarded', '', {}
            study.save(update_fields=['status', 'file_path', 'result'])
            if path:
                transaction.on_commit(lambda path=path: delete_file(path))
        for study in AudioStudy.objects.select_for_update().filter(source_text_id__in=word_ids).exclude(status='discarded'):
            path = study.file_path
            study.status, study.file_path, study.source_text = 'discarded', '', ''
            study.save(update_fields=['status', 'file_path', 'source_text'])
            if path:
                transaction.on_commit(lambda path=path: delete_file(path))
        for pk in original_entries | destinations:
            rebuild(Entry.objects.select_for_update().get(pk=pk))
        return len(moving)


def share(user, ids, target_dictionary, target_entry=None):
    """Explicit, reviewable sharing. Repeated posts are wrapped in submit_once."""
    get_dictionary(user, target_dictionary.pk)
    if target_dictionary.personal:
        raise Conflict('Choose a shared dictionary.')
    items = list(Contribution.objects.select_for_update(of=('self',)).filter(pk__in=ids, entry__dictionary__personal=True,
        entry__dictionary__owner=user).select_related('entry__dictionary'))
    if len(items) != len(set(ids)) or not items:
        raise Conflict('Select material from your private collection.')
    if any(controller(c) != user.pk for c in items):
        raise Conflict('Only the custodian can share this material.')
    if any(c.entry.dictionary.language != target_dictionary.language for c in items):
        raise Conflict('Choose a dictionary in the same language. Language translation is a separate future operation.')
    text_fields = [c.text_field for c in items if c.kind == 'text']
    if len(text_fields) != len(set(text_fields)):
        raise Conflict('Select only one version of each text component for an entry.')
    entry = target_entry or Entry.objects.create(dictionary=target_dictionary, created_by=user)
    if entry.dictionary_id != target_dictionary.pk or entry.archived:
        raise Conflict('Choose an available entry in this dictionary.')
    for item in items:
        queue, visited = [item], set()
        while queue:
            source = queue.pop()
            if source.pk in visited:
                continue
            visited.add(source.pk)
            if source.entry.dictionary.personal and controller(source) != user.pk:
                raise Conflict('A source contributor has withdrawn material this contribution depends on.')
            queue.extend(c for c in (source.shared_from, source.previous_revision) if c is not None)
        if item.kind == 'audio' and item.provenance.get('origin') == 'synthetic':
            selected_word = next((c.word for c in items if c.text_field == 'word'), entry.word)
            if item.provenance.get('source_text') != selected_word or item.provenance.get('language') != target_dictionary.language:
                raise Conflict('This synthetic recording does not match the destination wording.')
        data = {f: getattr(item, f) for f in ['kind', 'text_field', 'word', 'meaning', 'category', 'label', 'body', 'file_path', 'mime_type', 'file_size']}
        field = item.text_field
        if field and getattr(entry, field) == getattr(item, field):
            continue
        # Avoid replacing somebody else's contribution through a sharing shortcut.
        if field and getattr(entry, field):
            raise Conflict('The destination already has this text component. Use Edit words there to propose a revision.')
        clone = Contribution.objects.create(entry=entry, author=item.author, controlled_by_id=controller(item),
            shared_from=item, base_version=version(entry, field) if field else 0,
            provenance={**item.provenance, 'shared_by': user.pk, 'shared_at': timezone.now().isoformat()}, **data)
        if field:
            clone.previous_revision = current(entry, field)
            clone.save(update_fields=['previous_revision'])
        event(target_dictionary, user, 'share_contribution', entry, f'Contribution {clone.pk}')
        # All reshared content follows the destination's normal review path.
        # Even editors explicitly accept it from the entry, avoiding mixed-field
        # ordering and making the scope of publication visible.
    return entry
