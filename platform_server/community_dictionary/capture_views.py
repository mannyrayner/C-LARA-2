"""Optional picture-first descriptions and a shared language-attention queue."""
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from projects.billing import has_minimum_balance_for_compile
from . import capture, photo_ai, tts, capture_limits
from .capture_forms import CaptureForm, VocabularyForms
from .models import (PictureCapture, CaptureSpeech, Contribution, ContributionDependency, Dictionary,
    Entry, Participation, VoicePreference, AttentionReport, LanguageCheck)
from .permissions import get_dictionary, require_editor
from .services import Conflict, submit_once, event, entry_url
from .storage import path_for, write_upload
from .views import context, fail, saved, private_media_response, get_entry


def url(study):
    return reverse('community_dictionary:capture-detail',args=[study.dictionary_id,study.pk])

def own(request,pk,study_id):
    dictionary=get_dictionary(request.user,pk)
    study=get_object_or_404(PictureCapture,dictionary=dictionary,user=request.user,pk=study_id,expires_at__gt=timezone.now())
    if study.status=='discarded': raise Http404
    return study

@login_required
def start(request,pk,image_id=None):
    dictionary=get_dictionary(request.user,pk)
    if not dictionary.sentence_capture_enabled:
        return fail(request,'The owner can enable Picture descriptions in Settings.',403)
    image=get_object_or_404(Contribution,pk=image_id,entry__dictionary=dictionary,entry__archived=False,
        kind='image',status='accepted') if image_id else None
    previous=None
    if request.GET.get('revise'):
        previous=own(request,pk,request.GET['revise'])
        capture.allowed(previous)
    prefs=request.session.get(f'capture-{pk}',{})
    initial={'input_mode':'text','input_language':dictionary.explanation_language or 'English','voice':tts.VOICE,**prefs}
    if previous:
        initial.update(description=previous.description,input_language=previous.input_language,input_mode='text')
    form=CaptureForm(request.POST or None,request.FILES or None,dictionary=dictionary,
        existing=bool(image or previous),initial=initial)
    config=None; setup_error=''
    try:
        config=photo_ai.configuration(request.user)
        if not dictionary.tts_enabled or not all(tts.language_code(l) for l in [dictionary.language,dictionary.explanation_language or 'English']):
            raise Conflict('Picture descriptions need supported text-to-speech languages and saved audio enabled.')
    except Conflict as exc: setup_error=str(exc)
    if request.method=='POST' and form.is_valid() and not setup_error:
        model,key,personal,prices=config
        def create(paths):
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            current=get_dictionary(request.user,pk)
            if not current.sentence_capture_enabled or not current.tts_enabled or current.capture_revision!=dictionary.capture_revision:
                raise Conflict('The capture settings changed. Reload this page.')
            if not has_minimum_balance_for_compile(request.user):
                raise Conflict('Your C-LARA balance is too low. Add credit or use your own OpenAI key.')
            capture_limits.enforce(current, request.user)
            if previous:
                capture.allowed(previous)
                prepared=(path_for(previous.file_path).read_bytes(),'image/jpeg','.jpg')
                source=previous.source_image
            elif image:
                source=get_object_or_404(Contribution,pk=image.pk,entry__dictionary=current,status='accepted',entry__archived=False)
                prepared=(path_for(source.file_path).read_bytes(),'image/jpeg','.jpg')
            else:
                source=None; prepared=form.cleaned_data['prepared_photo']
            photo=write_upload(prepared,pk,paths)
            audio=write_upload(form.cleaned_data['prepared_audio'],pk,paths) if form.cleaned_data['input_mode']=='voice' else {}
            study=PictureCapture.objects.create(dictionary=current,user=request.user,source_image=source,
                expires_at=timezone.now()+timedelta(days=2),language=current.language,
                explanation_language=current.explanation_language or 'English',input_language=form.cleaned_data['input_language'],
                input_mode=form.cleaned_data['input_mode'],description=form.cleaned_data.get('description',''),
                file_path=photo['file_path'],recording_path=audio.get('file_path',''),model=model,personal_key=personal,
                voice=form.cleaned_data['voice'],revision=current.capture_revision,membership_revision=current.membership_revision,
                participation_revision=Participation.objects.filter(dictionary=current,user=request.user).values_list('revision',flat=True).first() or 0)
            # Bound outbound context and cost. Larger dictionaries still get exact
            # lemma/sense reuse at publication, including words outside this window.
            entries=list(current.entries.filter(entry_type='word',archived=False).exclude(word='').select_related('current_text','current_meaning').order_by('-created_at')[:200])
            ids=[]; context_size=0
            for e in entries:
                if not e.current_text or e.current_text.status!='accepted' or len(e.meaning)>300:
                    continue
                size=len(e.word)+len(e.meaning)
                if context_size+size>24000: break
                context_size+=size
                ids.extend(c.pk for c in [e.current_text,e.current_meaning] if c and c.status=='accepted')
            if source: ids.append(source.pk)
            study.sources.set(ids)
            event(current,request.user,'capture_started',detail=f'OpenAI photo/description/vocabulary consent; attempt {study.pk}')
            return url(study)
        try:
            result=submit_once(request,dictionary,f'capture:{image_id}:{previous.pk if previous else "new"}',create)
        except (Conflict,OSError) as exc:
            if isinstance(exc,OSError): exc=Conflict('The picture file is unavailable. Choose a picture again.')
            if 'application/json' in request.headers.get('Accept',''): return fail(request,exc,409)
            form.add_error(None,str(exc))
        else:
            request.session[f'capture-{pk}']={key:form.cleaned_data[key] for key in ['input_mode','input_language','voice']}
            return saved(request,result)
    recent=PictureCapture.objects.filter(dictionary=dictionary,user=request.user,expires_at__gt=timezone.now()).exclude(status='discarded').order_by('-created_at')[:8]
    prices=config[3] if config else {'input':0,'output':0}
    estimate=capture_limits.unit_estimate(prices)
    return render(request,'community_dictionary/capture_start.html',context(request,dictionary,form=form,image=image,previous=previous,
        recent=recent,setup_error=setup_error,estimate=estimate,personal=config[2] if config else False,
        counts=capture_limits.usage(dictionary,request.user),
        submission_id=request.POST.get('submission_id') or context(request)['submission_id']))

