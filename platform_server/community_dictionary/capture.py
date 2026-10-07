"""Picture capture lifecycle. Never hold a database transaction across a provider call."""
from datetime import timedelta
from decimal import Decimal
import logging
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404
from django.utils import timezone
from projects.billing import (apply_credit_delta, credits_enabled, has_minimum_balance_for_compile,
    estimate_openai_token_cost_usd)
from projects.models import AIUsageCharge, CreditLedgerEntry
from . import capture_ai, photo_ai, tts
from .models import (PictureCapture, CaptureSpeech, Contribution, ContributionDependency,
    Dictionary, Entry, ImageWordLink, SentenceWord, Participation, LanguageCheck, AttentionReport)
from .permissions import get_dictionary
from .services import Conflict, event
from .storage import path_for, write_upload, delete_file
from .text import FIELDS
from .capture_vocabulary import MAX_EDITED_WORDS

log=logging.getLogger(__name__)

def locks():
    list(Dictionary.objects.select_for_update().order_by('pk').values_list('pk',flat=True))

def fetch(pk,lock=False):
    qs=PictureCapture.objects.select_for_update(of=('self',)) if lock else PictureCapture.objects
    return qs.select_related('dictionary','user','source_image__entry').get(pk=pk)

def allowed(study, *, payment=False):
    dictionary=get_dictionary(study.user,study.dictionary_id)
    revision=Participation.objects.filter(user=study.user,dictionary=dictionary).values_list('revision',flat=True).first() or 0
    if (not dictionary.sentence_capture_enabled or not dictionary.tts_enabled or
        dictionary.capture_revision!=study.revision or dictionary.membership_revision!=study.membership_revision or
        revision!=study.participation_revision or dictionary.language!=study.language or
        (dictionary.explanation_language or 'English')!=study.explanation_language or
        study.status=='discarded' or study.expires_at<=timezone.now()):
        raise Conflict('The capture settings or your participation changed. Start again from the dictionary.')
    if study.source_image_id and not Contribution.objects.filter(pk=study.source_image_id,
            entry__dictionary=dictionary,entry__archived=False,status='accepted',kind='image').exclude(file_path='').exists():
        raise Conflict('The original picture is no longer shared.')
    if study.status!='saved':
        for source in study.sources.select_related('entry'):
            if (source.entry.dictionary_id!=dictionary.pk or source.status!='accepted' or source.entry.archived or
                (source.text_field and getattr(source.entry,FIELDS[source.text_field][0]+'_id')!=source.pk)):
                raise Conflict('Some source material changed. Please prepare a fresh suggestion.')
    if payment:
        if not has_minimum_balance_for_compile(study.user):
            raise Conflict('Your balance is too low to continue generating audio.')
        key,personal=photo_ai.api_credentials(study.user)
        if personal!=study.personal_key:
            raise Conflict('Your API payment settings changed. Start a fresh capture.')
        return key

def charge(study, operation, cost, model, suffix):
    if study.personal_key or cost is None:
        return
    cost=Decimal(cost).quantize(Decimal('.000001'))
    ledger=None
    if cost and credits_enabled():
        ledger=apply_credit_delta(user=study.user,amount_usd=-cost,entry_type=CreditLedgerEntry.ENTRY_USAGE,
            description='Community picture description: '+operation,
            metadata={'operation':operation,'request_type':f'capture:{study.pk}:{suffix}','cost_usd':str(cost)})
    AIUsageCharge.objects.create(user=study.user,provider=AIUsageCharge.PROVIDER_OPENAI,model=model,
        operation='community_capture',request_type=f'capture:{study.pk}:{suffix}',cost_usd=cost,
        status=AIUsageCharge.STATUS_CHARGED if ledger else AIUsageCharge.STATUS_SKIPPED,ledger_entry=ledger,
        notes='Returned token usage, or estimated TTS duration/input cost; provider invoice is authoritative.')

def account(study_id, stage, response, *, transcription=False):
    with transaction.atomic():
        study=fetch(study_id,True)
        if stage in study.usage:
            return
        usage=getattr(response,'usage',None)
        counts={k:max(0,int(getattr(usage,k,0) or 0)) for k in ['input_tokens','output_tokens']} if usage else {}
        cost=capture_ai.transcription_cost(response) if transcription else (
            estimate_openai_token_cost_usd(study.model,counts['input_tokens'],counts['output_tokens']) if counts else None)
        study.usage={**study.usage,stage:{'cost_usd':str(cost) if cost is not None else None, 'tokens':counts}}
        study.save(update_fields=['usage'])
        charge(study,stage,cost,capture_ai.ASR_MODEL if transcription else study.model,stage)

