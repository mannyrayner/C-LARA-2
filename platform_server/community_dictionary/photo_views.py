"""Photo learning is private until the learner explicitly contributes it."""
from datetime import timedelta
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from projects.billing import (credits_enabled, estimate_openai_token_cost_usd,
    has_minimum_balance_for_compile, record_openai_usage_and_charge)
from . import photo_ai
from .forms import PhotoSaveForm, PhotoStudyForm
from .models import Contribution, Dictionary, Entry, PhotoStudy
from .permissions import get_dictionary, is_editor
from .services import Conflict, add_contributions, entry_url, event, submit_once
from .storage import delete_file, path_for, write_upload
from .views import context, fail, get_entry

logger = logging.getLogger(__name__)


def study_url(study):
    return reverse('community_dictionary:photo-study', args=[study.dictionary_id, study.pk])


def get_study(request, dictionary, study_id, *, lock=False):
    query = PhotoStudy.objects.select_for_update() if lock else PhotoStudy.objects.all()
    return get_object_or_404(query, pk=study_id, dictionary=dictionary, user=request.user, expires_at__gt=timezone.now())


def finish_analysis(study, api_key):
    """Called ONLY by the request that committed the attempt, never by a replay.

    The claim commits before the network call. An interrupted/unknown attempt is
    never automatically retried, even if this means losing a result after a crash.
    """
    response, result, failure = None, {}, ''
    try:
        response = photo_ai.analyse(path_for(study.file_path).read_bytes(), language=study.language,
            explanation_language=study.explanation_language, model=study.model, api_key=api_key)
        result = photo_ai.parse_result(response)
    except Exception as exc:
        # Provider exceptions can contain photo/prompt data: never log their message.
        failure = 'provider_or_result'
        logger.warning('Photo study %s failed (%s)', study.pk, type(exc).__name__)
    usage = {}
    if response is not None and getattr(response, 'usage', None):
        usage = {key: max(0, int(getattr(response.usage, key, 0) or 0))
                 for key in ['input_tokens', 'output_tokens', 'total_tokens']}
    with transaction.atomic():
        current = PhotoStudy.objects.select_for_update().get(pk=study.pk)
        # Accounting belongs to the attempt even if its user discarded it while waiting.
        if not current.usage and usage:
            current.usage = usage
            current.cost_usd = estimate_openai_token_cost_usd(study.model, usage['input_tokens'], usage['output_tokens'])
            if not study.personal_key:
                record_openai_usage_and_charge(user_id=study.user_id, project_id=None, model=study.model,
                    operation='community_photo', request_type=f'photo:{study.pk}', prompt_tokens=usage['input_tokens'],
                    completion_tokens=usage['output_tokens'], total_tokens=usage['total_tokens'])
        if current.status == 'processing':
            current.result = result
            current.failure_code = failure
            current.status = 'failed' if failure else ('candidate' if result['outcome'] == 'candidate' else 'unclear')
        current.save()