@login_required
def detail(request,pk,study_id,vocabulary=None):
    study=own(request,pk,study_id)
    try: capture.allowed(study)
    except Conflict as exc: return fail(request,exc,409)
    if study.status=='saved' and study.saved_entry_id:
        if (not study.saved_entry.current_text or study.saved_entry.current_text.provenance.get('capture_id')!=str(study.pk) or
            study.saved_entry.word!=study.result.get('sentence') or study.saved_entry.meaning!=study.result.get('translation')):
            return redirect(entry_url(study.saved_entry))
    if vocabulary is None and study.status=='ready':
        vocabulary=VocabularyForms(initial=study.result.get('words',[]),
            sentence=study.result.get('sentence',''),prefix='words')
    pending=study.speech.filter(status__in=['waiting','running']).exists()
    feedback=study.speech.filter(kind='feedback',status='ready').exclude(file_path='').first()
    next_image=None
    if study.source_image_id:
        used=Contribution.objects.filter(entry__dictionary_id=pk,entry__entry_type='sentence',
            entry__archived=False,kind='image',status='accepted',entry__current_text__status='accepted'
        ).exclude(entry__word='').exclude(shared_from=None).values('shared_from_id')
        next_image=Contribution.objects.filter(entry__dictionary_id=pk,entry__archived=False,entry__entry_type='word',
            kind='image',status='accepted').exclude(pk__in=used).order_by('created_at','pk').first()
    from .lexicon import word_row
    word_rows=[]; language_check=None
    if study.saved_entry_id:
        sentence_data=capture.sentence_context(study.saved_entry)
        word_rows=sentence_data['sentence_words']; language_check=sentence_data['language_check']
    sentence_row=word_row(study.saved_entry,study.dictionary) if study.saved_entry_id else None
    # A failed attempt is historical, but the shared word may now have a valid
    # replacement (manual TTS or human audio). Use the same current recordings as
    # the displayed rows; never promote a private preview or pending contribution.
    recovered={row['entry'].pk for row in [sentence_row,*word_rows] if row and row['audio']}
    failed_audio=[clip for clip in study.speech.filter(status='failed') if clip.entry_id not in recovered]
    for clip in failed_audio:
        clip.failure_reason=tts.failure_message(clip.report)
    return render(request,'community_dictionary/capture_detail.html',context(request,study.dictionary,study=study,
        pending=pending,feedback=feedback,next_image=next_image,vocabulary=vocabulary,word_rows=word_rows,language_check=language_check,
        sentence_row=sentence_row,
        failed_audio=failed_audio,running_audio=study.speech.filter(status='running'),
        auto_process=study.status=='waiting' or study.speech.filter(kind='feedback',status='waiting').exists()))

