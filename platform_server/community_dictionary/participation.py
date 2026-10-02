"""Dictionary-wide departure and return, with private retention and provenance."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from .collections import controller, withdraw, rebuild
from .models import Contribution, Dictionary, Entry, Event, ImageWordLink, Membership, Participation, Request, WithdrawalHold
from .permissions import dictionaries_for, entitled_dictionaries, membership_allows
from .services import Conflict, event
from .text import FIELDS, version


def owned(user):
    return Contribution.objects.filter(Q(controlled_by=user) | Q(controlled_by__isnull=True, author=user)).exclude(status='removed')


def content_for(user, dictionary):
    return owned(user).filter(Q(entry__dictionary=dictionary) |
        Q(entry__dictionary__personal=True, withdrawn_from__dictionary=dictionary))


def state_for(user, dictionary):
    return Participation.objects.filter(user=user, dictionary=dictionary).first() or Participation(user=user, dictionary=dictionary)


def successors(dictionary, user):
    withdrawn = Participation.objects.filter(dictionary=dictionary, withdrawn=True).values('user_id')
    return get_user_model().objects.filter(is_active=True, membership__dictionary=dictionary,
        membership__accepted=True, membership__status='active').exclude(pk=user.pk).exclude(pk__in=withdrawn).distinct().order_by('username')


def controls(user, dictionary):
    state = state_for(user, dictionary)
    return {'dictionary': dictionary, 'state': state,
        'can_browse': dictionaries_for(user).filter(pk=dictionary.pk).exists(),
        'can_restore': membership_allows(user, dictionary) and (not dictionary.archived or dictionary.owner_id == user.pk)}


def _start(user, dictionary_id, expected_revision, desired):
    # Shared with withdrawal's lock order; metadata and all affected dictionaries
    # commit together. No network/provider calls occur inside these operations.
    list(Dictionary.objects.select_for_update().order_by('pk').values_list('pk', flat=True))
    try:
        dictionary = entitled_dictionaries(user).get(pk=dictionary_id)
    except Dictionary.DoesNotExist:
        raise Http404
    state, _ = Participation.objects.select_for_update().get_or_create(user=user, dictionary=dictionary)
    try:
        revision = int(expected_revision)
        if revision < 0:
            raise ValueError
    except (ValueError, TypeError):
        raise Conflict('Reload this dictionary before changing your participation.')
    if state.withdrawn == desired and revision == state.revision - 1:
        return dictionary, state, True  # Immediate duplicate POST, not a new cycle.
    if revision != state.revision or state.withdrawn == desired:
        raise Conflict('Your participation changed. Reload this dictionary before continuing.')
    return dictionary, state, False


def _finish(state, withdrawn):
    state.withdrawn = withdrawn
    state.revision += 1
    state.updated_at = timezone.now()
    state.save(update_fields=['withdrawn', 'revision', 'updated_at'])
    dictionary = state.dictionary
    dictionary.membership_revision += 1
    dictionary.save(update_fields=['membership_revision'])


@transaction.atomic
def withdraw_all(user, dictionary_id, expected_revision, successor_id=None):
    dictionary, state, replay = _start(user, dictionary_id, expected_revision, True)
    if replay:
        return 0
    if dictionary.owner_id == user.pk:
        candidates = successors(dictionary, user)
        if candidates.exists():
            successor = candidates.filter(pk=successor_id).first() if str(successor_id or '').isdigit() else None
            if successor is None:
                raise Conflict('Choose an active member to become the new owner.')
            Membership.objects.update_or_create(dictionary=dictionary, user=user,
                defaults={'accepted': True, 'status': 'active', 'role': 'member'})
            dictionary.owner = successor
            dictionary.save(update_fields=['owner'])
            event(dictionary, user, 'transfer_ownership', detail=f'New owner: {successor.pk}')
        else:
            if successor_id:
                raise Conflict('That member cannot take ownership. Reload before withdrawing.')
            dictionary.archived = True
            dictionary.save(update_fields=['archived'])
            event(dictionary, user, 'archive_dictionary', detail='Owner withdrew; no active successor')
    ids = list(content_for(user, dictionary).values_list('pk', flat=True))
    count = withdraw(user, ids, participation=state) if ids else 0
    _finish(state, True)
    event(dictionary, user, 'withdraw_all', detail=f'{count} contributions retained privately')
    return count


def _restore_available(ids, actor):
    """Move retained records back, never manufacture new copies or ownership."""
    parts = list(Contribution.objects.select_for_update(of=('self',)).filter(pk__in=ids,
        entry__dictionary__personal=True, withdrawn_from__isnull=False,
        withdrawal_holds__isnull=True).select_related('entry__dictionary', 'withdrawn_from__dictionary'))
    # Some dependents belong to another custodian who also withdrew. Their own
    # participation is independently authoritative, even without a matching hold.
    blocked = set(Participation.objects.filter(withdrawn=True).values_list('dictionary_id', 'user_id'))
    parts = [p for p in parts if (p.withdrawn_from.dictionary_id, controller(p)) not in blocked]
    eligible = {p.pk for p in parts}
    # Never expose a descendant while any ancestor remains private. Fixed point
    # also handles descendants several revisions away and overlapping departures.
    while True:
        before = set(eligible)
        for part in parts:
            if part.pk not in eligible:
                continue
            ancestors = [part.shared_from, part.previous_revision]
            if any(a and a.entry.dictionary.personal and a.pk not in eligible for a in ancestors):
                eligible.remove(part.pk)
        if eligible == before:
            break
    parts = [p for p in parts if p.pk in eligible]
    affected = {p.entry_id for p in parts} | {p.withdrawn_from_id for p in parts}
    entry_map = {e.pk: e for e in Entry.objects.select_for_update().select_related('dictionary').filter(pk__in=affected)}
    # Latest current revisions win only where no intervening edit occurred.
    parts.sort(key=lambda p: (p.created_at, p.pk))
    for part in parts:
        target = entry_map[part.withdrawn_from_id]
        retained = part.provenance.get('retention', {})
        status = retained.get('status', part.provenance.get('status_before_withdrawal', 'pending'))
        if status not in {'accepted', 'pending', 'rejected', 'superseded'}:
            status = 'pending'
        if part.provenance.get('withdrawal_mode') == 'moderator':
            status = 'pending'
        part.entry = target
        part.status = status
        request_id = retained.get('request_id')
        part.request_id = request_id if Request.objects.filter(pk=request_id, entry=target).exists() else None
        part.provenance = {**part.provenance, 'returned_at': timezone.now().isoformat(), 'returned_by': actor.pk}
        part.save()
        if part.text_field and status == 'accepted' and retained.get('current'):
            pointer, counter = FIELDS[part.text_field]
            if getattr(target, counter) == retained.get('after_version'):
                setattr(target, part.text_field, part.text_value)
                setattr(target, pointer, part)
                setattr(target, counter, getattr(target, counter) + 1)
                target.save()
        if part.kind == 'image' and status == 'accepted' and retained.get('selected_image') and not target.selected_image_id:
            target.selected_image = part
            target.save(update_fields=['selected_image'])
        if part.kind == 'note' and part.label == 'Partner request' and part.request_id:
            Request.objects.filter(pk=part.request_id, note='').update(note=part.body)
            changed = Event.objects.filter(entry=target, action__in=['withdraw_request', 'reopen_request'],
                detail=f'Request {part.request_id}', created_at__gt=part.withdrawn_at).exists()
            if not changed and retained.get('request_was_withdrawn') is not None:
                Request.objects.filter(pk=part.request_id).update(withdrawn=retained['request_was_withdrawn'])
        event(target.dictionary, actor, 'restore_contribution', target, f'Contribution {part.pk}; {status}')
    for entry in entry_map.values():
        rebuild(entry)
    for part in parts:
        if part.status == 'accepted':
            Request.objects.filter(pk__in=part.provenance.get('retention', {}).get('completed_requests', []),
                completed_with__isnull=True, withdrawn=False).update(completed_with=part)
        if part.kind == 'image' and part.status == 'accepted':
            for link in part.provenance.get('retention', {}).get('links', []):
                if Entry.objects.filter(pk=link['word_entry_id'], dictionary_id=part.entry.dictionary_id,
                        archived=False).exclude(word='').exists():
                    ImageWordLink.objects.get_or_create(image=part, word_entry_id=link['word_entry_id'],
                        defaults={'created_by_id': link['created_by_id']})
    return len(parts)


@transaction.atomic
def restore_all(user, dictionary_id, expected_revision):
    dictionary, state, replay = _start(user, dictionary_id, expected_revision, False)
    # A suspension is independent of voluntary departure, including stale retries.
    if not membership_allows(user, dictionary):
        raise Conflict('Your membership is inactive. Ask the dictionary owner to reactivate it before restoring. Your saved content remains available.')
    if dictionary.archived and dictionary.owner_id != user.pk:
        raise Conflict('The dictionary is archived. Its owner must reopen it before you can rejoin. Your saved content remains available.')
    if replay:
        return 0, 0
    if dictionary.archived:
        dictionary.archived = False
        dictionary.save(update_fields=['archived'])
    ids = set(state.holds.values_list('contribution_id', flat=True))
    state.holds.all().delete()
    _finish(state, False)
    # Include content held by a different departure whose source is now back.
    # The full dependency check prevents premature release.
    ids.update(content_for(user, dictionary).filter(entry__dictionary__personal=True).values_list('pk', flat=True))
    restored = _restore_available(ids, user)
    remaining = content_for(user, dictionary).filter(entry__dictionary__personal=True).count()
    event(dictionary, user, 'restore_all', detail=f'{restored} contributions returned; {remaining} retained privately')
    return restored, remaining
