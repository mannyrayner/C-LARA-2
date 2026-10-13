"""Bounded Django-Q fan-out/fan-in. Queue payloads contain IDs only.

A committed claim precedes every paid attempt. Broker redelivery never repeats an
in-flight or terminal item. Explicit recovery abandons old claims rather than
replaying an uncertain provider request.
"""
from datetime import timedelta
from decimal import Decimal
import logging

from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from . import photo_ai, port_ai, porting, tts, port_categories, port_budget, port_language, port_costs
from .models import PortEntryLink, PortItem, PortRun
from .services import Conflict
from .storage import delete_file, path_for, write_upload

log = logging.getLogger(__name__)


def send(item_id):
    try:
        from django_q.tasks import async_task
        # Translation (45s), language check (20s), and up to two sentence
        # recordings (60s each) need headroom beyond the former 180s limit.
        async_task('community_dictionary.port_tasks.process_item', item_id,
                   q_options={'task_name':f'community-port-{item_id}', 'timeout':240, 'ack_failure':True})
    except Exception:
        # Durable queued row survives broker failure; Resume can safely enqueue it.
        PortRun.objects.filter(pk__in=PortItem.objects.filter(pk=item_id).values('run_id')).update(queue_error=True)
        log.warning('Could not enqueue language-port item %s', item_id)


@transaction.atomic
def dispatch(run_id):
    porting.locks()
    run = PortRun.objects.select_for_update(of=('self',)).select_related('port__user').get(pk=run_id)
    if run.status != 'running':
        porting.settle(run)
        return
    from .automatic import publish_ready
    publish_ready(run)
    if run.stage in {'vocabulary','audio'}:
        from .port_vocabulary_tasks import dispatch as dispatch_vocabulary
        return dispatch_vocabulary(run)
    active = run.items.filter(status__in=['queued','running']).count()
    limit = max(1,min(8,getattr(settings,'COMMUNITY_DICTIONARY_PORT_WINDOW',4)))
    for item in run.items.filter(status='waiting').order_by('pk')[:max(0,limit-active)]:
        item.status = 'queued'
        item.save(update_fields=['status'])
        transaction.on_commit(lambda pk=item.pk:send(pk))
    porting.settle(run)


def fetch(item_id, lock=False):
    qs = PortItem.objects.select_for_update(of=('self',)) if lock else PortItem.objects
    return qs.select_related('run__port__source','run__port__destination','run__port__user').get(pk=item_id)


def credentials(item):
    if item.run.status != 'running':
        raise Conflict('The job was cancelled.')
    if item.run.prices.get('speech_recipe') != tts.INSTRUCTIONS_VERSION:
        raise Conflict('Pronunciation processing changed. Prepare and approve a fresh estimate.')
    if (item.run.stage != 'vocabulary' and item.snapshot.get('entry_type') == 'sentence' and
            item.run.prices.get('sentence_speech_recipe') != port_ai.speech_version(item.snapshot)):
        raise Conflict('Sentence speech processing changed. Prepare and approve a fresh estimate.')
    if item.run.stage == 'descriptions':
        from .batch_descriptions import VERSION
        if item.run.prices.get('description_recipe') != VERSION:
            raise Conflict('Picture-description processing changed. Prepare a fresh estimate.')
    porting.current_item(item)
    if porting.payer_now(item.run.port.user) != item.run.payer:
        raise Conflict('Your payment account changed. Prepare a fresh estimate.')
    key, _ = photo_ai.api_credentials(item.run.port.user)
    return key


