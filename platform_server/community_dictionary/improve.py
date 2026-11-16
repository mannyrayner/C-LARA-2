"""Private, version-bound bilingual suggestions; explicit approval precedes text changes."""
from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher
import logging
import re
from django.core import signing
from django.db import close_old_connections, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import get_language
from . import capture, capture_limits, improve_ai, photo_ai, port_vocabulary, refresh
from .models import Contribution, Entry, PictureCapture, Participation
from .services import Conflict, accept, event
from .storage import path_for

VERSION=improve_ai.VERSION
SALT='community-bilingual-review-1'
log=logging.getLogger(__name__)


def policy(user,entry):
    values=refresh.values(user,entry);values.pop('snapshot')
    values['version']=VERSION
    return values


def quote_values(user,entry):
    return {'policy':policy(user,entry),'snapshot':port_vocabulary.sentence_snapshot(entry)}


def check_estimate(rates):
    return (Decimal(24000)*Decimal(rates['input'])+Decimal(2400)*Decimal(rates['output']))/1000000


def replacements(before,after):
    def tokens(text):return [t.strip('.,;:!?…()[]{}"“”') for t in text.split() if t.strip('.,;:!?…()[]{}"“”')]
    old,new=tokens(before),tokens(after);found=[]
    for tag,a,b,c,d in SequenceMatcher(a=[improve_ai.normal(x) for x in old],
                                      b=[improve_ai.normal(x) for x in new],autojunk=False).get_opcodes():
        rejected,replacement=' '.join(old[a:b]),' '.join(new[c:d])
        if tag=='replace' and 0<b-a<=3 and 0<d-c<=3 and len(replacement)<=80 and len(rejected)<=80:
            found.append({'rejected':rejected,'replacement':replacement})
    return found


def history(entry):
    result,ids,preferred={},[],{}
    for field,pointer in [('word','current_text'),('meaning','current_meaning')]:
        rows=[];pairs=[];part=getattr(entry,pointer);seen=set()
        while part and len(rows)<12 and part.pk not in seen:
            seen.add(part.pk)
            if part.entry_id!=entry.pk or part.text_field!=field or part.status!='accepted':break
            rows.append({'id':part.pk,'text':getattr(part,field),'human_edit':not part.provenance.get('origin')})
            ids.append(part.pk)
            pairs.extend(part.provenance.get('preferred_corrections',{}).get(field,[]))
            previous=part.previous_revision
            if (not part.provenance.get('origin') and previous and previous.status=='accepted'
                    and previous.entry_id==entry.pk and previous.text_field==field):
                pairs.extend(replacements(getattr(previous,field),getattr(part,field)))
            part=previous
        result[field]=rows
        preferred[field]=[]
        for pair in pairs:
            if (pair not in preferred[field] and improve_ai.contains(getattr(entry,field),pair['replacement'])
                    and not improve_ai.contains(getattr(entry,field),pair['rejected'])):
                preferred[field].append(pair)
    return {'history':result,'history_ids':ids,'preferred_corrections':preferred}


def values(user,entry,notes=''):
    return {**quote_values(user,entry),'notes':notes,**history(entry)}


def validate(study,*,payment=False):
    info=study.result.get('improve',{});consent=info.get('consent',{})
    entry=Entry.objects.select_related('dictionary','current_text','current_meaning').filter(pk=study.saved_entry_id).first()
    if (not entry or study.input_mode!='improve' or info.get('version')!=VERSION or
        not refresh.available(study.user,entry) or
        port_vocabulary.sentence_snapshot(entry)!=consent.get('snapshot')):
        raise Conflict('This entry changed. Check its current wording again before applying suggestions.')
    ids=consent.get('history_ids',[])
    if Contribution.objects.filter(pk__in=ids,entry=entry,status='accepted').count()!=len(set(ids)):
        raise Conflict('Some edit history is no longer available. Start a fresh check.')
    if payment and consent['policy']!=policy(study.user,entry):
        raise Conflict('The AI prices or settings changed. Review a fresh check estimate.')
    return entry


def create(user,entry,notes='',*,language=None):
    # Caller holds dictionary/user locks and the surrounding submission receipt.
    consent=values(user,entry,notes)
    for old in PictureCapture.objects.filter(dictionary=entry.dictionary,saved_entry=entry,
            input_mode='improve',expires_at__gt=timezone.now()).order_by('-created_at'):
        recover(old)
        previous=old.result.get('improve',{}).get('consent',{})
        if previous==consent and old.user_id==user.pk and old.status in {'waiting','processing','ready'}:return old
        if previous.get('snapshot')==consent['snapshot'] and old.status in {'waiting','processing'}:
            raise Conflict('A check for this entry is already running. Check the entry again shortly.')
    capture_limits.enforce(entry.dictionary,user)
    d=entry.dictionary; chosen=consent['policy']
    study=PictureCapture.objects.create(dictionary=d,user=user,saved_entry=entry,
        source_image_id=consent['snapshot']['image'],input_mode='improve',
        expires_at=timezone.now()+timedelta(days=2),language=d.language,
        explanation_language=d.explanation_language or 'English',input_language=d.language,
        description=notes,model=chosen['model'],personal_key=chosen['personal'],voice=capture.tts.VOICE,
        revision=d.capture_revision,membership_revision=d.membership_revision,
        participation_revision=Participation.objects.filter(dictionary=d,user=user).values_list('revision',flat=True).first() or 0,
        result={'improve':{'version':VERSION,'consent':consent,'feedback_language':language or get_language() or 'en'}})
    refs=[i for ref in port_vocabulary.context(d) for i in (ref['text'],ref['meaning']) if i]
    study.sources.set(set(refs+consent['snapshot']['ids']))
    capture.allowed(study,payment=True)
    transaction.on_commit(lambda:queue(study.pk))
    return study


