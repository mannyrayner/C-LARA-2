"""Selectable lemma-picture cards, bounded bulk operations and durable batch totals."""
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import uuid
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core import signing
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy

from . import lemma_images as pictures, lemma_picture_costs as costs, public_browsing as public
from .models import Entry, LemmaImage, Submission
from .permissions import get_dictionary, is_owner, require_editor
from .services import Conflict, event, submit_once
from .views import context

CARD_SALT, BATCH_SALT = 'lemma-picture-card-1', 'lemma-picture-selection-1'
MAX_SELECTED = 50


class ApprovalForm(forms.Form):
    ai_consent = forms.BooleanField(required=False, label=gettext_lazy(
        'I approve sending these accepted words and translations to OpenAI, at the estimated cost shown. Publish the pictures automatically.'))
    extra_allowance = forms.BooleanField(required=False, label=gettext_lazy(
        'Allow these selected word pictures above the normal daily image limit, for this batch only.'))


def entries(dictionary):
    return Entry.objects.filter(dictionary=dictionary, archived=False, entry_type='word').exclude(word='').filter(
        Q(current_text__isnull=True) | Q(current_text__status='accepted'),
        Q(current_meaning__isnull=True) | Q(current_meaning__status='accepted')).select_related(
            'current_text', 'current_meaning', 'lemma_image__image')


