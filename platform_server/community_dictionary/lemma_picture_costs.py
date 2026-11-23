"""Durable per-attempt costs and batch membership in existing image receipts."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import uuid

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Length
from django.utils import timezone

from .models import ImageStudy

KEY = 'lemma_picture'


def money(value):
    value = Decimal(value).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)
    return (format(value, '.6f').rstrip('0').rstrip('.') if 0 < value < Decimal('.01')
            else format(value, '.2f'))


def metadata(row, *, batch='', unit_estimate='0'):
    return {'version': 1, 'attempt': row.pk, 'revision': row.revision, 'entry': row.entry_id,
        'batch': str(batch), 'batch_created': timezone.now().isoformat(),
        'unit_estimate': str(unit_estimate), 'started': False, 'finished': False,
        'status': 'waiting', 'planning_started': False, 'planning_cost': None,
        'image_started': False, 'image_cost': None, 'error_code': ''}


def create_study(row, *, batch='', unit_estimate='0'):
    from . import image_generation as images
    return ImageStudy.objects.create(dictionary=row.entry.dictionary, entry=row.entry, user=row.requested_by,
        kind='entry', expires_at=timezone.now()+timedelta(days=1), subject=row.entry.word,
        model=row.quote['model'], quality=images.QUALITY, personal_key=row.quote['personal'],
        style_description=row.quote['style_description'], source_style_id=row.quote['style'],
        style_baseline_id=row.quote['style'], policy_revision=row.quote['policy'],
        membership_revision=row.quote['membership'], participation_revision=row.quote['participation'],
        usage={KEY: metadata(row, batch=batch, unit_estimate=unit_estimate)})


@transaction.atomic
def track(study, **changes):
    """Merge stage observations without overwriting returned image-token usage."""
    receipt = ImageStudy.objects.select_for_update().get(pk=study.pk)
    meta = receipt.usage.get(KEY)
    if meta is not None:
        receipt.usage = {**receipt.usage, KEY: {**meta, **changes}}
        receipt.save(update_fields=['usage'])
    return receipt


def cancel_unstarted(study):
    if study and KEY in study.usage and not study.usage[KEY].get('started'):
        track(study, status='cancelled', finished=True)
        ImageStudy.objects.filter(pk=study.pk).update(status='discarded')


def supersede(study):
    if study and KEY in study.usage and not study.usage[KEY].get('finished'):
        track(study, status='cancelled', finished=True)
        ImageStudy.objects.filter(pk=study.pk).update(status='discarded')


def cancel_revision(attempt, revision):
    for study in ImageStudy.objects.filter(usage__lemma_picture__attempt=attempt,
            usage__lemma_picture__revision=revision, usage__lemma_picture__started=False):
        cancel_unstarted(study)


def summaries(studies):
    """Sum before rounding. Missing provider data never becomes a zero-cost claim."""
    from projects.models import AIUsageCharge
    from .capture import charge_request_type
    studies = list(studies)
    legacy = [s for s in studies if KEY not in s.usage]
    charge_ids = {charge_request_type(s, 'lemma_picture_plan'): (s.pk,s.user_id) for s in legacy}
    planning = {}
    for charge in AIUsageCharge.objects.filter(request_type__in=charge_ids,provider='openai',operation='community_capture').only('user_id','request_type','cost_usd'):
        pk,user_id=charge_ids[charge.request_type]
        if user_id==charge.user_id:
            planning[pk]=planning.get(pk,Decimal('0'))+charge.cost_usd
    amount, unknown, pending, skipped = Decimal('0'), 0, 0, 0
    counts = {}
    for s in studies:
        meta = s.usage.get(KEY)
        missing = False
        if meta is not None:
            status = meta['status']
            pending += not meta.get('finished', False)
            skipped += meta.get('error_code') in {'daily_limit', 'credit'}
            for stage in ['planning', 'image']:
                if meta.get(stage+'_started'):
                    cost = meta.get(stage+'_cost')
                    if cost is None:
                        missing = True
                    else:
                        amount += Decimal(cost)
        else:
            status = s.status
            # Old personal-key planning requests did not retain their cost.
            # A missing old receipt is explicitly incomplete, never guessed free.
            if s.pk in planning:
                amount += planning[s.pk]
            else:
                missing = True
            if s.accounted:
                if s.cost_usd is None:
                    missing = True
                else:
                    amount += s.cost_usd
            elif s.prompt_length or s.status != 'saved':
                missing = True
            pending += s.status == 'processing'
        unknown += missing
        counts[status] = counts.get(status, 0)+1
    return {'amount': money(amount), 'exact_amount': str(amount), 'unknown': unknown,
        'pending': pending, 'skipped': skipped, 'total': len(studies), 'counts': counts}


def word_studies(dictionary):
    return ImageStudy.objects.filter(dictionary=dictionary).filter(
        Q(entry__entry_type='word') | Q(usage__has_key=KEY)).annotate(
        prompt_length=Length('prompt')).defer('prompt', 'subject', 'style_description')


def cumulative(dictionary):
    return summaries(word_studies(dictionary))


def batch_summary(dictionary, user, batch_id=None):
    query = word_studies(dictionary).filter(user=user, usage__has_key=KEY).exclude(
        usage__lemma_picture__batch='')
    if batch_id:
        try:
            batch_id = str(uuid.UUID(str(batch_id)))
        except ValueError:
            return None
    else:
        latest = query.order_by('-usage__lemma_picture__batch_created').first()
        if not latest:
            return None
        batch_id = latest.usage[KEY]['batch']
    rows = list(query.filter(usage__lemma_picture__batch=batch_id).order_by('created_at'))
    if not rows:
        return None
    result = summaries(rows)
    return {**result, 'id': batch_id,
        'estimate': money(sum((Decimal(s.usage[KEY]['unit_estimate']) for s in rows), Decimal('0'))),
        'created': rows[0].usage[KEY]['batch_created'],
        'complete': result['pending'] == 0, 'finished': len(rows)-result['pending']}
