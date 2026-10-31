"""Per-item forecast guards and once-only refunds. Call under porting.locks().

Unknown provider totals and a single response exceeding its forecast are possible:
the approved allowance caps the C-LARA charge, not the provider's invoice.
"""
from decimal import Decimal
from django.core import signing
from django.db import transaction
from projects.billing import apply_credit_delta
from projects.models import CreditAccount, CreditLedgerEntry
from .models import PortRun, PortItem
from .services import Conflict
from . import port_costs

ZERO = Decimal('0')
SALT = 'community-port-budget-v1'


def enabled(run):
    return run.options.get('budget_version') == 1


def speech_forecast(clip):
    if clip.run.port.is_audio_batch:
        from .carrier import estimate
        return estimate(clip.text.word, clip.run.port.language, allowance=True)
    return port_costs.speech(clip.text.word, clip.run.port.language, clip.run.prices,
        sentence=clip.text.kind != 'form' and clip.entry.entry_type == 'sentence') * Decimal('1.5')


def claim(item, key, amount):
    """Claim before a paid operation; concurrent clips share an item budget."""
    if not enabled(item.run):
        return True
    run = PortRun.objects.select_for_update().get(pk=item.run_id)
    claims = run.options.setdefault('budget_claims', {})
    if key in claims:
        return False  # delivery/claim must never repeat a paid operation
    item.refresh_from_db()
    committed = sum((Decimal(v['amount']) for v in claims.values() if v['item']==item.pk), ZERO)
    available = item.allowance_usd - item.translation_cost - item.audio_cost - committed
    if item.budget_closed or amount > available:
        run.options.setdefault('budget_waiters', {})[key] = {'item':item.pk, 'amount':str(amount)}
        run.save(update_fields=['options'])
        return False
    claims[key] = {'item':item.pk, 'amount':str(amount)}
    run.options.setdefault('budget_waiters', {}).pop(key, None)
    run.save(update_fields=['options'])
    return True


def release_claim(run_id, key):
    run = PortRun.objects.select_for_update().get(pk=run_id)
    if not enabled(run):
        return
    run.options.setdefault('budget_claims', {}).pop(key, None)
    run.options.setdefault('budget_waiters', {}).pop(key, None)
    run.save(update_fields=['options'])


def charge(item):
    from .porting import money
    return min(money(item.translation_cost+item.audio_cost), item.allowance_usd)


def release_finished(run):
    """Return each finished item's unused allowance while other items wait."""
    if not enabled(run) or not run.approved_at:
        return
    from .porting import TERMINAL
    run.refresh_from_db()
    active = {'waiting','queued','running','budget'}
    for item in run.items.filter(budget_closed=False):
        if item.status not in TERMINAL or (run.stage=='vocabulary' and item.status in {'ready','unclear'}):
            continue
        if item.speech.filter(status__in=active).exists():
            continue
        refund = item.allowance_usd-charge(item)
        if run.payer == 'credits' and refund:
            apply_credit_delta(user=run.port.user, amount_usd=refund, entry_type=CreditLedgerEntry.ENTRY_USAGE,
                description='Language port: finished item unused credit returned',
                metadata={'port_run':str(run.pk),'kind':'partial_refund','item':item.pk})
            run.released_usd += refund
        item.budget_closed=True
        item.save(update_fields=['budget_closed'])
    run.save(update_fields=['released_usd'])


def offer(run):
    """Read-only signed offer for paused work, including pending clips on its item."""
    if not enabled(run) or run.status!='running' or run.settled:
        return None
    paused = set(run.items.filter(status='budget').values_list('pk',flat=True))
    paused.update(run.speech.filter(status='budget').values_list('item_id',flat=True))
    if not paused:
        return None
    from .porting import money
    amounts = {}
    for item in run.items.filter(pk__in=paused, budget_closed=False):
        needed = sum((Decimal(v['amount']) for v in run.options.get('budget_waiters',{}).values()
                      if v['item']==item.pk),ZERO)
        clips = item.speech.filter(status__in=['waiting','queued','budget','running']).select_related('text','entry','run__port')
        if clips:
            needed = max(needed, sum((speech_forecast(c) for c in clips), ZERO))
        amounts[str(item.pk)] = str(money(max(Decimal('.01'),
            item.translation_cost+item.audio_cost+needed*Decimal('1.5')-item.allowance_usd)))
    total = sum((Decimal(v) for v in amounts.values()),ZERO)
    if not amounts:
        return None
    payload={'run':str(run.pk),'user':run.port.user_id,'ceiling':str(run.allowance_usd),'items':amounts}
    return {'amount':total,'token':signing.dumps(payload,salt=SALT)}


@transaction.atomic
def approve_more(user, run_id, token):
    from . import porting, port_tasks
    porting.locks()
    run=PortRun.objects.select_for_update(of=('self',)).select_related('port__user','port__source','port__destination').get(pk=run_id,port__user=user)
    try:
        payload=signing.loads(token,salt=SALT,max_age=3600)
    except signing.BadSignature:
        raise Conflict('This allowance approval expired. Reload the progress page.')
    if payload.get('run')!=str(run.pk) or payload.get('user')!=user.pk:
        raise Conflict('This allowance belongs to another job.')
    # Retries of a signed approval must never debit again, even after settlement.
    if token in run.options.get('budget_approvals',[]):
        return run
    porting.authority(run.port)
    current=offer(run)
    if not current or porting.payer_now(user)!=run.payer:
        raise Conflict('The job or payment account changed. Reload the progress page.')
    fresh=signing.loads(current['token'],salt=SALT)
    if payload!=fresh:
        raise Conflict('The remaining work changed. Reload to check the new allowance.')
    amount=current['amount']
    if run.payer=='credits':
        account,_=CreditAccount.objects.select_for_update().get_or_create(user=user)
        if account.balance_usd<amount:
            raise Conflict('There is not enough available credit for this additional allowance.')
        apply_credit_delta(user=user,amount_usd=-amount,entry_type=CreditLedgerEntry.ENTRY_USAGE,
            description='Language port: approved additional allowance',
            metadata={'port_run':str(run.pk),'kind':'topup'})
        run.reserved_usd+=amount
    for pk,value in payload['items'].items():
        item=run.items.get(pk=pk)
        item.allowance_usd+=Decimal(value)
        if item.status=='budget':
            item.status='waiting';item.message=''
        item.save(update_fields=['allowance_usd','status','message'])
        item.speech.filter(status='budget').update(status='waiting',report={})
    run.allowance_usd+=amount
    run.options.setdefault('budget_approvals',[]).append(token)
    run.options['budget_waiters']={}
    run.save(update_fields=['allowance_usd','reserved_usd','options'])
    transaction.on_commit(lambda:port_tasks.dispatch(str(run.pk)))
    return run