def prepare(study_id):
    with transaction.atomic():
        locks(); study=fetch(study_id,True)
        if study.status!='waiting':
            return
        key=allowed(study,payment=True)
        study.status='processing'; study.save(update_fields=['status'])
    try:
        description=study.description
        if study.input_mode=='voice':
            response=capture_ai.transcribe(path_for(study.recording_path),tts.language_code(study.input_language),key)
            account(study.pk,'transcription',response,transcription=True)
            description=getattr(response,'text','').strip()
            if not 0<len(description)<=1000:
                raise ValueError('description_length')
        current=fetch(study.pk); allowed(current,payment=True)
        words=[]
        for source in current.sources.filter(text_field='word').select_related('entry'):
            words.append({'id':source.entry_id,'lemma':source.word,'meaning':source.entry.meaning})
        response=capture_ai.interpret(path_for(study.file_path).read_bytes(),{
            'target_language':study.language,'explanation_language':study.explanation_language,
            'input_language':study.input_language,'description':description,'vocabulary':words},model=study.model,api_key=key)
        account(study.pk,'interpretation',response)
        result=capture_ai.parse(response)
        result['recipe']=capture_ai.VERSION
        # A model-supplied ID is only a candidate, not an authorization or edit.
        eligible={row['id']:row for row in words}
        for word in result['words']:
            old=eligible.get(word['existing_id'])
            if word['existing_id'] and (not old or old['lemma']!=word['lemma'] or old['meaning']!=word['meaning']):
                word['existing_id']=0
        with transaction.atomic():
            locks(); current=fetch(study.pk,True); allowed(current)
            current.result=result; current.description=description
            current.status=result['outcome']; current.save(update_fields=['result','description','status'])
            if current.input_mode=='voice':
                CaptureSpeech.objects.create(capture=current,kind='feedback',text=result['feedback'],language=current.input_language)
        # Speech is separately claimed; failure leaves the written preview usable.
    except Exception as exc:
        log.warning('Picture capture %s failed (%s)',study_id,type(exc).__name__)
        PictureCapture.objects.filter(pk=study_id,status='processing').update(status='failed')

def component(entry,user,field,value,provenance,sources=()):
    part=Contribution.objects.create(entry=entry,author=user,controlled_by=user,kind='text',text_field=field,
        status='accepted',provenance=provenance,**{field:value})
    pointer,counter=FIELDS[field]
    setattr(entry,field,value); setattr(entry,pointer,part); setattr(entry,counter,1)
    entry.save()
    ContributionDependency.objects.bulk_create([ContributionDependency(source=s,derived=part) for s in sources])
    return part

def plan_speech(study,entry):
    from .lexicon import recordings
    if recordings(entry,study.dictionary):
        return
    CaptureSpeech.objects.create(capture=study,kind='entry',entry=entry,text=entry.word,
        meaning=entry.meaning,language=study.language,text_id=entry.current_text_id,meaning_id=entry.current_meaning_id)

