"""Public metadata is a separate permission from public dictionary contents."""
from django.db.models import Q

from . import public_browsing as public
from .models import CommunityProfile, Dictionary, Membership, MembershipRequest, Participation


def dictionaries():
    return Dictionary.objects.filter(discoverable=True, hidden=False, archived=False, personal=False)


def contributors():
    return CommunityProfile.objects.filter(list_as_contributor=True, user__is_active=True).exclude(public_name='').order_by('public_name', 'pk')


def state(user, dictionary):
    if not user.is_authenticated:
        return 'anonymous'
    if Participation.objects.filter(dictionary=dictionary, user=user, withdrawn=True).exists():
        return 'withdrawn'
    if dictionary.owner_id == user.pk:
        return 'owner'
    member = Membership.objects.filter(dictionary=dictionary, user=user).first()
    if member:
        if member.status == 'inactive':
            return 'inactive'
        return 'member' if member.accepted and member.status == 'active' else 'invited'
    request = MembershipRequest.objects.filter(dictionary=dictionary, user=user).first()
    return request.status if request and request.status in {'pending', 'declined'} else 'available'


def row(dictionary, user):
    parts = public.entries(dictionary)
    owner = contributors().filter(user_id=dictionary.owner_id).first()
    return {'id': dictionary.pk, 'name': dictionary.name, 'language': dictionary.language,
            'explanation_language': dictionary.explanation_language,
            'entry_count': parts.filter(Q(public_image=True) | Q(public_audio=True) | ~Q(public_word='')).count(),
            'sentence_count': public.sentences(dictionary).count(), 'word_count': public.words(dictionary).count(),
            'public': dictionary.public_browsing_enabled, 'state': state(user, dictionary),
            'owner_name': owner.public_name if owner else '', 'owner_id': owner.user_id if owner else None}


def pending_for(user):
    if not user.is_authenticated:
        return MembershipRequest.objects.none()
    return MembershipRequest.objects.filter(status='pending', dictionary__owner=user,
        dictionary__personal=False, dictionary__archived=False)
