"""Phone-friendly, independent provider evaluation under Evaluate."""
from collections import Counter
import csv
import io
import json
import os
from pathlib import Path
import uuid

from django import forms
from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from . import audio_evaluation as study, evaluation as ev, google_tts, homograph_experiments as exp, porting, tts
from .evaluation_views import page, context, competence_display, csv_cell
from .models import EvaluationItem, EvaluationRating, EvaluationSession, EvaluationSet, PortRun
from .permissions import get_dictionary, require_owner
from .services import Conflict
from .views import private_media_response


class CreateForm(forms.Form):
    token = forms.UUIDField(widget=forms.HiddenInput)
    name = forms.CharField(max_length=160,initial='English word audio comparison',label=_('Study name'))
    sampling = forms.ChoiceField(label=_('Sample'),choices=[('random',_('Random dictionary vocabulary')),
        ('expressions',_('Separate challenge set: multi-word expressions')),('forms',_('Separate challenge set: sentence forms'))])
    sample_size = forms.IntegerField(min_value=1,max_value=100,initial=100,label=_('Number of items'))
    voice = forms.ChoiceField(choices=[(v,v) for v in tts.VOICE_NAMES],initial=tts.VOICE,label=_('OpenAI voice'))
    allow_visitors = forms.BooleanField(required=False,label=_('Invite signed-in visitors while public browsing is enabled'))


@page(['GET','POST'])
def start(request,pk):
    dictionary=get_dictionary(request.user,pk);require_owner(request.user,dictionary)
    if tts.language_code(dictionary.language)!='en':
        raise Conflict('The first provider evaluation study is for English dictionaries.')
    google_tts.require_access(request.user)
    form=CreateForm(request.POST if request.method=='POST' else None,initial={'token':uuid.uuid4()})
    if request.method=='POST' and form.is_valid():
        v=form.cleaned_data
        if v['allow_visitors'] and (not dictionary.public_browsing_enabled or dictionary.hidden):
            raise Conflict('Enable public browsing before inviting visitors.')
        if dictionary.evaluation_sets.filter(closed_at__isnull=True).count()>=10:
            raise Conflict('Close an existing evaluation first (maximum ten open sets).')
        run=exp.quote(request.user,dictionary,v['token'],[],1,v['voice'],comparison=True,
            sampling=v['sampling'],sample_size=v['sample_size'],study={
                'rubric':study.RUBRIC,'name':v['name'],'allow_visitors':v['allow_visitors']})
        return redirect('community_dictionary:audio-study-prepare',pk=pk,run_id=run.pk)
    return render(request,'community_dictionary/audio_study_start.html',context(request,dictionary,True,form=form))


@page(['GET','POST'])
def prepare(request,pk,run_id):
    dictionary,run=exp.owner_run(request,pk,run_id)
    if run.options.get('evaluation_study',{}).get('rubric')!=study.RUBRIC:
        raise Http404
    google_error = None
    google_checked = False
    if request.method=='POST':
        action=request.POST.get('action')
        if action in {'approve', 'check-google'}:
            if action=='approve' and request.POST.get('approve')!='on':
                raise Conflict('Approve the allowance and permission to send the selected text to the providers.')
            if run.status=='estimate':
                exp.comparison_recipes(run)
                try:
                    google_tts.check_access(request.user,run.port.language,
                        selected_voices=[run.prices['google_voices']['en'][m] for m in study.METHODS[1:]])
                    google_checked = True
                except google_tts.GoogleAccessError as exc:
                    google_error = exc
            if action=='approve' and google_error is None:
                porting.approve(request.user,run.pk)
                return redirect('community_dictionary:audio-study-prepare',pk=pk,run_id=run.pk)
        elif action=='open':
            batch=study.freeze(request.user,run)
            return redirect('community_dictionary:evaluation-set',pk=pk,set_id=batch.pk)
        elif action=='resume': exp.resume(request.user,run.pk)
        elif action=='cancel': porting.cancel(request.user,run.pk)
        else: raise Conflict('Unknown study action.')
        if action not in {'approve','check-google'}:
            return redirect('community_dictionary:audio-study-prepare',pk=pk,run_id=run.pk)
    items=list(run.items.all())
    counts=Counter(c['status'] for i in items for c in i.result.get('clips',[]))
    return render(request,'community_dictionary/audio_study_prepare.html',context(request,dictionary,True,
        run=run,total=sum(counts.values()),finished=counts['ready']+counts['failed'],failures=counts['failed'],
        planned=sum(len(i.snapshot['words']) for i in items),batch=EvaluationSet.objects.filter(pk=run.pk).first(),
        voices=[run.port.voice,*[run.prices['google_voices']['en'][m] for m in study.METHODS[1:]]],
        google_error=google_error,google_checked=google_checked,windows_host=os.name=='nt',
        google_credential_location=str(google_tts.credential_path()) if google_error else '',
        google_launcher=str(Path(__file__).resolve().parents[2]/'Connect-Google-TTS.cmd')))


