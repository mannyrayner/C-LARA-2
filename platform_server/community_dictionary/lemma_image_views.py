"""Costed, incremental backfill and optimistic per-lemma picture controls."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.http import require_http_methods

from . import lemma_images as pictures
from .models import Entry, LemmaImage
from .permissions import get_dictionary, require_editor
from .services import Conflict, event, submit_once
from .storage import prepare_upload, write_upload
from .views import context


class BatchForm(forms.Form):
    limit = forms.IntegerField(min_value=1, max_value=50, initial=5,
        label=gettext_lazy('Number of missing word pictures to try'))
    ai_consent = forms.BooleanField(required=False, label=gettext_lazy(
        'I approve sending these accepted words, translations and up to three example sentences per word to OpenAI, at the estimated cost shown. Publish the pictures automatically.'))


class PictureForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    photo = forms.FileField(required=False, label=gettext_lazy('Replacement picture'),
        widget=forms.FileInput(attrs={'accept': 'image/*'}))
    ai_consent = forms.BooleanField(required=False, label=gettext_lazy(
        'I approve sending this word, translation and up to three example sentences to OpenAI at the estimated cost shown, and publishing its picture automatically.'))
    upload_consent = forms.BooleanField(required=False, label=gettext_lazy(
        'I have permission to share this replacement picture.'))

    def clean_photo(self):
        upload = self.cleaned_data.get('photo')
        return prepare_upload(upload, 'image') if upload else None


@login_required
@require_http_methods(['GET', 'POST'])
def backfill(request, pk):
    dictionary = get_dictionary(request.user, pk)
    require_editor(request.user, dictionary)
    action = request.POST.get('action') if request.method == 'POST' else request.GET.get('action')
    preview_requested = action == 'preview'
    data = request.POST if request.method == 'POST' else request.GET if preview_requested else None
    form = BatchForm(data)
    values, setup_error = None, ''
    try:
        if not pictures.enabled(dictionary):
            raise Conflict(_('Enable AI picture generation in Settings for a supported language.'))
        values = pictures.quote(request.user, dictionary)
    except Conflict as exc:
        setup_error = str(exc)
    if request.method == 'POST' and request.POST.get('action') == 'resume':
        def resume(paths):
            waiting = list(LemmaImage.objects.filter(entry__dictionary=dictionary, requested_by=request.user, status='waiting'))
            for row in waiting:
                transaction.on_commit(lambda pk=row.pk, rev=row.revision: pictures.queue(pk, rev))
            messages.info(request, _('Queued word-picture requests have been resubmitted.') if waiting
                          else _('There are no unstarted word-picture requests to resume.'))
            return reverse('community_dictionary:word-images', args=[pk]) + '?refresh=1#word-image-progress'
        try:
            return redirect(submit_once(request, dictionary, 'lemma-image-resume', resume))
        except Conflict as exc:
            form.add_error(None, str(exc))
    if request.method == 'POST' and request.POST.get('action') == 'generate' and form.is_valid():
        try:
            if setup_error:
                raise Conflict(setup_error)
            if not form.cleaned_data['ai_consent']:
                raise Conflict(_('Confirm AI processing and automatic publication before starting.'))
            approved = signing.loads(request.POST.get('quote', ''), salt='lemma-pictures', max_age=3600)
            if (approved['user'] != request.user.pk or approved['dictionary'] != pk or approved['quote'] != values):
                raise Conflict(_('Settings or prices changed. Preview the batch again.'))
            def create(paths):
                fresh = get_dictionary(request.user, pk)
                require_editor(request.user, fresh)
                if not pictures.enabled(fresh) or pictures.quote(request.user, fresh) != approved['quote']:
                    raise Conflict(_('Settings or prices changed. Preview the batch again.'))
                entries = list(pictures.missing(fresh)[:len(approved['ids'])])
                if not entries or [e.pk for e in entries] != approved['ids']:
                    raise Conflict(_('The missing words changed. Preview the batch again.'))
                if [pictures.basis(e) for e in entries] != approved['basis']:
                    raise Conflict(_('The words or meanings changed. Preview the batch again.'))
                for entry in entries:
                    pictures.request(entry, request.user)
                event(fresh, request.user, 'lemma_image_backfill', detail=f'Approved {len(entries)} missing word pictures')
                messages.success(request, _('Your word-picture batch has started. See Progress below.'))
                return reverse('community_dictionary:word-images', args=[pk]) + '?refresh=1#word-image-progress'
            return redirect(submit_once(request, dictionary, 'lemma-image-backfill', create))
        except (signing.BadSignature, KeyError, TypeError):
            form.add_error(None, _('This estimate expired. Preview the batch again.'))
        except Conflict as exc:
            form.add_error(None, str(exc))
    limit = 5
    if form.is_bound:
        form.is_valid()
        if 'limit' in form.cleaned_data:
            limit = form.cleaned_data['limit']
    candidates = list(pictures.missing(dictionary)[:limit])
    preview_ready = bool(form.is_bound and action in {'preview', 'generate'}
                         and 'limit' in form.cleaned_data and candidates and not setup_error)
    signed = signing.dumps({'user': request.user.pk, 'dictionary': pk,
        'ids': [e.pk for e in candidates], 'basis': [pictures.basis(e) for e in candidates],
        'quote': values}, salt='lemma-pictures') if values else ''
    jobs = LemmaImage.objects.filter(entry__dictionary=dictionary).select_related('entry').order_by('-updated_at')
    from django.db.models import Count
    counts = list(jobs.values('status').annotate(total=Count('pk')).order_by('status'))
    labels = dict(LemmaImage._meta.get_field('status').choices)
    for group in counts:
        group['label'] = _(labels[group['status']])
    return render(request, 'community_dictionary/word_images.html', context(request, dictionary,
        form=form, candidates=candidates, missing_count=pictures.missing(dictionary).count(),
        preview_ready=preview_ready, preview_requested=preview_requested, batch_limit=limit,
        progress_refreshed=request.GET.get('refresh') == '1', checked_at=timezone.now(),
        quote=signed, estimate=pictures.estimate(values)*len(candidates) if values else '',
        setup_error=setup_error, jobs=jobs[:50], counts=counts,
        active=jobs.filter(status__in=['waiting', *pictures.ACTIVE]).exists()))


@login_required
@require_http_methods(['GET', 'POST'])
def word_picture(request, pk, entry_id):
    dictionary = get_dictionary(request.user, pk)
    require_editor(request.user, dictionary)
    entry = get_object_or_404(Entry, dictionary=dictionary, pk=entry_id, entry_type='word', archived=False)
    row = LemmaImage.objects.filter(entry=entry).first()
    form = PictureForm(request.POST or None, request.FILES or None,
        initial={'revision': row.revision if row else 0})
    allowance, setup_error, generation_quote = '', '', ''
    try:
        if not pictures.enabled(dictionary):
            raise Conflict(_('Enable AI picture generation in Settings for a supported language.'))
        prices = pictures.quote(request.user, dictionary)
        allowance = pictures.estimate(prices)
        generation_quote = signing.dumps({'entry': entry.pk, 'user': request.user.pk,
            'basis': pictures.basis(entry), 'quote': prices}, salt='one-lemma-picture')
    except Conflict as exc:
        setup_error = str(exc)
    if request.method == 'POST' and form.is_valid():
        action = request.POST.get('action')
        def update(paths):
            fresh = get_dictionary(request.user, pk)
            require_editor(request.user, fresh)
            target = get_object_or_404(Entry.objects.select_for_update(), pk=entry_id, dictionary=fresh,
                entry_type='word', archived=False)
            current = LemmaImage.objects.select_for_update().filter(entry=target).first()
            if form.cleaned_data['revision'] != (current.revision if current else 0):
                raise Conflict(_('The word picture changed. Reload before making another change.'))
            if action == 'generate':
                if not form.cleaned_data['ai_consent']:
                    raise Conflict(_('Confirm AI processing before generating a picture.'))
                try:
                    approved = signing.loads(request.POST.get('quote', ''), salt='one-lemma-picture', max_age=3600)
                    if (approved['entry'] != entry_id or approved['user'] != request.user.pk or
                            approved['basis'] != pictures.basis(target) or approved['quote'] != pictures.quote(request.user, fresh)):
                        raise Conflict(_('The word, settings or prices changed. Reload before generating.'))
                except (signing.BadSignature, KeyError, TypeError):
                    raise Conflict(_('This estimate expired. Reload before generating.'))
                pictures.request(target, request.user, replace=True)
            elif action == 'resume':
                if current and current.status == 'waiting':
                    transaction.on_commit(lambda: pictures.queue(current.pk, current.revision))
            elif action in {'clue', 'illustration', 'none', 'remove', 'upload', 'select'}:
                from . import public_browsing as public
                from .models import Contribution
                if current is None:
                    info = pictures.picture(target)
                    current = LemmaImage(entry=target, requested_by=request.user, image_id=info.get('id'), revision=0)
                current.revision += 1
                current.snapshot = pictures.basis(target)
                if action == 'upload':
                    if not form.cleaned_data['photo'] or not form.cleaned_data['upload_consent']:
                        raise Conflict(_('Choose a replacement picture and confirm permission to share it.'))
                    current.image = Contribution.objects.create(entry=target, author=request.user,
                        kind='image', status='accepted', provenance={'role': 'lemma_image',
                            'picture_clue': True, 'permission_confirmed': True},
                        **write_upload(form.cleaned_data['photo'], pk, paths))
                    current.status, current.suitability = 'ready', 'clue'
                elif action == 'select':
                    try:
                        image_id = int(request.POST.get('image_id', ''))
                    except ValueError:
                        raise Conflict(_('Choose an accepted picture for this word.'))
                    current.image = get_object_or_404(public.contributions(fresh), pk=image_id,
                        entry=target, kind='image')
                    current.status, current.suitability = 'ready', 'clue'
                elif action in {'none', 'remove'}:
                    current.status = 'none' if action == 'none' else 'removed'
                    current.suitability, current.image = 'none', None
                else:
                    if not current.image_id or not public.contributions(fresh).filter(pk=current.image_id, entry=target, kind='image').exclude(file_path='').exists():
                        raise Conflict(_('Upload or choose a picture first.'))
                    current.status, current.suitability = 'ready', action
                    current.image.provenance = {**current.image.provenance, 'picture_clue': action == 'clue'}
                    current.image.save(update_fields=['provenance'])
                current.updated_at = timezone.now()
                current.save()
                event(fresh, request.user, 'lemma_image_choice', target, action)
            else:
                raise Conflict(_('Choose a word-picture action.'))
            return reverse('community_dictionary:word-picture', args=[pk, entry_id])
        try:
            return redirect(submit_once(request, dictionary, f'lemma-image:{entry_id}', update))
        except Conflict as exc:
            form.add_error(None, str(exc))
    from . import public_browsing as public
    return render(request, 'community_dictionary/word_picture.html', context(request, dictionary,
        entry=entry, form=form, lemma_picture=pictures.picture(entry), allowance=allowance,
        generation_quote=generation_quote, picture_error=row.analysis.get('error', '') if row else '',
        setup_error=setup_error, own_pictures=public.contributions(dictionary).filter(entry=entry,
            kind='image').exclude(file_path='')))
