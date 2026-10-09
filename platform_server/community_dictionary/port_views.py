"""Owner-only language porting, explicit cost approval, and private review."""
import uuid
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.utils import timezone
from django.utils.html import format_html

from projects.billing import get_user_balance_usd
from . import porting, port_tasks, port_vocabulary
from .models import Contribution, LanguagePort, PortEntryLink, PortItem, PortRun
from .permissions import get_dictionary, require_owner
from .port_forms import PortForm, PortApproveForm, PortReviewForm, PortAttentionForm
from .services import Conflict
from .views import context, fail, private_media_response


def run_url(run):
    return reverse('community_dictionary:port-run',args=[run.port.source_id,run.pk])


def results_url(run, attention=False, page=None):
    query = {'attention':'1'} if attention else {}
    if page and str(page).isdigit():
        query['page'] = str(page)
    return run_url(run) + ('?' + urlencode(query) if query else '')


def review_url(run, item, attention=False):
    return reverse('community_dictionary:port-review', args=[run.port.source_id, run.pk, item.pk]) + ('?attention=1' if attention else '')


def next_review_url(run, item, attention=False):
    """Move across result pages, skipping saved, set-aside and stale previews."""
    pending = run.items.filter(status__in=['ready', 'unclear'], invalidated=False,
                               needs_attention=attention).exclude(pk=item.pk)
    for group in [pending.filter(pk__gt=item.pk), pending.filter(pk__lt=item.pk)]:
        for candidate in group:
            candidate.run = run
            try:
                porting.current_item(candidate)
            except (Conflict, Http404):
                continue
            return review_url(run, candidate, attention)
    return results_url(run, attention)


