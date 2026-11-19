"""Display existing accounting records; never initiate or charge AI work."""
from decimal import Decimal, InvalidOperation
from django.utils.translation import gettext as _


def number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def summary(study):
    info = study.result.get('practice', {})
    rows = []
    if info.get('mode') == 'voice':
        rows.append({'stage': 'recognition', 'label': _('Speech recognition'),
            'cost': number(study.usage.get('practice_transcription', {}).get('cost_usd'))})
    rows.append({'stage': 'review', 'label': _('AI image review and language feedback'),
        'cost': number(study.usage.get('practice_feedback', {}).get('cost_usd'))})
    if info.get('confirmed') or 'practice_feedback_confirmed' in study.usage:
        # A learner revision starts a new attempt: its only review is billed
        # under the confirmed key, not both keys.
        if info.get('parent_attempt'):
            rows.pop()
        rows.append({'stage': 'confirmation', 'label': _('AI review after confirmation'),
            'cost': number(study.usage.get('practice_feedback_confirmed', {}).get('cost_usd'))})
    # An edited transcript reuses earlier recognition; that earlier attempt's
    # cost is not charged or counted again in this attempt.
    if info.get('parent_attempt') and info.get('mode') == 'voice':
        rows = [r for r in rows if r['stage'] != 'recognition']
    for clip in study.speech.filter(kind='feedback').order_by('pk'):
        report = clip.report or {}
        amounts = [number(report.get(k)) for k in ['guidance_cost_usd', 'speech_cost_usd'] if k in report]
        known = sum((x for x in amounts if x is not None), Decimal('0')) if amounts else None
        rows.append({'stage': 'speech', 'label': _('Spoken version generation'), 'cost': known,
            'incomplete': bool(report.get('uncertain_cost')) or clip.status in {'waiting', 'running'} or
                any(x is None for x in amounts)})
    total = sum((r['cost'] for r in rows if r['cost'] is not None), Decimal('0'))
    complete = all(r['cost'] is not None and not r.get('incomplete') for r in rows)
    return {'items': rows, 'known_total': total, 'complete': complete,
            'has_known': any(r['cost'] is not None for r in rows), 'personal': study.personal_key}
