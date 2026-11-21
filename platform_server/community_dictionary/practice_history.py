"""Private picture rotation and activity summaries; no model calls or consent."""
from datetime import timedelta
from hashlib import sha256
import random

from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from . import learning
from .models import ContributionPreference, PictureCapture

KEY = '_picture_history'
MAX_PICTURES = 2000
RECENT = 5


def identity(path):
    # Copies of the same file are one picture. Store no private media paths.
    return sha256(path.encode()).hexdigest()[:32]


def initial(user, dictionary):
    state = {'version':1, 'step':0, 'new_since_review':0, 'seen':{}, 'recent':[]}
    paths = list(PictureCapture.objects.filter(user=user, dictionary=dictionary,
        input_mode='practice', source_image__isnull=False).exclude(source_image__file_path='')
        .order_by('-created_at', '-pk').values_list('source_image__file_path', flat=True)[:MAX_PICTURES])
    for path in reversed(paths):
        remember(state, identity(path))
    state['new_since_review'] = 0
    return state


def remember(state, key):
    # Refreshing the pinned URL, or clicking Try again, is not another exposure.
    if state['recent'] and state['recent'][-1] == key:
        return False
    previous = state['seen'].get(key)
    state['step'] += 1
    state['new_since_review'] = state['new_since_review'] + 1 if previous is None else 0
    state['seen'][key] = {'count':(previous or {}).get('count',0)+1, 'last':state['step']}
    state['recent'] = [k for k in state['recent'] if k != key][-RECENT+1:] + [key]
    if len(state['seen']) > MAX_PICTURES:
        oldest = min(state['seen'], key=lambda k: state['seen'][k]['last'])
        del state['seen'][oldest]
    return True


def choose(rows, state, skip=None):
    if not rows:
        return None
    # Avoid the current picture even in a small category; a single picture is
    # the unavoidable exception. Then avoid the recent five where possible.
    current = state['recent'][-1] if state['recent'] else None
    pool = [k for k in rows if k != skip] or list(rows)
    pool = [k for k in pool if k != current] or pool
    fresh_pool = [k for k in pool if k not in state['recent']]
    pool = fresh_pool or pool
    new = [k for k in pool if k not in state['seen']]
    reviews = [k for k in pool if k in state['seen']]
    if new and (state['new_since_review'] < 2 or not reviews):
        return rows[random.choice(new)]
    if reviews:
        key = min(reviews, key=lambda k:(state['seen'][k]['count'],state['seen'][k]['last']))
        return rows[key]
    return rows[random.choice(pool)]


@transaction.atomic
def select(request, dictionary, candidates, *, image=None, skip=None):
    rows = {}
    for candidate in candidates.order_by('pk'):
        rows.setdefault(identity(candidate.file_path), candidate)
    if not rows:
        return None
    default_mode = learning.mode(request, dictionary)
    row, _ = ContributionPreference.objects.select_for_update().get_or_create(
        user=request.user, dictionary=dictionary, defaults={'mode':default_mode})
    state = row.consent.get(KEY)
    if not isinstance(state, dict) or state.get('version') != 1:
        state = initial(request.user, dictionary)
    selected = image or choose(rows, state, identity(skip.file_path) if skip else None)
    remember(state, identity(selected.file_path))
    row.consent = {**row.consent, KEY:state}
    row.updated_at = timezone.now()
    row.save(update_fields=['consent','updated_at'])
    request._contribution_preferences = {}
    return selected


def overview(user, dictionary):
    """Activity, not a language proficiency score; cleared attempts are excluded."""
    now = timezone.now()
    attempts = PictureCapture.objects.filter(user=user, dictionary=dictionary,
        input_mode='practice', language=dictionary.language, created_at__gte=now-timedelta(days=30),
        expires_at__gt=now).exclude(status='discarded')
    completed = attempts.filter(status='feedback', result__practice__feedback__outcome='ready')
    counts = completed.aggregate(completed=Count('pk'),
        spoken=Count('pk', filter=Q(result__practice__mode='voice')))
    counts['active_days'] = attempts.annotate(day=TruncDate('created_at')).order_by().values('day').distinct().count()
    row = ContributionPreference.objects.filter(user=user, dictionary=dictionary).first()
    state = row.consent.get(KEY, {}) if row else {}
    counts['pictures'] = len(state.get('seen', {}))
    return counts
