"""Owner-only language porting, explicit cost approval, and private review."""
import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.utils import timezone

from projects.billing import get_user_balance_usd
from . import porting, port_tasks
from .models import Contribution, LanguagePort, PortItem, PortRun
from .permissions import get_dictionary, require_owner
from .port_forms import PortForm, PortApproveForm, PortReviewForm
from .services import Conflict
from .views import context, fail, private_media_response


def run_url(run):
    return reverse('community_dictionary:port-run',args=[run.port.source_id,run.pk])


def owned_run(request,pk,run_id):
    run = get_object_or_404(PortRun.objects.select_related('port__source','port__destination','port__user'),
                           pk=run_id,port__source_id=pk,port__user=request.user)
    porting.authority(run.port)
    return run


def no_store(response):
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@require_http_methods(['GET','POST'])
def start(request,pk,port_id=None):
    source = get_dictionary(request.user,pk)
    require_owner(request.user,source)
    port = get_object_or_404(LanguagePort,pk=port_id,source=source,user=request.user) if port_id else None
    if port:
        try:
            porting.authority(port)
            if request.method == 'POST':
                token = uuid.UUID(request.POST.get('submission_id',''))
                run = porting.quote(request.user,source,{},token,port=port)
                return redirect(run_url(run))
        except (Conflict,ValueError) as exc:
            return fail(request,exc,409)
    initial = {'submission_id':uuid.uuid4(),'name':source.name+' · new language',
               'language':source.language,'explanation_language':source.explanation_language or 'English'}
    form = PortForm(request.POST or None,initial=initial)
    form.source = source
    if not port and request.method == 'POST' and form.is_valid():
        data = {k:form.cleaned_data[k] for k in ['name','language','explanation_language','voice']}
        try:
            run = porting.quote(request.user,source,data,form.cleaned_data['submission_id'])
            return redirect(run_url(run))
        except Conflict as exc:
            form.add_error(None,str(exc))
    return no_store(render(request,'community_dictionary/port_start.html',context(request,source,form=form,
        port=port,ports=source.language_ports.filter(user=request.user).select_related('destination'))))


@login_required
@require_GET
def detail(request,pk,run_id):
    try:
        run = owned_run(request,pk,run_id)
    except Conflict as exc:
        return fail(request,exc,409)
    balance = get_user_balance_usd(request.user) if run.payer == 'credits' else None
    counts = {status:run.items.filter(status=status).count() for status in
              ['waiting','queued','running','ready','unclear','failed','saved','discarded']}
    page = Paginator(run.items.select_related('source_entry'),20).get_page(request.GET.get('page'))
    for item in page:
        item.preview_available = False
        if item.status in ['ready','unclear']:
            try:
                porting.current_item(item)
                item.preview_available = True
            except (Conflict,Http404):
                pass
        # Stale/withdrawn results reveal neither source nor translated wording.
        item.safe_label = f'Entry {item.source_entry_id}'
        if item.preview_available:
            item.safe_label = item.source_entry.word
            if item.result.get('word') and item.result['word'] != item.source_entry.word:
                item.safe_label += ' → ' + item.result['word']
    return no_store(render(request,'community_dictionary/port_run.html',context(request,run.port.source,
        run=run,counts=counts,page=page,balance=balance,
        enough_funds=balance is None or balance >= run.allowance_usd,
        expired=run.expires_at <= timezone.now(),approve_form=PortApproveForm(),
        uncertain=run.items.filter(uncertain_cost=True).exists())))


@login_required
@require_POST
def action(request,pk,run_id):
    # Cancellation remains available to the payer even if membership was revoked.
    run = get_object_or_404(PortRun,pk=run_id,port__source_id=pk,port__user=request.user)
    action = request.POST.get('action')
    try:
        if action == 'cancel':
            porting.cancel(request.user,run.pk)
        elif action == 'resume':
            port_tasks.resume(request.user,run.pk)
        elif action == 'approve':
            form = PortApproveForm(request.POST)
            if not form.is_valid():
                return fail(request,'Confirm permission and the displayed cost before starting.',400)
            porting.approve(request.user,run.pk)
        else:
            return fail(request,'Unknown action.')
    except Conflict as exc:
        return fail(request,exc,409)
    return redirect(run_url(run))


@login_required
@require_http_methods(['GET','POST'])
def review(request,pk,run_id,item_id):
    try:
        run = owned_run(request,pk,run_id)
        item = get_object_or_404(PortItem.objects.select_related('run__port__source','run__port__destination','run__port__user'),pk=item_id,run=run)
        if item.status not in ['ready','unclear']:
            return redirect(run_url(run))
        source, link = porting.current_item(item)
        if request.method == 'POST' and request.POST.get('action') == 'discard':
            with transaction.atomic():
                porting.locks()
                item = PortItem.objects.select_for_update(of=('self',)).get(pk=item.pk)
                if item.status in ['ready','unclear']:
                    porting.clear_preview(item,'Discarded by reviewer.')
            return redirect(run_url(run))
        change_target = not porting.same_language(run.source_language,run.port.language)
        change_explanation = not porting.same_language(run.source_explanation_language,run.port.explanation_language)
        initial = dict(item.result)
        if not change_target:
            initial['word'] = source.word
        if not change_explanation:
            initial['meaning'] = source.meaning
        initial['category'] = initial.get('category') or source.category
        form = PortReviewForm(request.POST or None,initial=initial,
                              change_target=change_target,change_explanation=change_explanation)
        if request.method == 'POST' and form.is_valid():
            changed_word = form.cleaned_data['word'] != item.result['word']
            entry = porting.save_item(request.user,item.pk,form.cleaned_data)
            messages.success(request,'Entry saved.' + (' Use Create audio on the saved entry to generate speech for your wording.' if changed_word or item.status == 'unclear' else ''))
            return redirect(run_url(run))
        return no_store(render(request,'community_dictionary/port_review.html',context(request,run.port.source,
            run=run,item=item,source=source,form=form,change_target=change_target)))
    except Conflict as exc:
        return fail(request,exc,409)


@login_required
@require_GET
def media(request,pk,run_id,item_id,kind):
    try:
        run = owned_run(request,pk,run_id)
        item = get_object_or_404(PortItem.objects.select_related('run__port__source','run__port__destination','run__port__user'),pk=item_id,run=run,status__in=['ready','unclear'])
        porting.current_item(item)
        if kind == 'audio' and item.file_path:
            return private_media_response(request,item.file_path,'audio/wav','ported-audio')
        if kind == 'audio' and item.result.get('reused_audio'):
            recording = get_object_or_404(Contribution,
                pk=item.result['reused_audio'],entry__dictionary=run.port.destination,kind='audio',status='accepted')
            return private_media_response(request,recording.file_path,recording.mime_type,'ported-audio')
        if kind == 'image' and item.snapshot.get('image'):
            picture = item.sources.get(pk=item.snapshot['image'])
            return private_media_response(request,picture.file_path,picture.mime_type,'source-picture')
    except Conflict:
        raise Http404
    raise Http404
