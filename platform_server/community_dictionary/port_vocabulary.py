"""Stage two: derive vocabulary from fixed, accepted destination sentences."""
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.utils import timezone
from projects.billing import credits_enabled
from . import capture_ai, photo_ai, porting, tts, capture_vocabulary
from .collections import content_digest
from .models import (Contribution, Entry, PortRun, PortItem, PortEntryLink, PortSpeech,
                     SentenceWord, ImageWordLink, VocabularyState)
from .services import Conflict, event

VERSION = 'accepted-sentence-vocabulary-1'


def authority(port):
    porting.authority(port)
    if not port.destination_id or not port.destination.photo_ai_enabled:
        raise Conflict('Enable Learn from a photo in the destination dictionary settings first.')
    if not port.destination.tts_enabled or not tts.language_code(port.language):
        raise Conflict('Enable supported spoken audio in the destination dictionary first.')


def sentence_snapshot(entry):
    """Audio and generated links do not change the accepted linguistic input."""
    fields = {}
    parts = []
    for field,pointer in [('word','current_text'),('meaning','current_meaning')]:
        part = getattr(entry,pointer)
        if part and part.entry_id == entry.pk and part.status == 'accepted':
            fields[field] = part.pk
            parts.append(part)
    images = entry.contributions.filter(kind='image',status='accepted').exclude(file_path='').order_by('pk')
    image = images.filter(pk=entry.selected_image_id).first() or images.first()
    if image:
        parts.append(image)
    data = {'fields':fields,'image':image.pk if image else None,
            'ids':sorted(c.pk for c in parts), 'languages':[entry.dictionary.language,entry.dictionary.explanation_language],
            'parts':[[c.pk,content_digest(c)] for c in parts]}
    return {**data,'digest':hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()}


def current_state(entry, state=None):
    state = state or VocabularyState.objects.filter(sentence=entry).first()
    if not state or state.recipe != VERSION or state.snapshot != sentence_snapshot(entry):
        return False
    wanted = {(w['entry'],w['text']) for w in state.words}
    actual = set(SentenceWord.objects.filter(sentence_text=entry.current_text,
        word_text__status='accepted',word_entry__archived=False,
        word_entry__current_text_id=F('word_text_id')).values_list('word_entry_id','word_text_id'))
    if actual != wanted:
        return False
    return all(Entry.objects.filter(pk=w['entry'],current_meaning_id=w['meaning']).exists() for w in state.words)


def current_item(item):
    port = item.run.port
    authority(port)
    if item.invalidated or item.run.status == 'cancelled':
        raise Conflict('This vocabulary result is no longer available.')
    entry = Entry.objects.select_related('dictionary','current_text','current_meaning').get(pk=item.source_entry_id)
    if (entry.dictionary_id != port.destination_id or entry.entry_type != 'sentence' or entry.archived or
            sentence_snapshot(entry) != item.snapshot['sentence']):
        raise Conflict('The accepted sentence, explanation or picture changed. Estimate vocabulary again.')
    ids = [ref[k] for ref in item.snapshot.get('context',[]) for k in ['text','meaning'] if ref[k]]
    parts = {p.pk:p for p in Contribution.objects.filter(pk__in=ids).select_related('entry')}
    for pk in ids:
        part = parts.get(pk)
        if (not part or part.status != 'accepted' or part.entry.dictionary_id != port.destination_id or part.entry.archived or
                getattr(part.entry,'current_'+('text' if part.text_field=='word' else 'meaning')+'_id') != pk):
            raise Conflict('Some supplied vocabulary changed or was withdrawn. Estimate again.')
    return entry


def context(dictionary):
    refs, size = [],0
    for entry in dictionary.entries.filter(entry_type='word',archived=False,current_text__status='accepted',
            current_meaning__status='accepted').select_related('current_text','current_meaning').order_by('-pk')[:200]:
        if not entry.word or len(entry.meaning)>300 or len(entry.word)>100:
            continue
        size += len(entry.word)+len(entry.meaning)
        if size>24000:
            break
        refs.append({'entry':entry.pk,'text':entry.current_text_id,'meaning':entry.current_meaning_id})
    return refs


