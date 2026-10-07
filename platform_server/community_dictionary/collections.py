"""Contribution custody, withdrawal and explicit sharing.

Withdrawal moves records, not merely links. A former project member's access to
these operations is checked against custody, independently of project membership.
"""
import hashlib
import json

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import ContributionDependency, AudioStudy, Contribution, Dictionary, Entry, ImageWordLink, PhotoStudy, Request
from .services import Conflict, event
from .storage import delete_file
from .text import FIELDS, current, version


def controller(item):
    return item.controlled_by_id or item.author_id


COPY_FIELDS = ['kind', 'text_field', 'word', 'meaning', 'category', 'label', 'body',
               'file_path', 'mime_type', 'file_size']


def content_digest(item):
    """Content identity, excluding the bookkeeping added by withdrawal/sharing."""
    data = {field: getattr(item, field) for field in COPY_FIELDS}
    data.update(author=item.author_id, custodian=controller(item),
                media={key: item.provenance.get(key) for key in
                       ('origin', 'source_text', 'language', 'voice')})
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


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
        query = Contribution.objects.filter(Q(shared_from_id__in=frontier) | Q(previous_revision_id__in=frontier) | Q(pk__in=ContributionDependency.objects.filter(source_id__in=frontier).values('derived_id')))
        if dictionary_id:
            query = query.filter(entry__dictionary_id=dictionary_id)
        new = set(query.values_list('pk', flat=True)) - result
        result.update(new)
        frontier = new
    return result


def withdraw(user, ids, *, moderator_dictionary=None, participation=None):
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
        from .porting import invalidate_sources
        invalidate_sources(moving_ids)
        from .capture import discard
        from .models import PictureCapture
        affected = PictureCapture.objects.filter(Q(source_image_id__in=moving_ids) | Q(sources__pk__in=moving_ids) |
            Q(saved_entry__current_text_id__in=moving_ids)).values('pk')
        discard(PictureCapture.objects.filter(pk__in=affected).exclude(status='discarded'))
        if participation:
            from .models import WithdrawalHold
            WithdrawalHold.objects.bulk_create([WithdrawalHold(participation=participation, contribution_id=pk)
                for pk in moving_ids], ignore_conflicts=True)
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
            request_was_withdrawn = item.request.withdrawn if item.request_id else None
            if item.kind == 'note' and item.request_id and item.request.created_by_id == controller(item):
                Request.objects.filter(pk=item.request_id).update(note='', withdrawn=True)
            retention = {'status': item.status, 'request_id': item.request_id, 'request_was_withdrawn': request_was_withdrawn,
                'current': bool(item.text_field and getattr(old_entry, FIELDS[item.text_field][0] + '_id') == item.pk),
                'selected_image': old_entry.selected_image_id == item.pk,
                'completed_requests': list(Request.objects.filter(completed_with=item).values_list('pk', flat=True)),
                'links': list(ImageWordLink.objects.filter(image=item).values('word_entry_id', 'created_by_id', 'sentence_text_id'))}
            item.withdrawn_from = old_entry
            item.withdrawn_at = timezone.now()
            item.entry = destination
            item.request = None
            # Private retention is not community approval; provenance keeps the
            # review status that applied when sharing stopped.
            item.provenance = {**item.provenance, 'status_before_withdrawal': item.status,
                'withdrawn_by': user.pk, 'withdrawal_mode': 'moderator' if moderator_dictionary else 'custodian',
                'withdrawn_content_digest': content_digest(item), 'retention': retention}
            item.status = 'accepted'
            item.save()
            destinations.add(destination.pk)
            event(old_entry.dictionary, user, 'withdraw_contribution', old_entry, f'Contribution {item.pk}; retained privately')
        ImageWordLink.objects.filter(image_id__in=moving_ids).delete()
        Request.objects.filter(completed_with_id__in=moving_ids).update(completed_with=None)
        # Private AI previews can contain a second copy of withdrawn media/text.
        from .image_generation import discard_studies
        from .models import ImageStudy
        discard_studies(ImageStudy.objects.filter(source_style_id__in=moving_ids))
        for study in PhotoStudy.objects.select_for_update().filter(source_image_id__in=moved_media_ids).exclude(status='discarded'):
            path = study.file_path
            study.status, study.file_path, study.result = 'discarded', '', {}
            study.save(update_fields=['status', 'file_path', 'result'])
            if path:
                transaction.on_commit(lambda path=path: delete_file(path))
        for study in AudioStudy.objects.select_for_update().filter(
                Q(source_text_id__in=word_ids) | Q(source_meaning_id__in=moving_ids)).exclude(status='discarded'):
            path = study.file_path
            study.status, study.file_path, study.source_text = 'discarded', '', ''
            study.source_meaning, study.synthesis = '', {}
            study.save(update_fields=['status', 'file_path', 'source_text', 'source_meaning', 'synthesis'])
            if path:
                transaction.on_commit(lambda path=path: delete_file(path))
        for pk in original_entries | destinations:
            rebuild(Entry.objects.select_for_update().get(pk=pk))
        for item in moving:
            if item.text_field:
                source = Entry.objects.get(pk=item.withdrawn_from_id)
                item.provenance['retention']['after_version'] = version(source, item.text_field)
                item.save(update_fields=['provenance'])
        return len(moving)