def publish(study_id, user, *, vocabulary=None):
    paths=[]
    try:
        with transaction.atomic():
            locks(); study=fetch(study_id,True)
            if study.user_id!=user.pk: raise Http404
            allowed(study)
            if study.status=='saved': return study.saved_entry
            if study.status!='ready': raise Conflict('Prepare and confirm the suggested meaning first.')
            data=dict(study.result)
            if vocabulary is not None:
                # Revalidate under the same lock as publication. No IDs supplied by
                # the browser are trusted; matching below is by local lemma/sense.
                if not vocabulary.is_valid():
                    raise Conflict('Please correct the vocabulary suggestions first.')
                data['suggested_words']=data['words']
                data['words']=vocabulary.words()
                if [(w['lemma'],w['meaning'],w['surface']) for w in data['words']] != [
                        (w['lemma'],w['meaning'],w['surface']) for w in data['suggested_words']]:
                    data['vocabulary_edited_by']=user.pk
                study.result=data
            entry=Entry.objects.create(dictionary=study.dictionary,created_by=user,entry_type='sentence')
            provenance={'origin':'picture-description','model':study.model,'recipe':data.get('recipe','picture-description-v1'),
                'capture_id':str(study.pk),'meaning_confirmed_by':user.pk,'language':study.language,
                'explanation_language':study.explanation_language,'source_image_id':study.source_image_id,
                'input_mode':study.input_mode,'input_language':study.input_language,'description':study.description,
                'suggested_words':data.get('suggested_words',data['words']),
                'confirmed_words':data['words'],'vocabulary_reviewed_by':user.pk}
            source=study.source_image
            image=Contribution.objects.create(entry=entry,kind='image',status='accepted',
                author=source.author if source else user,controlled_by=(source.controlled_by or source.author) if source else user,
                shared_from=source,provenance=source.provenance if source else {'origin':'human'},
                **write_upload((path_for(study.file_path).read_bytes(),'image/jpeg','.jpg'),study.dictionary_id,paths))
            entry.selected_image=image; entry.save(update_fields=['selected_image'])
            sentence=component(entry,user,'word',data['sentence'],provenance,[image])
            component(entry,user,'meaning',data['translation'],provenance,[sentence])
            for word in data['words']:
                target=Entry.objects.filter(dictionary=study.dictionary,entry_type='word',archived=False,
                    word=word['lemma'],meaning=word['meaning'],current_text__status='accepted',current_meaning__status='accepted').order_by('pk').first()
                if not target:
                    target=Entry.objects.create(dictionary=study.dictionary,created_by=user)
                    component(target,user,'word',word['lemma'],provenance,[sentence])
                    component(target,user,'meaning',word['meaning'],provenance,[target.current_text])
                SentenceWord.objects.get_or_create(sentence_text=sentence,word_entry=target,
                    defaults={'word_text':target.current_text,'surface':word['surface']})
                ImageWordLink.objects.get_or_create(image=image,word_entry=target,defaults={'created_by':user,'sentence_text':sentence})
                plan_speech(study,target)
            plan_speech(study,entry)
            transaction.on_commit(lambda:queue_audio(str(study.pk)))
            study.status='saved'; study.saved_entry=entry; study.save(update_fields=['status','saved_entry','result'])
            event(study.dictionary,user,'capture_confirmed',entry,'Contributor confirmed meaning; language not expert checked')
            return entry
    except Exception:
        for path in paths: delete_file(path)
        raise

def speech_allowed(clip, *, payment=False):
    key=allowed(clip.capture,payment=payment)
    if clip.entry_id:
        entry=Entry.objects.get(pk=clip.entry_id)
        if (entry.archived or entry.dictionary_id!=clip.capture.dictionary_id or
            entry.current_text_id!=clip.text_id or entry.current_meaning_id!=clip.meaning_id or entry.word!=clip.text):
            raise Conflict('The words changed; generate audio from the updated entry.')
    return key

def speak(clip_id):
    with transaction.atomic():
        locks()
        clip=CaptureSpeech.objects.select_for_update().select_related('capture__dictionary','capture__user').get(pk=clip_id)
        if clip.status!='waiting': return
        key=speech_allowed(clip,payment=True)
        if clip.entry_id:
            from .lexicon import recordings
            if recordings(Entry.objects.get(pk=clip.entry_id),clip.capture.dictionary):
                clip.status='ready'; clip.save(update_fields=['status']); return
        clip.status='running'; clip.save(update_fields=['status'])
    report={}; prepared=None
    def check():
        fresh=CaptureSpeech.objects.select_related('capture__dictionary','capture__user').get(pk=clip_id)
        if fresh.status!='running': raise Conflict('This audio attempt was cancelled.')
        speech_allowed(fresh,payment=True)
    try:
        prepared,_=tts.synthesize(clip.text,language=tts.language_code(clip.language),model=tts.MODEL,
            voice=clip.capture.voice,api_key=key,meaning=clip.meaning,meaning_language=clip.capture.explanation_language,
            report=report,before_request=check)
    except Exception as exc:
        log.warning('Capture speech %s failed (%s)',clip_id,type(exc).__name__)
    paths=[]
    try:
        with transaction.atomic():
            locks()
            current=CaptureSpeech.objects.select_for_update().select_related('capture__dictionary','capture__user').get(pk=clip_id)
            if not current.report:
                charge(current.capture,'speech',tts.report_cost(report),tts.MODEL,f'speech:{clip_id}')
                current.report={'accounted':True,**report} if current.status!='discarded' else {'accounted':True}
            try: speech_allowed(current)
            except (Conflict,Http404): prepared=None
            if current.status=='running':
                if prepared:
                    media=write_upload(prepared,current.capture.dictionary_id,paths)
                    if current.entry_id:
                        entry=Entry.objects.get(pk=current.entry_id)
                        audio=Contribution.objects.create(entry=entry,author=current.capture.user,controlled_by=current.capture.user,
                            kind='audio',status='accepted',provenance={'origin':'synthetic','provider':'openai','model':tts.MODEL,
                            'source_text':current.text,'source_meaning_id':current.meaning_id,'language':current.language,
                            'voice':current.capture.voice,'capture_id':str(current.capture_id),
                            'pronunciation_guidance':report.get('guidance',{}),'english_homographs':report.get('english_homographs',[])},**media)
                        for part_id in [current.text_id,current.meaning_id]:
                            if part_id: ContributionDependency.objects.get_or_create(source_id=part_id,derived=audio)
                        current.contribution=audio
                    else: current.file_path=media['file_path']
                    current.status='ready'
                else: current.status='failed'
            current.save()
    except Exception:
        for path in paths: delete_file(path)
        raise

