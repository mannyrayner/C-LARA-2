"""Quotes, source snapshots, reviewed copies, and credit settlement for language ports.

Every content mutation locks dictionaries in primary-key order, like withdrawal.
Network calls live in port_tasks and never run under these locks.
"""
from datetime import timedelta
from decimal import Decimal, ROUND_UP
import hashlib
import json

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from projects.billing import apply_credit_delta, credits_enabled, get_user_balance_usd
from projects.models import AIUsageCharge, CreditAccount, CreditLedgerEntry
from . import photo_ai, tts, port_categories, port_ai
from .collections import content_digest, controller
from .lexicon import outdated_tts, pictures_for_word
from .models import (Contribution, ContributionDependency, Dictionary, Entry, LanguagePort,
                     PortEntryLink, PortItem, PortRun, ImageWordLink)
from .permissions import require_owner
from .services import Conflict, accept, event
from .storage import delete_file, path_for
from .text import FIELDS

ZERO = Decimal('0')
FOUR = Decimal('.0001')
TERMINAL = {'ready','unclear','failed','saved','discarded'}


def money(value):
    return Decimal(value).quantize(FOUR, rounding=ROUND_UP)


def locks():
    # SQLite ignores SELECT FOR UPDATE. Acquire its writer lock before reading,
    # avoiding simultaneous read-to-write upgrades in laptop background workers.
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            cursor.execute('UPDATE community_dictionary_dictionary SET membership_revision = membership_revision '
                           'WHERE id = (SELECT MIN(id) FROM community_dictionary_dictionary)')
    list(Dictionary.objects.select_for_update(of=('self',)).order_by('pk').values_list('pk', flat=True))


def same_language(a, b):
    return (tts.language_code(a) or a.strip().casefold()) == (tts.language_code(b) or b.strip().casefold())


def authority(port):
    if not port.user.is_active:
        raise Http404
    require_owner(port.user, port.source)
    if port.destination_id:
        require_owner(port.user, port.destination)
        if (port.destination.language, port.destination.explanation_language) != (port.language, port.explanation_language):
            raise Conflict('The destination languages changed. Use a new language version.')
    if not port.source.photo_ai_enabled:
        raise Conflict('Enable Learn from a photo in the source dictionary settings before language porting.')


def snapshot(entry):
    fields = {}
    parts = []
    for field, (pointer, _) in FIELDS.items():
        part = getattr(entry, pointer)
        if part and part.entry_id == entry.pk and part.status == 'accepted' and part.text_field == field:
            fields[field] = part.pk
            parts.append(part)
    pictures = list(pictures_for_word(entry, entry.dictionary).filter(entry__archived=False).order_by('pk'))
    audio = [c for c in entry.contributions.filter(kind='audio', status='accepted').exclude(file_path='').order_by('pk')
             if not outdated_tts(c, entry, entry.dictionary)]
    parts += pictures + audio
    ids = sorted({p.pk for p in parts})
    selected = entry.selected_image_id if entry.selected_image_id in [p.pk for p in pictures] else (pictures[0].pk if pictures else None)
    signature = {'fields':fields, 'parts':[(p.pk,content_digest(p)) for p in parts],
                 'selected':selected, 'archived':entry.archived,
                 'languages':[entry.dictionary.language,entry.dictionary.explanation_language]}
    return {'fields':fields, 'images':[p.pk for p in pictures], 'audio':[p.pk for p in audio],
            'image':selected, 'ids':ids,
            'digest':hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()}


def input_data(item):
    parts = {c.pk:c for c in Contribution.objects.filter(pk__in=item.snapshot['ids'])}
    field = lambda name: getattr(parts.get(item.snapshot['fields'].get(name)), name, '')
    run, port = item.run, item.run.port
    return {'source_language':run.source_language,
            'source_explanation_language':run.source_explanation_language,
            'target_language':port.language, 'explanation_language':port.explanation_language,
            **{name:field(name) for name in FIELDS}, **port_categories.inputs(item)}


def current_item(item):
    """Recheck both sides before a call, before previewing, and before saving."""
    run, port = item.run, item.run.port
    authority(port)
    if item.invalidated:
        raise Conflict('This preview was cancelled or its source was withdrawn.')
    if (port.source.language, port.source.explanation_language) != (run.source_language,run.source_explanation_language):
        raise Conflict('The source languages changed. Prepare a fresh estimate.')
    entry = Entry.objects.select_related('dictionary','current_text','current_meaning','current_category').get(pk=item.source_entry_id)
    if entry.archived or snapshot(entry) != item.snapshot:
        raise Conflict('The source entry changed. Prepare a fresh estimate for this entry.')
    port_categories.check(item)
    link = PortEntryLink.objects.filter(port=port, source=entry).select_related('destination__dictionary').first()
    actual = snapshot(link.destination)['digest'] if link else ''
    if actual != item.destination_digest:
        raise Conflict('The destination was edited. Your changes have been kept.')
    return entry, link