class JoinForm(forms.Form):
    involvement=forms.ChoiceField(label=_('Did you help create or correct this dictionary?'),
        choices=[('',_('Choose…')),('no',_('No')),('yes',_('Yes')),('unsure',_('Not sure'))])
    prior_exposure=forms.ChoiceField(label=_('Have you heard these comparison recordings or seen their method labels before?'),
        choices=[('',_('Choose…')),('no',_('No')),('yes',_('Yes')),('unsure',_('Not sure'))])
    equipment=forms.ChoiceField(label=_('Listening equipment'),choices=[('',_('Choose…')),
        ('headphones',_('Headphones')),('speakers',_('Computer speakers')),('phone',_('Phone speaker')),('other',_('Other'))])
    consent=forms.BooleanField(label=_('I agree to share these ratings, comments and declared competences with the dictionary owner for evaluation. They are not automatically published.'))


@page(['GET','POST'])
def detail(request,pk,set_id):
    batch=get_object_or_404(EvaluationSet,pk=set_id,dictionary_id=pk,rubric=study.RUBRIC)
    dictionary,member=ev.access(request.user,pk,batch)
    attempt=batch.sessions.filter(user=request.user,evaluator_kind='human').first()
    competence=attempt.competences if attempt else ev.competence_snapshot(request.user,batch)
    form=JoinForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        study.join(request.user,batch,form.cleaned_data)
        return redirect('community_dictionary:audio-study-session',pk=pk,set_id=batch.pk)
    return render(request,'community_dictionary/audio_study_detail.html',context(request,dictionary,member,
        batch=batch,session=attempt,form=form,eligible='word_audio' in ev.eligible_dimensions(competence,'word_audio'),
        competence_rows=competence_display(competence),count=batch.items.count(),participants=batch.sessions.count()))


def get_session(request,pk,set_id):
    batch=get_object_or_404(EvaluationSet,pk=set_id,dictionary_id=pk,rubric=study.RUBRIC)
    dictionary,member=ev.access(request.user,pk,batch)
    attempt=get_object_or_404(EvaluationSession,evaluation_set=batch,user=request.user,evaluator_kind='human')
    return batch,dictionary,member,attempt


@page(['GET'])
def session(request,pk,set_id):
    batch,dictionary,member,attempt=get_session(request,pk,set_id)
    records={r.pk:r for r in batch.items.all()}
    visible=study.available(batch,records.values())
    completed=set(attempt.progress.values_list('item_id',flat=True))
    next_id=next((i for i in attempt.evaluator_metadata['item_order'] if i in visible and i not in completed),None)
    if next_id and not batch.closed_at:
        return redirect('community_dictionary:audio-study-item',pk=pk,set_id=batch.pk,item_id=next_id)
    return render(request,'community_dictionary/audio_study_session.html',context(request,dictionary,member,
        batch=batch,completed=len(completed & visible.keys()),total=len(records),unavailable=len(records)-len(visible),
        rows=[{'item':visible[i],'done':i in completed} for i in attempt.evaluator_metadata['item_order'] if i in visible]))


