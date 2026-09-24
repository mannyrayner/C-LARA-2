from django.db.models import Q
from django.http import Http404

from .models import Dictionary, Membership


def dictionaries_for(user):
    return Dictionary.objects.filter(Q(owner=user) | Q(memberships__user=user, memberships__accepted=True)).distinct()


def get_dictionary(user, pk):
    try:
        return dictionaries_for(user).get(pk=pk)
    except Dictionary.DoesNotExist:
        raise Http404


def is_editor(user, dictionary):
    return dictionary.owner_id == user.pk or Membership.objects.filter(dictionary=dictionary, user=user, accepted=True, role='editor').exists()


def require_editor(user, dictionary):
    if not is_editor(user, dictionary):
        raise Http404


def require_owner(user, dictionary):
    if dictionary.owner_id != user.pk:
        raise Http404
