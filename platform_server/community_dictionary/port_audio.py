"""Recover missing recordings from accepted results without retranslating."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from . import porting, photo_ai, tts, port_costs, port_ai
from .models import Entry, PortRun, PortItem, PortSpeech, PortEntryLink, SentenceWord
from .lexicon import recordings
from .services import Conflict


def fingerprint(entry):
    return {'entry_type':entry.entry_type,'text':entry.current_text_id,
        'meaning':entry.current_meaning_id,'word':entry.word,'meaning_value':entry.meaning,
        'image':None,'ids':[pk for pk in [entry.current_text_id,entry.current_meaning_id] if pk]}


def current_item(item):
    porting.authority(item.run.port)
    entry=Entry.objects.select_related('dictionary','current_text','current_meaning').get(pk=item.source_entry_id)
    if (item.invalidated or entry.archived or entry.dictionary_id!=item.run.port.target_id or
        not entry.current_text or entry.current_text.status!='accepted' or
        entry.current_text.entry_id!=entry.pk or fingerprint(entry)!=item.snapshot or
        entry.current_meaning and (entry.current_meaning.status!='accepted' or entry.current_meaning.entry_id!=entry.pk)):
        raise Conflict('The accepted wording or access changed. Prepare a fresh audio estimate.')
    return entry


def candidates(original):
    porting.authority(original.port)
    target=original.port.target
    if not target or not target.tts_enabled or not tts.language_code(target.language):
        raise Conflict('Enable supported spoken audio in the destination first.')
    items=original.items.filter(status='saved',invalidated=False)
    if original.stage in {'audio','descriptions'}:
        ids=set(items.exclude(saved_entry=None).values_list('saved_entry_id',flat=True))
    elif original.stage=='vocabulary':
        sentences=Entry.objects.filter(pk__in=items.values('source_entry_id'))
        ids=set(SentenceWord.objects.filter(sentence_text_id__in=sentences.values('current_text_id')).values_list('word_entry_id',flat=True))
    else:
        ids=set(PortEntryLink.objects.filter(port=original.port,source_id__in=items.values('source_entry_id')).values_list('destination_id',flat=True))
    entries=target.entries.filter(pk__in=ids,archived=False,current_text__status='accepted').exclude(word='').select_related('dictionary','current_text','current_meaning')
    return [e for e in entries if e.current_text.entry_id==e.pk and not recordings(e,target)]


@transaction.atomic
def quote(user, original, token):
    porting.locks()
    if original.port.user_id!=user.pk:
        raise Conflict('Only the owner of this job can recover its audio.')
    porting.authority(original.port)
    previous=PortRun.objects.filter(pk=token,port=original.port,stage='audio').first()
    if previous:
        return previous
    if PortRun.objects.filter(pk=token).exists():
        raise Conflict('Reload this form before estimating.')
    if original.port.runs.filter(status='running').exists():
        raise Conflict('Finish or cancel the current processing job before starting audio recovery.')
    entries=candidates(original)
    if not entries:
        raise Conflict('No accepted entries from this job need audio. Save any remaining text first.')
    model,key,personal,prices=photo_ai.configuration(user)
    run=PortRun.objects.create(pk=token,port=original.port,stage='audio',model=model,
        source_language=original.port.language,source_explanation_language=original.port.explanation_language,
        prices={**{k:str(v) for k,v in prices.items()},'speech_recipe':tts.INSTRUCTIONS_VERSION,
                'sentence_speech_recipe':port_ai.speech_version({'entry_type':'sentence'})},
        options={'budget_version':1,'retry_source_run':str(original.pk)},
        payer='personal' if personal else 'credits' if porting.credits_enabled() else 'server',
        expires_at=timezone.now()+timedelta(hours=1))
    for entry in entries:
        estimate=port_costs.speech(entry.word,entry.dictionary.language,prices,sentence=entry.entry_type=='sentence')
        item=PortItem.objects.create(run=run,source_entry=entry,saved_entry=entry,snapshot=fingerprint(entry),
            estimated_usd=porting.money(estimate),allowance_usd=port_costs.allowance(estimate))
        item.sources.set(item.snapshot['ids'])
        run.estimated_usd+=item.estimated_usd;run.allowance_usd+=item.allowance_usd
    run.save()
    return run


def prepare(run):
    for item in run.items.all():
        item.run=run
        entry=current_item(item)
        item.status='saved';item.save(update_fields=['status'])
        if not recordings(entry,entry.dictionary):
            PortSpeech.objects.get_or_create(run=run,item=item,entry=entry,text=entry.current_text,
                defaults={'meaning':entry.current_meaning})
