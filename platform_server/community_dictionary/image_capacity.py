"""Payer-locked picture admission; no lock is held during provider I/O.

Reservations conservatively cover running picture estimates. They are not a
provider spending cap: returned usage still determines actual billing.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from projects.billing import credits_enabled, get_user_balance_usd
from .services import Conflict

KEY = 'picture_capacity'


class Busy(Conflict):
    pass


def limit():
    try:
        value = int(settings.COMMUNITY_DICTIONARY_IMAGE_CONCURRENCY)
        if 1 <= value <= 4:
            return value
    except (TypeError, ValueError, OverflowError):
        pass
    raise Conflict('Configure between one and four concurrent pictures per account.')


def active(user_id):
    from . import image_generation as images
    return images.started_studies().filter(user_id=user_id, status='processing',
        created_at__gte=timezone.now()-timedelta(seconds=images.TIMEOUT+120))


def reserve(user, amount, *, personal=False, group='', credit_error=None):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError('Picture admission requires the receipt transaction.')
    get_user_model().objects.select_for_update().get(pk=user.pk)
    running = list(active(user.pk))
    if len(running) >= limit():
        raise Busy(_('Your picture slots are in use. Wait for a picture to finish before starting another.'))
    held = Decimal('0')
    try:
        amount = Decimal(amount)
        for receipt in running:
            if not receipt.personal_key:
                # Legacy in-flight receipts did not store a reservation.
                value = receipt.usage.get(KEY, {}).get('reserved_usd',
                    settings.COMMUNITY_DICTIONARY_IMAGE_ALLOWANCE_USD)
                held += Decimal(value)
        if not amount.is_finite() or amount < 0 or not held.is_finite() or held < 0:
            raise InvalidOperation
    except (InvalidOperation, TypeError, ValueError):
        raise Conflict(_('The cost reservation for a running picture is unavailable. Wait for it to finish.'))
    if not personal and credits_enabled():
        balance = get_user_balance_usd(user)
        if balance < amount:
            raise Conflict(credit_error or _('Your balance is too low to generate this picture.'))
        if balance < amount+held:
            raise Busy(_('Available credit is reserved for running pictures. Wait for them to finish.'))
    return {'version': 1, 'reserved_usd': str(Decimal('0') if personal else amount), 'group': group}


def group_for(dictionary_id, usage):
    batch = usage.get('lemma_picture', {}).get('batch')
    return 'batch:'+batch if batch else 'dictionary:'+str(dictionary_id)


def next_word(user_id):
    """Prefer batches without an active call, then least recently served; FIFO within a batch.

    The choice is advisory. run still locks and claims the exact revision once.
    Existing receipt batch IDs also supply history across process restarts.
    """
    from . import image_generation as images
    from .models import LemmaImage
    if active(user_id).count() >= limit():
        return None
    waiting = list(LemmaImage.objects.filter(requested_by_id=user_id, status='waiting')
        .select_related('entry', 'study').order_by('pk'))
    if not waiting:
        return None
    groups = {}
    for row in waiting:
        group = group_for(row.entry.dictionary_id, row.study.usage if row.study_id else {})
        groups.setdefault(group, row)
    served = {}
    for receipt in images.started_studies().filter(user_id=user_id,
            created_at__gte=timezone.now()-timedelta(days=1)).order_by('-created_at'):
        served.setdefault(group_for(receipt.dictionary_id, receipt.usage), receipt.created_at)
    occupying = Counter(group_for(r.dictionary_id, r.usage) for r in active(user_id))
    oldest = datetime.min.replace(tzinfo=dt_timezone.utc)
    selected = min(groups, key=lambda g: (occupying[g], served.get(g, oldest), groups[g].pk))
    return groups[selected]


def wake(user_id):
    from . import lemma_images
    transaction.on_commit(lambda: lemma_images.queue_next(user_id))
