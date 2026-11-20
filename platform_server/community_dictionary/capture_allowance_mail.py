"""One owner notice per dictionary per day; no content or recordings in email."""
import logging
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Dictionary, Event
from .permissions import dictionaries_for, is_owner

log = logging.getLogger(__name__)
ACTION = 'capture_allowance_notice'


def enqueue(event_id):
    try:
        from django_q.tasks import async_task
        async_task('community_dictionary.capture_allowance_mail.deliver', event_id,
            q_options={'task_name': f'capture-allowance-{event_id}', 'ack_failure': True})
    except Exception:
        Event.objects.filter(pk=event_id).update(detail='Owner notification could not be queued.')
        log.warning('Allowance notification %s could not be queued', event_id)


def notify_owner(dictionary, user):
    if is_owner(user, dictionary):
        return
    with transaction.atomic():
        current = Dictionary.objects.select_for_update().select_related('owner').get(pk=dictionary.pk)
        from .capture_limits import usage
        if (current.archived or not current.owner.is_active or not current.owner.email
                or not dictionaries_for(user).filter(pk=current.pk).exists()
                or usage(current)['remaining'] > 0
                or Event.objects.filter(dictionary=current, action=ACTION,
                    created_at__gte=timezone.now()-timedelta(hours=24)).exists()):
            return
        notice = Event.objects.create(dictionary=current, actor=user, action=ACTION,
            detail='Owner notification queued; no learner content included.')
        transaction.on_commit(lambda: enqueue(notice.pk))


def deliver(event_id):
    # Claim before sending so duplicate queue delivery cannot send a second email.
    with transaction.atomic():
        notice = Event.objects.select_for_update().select_related('dictionary__owner').get(pk=event_id, action=ACTION)
        if not notice.detail.startswith('Owner notification queued'):
            return False
        notice.detail = 'Owner notification claimed.'
        notice.save(update_fields=['detail'])
    try:
        dictionary = notice.dictionary
        from .capture_limits import usage
        if usage(dictionary)['remaining'] > 0:
            Event.objects.filter(pk=event_id).update(detail='Owner notification no longer needed; allowance is available.')
            return False
        if dictionary.archived or not dictionary.owner.is_active or timezone.now()-notice.created_at > timedelta(hours=24):
            raise ValueError('expired')
        origin = settings.PUBLIC_BASE_URL.rstrip('/')
        URLValidator(schemes=['https', 'http'])(origin)
        parts = urlsplit(origin)
        if parts.username or parts.password or parts.path or parts.query or parts.fragment:
            raise ValueError('origin')
        if parts.scheme != 'https' and parts.hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ValueError('origin')
        validate_email(dictionary.owner.email)
        link = origin + reverse('community_dictionary:capture-limit', args=[dictionary.pk])
        body = (f'A member could not continue picture creation or language practice in “{dictionary.name}” '
            'because the dictionary’s shared daily allowance was used up.\n\n'
            f'You can review the cost and increase the allowance here:\n{link}\n\n'
            'You can also leave the allowance as it is; earlier attempts leave the rolling 24-hour window over time. '
            'No allowance has been changed and no AI request was started by this notice. '
            'At most one such notification is sent for this dictionary in 24 hours.')
        if send_mail('Community Dictionaries: daily allowance used up', body,
                settings.DEFAULT_FROM_EMAIL, [dictionary.owner.email], fail_silently=False) != 1:
            raise ValueError('delivery')
    except Exception:
        Event.objects.filter(pk=event_id).update(detail='Owner notification could not be sent; no automatic retry.')
        log.warning('Allowance notification %s could not be sent', event_id)
        return False
    Event.objects.filter(pk=event_id).update(detail='Owner notification sent.')
    return True
