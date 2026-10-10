"""Bounded, resumable analysis and shared-word speech for vocabulary stage."""
from decimal import Decimal
import logging
from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from . import porting, port_tasks, port_vocabulary as vocabulary, port_vocabulary_ai, tts
from .models import PortItem, PortRun, PortSpeech, Contribution
from .services import Conflict, accept
from .storage import path_for, write_upload, delete_file

log=logging.getLogger(__name__)


def send_speech(pk):
    try:
        from django_q.tasks import async_task
        async_task('community_dictionary.port_vocabulary_tasks.speak',pk,
                   q_options={'task_name':f'community-vocabulary-audio-{pk}','timeout':180,'ack_failure':True})
    except Exception:
        PortRun.objects.filter(speech__pk=pk).update(queue_error=True)
        log.warning('Could not enqueue vocabulary audio %s',pk)


def dispatch(run):
    active=run.items.filter(status__in=['queued','running']).count()+run.speech.filter(status__in=['queued','running']).count()
    limit=max(1,min(8,getattr(settings,'COMMUNITY_DICTIONARY_PORT_WINDOW',4)))
    slots=max(0,limit-active)
    # A short speech job need not wait behind the entire analysis backlog.
    for clip in run.speech.filter(status='waiting').order_by('pk')[:slots]:
        clip.status='queued';clip.save(update_fields=['status']);slots-=1
        transaction.on_commit(lambda pk=clip.pk:send_speech(pk))
    for item in run.items.filter(status='waiting').order_by('pk')[:slots]:
        item.status='queued';item.save(update_fields=['status'])
        transaction.on_commit(lambda pk=item.pk:port_tasks.send(pk))
    porting.settle(run)


def credentials(item):
    if item.run.prices.get('vocabulary_recipe')!=vocabulary.VERSION:
        raise Conflict('Vocabulary processing changed. Prepare a new estimate.')
    return port_tasks.credentials(item)


def process_item(item_id):
    with transaction.atomic():
        porting.locks();item=port_tasks.fetch(item_id,True)
        if item.status!='queued':return
        try:
            key=credentials(item);data=vocabulary.input_data(item)
            photo=path_for(item.sources.get(pk=item.snapshot['image']).file_path).read_bytes() if item.snapshot['image'] else None
        except (Conflict,Http404,OSError,ValueError):
            porting.clear_preview(item,'The sentence, permissions or vocabulary changed. Prepare a new estimate.')
            transaction.on_commit(lambda:port_tasks.dispatch(str(item.run_id)))
            return
        item.status='running';item.phase='vocabulary';item.started_at=timezone.now();item.save()
    result=None;usage={}
    try:
        response=port_vocabulary_ai.analyse(data,photo,model=item.run.model,api_key=key)
        if getattr(response,'usage',None):
            usage={k:max(0,int(getattr(response.usage,k,0) or 0)) for k in ['input_tokens','output_tokens']}
        result=port_vocabulary_ai.parse(response,data)
    except Exception as exc:
        log.warning('Vocabulary item %s failed (%s)',item_id,type(exc).__name__)
    with transaction.atomic():
        porting.locks();item=port_tasks.fetch(item_id,True)
        if item.status!='running':return
        item.usage=usage;item.uncertain_cost=not bool(usage)
        if usage:
            item.translation_cost=(Decimal(usage['input_tokens'])*Decimal(item.run.prices['input'])+
                Decimal(usage['output_tokens'])*Decimal(item.run.prices['output']))/1_000_000
            porting.record_usage(item)
        try:credentials(item)
        except (Conflict,Http404):
            item.status='discarded';item.result={};item.message='The accepted input or permission changed; this result was discarded.'
        else:
            item.status='ready' if result is not None else 'failed'
            item.result={**result,'recipe':vocabulary.VERSION} if result is not None else {}
            if result is None:item.message='No usable vocabulary was returned. A new estimate is required to try again.'
        item.finished_at=timezone.now();item.save()
    port_tasks.dispatch(str(item.run_id))


def speech_row(pk,lock=False):
    query=PortSpeech.objects.select_for_update(of=('self',)) if lock else PortSpeech.objects
    return query.select_related('run__port__user','run__port__source','run__port__destination',
        'entry__current_text','entry__current_meaning','text','meaning','item').get(pk=pk)


