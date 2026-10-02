from django.db.models import Q
from django.http import Http404

from .models import Contribution, Dictionary, Membership, Participation


def entitled_dictionaries(user):
    """Project affiliation, including inactive members' contribution rights."""
    owned = Contribution.objects.filter(Q(controlled_by=user) | Q(controlled_by__isnull=True, author=user))
    return Dictionary.objects.filter(personal=False).filter(
        Q(owner=user) | Q(memberships__user=user, memberships__accepted=True) |
        Q(participations__user=user) | Q(pk__in=owned.values('entry__dictionary_id')) |
        Q(pk__in=owned.values('withdrawn_from__dictionary_id'))).distinct()


def membership_allows(user, dictionary):
    return dictionary.owner_id == user.pk or Membership.objects.filter(
        dictionary=dictionary, user=user, accepted=True, status='active').exists()


def dictionaries_for(user):
    # Personal collections are read-only through the custodian's own-content view.
    # Even their owner cannot use the normal contribution or AI endpoints there.
    withdrawn = Participation.objects.filter(user=user, withdrawn=True).values('dictionary_id')
    return Dictionary.objects.filter(personal=False, archived=False).filter(
        Q(owner=user) | Q(memberships__user=user, memberships__accepted=True,
                         memberships__status='active')).exclude(pk__in=withdrawn).distinct()


def get_dictionary(user, pk):
    try:
        return dictionaries_for(user).get(pk=pk)
    except Dictionary.DoesNotExist:
        raise Http404


def is_editor(user, dictionary):
    return dictionaries_for(user).filter(pk=dictionary.pk).exists() and (
        dictionary.owner_id == user.pk or Membership.objects.filter(dictionary=dictionary,
        user=user, accepted=True, status='active', role__in=['editor', 'coordinator']).exists())


def is_coordinator(user, dictionary):
    return dictionaries_for(user).filter(pk=dictionary.pk).exists() and (
        dictionary.owner_id == user.pk or Membership.objects.filter(dictionary=dictionary,
        user=user, accepted=True, status='active', role='coordinator').exists())


def require_editor(user, dictionary):
    if not is_editor(user, dictionary):
        raise Http404


def require_owner(user, dictionary):
    get_dictionary(user, dictionary.pk)
    if dictionary.owner_id != user.pk:
        raise Http404