def discard(query):
    """Erase private previews; never remove separately published contributions."""
    for study in query.select_for_update():
        paths=[study.file_path,study.recording_path]+list(study.speech.exclude(file_path='').values_list('file_path',flat=True))
        study.status='discarded'; study.result={}; study.description=''; study.file_path=study.recording_path=''
        study.save(update_fields=['status','result','description','file_path','recording_path'])
        study.speech.update(status='discarded',text='',meaning='',file_path='',report={})
        study.sources.clear()
        for path in paths:
            if path: transaction.on_commit(lambda path=path:delete_file(path))

def sentence_links(dictionary):
    return SentenceWord.objects.filter(sentence_text__entry__dictionary=dictionary,
        sentence_text__status='accepted',sentence_text_id=F('sentence_text__entry__current_text_id'),
        sentence_text__entry__archived=False,word_entry__dictionary=dictionary,word_entry__archived=False,
        word_text__status='accepted',word_text_id=F('word_entry__current_text_id'))

def linked_sentences(entry):
    links=sentence_links(entry.dictionary).filter(word_entry=entry)
    return Entry.objects.filter(pk__in=links.values('sentence_text__entry_id')).order_by('-created_at')

def sentence_context(entry):
    from .lexicon import word_row
    links=sentence_links(entry.dictionary).filter(sentence_text__entry=entry).select_related('word_entry')
    checked=LanguageCheck.objects.filter(entry=entry,text_id=entry.current_text_id,meaning_id=entry.current_meaning_id).first()
    reports=AttentionReport.objects.filter(entry=entry,note__entry=entry,note__status='accepted',resolved_at__isnull=True)
    return {'sentence_words':[{'surface':link.surface,**word_row(link.word_entry,entry.dictionary)} for link in links],
        'related_sentences':linked_sentences(entry), 'language_check':checked,'attention_count':reports.count(),
        'capture_origin':bool(entry.current_text and entry.current_text.provenance.get('origin')=='picture-description')}



def queue_audio(study_id):
    """One bounded job per capture; existing laptop/production Q adapters work.

    Queue payloads contain only an ID. Browser continuation claims the same rows,
    so refreshing or broker redelivery never repeats a paid attempt.
    """
    try:
        from django_q.tasks import async_task
        async_task('community_dictionary.capture.run_audio',study_id,
            q_options={'task_name':f'picture-audio-{study_id}','timeout':900,'ack_failure':True})
    except Exception:
        log.warning('Could not enqueue picture audio %s; browser continuation remains available',study_id)


def run_audio(study_id):
    from django.db import close_old_connections
    close_old_connections()
    try:
        ids=list(CaptureSpeech.objects.filter(capture_id=study_id,kind='entry',status='waiting').order_by('pk').values_list('pk',flat=True)[:MAX_EDITED_WORDS+1])
        for clip_id in ids:
            try:
                speak(clip_id)
            except (Conflict,Http404,PictureCapture.DoesNotExist,CaptureSpeech.DoesNotExist):
                CaptureSpeech.objects.filter(pk=clip_id,status='waiting').update(status='failed')
    finally:
        close_old_connections()
