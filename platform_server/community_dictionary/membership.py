"""Persistent membership and optional two-person decisions."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from .models import Dictionary, Membership, MembershipDecision, Participation
from .permissions import get_dictionary, is_coordinator
from .services import Conflict, event


def coordinators(dictionary):
    ids = list(Membership.objects.filter(dictionary=dictionary, accepted=True, status='active', role='coordinator').values_list('user_id', flat=True))
    withdrawn = Participation.objects.filter(dictionary=dictionary, withdrawn=True).values('user_id')
    return get_user_model().objects.filter(pk__in=[dictionary.owner_id, *ids], is_active=True).exclude(pk__in=withdrawn)


def validate(dictionary, action, member, value):
    if dictionary.personal:
        raise Conflict('Personal collections have no other members.')
    if action not in {'deactivate', 'reactivate', 'role', 'policy'}:
        raise Conflict('Unknown membership change.')
    if action != 'policy' and (not member or member.dictionary_id != dictionary.pk):
        raise Conflict('Choose a member of this dictionary.')
    if member and member.user_id == dictionary.owner_id:
        raise Conflict('The owner can transfer ownership when withdrawing; membership controls cannot suspend the owner.')
    if action == 'deactivate' and member.status == 'inactive':
        raise Conflict('This member is already inactive.')
    if action == 'reactivate' and member.status != 'inactive':
        raise Conflict('This member is not inactive.')
    if action == 'role' and value not in dict(Membership.ROLES):
        raise Conflict('Choose a valid role.')
    if action == 'policy' and value not in {'owner', 'coordinators'}:
        raise Conflict('Choose a valid membership policy.')
    if action == 'policy' and value == 'coordinators' and coordinators(dictionary).count() < 2:
        raise Conflict('Appoint a coordinator who has joined before enabling two-person decisions.')
    loses_coordinator = member and member.status == 'active' and member.role == 'coordinator' and (action == 'deactivate' or (action == 'role' and value != 'coordinator'))
    if dictionary.membership_policy == 'coordinators' and loses_coordinator and coordinators(dictionary).count() <= 2:
        raise Conflict('Appoint another coordinator first, so two-person decisions remain possible.')


def apply(dictionary, decision, actor):
    member = decision.member
    if decision.action == 'policy':
        dictionary.membership_policy = decision.value
    elif decision.action == 'role':
        member.role = decision.value
        member.save(update_fields=['role'])
    elif decision.action == 'deactivate':
        member.status = 'inactive'
        member.save(update_fields=['status'])
    elif decision.action == 'reactivate':
        member.status = 'active' if member.accepted else 'invited'
        member.save(update_fields=['status'])
    dictionary.membership_revision += 1
    dictionary.save(update_fields=['membership_policy', 'membership_revision'])
    decision.status, decision.approved_by, decision.decided_at = 'applied', actor, timezone.now()
    decision.save(update_fields=['status', 'approved_by', 'decided_at'])
    event(dictionary, actor, 'membership_' + decision.action, detail=f'Decision {decision.pk}; member {member.user_id if member else "policy"}; {decision.value}')


@transaction.atomic
def propose(user, dictionary, action, member=None, value=''):
    dictionary = Dictionary.objects.select_for_update().get(pk=dictionary.pk)
    get_dictionary(user, dictionary.pk)
    if not is_coordinator(user, dictionary):
        raise Http404
    if dictionary.membership_policy == 'owner' and dictionary.owner_id != user.pk:
        raise Http404
    if member:
        member = Membership.objects.select_for_update().get(pk=member.pk, dictionary=dictionary)
    validate(dictionary, action, member, value)
    decision = MembershipDecision.objects.create(dictionary=dictionary, proposed_by=user, action=action,
        member=member, value=value, base_revision=dictionary.membership_revision)
    recovery = (dictionary.membership_policy == 'coordinators' and dictionary.owner_id == user.pk
                and action == 'role' and value == 'coordinator' and member.accepted
                and member.status == 'active' and not Participation.objects.filter(dictionary=dictionary, user=member.user, withdrawn=True).exists()
                and coordinators(dictionary).count() < 2)
    if recovery:
        apply(dictionary, decision, user)
        event(dictionary, user, 'membership_recovery', detail='Owner appointed a second coordinator; two-person policy retained')
    elif dictionary.membership_policy == 'coordinators':
        event(dictionary, user, 'membership_proposed', detail=f'Decision {decision.pk}: {action}')
    else:
        apply(dictionary, decision, user)
    return decision


@transaction.atomic
def decide(user, dictionary, decision_id, *, cancel=False):
    dictionary = Dictionary.objects.select_for_update().get(pk=dictionary.pk)
    get_dictionary(user, dictionary.pk)
    if not is_coordinator(user, dictionary):
        raise Http404
    decision = MembershipDecision.objects.select_for_update(of=('self',)).select_related('member', 'proposed_by').get(pk=decision_id, dictionary=dictionary)
    if decision.status != 'pending':
        raise Conflict('This decision is no longer pending.')
    if cancel:
        decision.status, decision.decided_at = 'cancelled', timezone.now()
        decision.save(update_fields=['status', 'decided_at'])
        event(dictionary, user, 'membership_cancelled', detail=f'Decision {decision.pk}')
        return decision
    if decision.proposed_by_id == user.pk:
        raise Conflict('A different coordinator must approve this change.')
    if decision.base_revision != dictionary.membership_revision or not is_coordinator(decision.proposed_by, dictionary):
        raise Conflict('Membership changed after this proposal. Cancel it and make a new proposal.')
    validate(dictionary, decision.action, decision.member, decision.value)
    apply(dictionary, decision, user)
    return decision