def speech_credentials(clip):
    clip.item.run=clip.run
    key=credentials(clip.item)
    if (clip.entry.archived or clip.entry.dictionary_id!=clip.run.port.target_id or
            clip.entry.current_text_id!=clip.text_id or clip.entry.current_meaning_id!=clip.meaning_id or
            clip.text.status!='accepted' or clip.meaning and clip.meaning.status!='accepted'):
        raise Conflict('This word changed. Generate audio from its current entry instead.')
    return key


def speak(pk):
    with transaction.atomic():
        porting.locks();clip=speech_row(pk,True)
        if clip.status!='queued':return
        try:key=speech_credentials(clip)
        except (Conflict,Http404):
            clip.status='discarded';clip.save(update_fields=['status'])
            transaction.on_commit(lambda:port_tasks.dispatch(str(clip.run_id)));return
        from .lexicon import recordings
        if recordings(clip.entry,clip.run.port.target):
            clip.status='ready';clip.save(update_fields=['status'])
            transaction.on_commit(lambda:port_tasks.dispatch(str(clip.run_id)));return
        clip.status='running';clip.started_at=timezone.now();clip.save(update_fields=['status','started_at'])
    report={};prepared=None;duration=None
    def still_allowed():
        current=speech_row(pk)
        if current.status!='running' or speech_credentials(current)!=key:
            raise Conflict('This audio request is no longer authorised.')
    try:
        prepared,duration=tts.synthesize(clip.text.word,language=tts.language_code(clip.run.port.language),
            model=tts.MODEL,voice=clip.run.port.voice,api_key=key,
            meaning=clip.meaning.meaning if clip.meaning else '',meaning_language=clip.run.port.explanation_language,
            report=report,guidance_model=clip.run.model,guidance_prices=clip.run.prices,before_request=still_allowed)
    except Exception as exc:
        log.warning('Vocabulary audio %s failed (%s)',pk,type(exc).__name__)
    paths=[]
    try:
        with transaction.atomic():
            porting.locks();clip=speech_row(pk,True)
            if clip.status!='running':return
            cost=tts.report_cost(report) if report else tts.estimate_cost(clip.text.word,duration) if prepared else Decimal('0')
            clip.cost_usd=cost
            item=PortItem.objects.select_for_update(of=('self',)).get(pk=clip.item_id)
            item.run=clip.run
            item.audio_cost+=cost
            item.uncertain_cost=item.uncertain_cost or bool(report.get('uncertain_cost')) or not (prepared or report)
            item.save(update_fields=['audio_cost','uncertain_cost'])
            if report or prepared:porting.record_usage(item,audio=True,cost_override=cost,suffix=f':{clip.pk}')
            try:speech_credentials(clip)
            except (Conflict,Http404):
                clip.status='discarded';clip.report={}
            else:
                clip.report=report;clip.status='ready' if prepared else 'failed'
                if prepared:
                    from .lexicon import recordings
                    if not recordings(clip.entry,clip.run.port.target):
                        media=write_upload(prepared,clip.entry.dictionary_id,paths)
                        provenance={'origin':'synthetic','source_text':clip.text.word,'language':clip.run.port.language,
                            'voice':clip.run.port.voice,'model':tts.MODEL,'instructions_version':tts.INSTRUCTIONS_VERSION,
                            'language_port':clip.run.port_id,'synthesis':report}
                        if report.get('english_homographs') and clip.meaning_id:
                            provenance['source_meaning_id']=clip.meaning_id
                        part=Contribution.objects.create(entry=clip.entry,author=clip.run.port.user,
                            kind='audio',shared_from=clip.text,provenance=provenance,**media)
                        if clip.meaning_id:porting.dependencies(part,[clip.meaning_id])
                        accept(part,clip.run.port.user)
            clip.save(update_fields=['status','report','cost_usd'])
    except Exception:
        for path in paths:delete_file(path)
        raise
    port_tasks.dispatch(str(clip.run_id))


def recover_speech(run,cutoff):
    for clip in run.speech.filter(status='running',started_at__lt=cutoff):
        clip.status='failed';clip.report={};clip.save(update_fields=['status','report'])
        PortItem.objects.filter(pk=clip.item_id).update(uncertain_cost=True)
    if run.status=='running':
        for pk in run.speech.filter(status='queued').values_list('pk',flat=True):
            transaction.on_commit(lambda pk=pk:send_speech(pk))