@login_required
def start(request, pk, entry_id=None, image_id=None):
    dictionary = get_dictionary(request.user, pk)
    if not dictionary.photo_ai_enabled:
        return fail(request, 'The dictionary owner can enable Learn from a photo under People → Dictionary settings.', 403)
    source_entry = get_entry(dictionary, entry_id) if entry_id else None
    source_image = get_object_or_404(Contribution, pk=image_id, entry=source_entry,
        kind='image', status__in=['accepted', 'pending']) if source_entry else None
    form = PhotoStudyForm(request.POST or None, request.FILES or None,
        existing_image=bool(source_entry), initial={'base_version': source_entry.text_version if source_entry else 0})
    config, setup_error = None, ''
    try:
        config = photo_ai.configuration(request.user)
    except Conflict as exc:
        setup_error = str(exc)
    if request.method == 'POST' and form.is_valid() and config:
        created = []
        model, api_key, personal, prices = config

        def create(paths):
            # Serialize quota checks across dictionaries AND across users.
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            current_dictionary = Dictionary.objects.select_for_update().get(pk=pk)
            get_dictionary(request.user, pk)
            if not current_dictionary.photo_ai_enabled:
                raise Conflict('Photo learning has been disabled for this dictionary.')
            if not has_minimum_balance_for_compile(request.user):
                raise Conflict('Your C-LARA balance is too low. Add credit or use your own OpenAI key.')
            since = timezone.now() - timedelta(days=1)
            recent = PhotoStudy.objects.filter(created_at__gte=since)
            limit = settings.COMMUNITY_DICTIONARY_PHOTO_DAILY_LIMIT
            if recent.filter(user=request.user).count() >= limit or recent.filter(dictionary=dictionary).count() >= limit:
                raise Conflict('The daily photo-analysis limit has been reached. Please try tomorrow.')
            if recent.filter(user=request.user, status='processing', created_at__gte=timezone.now()-timedelta(seconds=60)).exists():
                raise Conflict('Your previous photo is still being analysed. Open it below before starting another.')
            source_fields = {}
            if source_entry:
                target = Entry.objects.select_for_update().get(pk=source_entry.pk)
                if target.text_version != form.cleaned_data['base_version']:
                    raise Conflict('The wording changed. Reload the entry before analysing this photo.')
                current_image = Contribution.objects.get(pk=source_image.pk, entry=target)
                if current_image.status not in {'accepted', 'pending'} or not current_image.file_path:
                    raise Conflict('This picture is no longer available. Reload the entry.')
                try:
                    prepared = (path_for(current_image.file_path).read_bytes(), 'image/jpeg', '.jpg')
                except FileNotFoundError:
                    raise Conflict('This picture file is missing. Please upload it again.')
                source_fields = dict(source_entry=target, source_image_id=current_image.pk,
                                     source_text_version=target.text_version)
            else:
                prepared = form.cleaned_data['photo']
            study = PhotoStudy.objects.create(dictionary=dictionary, user=request.user,
                expires_at=timezone.now()+timedelta(days=1), language=current_dictionary.language,
                explanation_language=current_dictionary.explanation_language or 'English', model=model,
                personal_key=personal, **source_fields, **write_upload(prepared, pk, paths))
            event(dictionary, request.user, 'photo_analysis', detail=f'OpenAI photo consent; attempt {study.pk}')
            created.append(study)
            return study_url(study)
        try:
            url = submit_once(request, dictionary, f'photo-study:{entry_id}:{image_id}' if source_entry else 'photo-study', create)
        except Conflict as exc:
            form.add_error(None, str(exc))
        else:
            if created:
                finish_analysis(created[0], api_key)
            return redirect(url)
    recent = PhotoStudy.objects.filter(dictionary=dictionary, user=request.user, expires_at__gt=timezone.now()).exclude(status='discarded').order_by('-created_at')[:5]
    return render(request, 'community_dictionary/photo_start.html', context(request, dictionary,
        form=form, source_entry=source_entry, source_image=source_image, setup_error=setup_error,
        model=config[0] if config else '', personal=config[2] if config else False,
        prices=config[3] if config else {}, charge_credits=credits_enabled(),
        daily_limit=settings.COMMUNITY_DICTIONARY_PHOTO_DAILY_LIMIT, recent=recent,
        submission_id=request.POST.get('submission_id') or context(request)['submission_id']))