def input_data(item):
    entry = current_item(item)
    ids=[ref[k] for ref in item.snapshot.get('context',[]) for k in ['text','meaning'] if ref[k]]
    parts={p.pk:p for p in Contribution.objects.filter(pk__in=ids)}
    return {'sentence':entry.word,'translation':entry.meaning,'target_language':entry.dictionary.language,
        'explanation_language':entry.dictionary.explanation_language or 'English',
        'vocabulary':[{'id':ref['entry'],'lemma':parts[ref['text']].word,
            'meaning':parts[ref['meaning']].meaning} for ref in item.snapshot.get('context',[])]}


def estimate(entry, prices, extra):
    # Analysis once per sentence; reuse can reduce audio requests substantially.
    analysis, allowance = porting.estimate_entry(entry,prices,False,extra)
    typical = tts.guidance_estimate(prices) + tts.estimate_cost('x'*1400,3)
    maximum = tts.guidance_estimate(prices,allowance=True) + 2*tts.estimate_cost('x'*12000,60)
    return porting.money(analysis+capture_ai.MAX_WORDS*typical), porting.money(allowance+capture_vocabulary.MAX_EDITED_WORDS*maximum)


@transaction.atomic
def quote(user, port, token):
    porting.locks()
    if port.user_id != user.pk:
        raise Http404
    authority(port)
    previous = PortRun.objects.filter(pk=token,port=port,stage='vocabulary').first()
    if previous:
        return previous
    if port.runs.filter(status='running').exists():
        raise Conflict('Finish the current job, including its vocabulary review, or cancel its unsaved results first.')
    if PortItem.objects.filter(run__port=port,source_entry__entry_type='sentence',
        status__in=['ready','unclear'],needs_attention=False,invalidated=False).exists():
        raise Conflict('Accept or flag the remaining sentence translations before building their vocabulary.')
    model,key,personal,prices = photo_ai.configuration(user)
    port.runs.filter(stage='vocabulary',status='estimate').update(status='cancelled')
    run = PortRun.objects.create(id=token,port=port,stage='vocabulary',model=model,
        source_language=port.language,source_explanation_language=port.explanation_language,
        prices={**{k:str(v) for k,v in prices.items()},'speech_recipe':tts.INSTRUCTIONS_VERSION,'vocabulary_recipe':VERSION},
        payer='personal' if personal else 'credits' if credits_enabled() else 'server',expires_at=timezone.now()+timedelta(hours=1))
    refs = context(port.destination)
    context_ids = [ref[k] for ref in refs for k in ['text','meaning'] if ref[k]]
    size = sum(len(c.word)+len(c.meaning) for c in Contribution.objects.filter(pk__in=context_ids))
    for entry in port.destination.entries.filter(entry_type='sentence',archived=False,current_text__status='accepted').exclude(word='').select_related('dictionary','current_text','current_meaning'):
        if current_state(entry):
            run.skipped += 1
            continue
        snap = sentence_snapshot(entry)
        estimated,maximum = estimate(entry,prices,size)
        item = PortItem.objects.create(run=run,source_entry=entry,
            snapshot={'entry_type':'sentence','sentence':snap,'image':snap['image'],'context':refs},
            estimated_usd=estimated,allowance_usd=maximum)
        item.sources.set(snap['ids']+context_ids)
        run.estimated_usd += estimated
        run.allowance_usd += maximum
    run.save()
    return run


def validated_words(words, sentence):
    from .capture_forms import VocabularyForms
    data={'words-TOTAL_FORMS':str(len(words)),'words-INITIAL_FORMS':'0'}
    for i,word in enumerate(words):
        for field in ['lemma','meaning','surface']:
            data[f'words-{i}-{field}']=word.get(field,'')
    form = VocabularyForms(data,prefix='words',sentence=sentence)
    if not form.is_valid():
        raise Conflict('Check the words, meanings and forms used in this sentence before accepting.')
    return form.words()


def trusted_links(port, sentence):
    ids = set(SentenceWord.objects.filter(sentence_text__entry=sentence).values_list('word_entry_id',flat=True)) | {sentence.pk}
    return [link for link in port.entry_links.filter(destination_id__in=ids).select_related('destination__dictionary')
            if not link.manually_edited and porting.destination_clean(link)]