def card_rows(dictionary, user, words):
    words = list(words)
    ids = [e.pk for e in words]
    images = {}
    for part in public.contributions(dictionary).filter(entry_id__in=ids, kind='image').exclude(file_path='').order_by('-pk'):
        images.setdefault(part.entry_id, []).append(part)
    text_ids = [pk for e in words for pk in [e.current_text_id, e.current_meaning_id] if pk]
    visible_texts = set(public.contributions(dictionary).filter(pk__in=text_ids).values_list('pk', flat=True))
    rows = []
    labels = {'not_attempted': _('Not yet attempted'), 'stale': _('Picture unavailable or outdated'),
        'resource': _('Resource limit reached'), **{k:_(v) for k,v in LemmaImage._meta.get_field('status').choices}}
    for entry in words:
        entry.dictionary = dictionary
        row = getattr(entry, 'lemma_image', None)
        own = images.get(entry.pk, [])
        visible = {p.pk:p for p in own}
        valid = all(pk in visible_texts for pk in [entry.current_text_id, entry.current_meaning_id] if pk)
        for field,part in [('word',entry.current_text),('meaning',entry.current_meaning)]:
            if part and (part.entry_id!=entry.pk or part.kind!='text' or part.text_field!=field or getattr(part,field)!=getattr(entry,field)):
                valid=False
        if not valid:
            continue
        image, error, suitability = None, '', 'clue'
        if row:
            status, suitability = row.status, row.suitability
            if row.snapshot != pictures.basis(entry) or not valid:
                status = 'stale'
            elif row.status not in {'none', 'removed'}:
                image = visible.get(row.image_id)
                if row.status == 'ready' and not image:
                    status = 'stale'
            error = row.analysis.get('error', '')
            if status == 'failed' and ('Daily image limit' in error or 'Insufficient credit' in error):
                status = 'resource'
        else:
            image = visible.get(entry.selected_image_id) or (own[0] if own else None)
            status = 'ready' if image else 'not_attempted'
            if image and image.provenance.get('picture_clue') is False:
                suitability = 'illustration'
        state = hashlib.sha256(json.dumps({'basis':pictures.basis(entry),
            'revision':row.revision if row else 0, 'image': image.pk if image else None},
            ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        token = signing.dumps({'user':user.pk,'dictionary':dictionary.pk,'entry':entry.pk,'state':state}, salt=CARD_SALT)
        rows.append({'entry':entry, 'image':image, 'status':status, 'label':labels[status],
            'error':error, 'suitability':suitability, 'state':state, 'token':token,
            'valid':valid, 'busy':row is not None and (row.status=='waiting' or row.status in pictures.ACTIVE and row.updated_at>timezone.now()-timedelta(minutes=10))})
    return rows


def read_selection(request, dictionary):
    try:
        raw = request.POST.get('selected_tokens', '')
        tokens = json.loads(raw) if raw else request.POST.getlist('selection')
        if not isinstance(tokens, list) or not 1 <= len(tokens) <= MAX_SELECTED:
            raise ValueError
        result = {}
        for token in tokens:
            value = signing.loads(token, salt=CARD_SALT, max_age=7*24*3600)
            if value['user'] != request.user.pk or value['dictionary'] != dictionary.pk:
                raise ValueError
            result[int(value['entry'])] = value
        return result
    except (ValueError, TypeError, KeyError, signing.BadSignature):
        raise Conflict(_('Select between 1 and 50 word pictures. Refresh the overview if the selection expired.'))


def selected_cards(request, dictionary, values):
    words = list(entries(dictionary).filter(pk__in=values).order_by('pk'))
    cards=card_rows(dictionary,request.user,words)
    if len(cards)!=len(values):
        raise Conflict(_('Some selected words or meanings changed or are unavailable. Refresh the overview.'))
    return cards


def undo_receipt(request, dictionary, token=None):
    query = Submission.objects.filter(user=request.user, dictionary=dictionary, scope__startswith='lemma-picture-remove:')
    if token:
        try:
            query = query.filter(token=uuid.UUID(str(token)))
        except ValueError:
            return None
    for receipt in query.order_by('-created_at')[:10]:
        candidates=LemmaImage.objects.filter(entry__dictionary=dictionary, status='removed',
            analysis__bulk_removal__token=str(receipt.token)).only('revision','analysis')
        if any(row.analysis['bulk_removal']['revision']==row.revision for row in candidates):
            return receipt
    return None


def overview(request, pk):
    dictionary = get_dictionary(request.user, pk)
    require_editor(request.user, dictionary)
    action = request.POST.get('action') if request.method == 'POST' else request.GET.get('action')
    form = ApprovalForm(request.POST if request.method == 'POST' else {})
    setup_error, prices, chosen, signed = '', None, [], ''
    try:
        if not pictures.enabled(dictionary):
            raise Conflict(_('Enable AI picture generation in Settings for a supported language.'))
        prices = pictures.quote(request.user, dictionary)
    except Conflict as exc:
        setup_error = str(exc)
    def location(**extra):
        params = {k:request.POST.get(k) or request.GET.get(k) for k in ['shown','page','q','batch','undo']}
        params.update(extra)
        return reverse('community_dictionary:word-images', args=[pk])+'?'+urlencode({k:v for k,v in params.items() if v})+'#word-image-progress'
    try:
        if request.method == 'POST' and action == 'resume':
            def resume(paths):
                waiting = list(LemmaImage.objects.filter(entry__dictionary=dictionary, requested_by=request.user, status='waiting'))
                for row in waiting:
                    transaction.on_commit(lambda row=row: pictures.queue(row.pk, row.revision))
                messages.info(request, _('Queued word-picture requests have been resubmitted.') if waiting else
                    _('There are no unstarted word-picture requests to resume.'))
                return location(refresh=1)
            return redirect(submit_once(request, dictionary, 'lemma-image-resume', resume))
        if request.method == 'POST' and action == 'generate' and form.is_valid():
            if setup_error:
                raise Conflict(setup_error)
            try:
                approved = signing.loads(request.POST.get('quote',''), salt=BATCH_SALT, max_age=3600)
                if (approved['user'] != request.user.pk or approved['dictionary'] != pk or
                        approved['prices'] != prices or not 1 <= len(approved['entries']) <= MAX_SELECTED):
                    raise ValueError
            except (signing.BadSignature, ValueError, TypeError, KeyError):
                raise Conflict(_('This estimate expired or the settings changed. Preview the selected cost again.'))
            chosen = selected_cards(request, dictionary, approved['entries'])
            if not form.cleaned_data['ai_consent']:
                raise Conflict(_('Confirm AI processing and automatic publication before starting.'))
            def generate(paths):
                fresh = get_dictionary(request.user, pk); require_editor(request.user, fresh)
                cards = selected_cards(request, fresh, approved['entries'])
                if pictures.quote(request.user, fresh) != approved['prices']:
                    raise Conflict(_('Settings or prices changed. Preview the batch again.'))
                if [c['state'] for c in cards] != approved['states']:
                    raise Conflict(_('The words or meanings changed, or a word-picture attempt changed. Preview the batch again.'))
                if any(c['busy'] for c in cards):
                    raise Conflict(_('Some selected pictures are still being prepared. Wait or resume the queued work.'))
                pictures.approve_capacity(fresh, request.user, len(cards), form.cleaned_data['extra_allowance'])
                batch = str(uuid.UUID(request.POST['submission_id']))
                for card in cards:
                    row = pictures.request(card['entry'], request.user, replace=True,
                        extra_allowance=form.cleaned_data['extra_allowance'])
                    row.study = costs.create_study(row, batch=batch, unit_estimate=pictures.estimate(prices))
                    row.save(update_fields=['study'])
                event(fresh, request.user, 'lemma_image_backfill', detail=f'Approved {len(cards)} selected word pictures; batch {batch}')
                messages.success(request, _('Your word-picture batch has started. See Progress below.'))
                return location(batch=batch, refresh=1)
            return redirect(submit_once(request, dictionary, 'lemma-image-bulk', generate))
        if request.method == 'POST' and action == 'remove':
            values = read_selection(request, dictionary)
            def remove(paths):
                fresh = get_dictionary(request.user, pk); require_editor(request.user,fresh)
                cards = selected_cards(request, fresh, values)
                if any(c['state'] != values[c['entry'].pk]['state'] for c in cards):
                    raise Conflict(_('Some selected pictures changed. Refresh before removing them.'))
                token = str(uuid.UUID(request.POST['submission_id']))
                for card in cards:
                    entry = card['entry']
                    row = LemmaImage.objects.select_for_update().filter(entry=entry).first()
                    previous = {'existed':row is not None, 'error':row.analysis.get('error','') if row else '', 'status':row.status if row else card['status'],
                        'image':card['image'].pk if card['image'] else None,
                        'suitability':card['suitability'], 'snapshot':row.snapshot if row else pictures.basis(entry)}
                    if row:
                        costs.cancel_unstarted(row.study)
                        row.revision += 1
                    else:
                        row = LemmaImage(entry=entry, requested_by=request.user)
                    row.status, row.image, row.suitability = 'removed', None, 'none'
                    row.snapshot = pictures.basis(entry)
                    row.analysis = {'bulk_removal':{'token':token,'revision':row.revision,'previous':previous}}
                    row.updated_at=timezone.now(); row.save()
                event(fresh,request.user,'lemma_image_bulk_remove',detail=f'Removed {len(cards)} pictures; undo {token}')
                messages.success(request,_('Selected pictures removed. You can undo this removal below.'))
                return location(undo=token)
            return redirect(submit_once(request,dictionary,f'lemma-picture-remove:{len(values)}',remove))
        if request.method == 'POST' and action == 'undo':
            receipt = undo_receipt(request,dictionary,request.POST.get('undo')) if request.POST.get('undo') else None
            if not receipt:
                raise Conflict(_('This removal can no longer be undone.'))
            def restore(paths):
                fresh=get_dictionary(request.user,pk); require_editor(request.user,fresh)
                restored=0
                for row in LemmaImage.objects.select_for_update().filter(entry__dictionary=fresh,
                        analysis__bulk_removal__token=str(receipt.token)).select_related('entry'):
                    marker=row.analysis['bulk_removal']; previous=marker['previous']; row.entry.dictionary=fresh
                    if marker['revision'] != row.revision or previous['snapshot'] != pictures.basis(row.entry):
                        continue
                    image=public.contributions(fresh).filter(pk=previous['image'],entry=row.entry,kind='image').exclude(file_path='').first() if previous['image'] else None
                    if previous['image'] and not image:
                        continue
                    if not previous['existed'] and not image:
                        row.delete(); restored+=1; continue
                    row.revision+=1; row.image=image; row.suitability=previous['suitability']
                    row.status=('ready' if image else previous['status'] if previous['status'] in {'none','removed'} else 'failed')
                    row.analysis={} if row.status!='failed' else {'error':previous.get('error') or _('Generation was cancelled. Select this word to start a fresh attempt.')}
                    row.updated_at=timezone.now();row.save();restored+=1
                messages.success(request,_('Pictures restored: %(count)s. Changed or withdrawn pictures were kept as they are.') % {'count':restored})
                return location(undo='')
            return redirect(submit_once(request,dictionary,'lemma-picture-undo',restore))
        if (request.method == 'POST' and action == 'preview') or (request.method == 'GET' and action == 'preview'):
            if request.method=='GET':
                # Retain old bookmarked five-word preview links during the UI transition.
                limit=max(1,min(50,int(request.GET.get('limit',5))))
                values={e.pk:{} for e in pictures.missing(dictionary)[:limit]}
                chosen=selected_cards(request,dictionary,values) if values else []
            else:
                chosen=selected_cards(request,dictionary,read_selection(request,dictionary))
    except (Conflict, ValueError) as exc:
        form.add_error(None,str(exc))
    if chosen and prices:
        signed=signing.dumps({'user':request.user.pk,'dictionary':pk,'prices':prices,
            'entries':[c['entry'].pk for c in chosen],'states':[c['state'] for c in chosen]},salt=BATCH_SALT)
    from django.core.paginator import Paginator
    try: shown=max(20,min(100,int(request.POST.get('shown') or request.GET.get('shown',20))))
    except ValueError: shown=20
    q=(request.POST.get('q') or request.GET.get('q','')).strip()[:128]
    query=entries(dictionary)
    if q:query=query.filter(Q(word__icontains=q)|Q(meaning__icontains=q))
    page=Paginator(query.order_by('pk'),shown).get_page(request.POST.get('page') or request.GET.get('page',1))
    cards=card_rows(dictionary,request.user,page.object_list)
    selected_ids={c['entry'].pk for c in chosen}
    for card in cards:card['selected']=card['entry'].pk in selected_ids
    batch=costs.batch_summary(dictionary,request.user,request.GET.get('batch') or request.POST.get('batch'))
    undo=undo_receipt(request,dictionary,request.GET.get('undo') or request.POST.get('undo'))
    jobs=LemmaImage.objects.filter(entry__dictionary=dictionary)
    labels=dict(LemmaImage._meta.get_field('status').choices)
    counts=[{**v,'label':_(labels[v['status']])} for v in jobs.values('status').annotate(total=Count('pk')).order_by('status')]
    unit=pictures.estimate(prices) if prices else Decimal('0')
    def browse(**extra):
        args={'q':q,'shown':shown,'page':page.number,'batch':batch['id'] if batch else '', 'undo':str(undo.token) if undo else ''}
        args.update(extra)
        return reverse('community_dictionary:word-images',args=[pk])+'?'+urlencode({k:v for k,v in args.items() if v})
    recent_batches=[]
    seen=set()
    for study in costs.word_studies(dictionary).filter(user=request.user,usage__has_key=costs.KEY).exclude(usage__lemma_picture__batch='').order_by('-usage__lemma_picture__batch_created')[:250]:
        meta=study.usage[costs.KEY]
        if meta['batch'] not in seen:
            seen.add(meta['batch'])
            recent_batches.append({'url':browse(batch=meta['batch']), 'created':meta['batch_created'], 'total':costs.word_studies(dictionary).filter(user=request.user,usage__lemma_picture__batch=meta['batch']).count()})
        if len(recent_batches)==5:break
    return render(request,'community_dictionary/word_images.html',context(request,dictionary,recent_batches=recent_batches,
        cards=cards,preview_cards=chosen,form=form,quote=signed,preview_ready=bool(chosen and prices and not setup_error),
        preview_requested=action=='preview',candidates=[c['entry'] for c in chosen],
        selected_tokens=[c['token'] for c in chosen],selection_data={str(c['entry'].pk):c['token'] for c in chosen},server_selection=bool(chosen),
        estimate=costs.money(unit*len(chosen)),unit_micro=int(unit*1_000_000),
        setup_error=setup_error, daily_counts=pictures.daily_usage(dictionary,request.user),
        can_extra_allowance=is_owner(request.user,dictionary),batch=batch,cumulative=costs.cumulative(dictionary),
        undo=str(undo.token) if undo else '',page=page,shown=shown,q=q,
        more_url=browse(shown=min(100,shown+20)) if shown<100 and page.number==1 and page.has_next() else '',
        next_url=browse(page=page.next_page_number()) if page.has_next() else '',
        previous_url=browse(page=page.previous_page_number()) if page.has_previous() else '',
        refresh_url=browse(refresh=1)+'#word-image-progress',
        progress_refreshed=request.GET.get('refresh')=='1',checked_at=timezone.now(),counts=counts,
        missing_count=pictures.missing(dictionary).count(),active=jobs.filter(status__in=['waiting',*pictures.ACTIVE]).exists()))