@login_required
def detail(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    study = get_study(request, dictionary, study_id)
    if study.status == 'saved' and study.saved_entry_id:
        return redirect(entry_url(study.saved_entry))
    form = PhotoSaveForm(initial={'word': study.result.get('word', ''), 'meaning': study.result.get('meaning', ''), 'publish_now': is_editor(request.user, dictionary)})
    return render_study(request, dictionary, study, form)


def render_study(request, dictionary, study, form):
    if not is_editor(request.user, dictionary):
        form.fields.pop('publish_now', None)
    if study.source_image_id:
        form.fields['consent'].label = 'I have permission to share this suggested wording with the dictionary.'
    return render(request, 'community_dictionary/photo_study.html', context(request, dictionary, study=study, form=form,
        timed_out=study.status == 'processing' and study.created_at < timezone.now()-timedelta(seconds=60)))


@login_required
def media(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    study = get_study(request, dictionary, study_id)
    if not study.file_path or study.status in {'discarded', 'saved'}:
        raise Http404
    try:
        return FileResponse(path_for(study.file_path).open('rb'), content_type='image/jpeg')
    except FileNotFoundError:
        raise Http404


@login_required
@require_POST
def action(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    try:
        with transaction.atomic():
            Dictionary.objects.select_for_update().get(pk=pk)
            get_dictionary(request.user, pk)
            study = get_study(request, dictionary, study_id, lock=True)
            choice = request.POST.get('action')
            if choice == 'discard' and study.status != 'saved':
                path = study.file_path
                study.status, study.file_path, study.result = 'discarded', '', {}
                study.save()
                transaction.on_commit(lambda: delete_file(path) if path else None)
                return redirect(entry_url(study.source_entry)) if study.source_entry_id else redirect('community_dictionary:photo-start', pk=pk)
            if choice == 'confirm' and study.status in {'candidate', 'confirmed'}:
                study.status = 'confirmed'
                study.confirmed_at = study.confirmed_at or timezone.now()
                study.save(update_fields=['status', 'confirmed_at'])
                return redirect(study_url(study))
            if choice != 'save':
                raise Conflict('This photo is no longer awaiting that action.')
            if study.status == 'saved':
                if study.saved_entry_id:
                    return redirect(entry_url(study.saved_entry))
                raise Conflict('The saved entry has since been removed.')
            if study.status != 'confirmed':
                raise Conflict('Confirm the proposed object before saving it.')
            form = PhotoSaveForm(request.POST)
            if not form.is_valid():
                return render_study(request, dictionary, study, form)
            created_paths = []
            try:
                if dictionary.language != study.language:
                    raise Conflict('The dictionary language changed. Start a new interpretation before saving.')
                data = form.cleaned_data
                if study.source_image_id:
                    entry = Entry.objects.select_for_update().filter(pk=study.source_entry_id, dictionary=dictionary).first()
                    if not entry or not Contribution.objects.filter(pk=study.source_image_id, entry=entry,
                            kind='image', status__in=['accepted', 'pending']).exists():
                        raise Conflict('The original entry or picture is no longer available.')
                    if entry.text_version != study.source_text_version:
                        raise Conflict('The entry wording changed. Return to the entry and review its latest words before starting again.')
                    data.update(base_version=study.source_text_version, category=entry.category, edit_text=True)
                else:
                    entry = Entry.objects.create(dictionary=dictionary, created_by=request.user)
                    data['prepared_photo'] = (path_for(study.file_path).read_bytes(), 'image/jpeg', '.jpg')
                made = add_contributions(entry, request.user, data, created_paths,
                    publish=is_editor(request.user, dictionary) and data.get('publish_now', False))
                for contribution in made:
                    if contribution.kind == 'text':
                        contribution.provenance = {'origin': 'ai-assisted', 'provider': 'openai', 'model': study.model,
                            'prompt_version': photo_ai.PROMPT_VERSION, 'study_id': str(study.pk),
                            'language': study.language, 'explanation_language': study.explanation_language,
                            'proposed_' + contribution.text_field: study.result.get(contribution.text_field, ''),
                            'subject_confirmed_by': request.user.pk, 'subject_confirmed_at': study.confirmed_at.isoformat(),
                            'source_image_id': study.source_image_id}
                        contribution.save(update_fields=['provenance'])
                old_path = study.file_path
                study.status, study.saved_entry, study.file_path = 'saved', entry, ''
                study.save(update_fields=['status', 'saved_entry', 'file_path'])
                transaction.on_commit(lambda: delete_file(old_path))
            except Exception:
                for path in created_paths:
                    delete_file(path)
                raise
        return redirect(entry_url(entry))
    except Conflict as exc:
        return fail(request, exc, 409)