def advance_baselines(port, links):
    for link in links:
        link.destination.refresh_from_db()
        before = link.destination_digest
        link.destination_digest = porting.refreshed_digest(link)
        link.save(update_fields=['destination_digest'])
        PortItem.objects.filter(run__port=port,run__stage='legacy',source_entry_id=link.source_id,
            destination_digest=before).exclude(status__in=['saved','discarded']).update(destination_digest=link.destination_digest)


def retire_unused(port, old_links):
    """Archive only unchanged, unused legacy ports of sentence-derived vocabulary."""
    from .capture import sentence_links
    from .port_sentences import vocabulary_only
    for link in old_links:
        entry = link.destination
        if entry.entry_type != 'word' or not vocabulary_only(link.source):
            continue
        if sentence_links(port.destination).filter(word_entry=entry).exists():
            continue
        if ImageWordLink.objects.filter(word_entry=entry,sentence_text__isnull=True).exists():
            continue
        if entry.contributions.filter(kind='note').exists():
            continue
        # The trusted snapshot was checked BEFORE replacing its derived links.
        entry.archived=True
        entry.save(update_fields=['archived'])


@transaction.atomic
def save_item(user, item_id, words):
    porting.locks()
    item = PortItem.objects.select_for_update(of=('self',)).select_related('run__port__user','run__port__source','run__port__destination').get(pk=item_id,run__port__user=user,run__stage='vocabulary')
    if item.status == 'saved':
        return item.source_entry
    if item.status != 'ready':
        raise Conflict('This vocabulary result is not ready to accept.')
    entry = current_item(item)
    words = validated_words(words,entry.word)
    old = trusted_links(item.run.port,entry)
    images = list(entry.contributions.filter(kind='image',status='accepted').exclude(file_path=''))
    provenance={'origin':'sentence-vocabulary','sentence_vocabulary':True,'model':item.run.model,
        'recipe':VERSION,'language':entry.dictionary.language,'language_port':item.run.port_id,
        'sentence_id':entry.pk,'accepted_by':user.pk}
    # Reusing a page never reattributes it or overwrites its wording/meaning.
    before_ids = set(entry.dictionary.entries.values_list('pk',flat=True))
    targets = capture_vocabulary.publish_words(entry.current_text,words,user,provenance,images,replace=True)
    for target in targets:
        if target.pk not in before_ids:
            porting.dependencies(target.current_text,list(item.sources.values_list('pk',flat=True)))
        from .lexicon import recordings
        if not recordings(target,entry.dictionary):
            PortSpeech.objects.get_or_create(run=item.run,entry=target,text=target.current_text,
                defaults={'item':item,'meaning':target.current_meaning})
    VocabularyState.objects.update_or_create(sentence=entry,defaults={
        'snapshot':item.snapshot['sentence'],'recipe':VERSION,'accepted_by':user,'accepted_at':timezone.now(),
        'words':[{'entry':target.pk,'text':target.current_text_id,'meaning':target.current_meaning_id} for target in targets]})
    advance_baselines(item.run.port,old)
    item.status='saved';item.result={}
    item.review_values={'replaced_word_ids':[link.destination_id for link in old if link.destination.entry_type=='word']}
    item.save(update_fields=['status','result','review_values'])
    event(entry.dictionary,user,'accept_sentence_vocabulary',entry,'Vocabulary accepted; no expert linguistic check claimed')
    from .port_tasks import dispatch
    transaction.on_commit(lambda:dispatch(str(item.run_id)))
    return entry


def pending(entry):
    state = VocabularyState.objects.filter(sentence=entry).first()
    if state:
        return not current_state(entry,state)
    return bool(entry.current_text and entry.entry_type=='sentence' and
                entry.current_text.provenance.get('language_port'))


def finish(run):
    if run.status == 'cancelled':
        return
    replaced={pk for item in run.items.filter(status='saved') for pk in item.review_values.get('replaced_word_ids',[])}
    links=[link for link in run.port.entry_links.filter(destination_id__in=replaced).select_related('source__dictionary','source__current_text','destination__dictionary')
           if link.destination.entry_type=='word' and not link.manually_edited and porting.destination_clean(link)]
    retire_unused(run.port,links)
    advance_baselines(run.port,links)