def queue(pk):
    try:
        from django_q.tasks import async_task
        async_task('community_dictionary.improve.run',str(pk),
            q_options={'task_name':f'bilingual-check-{pk}','timeout':120,'ack_failure':True})
    except Exception:
        log.warning('Could not enqueue bilingual check %s',pk)


def input_data(study):
    entry=validate(study);info=study.result['improve'];consent=info['consent']
    return {'target_language':study.language,'explanation_language':study.explanation_language,
        'sentence':entry.word,'translation':entry.meaning,'notes':consent['notes'],
        'history':consent['history'],'preferred_corrections':consent['preferred_corrections'],
        'feedback_language':info['feedback_language']}


def run(pk):
    close_old_connections()
    try:
        with transaction.atomic():
            capture.locks();study=capture.fetch(pk,True)
            if study.input_mode!='improve' or study.status!='waiting':return
            key=capture.allowed(study,payment=True);data=input_data(study)
            study.result['improve']['started_at']=timezone.now().isoformat()
            study.status='processing';study.save(update_fields=['status','result'])
        photo=path_for(study.source_image.file_path).read_bytes() if study.source_image_id else None
        response=improve_ai.analyse(data,photo,model=study.model,api_key=key)
        capture.account(pk,'bilingual_check',response)
        result=improve_ai.parse(response,data)
        with transaction.atomic():
            capture.locks();current=capture.fetch(pk,True);capture.allowed(current)
            if current.status!='processing':return
            current.result['improve']['review']=result
            current.status='ready';current.save(update_fields=['status','result'])
    except Exception as exc:
        log.warning('Bilingual check %s stopped (%s)',pk,type(exc).__name__)
        PictureCapture.objects.filter(pk=pk,input_mode='improve',status__in=['waiting','processing']).update(status='failed')
    finally:close_old_connections()


@transaction.atomic
def apply(study,user,word,meaning,choice):
    from . import text
    if study.user_id!=user.pk:raise Conflict('This check belongs to another editor.')
    if study.input_mode=='refresh':return  # Replayed approved submission; never enqueue twice.
    entry=validate(study,payment=True)
    if study.status!='ready':raise Conflict('Finish the check before applying suggestions.')
    review=study.result['improve']['review']
    options=review['options']
    if options:
        if not 0<=choice<len(options):raise Conflict('Choose one of the displayed suggestions.')
        proposed=options[choice]
    else:
        proposed={'sentence':entry.word,'translation':entry.meaning}
    final={'word':word,'meaning':meaning}
    preferred=study.result['improve']['consent']['preferred_corrections']
    for part in text.propose(entry,user,{**final,'edit_text':True}):
        field=part.text_field
        pairs=preferred.get(field,[])+replacements(proposed['sentence' if field=='word' else 'translation'],final[field])
        part.provenance={'origin':'ai-assisted-review','bilingual_check':str(study.pk),
            'model':study.model,'reviewed_by':user.pk,
            'preferred_corrections':{field:[p for p in pairs if improve_ai.contains(final[field],p['replacement'])
                and not improve_ai.contains(final[field],p['rejected'])]}}
        part.save(update_fields=['provenance']);accept(part,user)
    entry.refresh_from_db()
    consent=refresh.values(user,entry)
    study.result['improve']['approved']={'choice':choice,'word':word,'meaning':meaning,'by':user.pk}
    study.result['refresh']={'version':refresh.VERSION,'consent':consent}
    study.input_mode='refresh';study.status='waiting';study.save(update_fields=['result','input_mode','status'])
    ids=[i for ref in port_vocabulary.context(entry.dictionary) for i in (ref['text'],ref['meaning']) if i]
    study.sources.set(set(ids+consent['snapshot']['ids']))
    capture.allowed(study,payment=True)
    if port_vocabulary.current_state(entry):
        study.status='saved';study.save(update_fields=['status']);refresh.plan_audio(study,entry)
    event(entry.dictionary,user,'bilingual_suggestion_approved',entry,'Approved wording; dependent words/audio queued')
    transaction.on_commit(lambda:refresh.queue(study.pk))


def recover(study):
    if study.input_mode=='improve' and study.status=='processing':
        started=parse_datetime(study.result.get('improve',{}).get('started_at','')) or study.created_at
        if started<timezone.now()-timedelta(minutes=15):
            PictureCapture.objects.filter(pk=study.pk,status='processing').update(status='failed')
            study.refresh_from_db()


def auto_start(request,entry,before_snapshot,token):
    """Saving text succeeds even if the optional paid check cannot be admitted."""
    from django.contrib import messages
    from django.urls import reverse
    from django.utils.translation import gettext
    from django.contrib.auth import get_user_model
    try:
        with transaction.atomic():
            approved=signing.loads(token,salt=SALT,max_age=600)
            if approved!={'policy':policy(request.user,entry),'snapshot':before_snapshot}:
                raise Conflict('The check estimate changed.')
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            study=create(request.user,entry)
        return reverse('community_dictionary:improve-detail',args=[entry.dictionary_id,study.pk])
    except Exception as exc:
        log.warning('Could not admit optional bilingual check (%s)',type(exc).__name__)
        messages.info(request,gettext('Your edit is saved. Open Check and improve to start a fresh check.'))
        return reverse('community_dictionary:improve-start',args=[entry.dictionary_id,entry.pk])
