"""Shared picture-description allowance and local-only cost previews."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.utils import timezone

from .models import PictureCapture
from . import photo_ai
from .services import Conflict

SALT = 'community-picture-description-limit-v1'
QUOTE_SECONDS = 600
ESTIMATE_VERSION = 'capture-budget-1'
# This is the existing short-description estimate, not a spending guarantee.
INPUT_TOKENS = 12000
OUTPUT_TOKENS = 2600
AUDIO_ALLOWANCE_USD = Decimal('.08')


def ceiling():
    return max(0, int(getattr(settings, 'COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT', 1000)))


def effective_limit(dictionary):
    return min(dictionary.capture_daily_limit, ceiling())


def recent():
    # Retain failed/discarded attempts in the allowance. Receipts prevent retries
    # of the same submission from creating a second PictureCapture.
    return PictureCapture.objects.filter(created_at__gte=timezone.now()-timedelta(hours=24))


def usage(dictionary, user=None):
    used = recent().filter(dictionary=dictionary).count()
    result = {'limit': effective_limit(dictionary), 'used': used,
              'remaining': max(0, effective_limit(dictionary)-used), 'ceiling': ceiling()}
    if user is not None:
        result['account_used'] = recent().filter(user=user).count()
        result['account_remaining'] = max(0, ceiling()-result['account_used'])
    return result


def enforce(dictionary, user):
    """Caller holds the dictionary and user locks across check and creation."""
    counts = usage(dictionary, user)
    if counts['used'] >= counts['limit']:
        raise Conflict('This dictionary has used its picture-description allowance for the last 24 hours. '
            'The owner can change it under Settings → Picture-description allowance, or wait for earlier requests to leave the 24-hour window.')
    if counts['account_used'] >= counts['ceiling']:
        raise Conflict('Your account has reached the server limit for picture descriptions across all dictionaries in the last 24 hours. '
            'Wait for earlier requests to leave the window or contact the administrator.')


def unit_estimate(prices):
    return ((Decimal(INPUT_TOKENS)*Decimal(str(prices['input'])) +
             Decimal(OUTPUT_TOKENS)*Decimal(str(prices['output']))) / 1_000_000 + AUDIO_ALLOWANCE_USD)


def quote_values(dictionary, user, limit):
    if not 1 <= limit <= ceiling():
        raise Conflict('The server allowance changed. Preview the cost again.')
    model, prices = photo_ai.pricing_configuration()
    rates = {k: str(prices[k]) for k in ('input', 'output')}
    return {'dictionary': dictionary.pk, 'user': user.pk, 'owner': dictionary.owner_id,
            'base_limit': dictionary.capture_daily_limit, 'limit': limit,
            'capture_revision': dictionary.capture_revision, 'ceiling': ceiling(),
            'model': model, 'prices': rates, 'estimate_version': ESTIMATE_VERSION,
            'per_request': str(unit_estimate(rates))}


def preview(dictionary, user, limit):
    values = quote_values(dictionary, user, limit)
    return {**values, 'daily_estimate': Decimal(values['per_request'])*limit,
            'token': signing.dumps(values, salt=SALT)}


def approved_limit(token, dictionary, user):
    try:
        values = signing.loads(token, salt=SALT, max_age=QUOTE_SECONDS)
        if not isinstance(values, dict) or type(values.get('limit')) is not int:
            raise ValueError
        fresh = quote_values(dictionary, user, values['limit'])
        # A repeated confirmation is harmless, but cannot undo a later different
        # setting. Other ownership, pricing, policy and user checks still apply.
        if dictionary.capture_daily_limit == values['limit']:
            fresh['base_limit'] = values.get('base_limit')
        if values != fresh:
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError, KeyError):
        raise Conflict('This cost preview expired or the settings or prices changed. Preview the cost again.')
    return values['limit']
