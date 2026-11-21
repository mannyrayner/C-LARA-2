"""Shared picture-description allowance and local-only cost previews."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.urls import reverse
from django.utils.translation import gettext as _

from .models import PictureCapture
from . import photo_ai, vocabulary_policy
from .services import Conflict

SALT = 'community-picture-description-limit-v1'
QUOTE_SECONDS = 600
ESTIMATE_VERSION = 'capture-budget-vocabulary-3'
# More shared guidance and up to twelve items, each with lemma/form audio.
# This is a rough preview, not a spending guarantee.
INPUT_TOKENS = 16000
OUTPUT_TOKENS = vocabulary_policy.MAX_OUTPUT_TOKENS
AUDIO_ALLOWANCE_USD = Decimal('.30')
NEW_DICTIONARY_LIMIT = 50


class AllowanceExhausted(Conflict):
    def __init__(self, dictionary, scope='dictionary'):
        self.dictionary, self.scope = dictionary, scope
        super().__init__(_('Your daily allowance for picture creation and practice is used up.'))


def offer(request, dictionary, *, scope=None):
    """A local preview offer, never an allocation or a paid request."""
    from .permissions import is_owner
    counts = usage(dictionary, request.user)
    if scope is None:
        if counts['account_remaining'] == 0:
            scope = 'account'
        elif counts['remaining'] == 0:
            scope = 'dictionary'
        else:
            return None
    # A dictionary increase cannot bypass the account/server ceiling.
    if counts['account_remaining'] == 0 or counts['ceiling'] == 0:
        scope = 'account'
    proposed = min(counts['ceiling'], max(NEW_DICTIONARY_LIMIT,
        dictionary.capture_daily_limit + 25, counts['used'] + 25))
    can_increase = (scope == 'dictionary' and is_owner(request.user, dictionary)
        and proposed > counts['limit'] and proposed > counts['used'])
    request.capture_allowance_offer = {
        'scope': scope, 'used': counts['used'], 'limit': counts['limit'],
        'message': (_('Your daily allowance across dictionaries has been used up.') if scope == 'account'
            else _('This dictionary’s daily allowance for picture creation and practice has been used up.')),
        'proposed': proposed if can_increase else None,
        'extra': proposed - counts['limit'] if can_increase else None,
        'url': reverse('community_dictionary:capture-limit', args=[dictionary.pk]) if can_increase else '',
        'dictionary_url': reverse('community_dictionary:dictionary', args=[dictionary.pk]),
        'server_limit': scope == 'account' or counts['limit'] >= counts['ceiling'],
    }
    return request.capture_allowance_offer


def show_exhausted(request, error):
    if not isinstance(error, AllowanceExhausted):
        return False
    values = offer(request, error.dictionary, scope=error.scope)
    if values and not values['server_limit']:
        from .capture_allowance_mail import notify_owner
        notify_owner(error.dictionary, request.user)
    return True


def ceiling():
    return max(0, int(getattr(settings, 'COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT', 1000)))


def effective_limit(dictionary):
    return min(dictionary.capture_daily_limit, ceiling())


def recent():
    # Retain failed/discarded attempts in the allowance. Receipts prevent retries
    # of the same submission from creating a second PictureCapture.
    return PictureCapture.objects.filter(created_at__gte=timezone.now()-timedelta(hours=24)).exclude(
        input_mode='writing', usage__writing_request__isnull=True).exclude(
        input_mode='guided', usage__guided_request__isnull=True)


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
    if counts['account_used'] >= counts['ceiling']:
        raise AllowanceExhausted(dictionary, 'account')
    if counts['used'] >= counts['limit']:
        raise AllowanceExhausted(dictionary)


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