class RatingForm(forms.Form):
    revision=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    preference=forms.ChoiceField(label=_('Which sounds most natural and useful for learning?'),
                                choices=[('',_('Choose…')),*study.PREFERENCE])
    preferred=forms.MultipleChoiceField(required=False,widget=forms.CheckboxSelectMultiple,label=_('Preferred version(s)'))
    preference_comment=forms.CharField(max_length=1000,required=False,widget=forms.Textarea(attrs={'rows':2}),label=_('Preference comment (optional)'))

    def __init__(self,*args,clips,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['preferred'].choices=[(c['id'],label) for label,c in clips if c['status']=='ready']
        for label,clip in clips:
            if clip['status']!='ready':continue
            self.fields['score_'+clip['id']]=forms.ChoiceField(label=_('Pronunciation correctness')+' '+label,
                choices=[('',_('Choose…')),*EvaluationRating.SCORES])
            self.fields['comment_'+clip['id']]=forms.CharField(max_length=1000,required=False,
                label=_('Comment (optional)'),widget=forms.Textarea(attrs={'rows':2}))

    def clean(self):
        data=super().clean()
        chosen=data.get('preferred',[]);outcome=data.get('preference')
        if (outcome=='choose' and len(chosen)!=1) or (outcome=='tie' and len(chosen)<2):
            raise forms.ValidationError(_('Select one preferred version, or at least two for a tie.'))
        if outcome in {'none','cannot'}:
            data['preferred']=[]
        return data


@page(['GET','POST'])
def item(request,pk,set_id,item_id):
    batch,dictionary,member,attempt=get_session(request,pk,set_id)
    record=get_object_or_404(EvaluationItem,pk=item_id,evaluation_set=batch)
    if batch.closed_at:raise Conflict('This study is closed.')
    if record.pk not in study.available(batch,[record]):
        raise Conflict('This source changed or was withdrawn. Return to the study and continue.')
    clips=study.ordered_clips(attempt,record)
    progress=attempt.progress.filter(item=record).first()
    initial={'revision':progress.revision if progress else 0}
    for r in attempt.ratings.filter(unit__item=record).select_related('unit'):
        initial['score_'+r.unit.key]=r.score;initial['comment_'+r.unit.key]=r.comment
    pref=attempt.evaluator_metadata['preferences'].get(str(record.pk),{})
    initial.update(preference=pref.get('outcome',''),preferred=pref.get('choices',[]),preference_comment=pref.get('comment',''))
    form=RatingForm(request.POST if request.method=='POST' else None,clips=clips,initial=initial)
    if request.method=='POST' and form.is_valid():
        study.save(request.user,batch,record,form.cleaned_data)
        return redirect('community_dictionary:audio-study-session',pk=pk,set_id=batch.pk)
    presentation=[]
    for label,clip in clips:
        ready=clip['status']=='ready'
        presentation.append({'label':label,'id':clip['id'],'ready':ready,
            'score':form['score_'+clip['id']] if ready else None,'comment':form['comment_'+clip['id']] if ready else None})
    return render(request,'community_dictionary/audio_study_item.html',context(request,dictionary,member,
        batch=batch,item=record,word=record.snapshot['word'],form=form,clips=presentation,
        number=attempt.evaluator_metadata['item_order'].index(record.pk)+1,total=batch.items.count()))


@page(['GET'])
def media(request,pk,set_id,item_id,clip_id):
    batch,dictionary,member,attempt=get_session(request,pk,set_id)
    record=get_object_or_404(EvaluationItem,pk=item_id,evaluation_set=batch)
    if record.pk not in study.available(batch,[record]):raise Http404
    clip=next((c for _,c in study.ordered_clips(attempt,record) if c['id']==clip_id),None)
    if not clip or clip['status']!='ready' or not clip.get('path'):raise Http404
    return private_media_response(request,clip['path'],'audio/wav','recording.wav')


@page(['GET'])
def results(request,pk,set_id,format=None):
    batch=get_object_or_404(EvaluationSet,pk=set_id,dictionary_id=pk,rubric=study.RUBRIC)
    dictionary,member=ev.access(request.user,pk,batch);require_owner(request.user,dictionary)
    if not batch.closed_at:raise Conflict('Close the study after all evaluators finish before revealing methods or results.')
    data=study.results(batch)
    if format=='json':
        response=JsonResponse(data,json_dumps_params={'ensure_ascii':False,'indent':2})
        response['Content-Disposition']=f'attachment; filename="word-audio-study-{batch.pk}.json"'
        return response
    if format=='csv':
        output=io.StringIO(newline='');writer=csv.writer(output)
        columns=['set_id','cohort','sampling_seed','population_size','available_items','evaluator','item','word','meaning','kind','context','source_part','source_entry',
            'take','label','method','voice','model','recipe','carrier_recipe','attempts','status','failure','score','comment',
            'preference','preferred','complete_triplet','preference_comment','involvement','equipment','prior_exposure','competences']
        writer.writerow(columns)
        prefs={(p['evaluator'],p['item']):p for p in data['preferences']}
        for row in data['ratings']:
            p=prefs.get((row['evaluator'],row['item']),{})
            values={**row,'set_id':str(batch.pk),'cohort':data['cohort'],'sampling_seed':batch.seed,
                'population_size':len(batch.population_ids),'available_items':data['available_items'],'preference':p.get('outcome',''),
                'preferred':row['method'] in p.get('methods',[]) if p else '',
                'complete_triplet':p.get('complete_triplet',''),'preference_comment':p.get('comment','')}
            writer.writerow([csv_cell(json.dumps(values[c],ensure_ascii=False) if isinstance(values.get(c),dict) else values.get(c,'')) for c in columns])
        response=HttpResponse('\ufeff'+output.getvalue(),content_type='text/csv; charset=utf-8')
        response['Content-Disposition']=f'attachment; filename="word-audio-study-{batch.pk}.csv"'
        return response
    return render(request,'community_dictionary/audio_study_results.html',context(request,dictionary,member,batch=batch,**data))