@login_required
@require_POST
def action(request,pk,study_id):
    study=own(request,pk,study_id)
    try:
        choice=request.POST.get('action')
        if choice=='process':
            if study.status=='waiting': capture.prepare(study.pk)
            else:
                clip=study.speech.filter(status='waiting').order_by('pk').first()
                if clip: capture.speak(clip.pk)
        elif choice=='add-word':
            if study.status!='ready': raise Conflict('Prepare a suggestion first.')
            data=request.POST.copy()
            try: count=int(data.get('words-TOTAL_FORMS','0'))
            except ValueError: raise Conflict('Reload the vocabulary form.')
            from .capture_vocabulary import MAX_EDITED_WORDS
            data['words-TOTAL_FORMS']=str(min(max(count,0)+1,MAX_EDITED_WORDS))
            forms=VocabularyForms(data,initial=study.result.get('words',[]),sentence=study.result.get('sentence',''),prefix='words')
            return detail(request,pk,study_id,vocabulary=forms)
        elif choice=='confirm':
            if request.POST.get('permission')!='yes': raise Conflict('Confirm your permission to share this contribution.')
            forms=None
            if any(key.startswith('words-') for key in request.POST) and study.status!='saved':
                forms=VocabularyForms(request.POST,initial=study.result.get('words',[]),
                    sentence=study.result.get('sentence',''),prefix='words')
                if not forms.is_valid():
                    return detail(request,pk,study_id,vocabulary=forms)
            capture.publish(study.pk,request.user,vocabulary=forms)
        elif choice=='discard':
            with transaction.atomic():
                capture.locks(); capture.discard(PictureCapture.objects.filter(pk=study.pk,user=request.user))
            return redirect('community_dictionary:capture-start',pk=pk)
        else: raise Conflict('Choose an action shown on this page.')
        return saved(request,url(study))
    except Conflict as exc: return fail(request,exc,409)

@login_required
def media(request,pk,study_id,kind):
    study=own(request,pk,study_id)
    try: capture.allowed(study)
    except Conflict: raise Http404
    if kind=='picture': relative,mime=study.file_path,'image/jpeg'
    elif kind=='feedback':
        clip=get_object_or_404(study.speech,kind='feedback',status='ready')
        relative,mime=clip.file_path,'audio/wav'
    else: raise Http404
    if not relative: raise Http404
    return private_media_response(request,relative,mime,'capture-preview')

@login_required
def attention(request,pk):
    dictionary=get_dictionary(request.user,pk)
    reports=AttentionReport.objects.filter(entry__dictionary=dictionary,entry__archived=False,
        note__entry__dictionary=dictionary,note__status='accepted',resolved_at__isnull=True).select_related('entry','note__author','note')
    unchecked=dictionary.entries.filter(archived=False,current_text__provenance__origin='picture-description').select_related('current_text')
    checked=LanguageCheck.objects.filter(entry__dictionary=dictionary,text_id=F('entry__current_text_id'),meaning_id=F('entry__current_meaning_id')).values('entry_id')
    return render(request,'community_dictionary/attention.html',context(request,dictionary,reports=reports,
        unchecked=unchecked.exclude(pk__in=checked).order_by('-created_at')[:100]))

@login_required
@require_POST
def flag(request,pk,entry_id):
    dictionary=get_dictionary(request.user,pk)
    def create(paths):
        entry=get_entry(dictionary,entry_id)
        body=request.POST.get('reason','').strip()[:1000] or 'Please check this entry.'
        note=Contribution.objects.create(entry=entry,author=request.user,controlled_by=request.user,kind='note',status='accepted',
            body=body,label='Needs attention')
        # If the referenced wording or picture is withdrawn, hide the report too.
        for part in [entry.current_text,entry.current_meaning,entry.selected_image]:
            if part: ContributionDependency.objects.get_or_create(source=part,derived=note)
        AttentionReport.objects.create(entry=entry,note=note)
        event(dictionary,request.user,'flag_attention',entry)
        return entry_url(entry)
    try: return redirect(submit_once(request,dictionary,f'attention:{entry_id}',create))
    except Conflict as exc: return fail(request,exc,409)

@login_required
@require_POST
@transaction.atomic
def checked(request,pk,entry_id):
    capture.locks(); dictionary=get_dictionary(request.user,pk); require_editor(request.user,dictionary)
    entry=get_entry(dictionary,entry_id)
    if str(entry.current_text_id)!=request.POST.get('text_id') or str(entry.current_meaning_id or '')!=request.POST.get('meaning_id',''):
        return fail(request,'The wording changed. Read the latest entry before marking it checked.',409)
    if not entry.current_text_id: return fail(request,'Add the wording first.',409)
    LanguageCheck.objects.create(entry=entry,text=entry.current_text,meaning=entry.current_meaning,checked_by=request.user)
    AttentionReport.objects.filter(entry=entry,note__entry=entry,resolved_at__isnull=True).update(resolved_at=timezone.now(),resolved_by=request.user)
    event(dictionary,request.user,'language_checked',entry)
    messages.success(request,'Current wording marked as linguistically checked.')
    return redirect('community_dictionary:attention',pk=pk)