def process_item(item_id):
    if fetch(item_id).run.stage == 'vocabulary':
        from .port_vocabulary_tasks import process_item as process_vocabulary
        return process_vocabulary(item_id)
    pending = fetch(item_id)
    if pending.status == 'queued' and pending.phase == 'audio' and pending.result:
        process_audio(item_id)
        return
    with transaction.atomic():
        porting.locks()
        item = fetch(item_id,True)
        if item.status != 'queued':
            return
        try:
            key = credentials(item)
            if item.run.stage == 'descriptions':
                from .batch_descriptions import input_data
                data = input_data(item)
            else:
                data = porting.input_data(item)
            image_id = item.snapshot['image']
            photo = path_for(item.sources.get(pk=image_id).file_path).read_bytes() if image_id else None
        except (Conflict,Http404,OSError,ValueError):
            porting.clear_preview(item,'The source, access or payment settings changed. Prepare a fresh estimate.')
            transaction.on_commit(lambda:dispatch(str(item.run_id)))
            return
        if not port_budget.claim(item, f'item:{item.pk}', item.estimated_usd):
            item.status='budget';item.message='More allowance is needed before this request. Approve it on the progress page.'
            item.save(update_fields=['status','message'])
            transaction.on_commit(lambda:dispatch(str(item.run_id)))
            return
        item.status, item.phase, item.started_at = 'running','translation',timezone.now()
        item.save(update_fields=['status','phase','started_at'])
    response, result, error, usage = None, None, '', {}
    check_uncertain = False
    try:
        if item.run.stage == 'descriptions':
            from .batch_descriptions import interpret
            response = interpret(photo, data, model=item.run.model, api_key=key)
        else:
            response = port_ai.translate(data,photo,model=item.run.model,api_key=key)
        if getattr(response,'usage',None):
            usage = {k:max(0,int(getattr(response.usage,k,0) or 0)) for k in ['input_tokens','output_tokens']}
        if item.run.stage == 'descriptions':
            from .batch_descriptions import parse
            result = parse(response)
        else:
            result = port_ai.parse(response, data)
        if item.run.stage == 'descriptions':
            from .batch_descriptions import VERSION
            result['recipe'] = VERSION
        else:
            result['recipe'] = port_ai.version_for(data)
        # Model output can never change fields whose language was unchanged.
        if item.run.stage != 'descriptions' and porting.same_language(item.run.source_language,item.run.port.language):
            result['word'] = data['word']
            if data.get('entry_type') == 'sentence' and not data.get('sentence_only'):
                result['word_links'] = [{'source_entry_id': ref['source_entry_id'], 'surface': ref['surface']}
                                        for ref in data.get('sentence_words', [])]
        if item.run.stage != 'descriptions' and porting.same_language(item.run.source_explanation_language,item.run.port.explanation_language):
            result['meaning'] = data['meaning']
    except Exception as exc:
        error = type(exc).__name__
        log.warning('Language-port item %s translation failed (%s)',item_id,error)
    if (result and not error and result.get('word') and item.snapshot.get('entry_type')=='sentence'
            and item.run.options.get('language_check') and (item.run.stage=='descriptions' or
            not porting.same_language(item.run.source_language,item.run.port.language))):
        verdict='unavailable'
        try:
            current=fetch(item_id)
            if current.status!='running':
                raise Conflict('This request was interrupted.')
            key=credentials(current)
            checked=port_language.check(result['word'],item.run.port.language,model=item.run.model,api_key=key)
            check_usage=getattr(checked,'usage',None)
            if check_usage:
                for k in ['input_tokens','output_tokens']:
                    usage[k]=usage.get(k,0)+max(0,int(getattr(check_usage,k,0) or 0))
            else:
                check_uncertain=True
            verdict=port_language.parse(checked)
        except Exception:
            check_uncertain=True
            log.warning('Language-port item %s language check unavailable',item_id)
        result['language_check']=verdict
    with transaction.atomic():
        porting.locks()
        item = fetch(item_id,True)
        if item.status != 'running':
            return  # explicitly abandoned stale attempt; no paid retry
        item.usage = usage
        item.uncertain_cost = not bool(usage) or check_uncertain
        if usage:
            prices = item.run.prices
            item.translation_cost = ((Decimal(usage['input_tokens'])*Decimal(prices['input'])+
                Decimal(usage['output_tokens'])*Decimal(prices['output']))/1_000_000).quantize(Decimal('.000001'))
            porting.record_usage(item)
        try:
            key = credentials(item)
        except (Conflict,Http404):
            item.status, item.result = 'discarded',{}
            item.message = 'The source, access or payment settings changed; the result was discarded.'
        else:
            if result and not error and item.run.stage != 'descriptions':
                port_categories.canonicalize(item, result)
            if error:
                item.status, item.message = 'failed','No usable result was returned. A new estimate is required to try again.'
            elif result['outcome'] != 'candidate':
                item.status,item.result = 'unclear',result
                item.message = 'Check the suggestion or enter your own translation, then save. The original entry can stay as it is.'
            else:
                item.result = result
                if result.get('language_check') in {'mismatch','uncertain','unavailable'}:
                    item.status='ready'; item.needs_attention=True
                    item.attention_note='Check the sentence language: '+item.run.port.language
                    item.message='The target-language check did not pass. Please check or edit this sentence before creating audio. Accept all will skip it.'
                elif item.run.stage != 'descriptions' and porting.same_language(item.run.source_language,item.run.port.language):
                    item.status = 'ready'
                else:
                    link = PortEntryLink.objects.filter(port=item.run.port,source_id=item.source_entry_id).first()
                    recording = link.destination.contributions.filter(kind='audio',status='accepted',
                        provenance__origin='synthetic',provenance__source_text=result['word'],
                        provenance__language=item.run.port.language,provenance__voice=item.run.port.voice,
                        provenance__instructions_version=port_ai.speech_version(item.snapshot)).exclude(file_path='').first() if link else None
                    if (recording and recording.provenance.get('synthesis', {}).get('english_homographs') and
                            link.destination.meaning != result.get('meaning', '')):
                        recording = None
                    if recording:
                        item.result['reused_audio'] = recording.pk
                        item.status = 'ready'
                    else:
                        item.phase = 'audio'
        item.save()
        needs_audio = item.status == 'running' and item.phase == 'audio'
    if needs_audio:
        process_audio(item_id)
        return
    PortItem.objects.filter(pk=item_id).update(finished_at=timezone.now())
    with transaction.atomic():
        porting.locks()
        port_budget.release_claim(item.run_id, f'item:{item.pk}')
    dispatch(str(item.run_id))


