"""Owner-facing batch descriptions and a deliberately small rename form."""
import uuid
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from . import batch_descriptions
from .models import Dictionary, LanguagePort
from .permissions import get_dictionary, require_owner
from .port_views import run_url, no_store
from .services import Conflict, event
from .views import context, fail
from .voices import VOICE_CHOICES, DEFAULT_VOICE


class BatchForm(forms.Form):
    submission_id=forms.UUIDField(widget=forms.HiddenInput)
    image_status=forms.ChoiceField(label='Pictures to include',choices=[
        ('both','Accepted and awaiting review'),('accepted','Accepted only'),('pending','Awaiting review only')],initial='both')
    voice=forms.ChoiceField(label='Voice for sentence and word audio',choices=VOICE_CHOICES,initial=DEFAULT_VOICE)


class RenameForm(forms.Form):
    name=forms.CharField(label='Dictionary name',max_length=160,widget=forms.TextInput(attrs={'id':'id_dictionary_name'}))


@login_required
@require_http_methods(['GET','POST'])
def start(request,pk):
    dictionary=get_dictionary(request.user,pk);require_owner(request.user,dictionary)
    port=LanguagePort.objects.filter(source=dictionary,user=request.user,is_description_batch=True).first()
    form=BatchForm(request.POST or None,initial={'submission_id':uuid.uuid4(),'voice':port.voice if port else DEFAULT_VOICE})
    if request.method=='POST' and form.is_valid():
        try:
            run=batch_descriptions.quote(request.user,dictionary,**{
                'token':form.cleaned_data['submission_id'],'image_status':form.cleaned_data['image_status'],
                'voice':form.cleaned_data['voice']})
            return redirect(run_url(run))
        except Conflict as exc:form.add_error(None,str(exc))
    return no_store(render(request,'community_dictionary/batch_start.html',context(request,dictionary,
        form=form,port=port,runs=port.runs.all()[:20] if port else [])))


@login_required
@require_POST
@transaction.atomic
def rename(request,pk):
    get_object_or_404(Dictionary.objects.select_for_update(),pk=pk)
    dictionary=get_dictionary(request.user,pk);require_owner(request.user,dictionary)
    form=RenameForm(request.POST)
    if not form.is_valid():return fail(request,'Enter a dictionary name of at most 160 characters.',400)
    if dictionary.name != form.cleaned_data['name']:
        dictionary.name=form.cleaned_data['name'];dictionary.save(update_fields=['name'])
        event(dictionary,request.user,'rename_dictionary')
    messages.success(request,'Dictionary renamed.')
    return redirect('community_dictionary:settings',pk=pk)