def saved_entry(item):
    """Use current authorised content, never the retained translation snapshot."""
    if item.status != 'saved' or item.invalidated or item.source_entry.archived:
        return None
    if item.run.stage == 'vocabulary':
        try:
            porting.authority(item.run.port)
            return item.source_entry if port_vocabulary.sentence_snapshot(item.source_entry) == item.snapshot['sentence'] else None
        except (Conflict,Http404):
            return None
    if porting.snapshot(item.source_entry, sentence_only=item.snapshot.get('sentence_only',False)) != item.snapshot:
        return None
    link = PortEntryLink.objects.filter(port=item.run.port, source=item.source_entry,
        destination__dictionary_id=item.run.port.destination_id,
        destination__archived=False, destination__current_text__status='accepted').select_related(
            'destination__current_text').first()
    return link.destination if link and link.destination.word else None


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
    attention_only = request.GET.get('attention') == '1'
    attention_count = run.items.filter(needs_attention=True).count()
    items = run.items.filter(needs_attention=True) if attention_only else run.items.all()
    page = Paginator(items.select_related('source_entry__dictionary', 'source_entry__current_text',
        'source_entry__current_meaning', 'source_entry__current_category'),20).get_page(request.GET.get('page'))
    for item in page:
        item.run = run
        item.preview_available = False
        item.saved_entry = saved_entry(item)
        item.attention_available = bool(item.saved_entry)
        if item.status in ['ready','unclear']:
            try:
                porting.current_item(item)
                item.preview_available = True
                item.attention_available = True
            except (Conflict,Http404):
                pass
        # Stale/withdrawn results reveal neither source nor translated wording.
        item.safe_label = f'Entry {item.source_entry_id}'
        if item.saved_entry:
            item.safe_label = item.saved_entry.word
        elif item.preview_available:
            item.safe_label = item.source_entry.word
            if item.result.get('word') and item.result['word'] != item.source_entry.word:
                item.safe_label += ' → ' + item.result['word']
    return no_store(render(request,'community_dictionary/port_run.html',context(request,run.port.source,
        run=run,counts=counts,page=page,balance=balance,
        bulk_count=run.items.filter(status='ready',invalidated=False,needs_attention=False).count(),
        speech_counts={s:run.speech.filter(status=s).count() for s in ['waiting','queued','running','ready','failed','discarded']},
        review_count=counts['ready'] + counts['unclear'],
        first_review=run.items.filter(status__in=['ready','unclear'], invalidated=False).first(),
        sentence_count=run.items.filter(snapshot__entry_type='sentence').count(),
        attention_only=attention_only,attention_count=attention_count,
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
        elif action == 'accept-all':
            if request.POST.get('accept_all') != 'on':
                return fail(request,'Confirm acceptance of the remaining suggestions.',400)
            saved, skipped = porting.accept_remaining(request.user,run.pk)
            messages.success(request,f'Accepted {saved} results. {skipped} changed results were skipped; flagged or failed results are left for you.')
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
    attention_only = request.GET.get('attention') == '1'
    try:
        run = owned_run(request,pk,run_id)
        item = get_object_or_404(PortItem,pk=item_id,run=run)
        item.run = run
        if item.status not in ['ready','unclear']:
            return redirect(next_review_url(run,item,attention_only))
        source, link = porting.current_item(item)
        if run.stage == 'vocabulary':
            return vocabulary_review(request,run,item,source,attention_only)
        operation = request.POST.get('action','save')
        if request.method == 'POST' and operation == 'discard':
            with transaction.atomic():
                porting.locks()
                item = PortItem.objects.select_for_update(of=('self',)).get(pk=item.pk)
                item.run = run
                porting.current_item(item)
                if item.status in ['ready','unclear']:
                    porting.clear_preview(item,'Discarded by reviewer.')
            return redirect(next_review_url(run,item,attention_only))
        if request.method == 'POST' and operation not in ['save','flag']:
            return fail(request,'Unknown action.',400)
        change_target = not porting.same_language(run.source_language,run.port.language)
        change_explanation = not porting.same_language(run.source_explanation_language,run.port.explanation_language)
        initial = {**item.result, **item.review_values,
                   'needs_attention':item.needs_attention,'attention_note':item.attention_note}
        if not change_target:
            initial['word'] = source.word
        if not change_explanation:
            initial['meaning'] = source.meaning
        if 'category' not in item.review_values:
            initial['category'] = initial.get('category') or source.category
        form = PortReviewForm(request.POST if request.method == 'POST' else None,initial=initial,
                              change_target=change_target,change_explanation=change_explanation, entry_type=source.entry_type)
        if operation == 'flag':
            form.fields['word'].required = False
        if request.method == 'POST' and form.is_valid():
            if operation == 'flag':
                with transaction.atomic():
                    porting.locks()
                    locked = PortItem.objects.select_for_update(of=('self',)).get(pk=item.pk)
                    locked.run = run
                    porting.current_item(locked)
                    if locked.status not in ['ready','unclear']:
                        raise Conflict('This result is no longer available for review.')
                    locked.needs_attention = True
                    locked.attention_note = form.cleaned_data['attention_note']
                    locked.review_values = {key:form.cleaned_data[key] for key in ['word','meaning','category']}
                    locked.save(update_fields=['needs_attention','attention_note','review_values'])
                messages.success(request,'Flagged for later. Your edits are kept; this result has not been saved to the dictionary.')
            else:
                entry = porting.save_item(request.user,item.pk,form.cleaned_data)
                destination_url = reverse('community_dictionary:entry',args=[entry.dictionary_id,entry.pk])
                messages.success(request,format_html('Saved “{}”. <a href="{}">Open saved entry</a>.',entry.word,destination_url))
                if change_target and (form.cleaned_data['word'] != item.result.get('word') or
                    form.cleaned_data['meaning'] != item.result.get('meaning') and
                    item.result.get('tts_synthesis',{}).get('english_homographs') or
                    not (item.file_path or item.result.get('reused_audio'))):
                    messages.info(request,'Use Create audio on the saved entry to generate speech for the revised wording.')
            return redirect(next_review_url(run,item,attention_only))
        remaining = run.items.filter(status__in=['ready','unclear'],invalidated=False,
                                     needs_attention=attention_only).count()
        return no_store(render(request,'community_dictionary/port_review.html',context(request,run.port.source,
            run=run,item=item,source=source,form=form,change_target=change_target,
            attention_only=attention_only,results_url=results_url(run,attention_only),remaining=remaining)))
    except Conflict as exc:
        return fail(request,exc,409)


@login_required
@require_POST
def attention(request,pk,run_id,item_id):
    """Explicit set/clear, safe to retry, for already saved results."""
    try:
        with transaction.atomic():
            porting.locks()
            run = owned_run(request,pk,run_id)
            item = get_object_or_404(PortItem.objects.select_for_update(of=('self',)),pk=item_id,run=run)
            item.run = run
            if not saved_entry(item):
                raise Conflict('This saved entry is no longer available here.')
            operation = request.POST.get('action')
            form = PortAttentionForm(request.POST)
            if operation not in ['flag','clear'] or not form.is_valid():
                return fail(request,'Use a note of at most 500 characters and a valid flag action.',400)
            item.needs_attention = operation == 'flag'
            item.attention_note = form.cleaned_data['attention_note'] if item.needs_attention else ''
            item.save(update_fields=['needs_attention','attention_note'])
        messages.success(request,'Flagged for attention.' if item.needs_attention else 'Attention flag cleared.')
        return redirect(results_url(run,request.GET.get('attention') == '1',request.GET.get('page')))
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


@login_required
@require_http_methods(['GET','POST'])
def vocabulary_start(request,pk,port_id):
    port=get_object_or_404(LanguagePort.objects.select_related('source','destination','user'),
        pk=port_id,source_id=pk,user=request.user)
    try:
        port_vocabulary.authority(port)
        if request.method=='POST':
            run=port_vocabulary.quote(request.user,port,uuid.UUID(request.POST.get('submission_id','')))
            return redirect(run_url(run))
    except (Conflict,ValueError) as exc:
        return fail(request,exc,409)
    return no_store(render(request,'community_dictionary/port_vocabulary_start.html',context(request,port.destination,
        port=port,previous=port.runs.filter(stage='vocabulary').first())))


def vocabulary_review(request,run,item,source,attention_only):
    from .capture_forms import VocabularyForms
    from .port_tasks import dispatch
    operation=request.POST.get('action','save')
    if request.method=='POST' and operation=='discard':
        with transaction.atomic():
            porting.locks()
            locked=PortItem.objects.select_for_update().get(pk=item.pk)
            locked.run=run;porting.current_item(locked)
            if locked.status=='ready':
                porting.clear_preview(locked,'Discarded by reviewer.')
            transaction.on_commit(lambda:dispatch(str(run.pk)))
        return redirect(next_review_url(run,item,attention_only))
    initial=item.review_values.get('words',item.result.get('words',[]))
    data=request.POST if request.method=='POST' else None
    if operation=='add-word' and data is not None:
        data=data.copy()
        try:count=int(data.get('words-TOTAL_FORMS','0'))
        except ValueError:count=0
        data['words-TOTAL_FORMS']=str(min(12,max(0,count)+1))
    vocabulary=VocabularyForms(data,initial=initial,prefix='words',sentence=source.word)
    note=request.POST.get('attention_note',item.attention_note)[:500]
    if request.method=='POST' and operation in ['save','flag'] and vocabulary.is_valid():
        if operation=='flag':
            with transaction.atomic():
                porting.locks()
                locked=PortItem.objects.select_for_update().get(pk=item.pk)
                locked.run=run;porting.current_item(locked)
                if locked.status!='ready':raise Conflict('This result is no longer awaiting review.')
                locked.needs_attention=True;locked.attention_note=note
                locked.review_values={'words':vocabulary.words()}
                locked.save(update_fields=['needs_attention','attention_note','review_values'])
            messages.success(request,'Flagged for later. Your word edits are kept.')
        else:
            entry=port_vocabulary.save_item(request.user,item.pk,vocabulary.words())
            messages.success(request,f'Vocabulary saved for “{entry.word}”. Missing word audio is queued.')
        return redirect(next_review_url(run,item,attention_only))
    if request.method=='POST' and operation not in ['save','flag','add-word']:
        return fail(request,'Unknown action.',400)
    return no_store(render(request,'community_dictionary/port_vocabulary_review.html',context(request,run.port.source,
        run=run,item=item,source=source,vocabulary=vocabulary,vocabulary_open=True,attention_note=note,
        results_url=results_url(run,attention_only),
        remaining=run.items.filter(status='ready',invalidated=False,needs_attention=attention_only).count())))
