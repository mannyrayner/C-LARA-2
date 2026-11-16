"""Small bilingual-check form, advisory preview and explicit publication approval."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, gettext
from django.views.decorators.http import require_GET, require_POST
from . import capture, capture_limits, improve, refresh
from .models import PictureCapture
from .permissions import get_dictionary, require_editor
from .services import Conflict, submit_once
from .views import context, fail, get_entry, saved
from .refresh_views import private


class CheckForm(forms.Form):
    notes=forms.CharField(required=False,max_length=1000,label=_('Anything you would like changed?'),
        widget=forms.Textarea(attrs={'rows':2,'placeholder':_('Optional: describe an improvement or a word you want to keep.')}))
    permission=forms.BooleanField(label=_('I approve the estimate and may send these descriptions, picture and recent edits to OpenAI for a suggestion.'))
    quote=forms.CharField(max_length=16000,widget=forms.HiddenInput)


class ApplyForm(forms.Form):
    word=forms.CharField(max_length=255,widget=forms.Textarea(attrs={'rows':2,'dir':'auto'}))
    meaning=forms.CharField(max_length=3000,widget=forms.Textarea(attrs={'rows':3,'dir':'auto'}))
    choice=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    permission=forms.BooleanField(label=_('Update the words and audio too. I approve the estimate and the existing provider permissions.'))


def location(study):
    return reverse('community_dictionary:improve-detail',args=[study.dictionary_id,study.pk])


@login_required
def start(request,pk,entry_id):
    dictionary=get_dictionary(request.user,pk);require_editor(request.user,dictionary)
    entry=get_entry(dictionary,entry_id);form=CheckForm(request.POST or None)
    quote=None;error=''
    try:
        quote=improve.quote_values(request.user,entry)
        if request.method=='POST' and form.is_valid():
            def create(paths):
                capture.locks();get_user_model().objects.select_for_update().get(pk=request.user.pk)
                current=get_entry(get_dictionary(request.user,pk),entry_id)
                try:approved=signing.loads(form.cleaned_data['quote'],salt=improve.SALT,max_age=600)
                except signing.BadSignature:raise Conflict(_('This estimate expired. Review a fresh estimate.'))
                if approved!=improve.quote_values(request.user,current):
                    raise Conflict(_('The sentence or settings changed. Review a fresh estimate.'))
                return location(improve.create(request.user,current,form.cleaned_data['notes']))
            return saved(request,submit_once(request,dictionary,f'improve:{entry.pk}',create))
    except (Conflict,OSError) as exc:error=str(exc)
    if not form.is_bound and quote:form=CheckForm(initial={'quote':signing.dumps(quote,salt=improve.SALT)})
    return private(render(request,'community_dictionary/improve_start.html',context(request,dictionary,
        entry=entry,form=form,setup_error=error,
        estimate=improve.check_estimate(quote['policy']['rates']) if quote else None)))


def own(request,pk,study_id,lock=False):
    dictionary=get_dictionary(request.user,pk);require_editor(request.user,dictionary)
    queryset=PictureCapture.objects.select_for_update() if lock else PictureCapture.objects
    study=get_object_or_404(queryset,pk=study_id,dictionary=dictionary,user=request.user,
        expires_at__gt=timezone.now(),input_mode__in=['improve','refresh'])
    if 'improve' not in study.result:
        from django.http import Http404
        raise Http404
    capture.allowed(study)
    return dictionary,study


@login_required
@require_GET
def detail(request,pk,study_id):
    try:
        dictionary,study=own(request,pk,study_id)
        if study.input_mode=='refresh':return redirect('community_dictionary:refresh-detail',pk=pk,study_id=study.pk)
        improve.recover(study);entry=improve.validate(study)
    except Conflict as exc:return fail(request,exc,409)
    review=study.result['improve'].get('review',{})
    choices=review.get('options',[])
    if not choices and study.status=='ready':
        choices=[{'sentence':entry.word,'translation':entry.meaning,'basis':''}]
    proposals=[]
    for i,option in enumerate(choices):
        form=ApplyForm(initial={'word':option['sentence'],'meaning':option['translation'],'choice':i},auto_id=f'improve-{i}-%s')
        form.fields['word'].label=dictionary.language
        form.fields['meaning'].label=dictionary.explanation_language or 'English'
        proposals.append({'form':form,'basis':option['basis'],'has_suggestion':bool(review.get('options'))})
    return private(render(request,'community_dictionary/improve_detail.html',context(request,dictionary,
        study=study,entry=entry,review=review,proposals=proposals,
        estimate=capture_limits.unit_estimate(study.result['improve']['consent']['policy']['rates']),
        polling=study.status in {'waiting','processing'})))


@login_required
@require_POST
def action(request,pk,study_id):
    try:
        def update(paths):
            capture.locks();dictionary,study=own(request,pk,study_id,lock=True)
            if study.input_mode=='refresh':return reverse('community_dictionary:refresh-detail',args=[pk,study.pk])
            choice=request.POST.get('action')
            if choice=='continue':
                transaction.on_commit(lambda:improve.queue(study.pk));return location(study)
            if choice=='keep':
                study.status='discarded';study.save(update_fields=['status'])
                return reverse('community_dictionary:entry',args=[pk,study.saved_entry_id])
            if choice!='apply':raise Conflict(_('Choose an action shown on this page.'))
            form=ApplyForm(request.POST)
            if not form.is_valid():raise Conflict(form.errors.as_text())
            improve.apply(study,request.user,form.cleaned_data['word'],form.cleaned_data['meaning'],form.cleaned_data['choice'])
            return reverse('community_dictionary:refresh-detail',args=[pk,study.pk])
        dictionary=get_dictionary(request.user,pk);require_editor(request.user,dictionary)
        return saved(request,submit_once(request,dictionary,f'improve-apply:{study_id}',update))
    except Conflict as exc:return fail(request,exc,409)