def estimate_entry(entry, prices, audio, extra_bytes=0):
    # Deliberately rough: image tokenization and target length vary. The separate
    # allowance covers a larger prompt/output and up to a minute of speech.
    size = sum(len(getattr(entry,f).encode('utf-8')) for f in FIELDS) + extra_bytes
    estimate = ((Decimal(2200 + size // 3) * prices['input'] + Decimal(500) * prices['output']) / 1_000_000)
    allowance = ((Decimal(10000 + size * 2) * prices['input'] + Decimal(1400) * prices['output']) / 1_000_000)
    if audio:
        estimate += tts.guidance_estimate(prices) + tts.estimate_cost(entry.word + 'x'*1200, max(3, len(entry.word) / 10))
        allowance += tts.guidance_estimate(prices, allowance=True) + 2*tts.estimate_cost('x'*12000, 60)
    return money(estimate), money(max(allowance, estimate * 2, Decimal('.01')))


@transaction.atomic
def quote(user, source, data, token, port=None):
    locks()
    previous = PortRun.objects.filter(pk=token, port__user=user, port__source=source).first()
    if previous:
        if data and any(getattr(previous.port,k) != v for k,v in data.items()):
            raise Conflict('This estimate form changed. Reload before requesting a different version.')
        if port and previous.port_id != port.pk:
            raise Conflict('This estimate belongs to a different language version.')
        return previous
    require_owner(user, source)
    if not port:
        if same_language(source.language,data['language']) and same_language(source.explanation_language,data['explanation_language']):
            raise Conflict('Choose a different target language or commenting language.')
        port = LanguagePort.objects.create(source=source, user=user, **data)
    elif port.user_id != user.pk or port.source_id != source.pk:
        raise Http404
    authority(port)
    if port.runs.filter(status='running').exists() or PortItem.objects.filter(run__port=port,status__in=['ready','unclear']).exists():
        raise Conflict('Finish reviewing or discard the previous results before updating this version.')
    model, key, personal, prices = photo_ai.configuration(user)
    if not same_language(source.language,port.language) and not tts.language_code(port.language):
        raise Conflict('Choose a target language with configured TTS for this first version.')
    port.runs.filter(status='estimate').update(status='cancelled')
    run = PortRun.objects.create(id=token, port=port, model=model,
        source_language=source.language, source_explanation_language=source.explanation_language,
        prices={**{k:str(v) for k,v in prices.items()}, 'speech_recipe':tts.INSTRUCTIONS_VERSION},
        payer='personal' if personal else ('credits' if credits_enabled() else 'server'),
        expires_at=timezone.now()+timedelta(hours=1))
    links = {l.source_id:l for l in port.entry_links.select_related('destination__dictionary')}
    entries = list(source.entries.filter(archived=False).exclude(word='').select_related(
        'dictionary','current_text','current_meaning','current_category').order_by('pk'))
    run.category_plan = port_categories.build_plan(entries, port)
    for entry in entries:
        snap = snapshot(entry)
        if not snap['fields'].get('word'):
            run.skipped += 1
            continue
        link = links.get(entry.pk)
        dest_digest = snapshot(link.destination)['digest'] if link else ''
        if link and (link.manually_edited or dest_digest != link.destination_digest):
            run.protected += 1
            continue
        group = run.category_plan.get(port_categories.key(entry.category))
        if link and port_categories.digest(snap, group) == link.source_digest:
            run.skipped += 1
            continue
        context_ids = port_categories.context_ids(group) if group else []
        extra_bytes = sum(len(getattr(c,c.text_field).encode('utf-8')) for c in
            Contribution.objects.filter(pk__in=context_ids))
        estimate, allowance = estimate_entry(entry, prices, not same_language(source.language,port.language), extra_bytes)
        item = PortItem.objects.create(run=run,source_entry=entry,snapshot=snap,
            destination_digest=dest_digest,estimated_usd=estimate,allowance_usd=allowance)
        item.sources.set(snap['ids'] + context_ids + (port_categories.basis_ids(group) if group else []))
        run.estimated_usd += estimate
        run.allowance_usd += allowance
    run.save()
    return run


def payer_now(user):
    _, personal = photo_ai.api_credentials(user)
    return 'personal' if personal else ('credits' if credits_enabled() else 'server')


@transaction.atomic
def approve(user, run_id):
    locks()
    run = PortRun.objects.select_for_update(of=('self',)).select_related('port__source','port__destination','port__user').get(pk=run_id,port__user=user)
    authority(run.port)
    if run.status != 'estimate':
        return run  # retrying the same approval never sends again
    if run.expires_at <= timezone.now() or payer_now(user) != run.payer:
        raise Conflict('This estimate expired or the payment account changed. Prepare a new estimate.')
    model, _, _, prices = photo_ai.configuration(user)
    if model != run.model or {**{k:str(v) for k,v in prices.items()}, 'speech_recipe':tts.INSTRUCTIONS_VERSION} != run.prices:
        raise Conflict('The model or configured prices changed. Prepare a new estimate.')
    if not run.items.exists():
        raise Conflict('There are no new or changed entries to port.')
    for item in run.items.all():
        current_item(item)
    if run.payer == 'credits':
        account, _ = CreditAccount.objects.select_for_update(of=('self',)).get_or_create(user=user)
        if account.balance_usd < run.allowance_usd:
            raise Conflict(f'Your C-LARA balance is US${account.balance_usd}. This job needs a US${run.allowance_usd} reservation. Add credit before starting.')
        apply_credit_delta(user=user, amount_usd=-run.allowance_usd, entry_type=CreditLedgerEntry.ENTRY_USAGE,
            description='Language port: temporary credit reservation', metadata={'port_run':str(run.pk),'kind':'reservation'})
        run.reserved_usd = run.allowance_usd
    port = run.port
    if not port.destination_id:
        port.destination = Dictionary.objects.create(name=port.name,language=port.language,
            explanation_language=port.explanation_language,owner=user,photo_ai_enabled=port.source.photo_ai_enabled,
            tts_enabled=bool(tts.language_code(port.language)), image_generation_enabled=False)
        port.save(update_fields=['destination'])
        event(port.destination,user,'create_language_port',detail=f'Source dictionary {port.source_id}')
    run.status, run.approved_at = 'running', timezone.now()
    run.save()
    from .port_tasks import dispatch
    transaction.on_commit(lambda: dispatch(str(run.pk)))
    return run


def clear_preview(item, message='This preview is no longer available.'):
    path = item.file_path
    item.file_path, item.result, item.message, item.invalidated = '', {}, message, True
    item.needs_attention, item.attention_note, item.review_values = False, '', {}
    if item.status != 'running':
        item.status = 'discarded'
    item.save(update_fields=['file_path','result','status','message','invalidated',
                            'needs_attention','attention_note','review_values'])
    if path:
        transaction.on_commit(lambda path=path:delete_file(path))


def invalidate_sources(ids):
    """Withdrawal never leaves copies of source text/audio in a private job preview."""
    PortItem.objects.filter(sources__pk__in=ids).update(
        needs_attention=False, attention_note='', review_values={})
    runs = set()
    for item in PortItem.objects.filter(sources__pk__in=ids).exclude(status__in=['saved','discarded']).distinct():
        clear_preview(item, 'A source contribution was withdrawn. Prepare a fresh estimate after it returns.')
        runs.add(item.run_id)
    # Clear cached labels as well as per-entry previews, including completed runs.
    for run in PortRun.objects.filter(items__sources__pk__in=ids).distinct():
        changed = False
        for group in run.category_plan.values():
            if set(ids).intersection(port_categories.context_ids(group) + port_categories.basis_ids(group)):
                group['decision'], group['invalidated'] = None, True
                changed = True
        if changed:
            run.save(update_fields=['category_plan'])
    from .port_tasks import dispatch
    for run_id in runs:
        transaction.on_commit(lambda run_id=run_id:dispatch(str(run_id)))


def settle(run):
    if run.settled:
        return
    items = list(run.items.all())
    if any(item.status not in TERMINAL for item in items):
        return
    cost = sum((min(item.translation_cost+item.audio_cost,item.allowance_usd) if run.payer == 'credits'
                else item.translation_cost+item.audio_cost for item in items), ZERO)
    charge = min(money(cost), run.reserved_usd) if run.payer == 'credits' else money(cost)
    if run.payer == 'credits':
        refund = run.reserved_usd - charge
        if refund:
            apply_credit_delta(user=run.port.user,amount_usd=refund,entry_type=CreditLedgerEntry.ENTRY_USAGE,
                description='Language port: unused reservation returned',metadata={'port_run':str(run.pk),'kind':'refund'})
    run.charged_usd, run.settled = charge, True
    if run.status != 'cancelled':
        run.status = 'complete'
    run.completed_at = timezone.now()
    run.save()


def record_usage(item, *, audio=False):
    run = item.run
    cost = item.audio_cost if audio else item.translation_cost
    AIUsageCharge.objects.create(user=run.port.user, model=tts.MODEL if audio else run.model,
        operation='community_port_tts' if audio else 'community_port_text',
        request_type=f'port:{item.pk}:{"audio" if audio else "text"}',
        prompt_tokens=0 if audio else item.usage.get('input_tokens',0),
        completion_tokens=0 if audio else item.usage.get('output_tokens',0),
        total_tokens=0 if audio else sum(item.usage.values()), cost_usd=cost,
        status=AIUsageCharge.STATUS_CHARGED if run.payer == 'credits' else AIUsageCharge.STATUS_SKIPPED,
        notes=('Includes pronunciation guidance token cost and all completed speech attempts estimated from duration/input bytes. ' if audio else 'Returned token usage. ') +
              'Settlement is through the port reservation; individual rows are not debited again.')


@transaction.atomic
def cancel(user, run_id):
    locks()
    run = PortRun.objects.select_for_update(of=('self',)).select_related('port__user','port__source','port__destination').get(pk=run_id,port__user=user)
    # Account owner may stop spending even after source membership changes.
    run.status = 'cancelled'
    run.save(update_fields=['status'])
    for item in run.items.exclude(status__in=['saved','discarded']):
        clear_preview(item, 'Cancelled. No further requests will be sent.')
    settle(run)
    return run


def dependencies(part, sources):
    ContributionDependency.objects.bulk_create([ContributionDependency(source_id=pk,derived=part)
        for pk in set(sources) if pk != part.pk], ignore_conflicts=True)


def copy_component(source, entry, user, port):
    part = Contribution.objects.create(entry=entry,author=source.author,controlled_by_id=controller(source),
        kind=source.kind,text_field=source.text_field,word=source.word,meaning=source.meaning,category=source.category,
        label=source.label,body=source.body,file_path=source.file_path,mime_type=source.mime_type,file_size=source.file_size,
        shared_from=source,base_version=getattr(entry,FIELDS[source.text_field][1]) if source.text_field else 0,
        provenance={**source.provenance,'language_port':port.pk,'copied_from':source.pk})
    accept(part,user)
    entry.refresh_from_db()
    return part


@transaction.atomic
def save_item(user, item_id, values):
    locks()
    item = PortItem.objects.select_for_update(of=('self',)).select_related('run__port__user','run__port__source','run__port__destination').get(pk=item_id,run__port__user=user)
    if item.status == 'saved':
        return PortEntryLink.objects.get(port=item.run.port,source=item.source_entry).destination
    if item.status not in {'ready','unclear'}:
        raise Conflict('This result is no longer ready to save.')
    if not str(values.get('word','')).strip():
        raise Conflict('Enter a word or phrase before saving.')
    source_entry, link = current_item(item)
    port, run = item.run.port, item.run
    unedited_links = [l for l in port.entry_links.select_related('destination__dictionary')
                      if snapshot(l.destination)['digest'] == l.destination_digest]
    if run.status == 'cancelled':
        raise Conflict('This port was cancelled.')
    entry = link.destination if link else Entry.objects.create(dictionary=port.destination,created_by=user)
    entry.refresh_from_db()
    source_parts = {c.pk:c for c in Contribution.objects.filter(pk__in=item.snapshot['ids'])}
    change_target = not same_language(run.source_language,port.language)
    change_explanation = not same_language(run.source_explanation_language,port.explanation_language)
    _, group, _ = port_categories.group_for(item)
    input_ids = list(item.snapshot['fields'].values()) + ([item.snapshot['image']] if item.snapshot['image'] else [])
    if group:
        input_ids += port_categories.context_ids(group) + port_categories.basis_ids(group)
    for field,(pointer,counter) in FIELDS.items():
        original = source_parts.get(item.snapshot['fields'].get(field))
        changed_language = change_target if field == 'word' else (change_explanation if field == 'meaning' else True)
        text = values[field] if changed_language else getattr(original,field,'')
        # An unchanged category is still the original contributor's text.
        if field == 'category' and original and text == original.category:
            changed_language = False
        field_inputs = input_ids
        if text == getattr(entry,field) and getattr(entry,pointer+'_id'):
            if changed_language:
                dependencies(getattr(entry,pointer),field_inputs)
            continue
        if not text and not getattr(entry,field):
            continue
        if not changed_language and original:
            part = copy_component(original,entry,user,port)
        else:
            language_kind = ('target' if field == 'word' else 'commenting' if field == 'meaning'
                             else item.result.get('category_language','uncertain'))
            source_language = run.source_language if language_kind == 'target' else run.source_explanation_language if language_kind == 'commenting' else ''
            language = port.language if language_kind == 'target' else port.explanation_language if language_kind == 'commenting' else ''
            part = Contribution.objects.create(entry=entry,author=user,controlled_by=user,kind='text',text_field=field,
                previous_revision=getattr(entry,pointer),shared_from=original,base_version=getattr(entry,counter),
                provenance={'origin':'language-port','language_port':port.pk,'model':run.model,
                    'source_language':source_language,'language':language,'reviewed_by':user.pk, 'recipe': item.result.get('recipe','dictionary-port-1')}, **{field:text})
            dependencies(part,field_inputs)
            accept(part,user)
        entry.refresh_from_db()
    image_map = {}
    for pk in item.snapshot['images']:
        existing = entry.contributions.filter(kind='image',status='accepted',shared_from_id=pk).first()
        image_map[pk] = existing or copy_component(source_parts[pk],entry,user,port)
    if item.snapshot['image']:
        entry.selected_image = image_map[item.snapshot['image']]
        entry.save(update_fields=['selected_image'])
    if not change_target:
        for pk in item.snapshot['audio']:
            if not entry.contributions.filter(kind='audio',status='accepted',shared_from_id=pk).exists():
                copy_component(source_parts[pk],entry,user,port)
    elif (item.file_path and values['word'] == item.result['word'] and
          (not item.result.get('tts_synthesis', {}).get('english_homographs') or
           entry.meaning == item.result.get('meaning', ''))):
        # Replace earlier speech created by this port, retaining its audit trail.
        entry.contributions.filter(kind='audio', status='accepted',
            provenance__origin='synthetic', provenance__language_port=port.pk).update(status='superseded')
        # Move ownership of the preview path to the durable contribution. No copy.
        part = Contribution.objects.create(entry=entry,author=user,kind='audio',file_path=item.file_path,
            mime_type='audio/wav',file_size=path_for(item.file_path).stat().st_size,shared_from=entry.current_text,
            provenance={'origin':'synthetic','source_text':entry.word,'language':port.language,
                'voice':port.voice,'model':tts.MODEL,'language_port':port.pk,
                'instructions_version':item.result.get('tts_instructions_version',''),
                'synthesis':item.result.get('tts_synthesis',{})})
        if item.result.get('tts_synthesis', {}).get('english_homographs') and entry.current_meaning_id:
            part.provenance['source_meaning_id'] = entry.current_meaning_id
            part.save(update_fields=['provenance'])
            dependencies(part, [entry.current_meaning_id])
        dependencies(part,input_ids)
        accept(part,user)
        item.file_path = ''
    if item.file_path:
        old_path = item.file_path
        transaction.on_commit(lambda:delete_file(old_path))
        item.file_path = ''
    # Preserve extra picture/word associations, including shared pictures saved
    # in a different order. The explicit links also keep practice distractors safe.
    for source_id, copied in image_map.items():
        copies = Contribution.objects.filter(entry__dictionary=port.destination,
            kind='image',status='accepted',shared_from_id=source_id).exclude(pk=copied.pk)
        for other in copies:
            if other.entry_id != entry.pk:
                ImageWordLink.objects.get_or_create(image=copied,word_entry=other.entry,defaults={'created_by':user})
                ImageWordLink.objects.get_or_create(image=other,word_entry=entry,defaults={'created_by':user})
    entry.refresh_from_db()
    manual = bool(link and link.manually_edited) or any(values[field] != item.result[field]
        for field in FIELDS if (change_target if field == 'word' else (change_explanation if field == 'meaning' else True)))
    PortEntryLink.objects.update_or_create(port=port,source=source_entry,defaults={'destination':entry,'manually_edited':manual,
        'source_digest':(port_categories.digest(item.snapshot, port_categories.group_for(item)[1])
            if item.result.get('recipe') == port_ai.VERSION else item.snapshot['digest']),'destination_digest':snapshot(entry)['digest']})
    for other_link in unedited_links:
        if other_link.destination_id != entry.pk:
            other_link.destination.refresh_from_db()
            other_link.destination_digest = snapshot(other_link.destination)['digest']
            other_link.save(update_fields=['destination_digest'])
    item.status, item.result, item.review_values = 'saved', {}, {}
    item.needs_attention = bool(values.get('needs_attention', item.needs_attention))
    item.attention_note = values.get('attention_note', item.attention_note) if item.needs_attention else ''
    item.save(update_fields=['status','result','file_path','review_values','needs_attention','attention_note'])
    event(port.destination,user,'save_port_entry',entry,f'Source entry {source_entry.pk}')
    return entry
