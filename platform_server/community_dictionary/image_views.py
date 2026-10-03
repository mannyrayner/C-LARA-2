"""Approve a dictionary style, then preview and save individual illustrations."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from projects.billing import credits_enabled, get_user_balance_usd
from . import image_generation as images
from .image_forms import ImageGenerateForm, ImageSaveForm
from .models import Contribution, Dictionary, Entry, ImageStudy, Participation
from .permissions import get_dictionary, is_editor, require_editor
from .services import Conflict, accept, entry_url, event, submit_once
from .storage import delete_file, path_for, write_upload
from .views import context, fail, get_entry, private_media_response


def style_url(dictionary):
    return reverse('community_dictionary:image-style', args=[dictionary.pk])


def study_url(study):
    return reverse('community_dictionary:image-study', args=[study.dictionary_id, study.pk])


def participation_revision(user, dictionary):
    return Participation.objects.filter(user=user, dictionary=dictionary).values_list('revision', flat=True).first() or 0


def source_visible(study):
    return not study.source_style_id or Contribution.objects.filter(pk=study.source_style_id,
        entry__dictionary_id=study.dictionary_id, status='accepted').exists()


def can_save(study, dictionary):
    return (study.user.is_active and is_editor(study.user, dictionary) and dictionary.image_generation_enabled
        and dictionary.image_generation_revision == study.policy_revision
        and dictionary.membership_revision == study.membership_revision
        and participation_revision(study.user, dictionary) == study.participation_revision
        and dictionary.image_style_id == study.style_baseline_id and source_visible(study)
        and study.expires_at > timezone.now()
        and (study.kind == 'style' or Entry.objects.filter(pk=study.entry_id,
            dictionary=dictionary, archived=False).exists()))


def get_study(request, dictionary, study_id, lock=False):
    query = ImageStudy.objects.select_for_update() if lock else ImageStudy.objects.all()
    study = get_object_or_404(query, pk=study_id, dictionary=dictionary, user=request.user,
        expires_at__gt=timezone.now())
    if not source_visible(study):
        raise Http404
    return study


def finish(study, key):
    # The receipt commits before the network call. A lost connection never
    # repeats a paid request automatically. No dictionary lock spans the call.
    prepared, usage, failure = images.generate(study, key)
    paths = []
    try:
        with transaction.atomic():
            dictionary = Dictionary.objects.select_for_update().get(pk=study.dictionary_id)
            current = ImageStudy.objects.select_for_update().select_related('user').get(pk=study.pk)
            images.account(current, usage)
            current.failure_code = failure
            if current.status == 'processing':
                if not can_save(current, dictionary):
                    current.status = 'discarded'
                    current.subject, current.style_description, current.prompt = '', '', ''
                elif prepared:
                    for key, value in write_upload(prepared, dictionary.pk, paths).items():
                        setattr(current, key, value)
                    current.status = 'ready'
                else:
                    current.status = 'failed'
            current.save()
    except Exception:
        for path in paths:
            delete_file(path)
        raise


@login_required
@require_http_methods(['GET', 'POST'])
def start(request, pk, entry_id=None):
    dictionary = get_dictionary(request.user, pk)
    require_editor(request.user, dictionary)
    if not dictionary.image_generation_enabled:
        return fail(request, 'The owner can enable AI picture generation under Settings.', 403)
    entry = get_entry(dictionary, entry_id) if entry_id else None
    style_sample = entry is None
    style = images.active_style(dictionary)
    config, setup_error = None, ''
    try:
        config = images.configuration(request.user)
        if not style_sample and not style:
            raise Conflict('Approve an image style before generating entry pictures.')
    except Conflict as exc:
        setup_error = str(exc)
    form = ImageGenerateForm(request.POST or None, style_sample=style_sample, initial={
        'style_id': dictionary.image_style_id or 0,
        'policy_revision': dictionary.image_generation_revision})
    if request.method == 'POST' and not setup_error and form.is_valid():
        model, key, personal, allowance = config
        created = []

        def create(paths):
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            current = get_dictionary(request.user, pk)  # submit_once holds its lock
            require_editor(request.user, current)
            if (not current.image_generation_enabled or
                    current.image_generation_revision != form.cleaned_data['policy_revision'] or
                    (current.image_style_id or 0) != form.cleaned_data['style_id']):
                raise Conflict('The image settings or style changed. Reload this page before generating.')
            target = get_entry(current, entry_id) if entry_id else None
            source = images.active_style(current) if target else None
            if target and not source:
                raise Conflict('The dictionary style is unavailable. Approve a shared style first.')
            if not personal and credits_enabled() and get_user_balance_usd(request.user) < allowance:
                raise Conflict(f'Allow at least US${allowance} in C-LARA credit for an image preview, or use your own OpenAI key.')
            recent = ImageStudy.objects.filter(created_at__gte=timezone.now()-timedelta(days=1))
            limit = settings.COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT
            if recent.filter(user=request.user).count() >= limit or recent.filter(dictionary=current).count() >= limit:
                raise Conflict('The daily image-generation limit has been reached. Please try tomorrow.')
            if recent.filter(user=request.user, status='processing',
                    created_at__gte=timezone.now()-timedelta(seconds=images.TIMEOUT+60)).exists():
                raise Conflict('Your previous image is still being generated. Open its recent attempt before starting another.')
            description = source.body if source else form.cleaned_data['style_description']
            study = ImageStudy.objects.create(dictionary=current, entry=target, user=request.user,
                kind='entry' if target else 'style', expires_at=timezone.now()+timedelta(days=1),
                subject=form.cleaned_data['subject'], style_description=description, source_style=source,
                style_baseline_id=current.image_style_id,
                participation_revision=participation_revision(request.user, current),
                membership_revision=current.membership_revision, policy_revision=current.image_generation_revision,
                model=model, quality=images.QUALITY, personal_key=personal,
                prompt=images.prompt_for(form.cleaned_data['subject'], description))
            event(current, request.user, 'image_generation', target, f'OpenAI consent; attempt {study.pk}')
            created.append(study)
            return study_url(study)

        try:
            url = submit_once(request, dictionary, f'image:{entry_id or "style"}', create)
        except Conflict as exc:
            form.add_error(None, str(exc))
        else:
            if created:
                finish(created[0], key)
            return redirect(url)
    recent = ImageStudy.objects.filter(dictionary=dictionary, user=request.user, entry=entry,
        expires_at__gt=timezone.now()).exclude(status='discarded').order_by('-created_at')[:5]
    return render(request, 'community_dictionary/image_start.html', context(request, dictionary,
        entry=entry, style=style, style_sample=style_sample, form=form, recent=recent,
        setup_error=setup_error, model=config[0] if config else settings.COMMUNITY_DICTIONARY_IMAGE_MODEL,
        allowance=config[3] if config else '', personal=config[2] if config else False,
        charge_credits=credits_enabled(), limit=settings.COMMUNITY_DICTIONARY_IMAGE_DAILY_LIMIT,
        submission_id=request.POST.get('submission_id') or context(request)['submission_id']))


def render_study(request, dictionary, study, form):
    return render(request, 'community_dictionary/image_study.html', context(request, dictionary,
        study=study, form=form, stale=not can_save(study, dictionary),
        timed_out=study.created_at < timezone.now()-timedelta(seconds=images.TIMEOUT+60)))


@login_required
def detail(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    require_editor(request.user, dictionary)
    study = get_study(request, dictionary, study_id)
    if study.status == 'saved':
        return redirect(style_url(dictionary) if study.kind == 'style' else entry_url(get_entry(dictionary, study.entry_id)))
    return render_study(request, dictionary, study, ImageSaveForm(style_sample=study.kind == 'style'))


@login_required
def media(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    require_editor(request.user, dictionary)
    study = get_study(request, dictionary, study_id)
    if study.status != 'ready' or not study.file_path:
        raise Http404
    return private_media_response(request, study.file_path, study.mime_type, 'generated-preview')


@login_required
@require_POST
def action(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    require_editor(request.user, dictionary)
    paths = []
    try:
        with transaction.atomic():
            Dictionary.objects.select_for_update().get(pk=pk)
            dictionary = get_dictionary(request.user, pk)
            require_editor(request.user, dictionary)
            study = get_study(request, dictionary, study_id, lock=True)
            target_url = style_url(dictionary) if study.kind == 'style' else reverse(
                'community_dictionary:dictionary', args=[pk]) if not study.entry_id else entry_url(study.entry)
            if study.status == 'saved':
                return redirect(target_url)
            if request.POST.get('action') == 'discard':
                images.discard_studies(ImageStudy.objects.filter(pk=study.pk))
                return redirect(target_url)
            if request.POST.get('action') != 'save' or study.status != 'ready' or not can_save(study, dictionary):
                raise Conflict('This preview is unavailable or its settings changed. Return and create a new preview.')
            form = ImageSaveForm(request.POST, style_sample=study.kind == 'style')
            if not form.is_valid():
                return render_study(request, dictionary, study, form)
            target = (Entry.objects.create(dictionary=dictionary, created_by=request.user, archived=True)
                if study.kind == 'style' else Entry.objects.select_for_update().get(pk=study.entry_id))
            # The hidden style entry participates in the same custody, export and
            # withdrawal graph as all other material, without appearing as a word.
            prepared = (path_for(study.file_path).read_bytes(), study.mime_type, '.jpg')
            contribution = Contribution.objects.create(entry=target, author=request.user, kind='image',
                label='Dictionary image style' if study.kind == 'style' else 'AI-generated picture',
                body=study.style_description if study.kind == 'style' else '', shared_from=study.source_style,
                provenance={'origin': 'generated', 'role': 'dictionary_style' if study.kind == 'style' else 'entry_image',
                    'provider': 'openai', 'model': study.model, 'quality': study.quality, 'size': images.SIZE,
                    'prompt': study.prompt, 'prompt_version': images.PROMPT_VERSION,
                    'subject': study.subject, 'style_description': study.style_description,
                    'source_style_id': study.source_style_id, 'study_id': str(study.pk),
                    'requested_by': request.user.pk, 'generated_at': study.created_at.isoformat(),
                    'permission_confirmed': True, 'reviewed_by': request.user.pk,
                    'reviewed_at': timezone.now().isoformat()},
                **write_upload(prepared, pk, paths))
            event(dictionary, request.user, 'contribute', target, f'Generated image {contribution.pk}; permission confirmed')
            if study.kind == 'style' or form.cleaned_data['publish_now']:
                accept(contribution, request.user)
            if study.kind == 'style':
                dictionary.image_style = contribution
                dictionary.save(update_fields=['image_style'])
                event(dictionary, request.user, 'approve_image_style', detail=f'Contribution {contribution.pk}')
            old_path = study.file_path
            study.status, study.file_path, study.saved_contribution = 'saved', '', contribution
            study.save(update_fields=['status', 'file_path', 'saved_contribution'])
            transaction.on_commit(lambda: delete_file(old_path))
        return redirect(style_url(dictionary) if study.kind == 'style' else entry_url(target))
    except Conflict as exc:
        for path in paths:
            delete_file(path)
        return fail(request, exc, 409)
    except Exception:
        for path in paths:
            delete_file(path)
        raise