def process_audio(item_id):
    """Resume audio without translating a paid, retained result again."""
    with transaction.atomic():
        porting.locks()
        item = fetch(item_id,True)
        if item.status not in {'queued','running'} or item.phase!='audio':
            return
        try:
            key=credentials(item)
        except (Conflict,Http404):
            item.status='discarded'
            porting.clear_preview(item,'The source or permissions changed; audio was not requested.')
            port_budget.release_claim(item.run_id, f'item:{item.pk}')
            transaction.on_commit(lambda:dispatch(str(item.run_id)))
            return
        result=item.result
        port_budget.release_claim(item.run_id, f'item:{item.pk}')
        forecast=port_costs.speech(result['word'],item.run.port.language,item.run.prices,
            sentence=item.snapshot.get('entry_type')=='sentence') * Decimal('1.5')
        if not port_budget.claim(item,f'audio:{item.pk}',forecast):
            item.status='budget';item.message='Text is ready. More allowance is needed for its audio; approve it on the progress page.'
            item.save(update_fields=['status','message'])
            transaction.on_commit(lambda:dispatch(str(item.run_id)))
            return
        item.status='running';item.started_at=timezone.now();item.save(update_fields=['status','started_at'])
    prepared, duration = None,None
    speech_report = {}

    def still_allowed():
        current = fetch(item_id)
        if current.status != 'running' or credentials(current) != key:
            raise Conflict('This audio request is no longer authorized.')

    try:
        prepared,duration = tts.synthesize(result['word'],language=tts.language_code(item.run.port.language),
            model=tts.MODEL,voice=item.run.port.voice,api_key=key,
            meaning=result.get('meaning',''), meaning_language=item.run.port.explanation_language,
            report=speech_report, guidance_model=item.run.model, guidance_prices=item.run.prices,
            before_request=still_allowed,
            speech_kind='sentence' if item.snapshot.get('entry_type') == 'sentence' else 'entry')
    except Exception as exc:
        log.warning('Language-port item %s audio failed (%s)',item_id,type(exc).__name__)
    paths = []
    try:
        with transaction.atomic():
            porting.locks()
            item = fetch(item_id,True)
            if item.status != 'running':
                return
            if speech_report or prepared:
                item.audio_cost = (tts.report_cost(speech_report) if speech_report else
                    tts.estimate_cost(item.result.get('word',result['word']),duration))
                porting.record_usage(item,audio=True)
            if speech_report.get('uncertain_cost') or (not prepared and not speech_report):
                item.uncertain_cost = True
            try:
                credentials(item)
            except (Conflict,Http404):
                item.status,item.result = 'discarded',{}
                item.message = 'The source, access or payment settings changed; the result was discarded.'
            else:
                item.status = 'ready'
                if speech_report:
                    item.result['tts_synthesis'] = speech_report
                if prepared:
                    item.file_path = write_upload(prepared,item.run.port.target_id,paths)['file_path']
                    item.result['tts_instructions_version'] = port_ai.speech_version(item.snapshot)
                else:
                    item.message = 'Text is ready; no usable audio was obtained. Save the text, then use Retry missing audio on the progress page, or add a human recording.'
                    if item.run.options.get('automatic'):
                        item.message = 'Published text has no usable audio. Retry incomplete work after this job finishes.'
            item.finished_at = timezone.now()
            item.save()
    except Exception:
        for path in paths:
            delete_file(path)
        raise
    with transaction.atomic():
        porting.locks()
        port_budget.release_claim(item.run_id, f'audio:{item.pk}')
    dispatch(str(item.run_id))


@transaction.atomic
def resume(user,run_id):
    """Safe broker recovery and explicit expiry, without repeating uncertain calls."""
    porting.locks()
    run = PortRun.objects.select_for_update(of=('self',)).select_related('port__user').get(pk=run_id,port__user=user)
    if run.options.get('automatic_child'):
        resume(user, run.options['automatic_child'])
    cutoff = timezone.now()-timedelta(minutes=15)
    if run.stage in {'vocabulary','audio'}:
        from .port_vocabulary_tasks import recover_speech
        recover_speech(run,cutoff)
    for item in run.items.filter(status='running',started_at__lt=cutoff):
        porting.clear_preview(item,'This interrupted attempt was not retried. Its provider cost may be unknown.')
        item.status, item.uncertain_cost = 'failed',True
        item.save(update_fields=['status','uncertain_cost'])
        port_budget.release_claim(run.pk, f'item:{item.pk}')
        port_budget.release_claim(run.pk, f'audio:{item.pk}')
    if run.status == 'running':
        for pk in run.items.filter(status='queued').values_list('pk',flat=True):
            transaction.on_commit(lambda pk=pk:send(pk))
    run.queue_error = False
    run.save(update_fields=['queue_error'])
    transaction.on_commit(lambda:dispatch(str(run.pk)))
    return run
