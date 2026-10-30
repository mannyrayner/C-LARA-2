"""Mobile writing flow: save picture, write, review corrections, approve once."""
from datetime import timedelta
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.http import require_http_methods, require_POST

from . import capture, capture_limits, photo_ai, tts, writing, writing_ai
from .models import PictureCapture, Participation
from .permissions import get_dictionary
from .port_views import no_store
from .services import Conflict, submit_once
from .storage import path_for, prepare_upload, write_upload
from .views import context, fail, saved
from .voices import VOICE_CHOICES


class PictureForm(forms.Form):
    photo = forms.FileField(label=gettext_lazy('Picture'), required=False)


class DraftForm(forms.Form):
    description = forms.CharField(label=gettext_lazy('My description'), max_length=255,
        required=False, widget=forms.Textarea(attrs={'rows': 5, 'spellcheck': 'true'}))
    feedback_language = forms.ChoiceField(label=gettext_lazy('Language for explanations'))
    voice = forms.ChoiceField(choices=VOICE_CHOICES, label=gettext_lazy('AI voice'))
    ai_consent = forms.BooleanField(required=False, label=gettext_lazy(
        'I agree to send this picture and my writing to OpenAI and pay the estimated cost shown here.'))

    def __init__(self, *args, dictionary, **kwargs):
        super().__init__(*args, **kwargs)
        languages = [dictionary.explanation_language or 'English', dictionary.language]
        self.fields['feedback_language'].choices = [(x, x) for x in dict.fromkeys(languages)]
        self.fields['description'].widget.attrs['lang'] = tts.language_code(dictionary.language)


def url(study):
    return reverse('community_dictionary:writing-detail', args=[study.dictionary_id, study.pk])


def dictionary_for(request, pk):
    dictionary = get_dictionary(request.user, pk)
    if not dictionary.sentence_capture_enabled or not dictionary.tts_enabled or not all(
            tts.language_code(x) for x in [dictionary.language, dictionary.explanation_language or 'English']):
        raise Conflict('The owner needs to enable Picture descriptions and saved audio for supported languages in Settings.')
    return dictionary


@login_required
@require_POST
def setting(request, pk):
    dictionary = get_dictionary(request.user, pk)
    choice = request.POST.get('mode')
    if choice not in {'on', 'off'}:
        return fail(request, _('Choose on or off.'))
    if choice == 'on':
        try: dictionary_for(request, pk)
        except Conflict as exc: return fail(request, exc, 409)
    request.session[f'writing-{pk}'] = {'enabled': choice == 'on'}
    messages.success(request, _('Your writing-practice preference is saved for this login.'))
    return redirect('community_dictionary:settings', pk=pk)


def new_attempt(request, dictionary, paths, *, prepared, source=None, previous=None):
    photo = write_upload(prepared, dictionary.pk, paths)
    study = PictureCapture.objects.create(dictionary=dictionary, user=request.user, source_image=source,
        status='draft', input_mode='writing', input_language=dictionary.language,
        language=dictionary.language, explanation_language=dictionary.explanation_language or 'English',
        expires_at=timezone.now() + timedelta(days=writing.RETENTION_DAYS),
        file_path=photo['file_path'], model='', voice=tts.VOICE,
        revision=dictionary.capture_revision, membership_revision=dictionary.membership_revision,
        participation_revision=Participation.objects.filter(dictionary=dictionary, user=request.user)
            .values_list('revision', flat=True).first() or 0,
        result={'writing': {'version': writing_ai.VERSION,
            'original_text': previous.result['writing']['original_text'] if previous else '', 'feedback_language':
            previous.result['writing']['feedback_language'] if previous else dictionary.explanation_language or 'English'}})
    if source: study.sources.add(source)
    return study


@login_required
@require_http_methods(['GET', 'POST'])
def start(request, pk, image_id=None):
    try: dictionary = dictionary_for(request, pk)
    except Conflict as exc: return fail(request, exc, 409)
    image = get_object_or_404(capture.available_images(request.user, dictionary), pk=image_id) if image_id else None
    form = PictureForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            if image:
                prepared = (path_for(image.file_path).read_bytes(), 'image/jpeg', '.jpg')
            elif form.cleaned_data.get('photo'):
                prepared = prepare_upload(form.cleaned_data['photo'], 'image')
            else:
                raise Conflict(_('Take or choose a picture.'))
            def create(paths):
                current = dictionary_for(request, pk)
                if image:
                    get_object_or_404(capture.available_images(request.user, current), pk=image.pk)
                return url(new_attempt(request, current, paths, prepared=prepared, source=image))
            return saved(request, submit_once(request, dictionary, f'writing-picture:{image_id}', create))
        except (Conflict, forms.ValidationError, OSError) as exc:
            form.add_error(None, str(exc) if not isinstance(exc, OSError) else _('The picture file is unavailable.'))
    if request.method == 'POST' and form.errors and 'application/json' in request.headers.get('Accept', ''):
        return fail(request, form.errors.as_text())
    return no_store(render(request, 'community_dictionary/writing_start.html', context(request, dictionary,
        image=image, form=form, recent=writing.recent(request.user, dictionary),
        submission_id=request.POST.get('submission_id') or context(request)['submission_id'])))


def page(request, dictionary, study, form=None):
    info = study.result.get('writing', {})
    if form is None:
        form = DraftForm(dictionary=dictionary, initial={'description': info['original_text'],
            'feedback_language': info['feedback_language'], 'voice': study.voice})
    error = ''
    try:
        model, key, personal, prices = photo_ai.configuration(request.user)
        # One feedback call plus the existing image/translation/vocabulary/audio estimate.
        estimate = capture_limits.unit_estimate(prices) + (
            Decimal(3000)*Decimal(str(prices['input'])) + Decimal(2600)*Decimal(str(prices['output']))) / 1_000_000
    except Conflict as exc:
        estimate, personal, error = None, False, str(exc)
    from .lexicon import word_row
    rows = capture.sentence_context(study.saved_entry)['sentence_words'] if study.saved_entry_id else []
    sentence = word_row(study.saved_entry, dictionary) if study.saved_entry_id else None
    recovered = {row['entry'].pk for row in [sentence, *rows] if row and row['audio']}
    pending = study.speech.filter(status__in=['waiting', 'running']).exists()
    failed = []
    seen = set()
    for clip in study.speech.filter(status='failed').order_by('-pk'):
        if clip.entry_id not in recovered and clip.entry_id not in seen:
            clip.failure_reason = tts.failure_message(clip.report)
            failed.append(clip)
            seen.add(clip.entry_id)
    feedback = info.get('feedback', {})
    return no_store(render(request, 'community_dictionary/writing_detail.html', context(request, dictionary,
        study=study, form=form, info=info, feedback=feedback,
        highlighted=writing.changes(info['original_text'], feedback.get('text', '')),
        estimate=estimate, personal=personal, setup_error=error, sentence_row=sentence, word_rows=rows,
        pending=pending, failed_audio=failed,
        complete=study.status == 'saved' and not pending and not failed,
        polling=study.status in {'waiting', 'processing', 'approved', 'ready'} or pending,
        submission_id=request.POST.get('submission_id') or context(request)['submission_id'])))


@login_required
@require_http_methods(['GET'])
def detail(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    try: study = writing.own(request.user, dictionary, study_id)
    except Conflict as exc: return fail(request, exc, 409)
    return page(request, dictionary, study)


@login_required
@require_POST
def action(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    try:
        study = writing.own(request.user, dictionary, study_id)
        choice = request.POST.get('action')
        if choice in {'save', 'check'}:
            form = DraftForm(request.POST, dictionary=dictionary)
            valid = form.is_valid()
            if valid and choice == 'check':
                if not form.cleaned_data['description']:
                    form.add_error('description', _('Write a short description first.'))
                if not form.cleaned_data['ai_consent']:
                    form.add_error('ai_consent', _('Confirm the AI request and its estimated cost.'))
            if not valid or form.errors:
                return page(request, dictionary, study, form)
            def update(paths):
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                current = capture.fetch(study.pk, True)
                capture.allowed(current)
                if current.status != 'draft':
                    raise Conflict(_('This draft has already been submitted. Open its latest feedback.'))
                current.result['writing']['original_text'] = form.cleaned_data['description']
                current.voice = form.cleaned_data['voice']
                current.result['writing']['feedback_language'] = form.cleaned_data['feedback_language']
                if choice == 'check':
                    model, key, personal, prices = photo_ai.configuration(request.user)
                    current.model, current.personal_key = model, personal
                    capture.allowed(current, payment=True)
                    capture_limits.enforce(current.dictionary, request.user)
                    current.status = 'waiting'
                    current.created_at = timezone.now()  # allowance starts on submission, not picture upload
                    current.usage['writing_request'] = {'cost_usd': '0', 'tokens': {}}
                    transaction.on_commit(lambda: writing.queue(str(current.pk)))
                current.save()
                return url(current)
            return saved(request, submit_once(request, dictionary, f'writing-draft:{study.pk}', update))
        if choice == 'approve':
            if request.POST.get('permission') != 'yes':
                raise Conflict(_('Confirm your permission to share this contribution.'))
            writing.approve(study.pk, request.user)
        elif choice == 'edit':
            if study.status not in {'feedback', 'failed'}:
                raise Conflict(_('Wait for the feedback before editing.'))
            def revise(paths):
                old = writing.own(request.user, dictionary, study.pk)
                prepared = (path_for(old.file_path).read_bytes(), 'image/jpeg', '.jpg')
                return url(new_attempt(request, dictionary, paths, prepared=prepared,
                    source=old.source_image, previous=old))
            return saved(request, submit_once(request, dictionary, f'writing-revise:{study.pk}', revise))
        elif choice == 'continue':
            # Only unclaimed stages are started; running/failed paid calls are not repeated.
            writing.queue(str(study.pk))
        elif choice == 'retry-audio':
            if request.POST.get('permission') != 'yes':
                raise Conflict(_('Confirm the new audio request.'))
            # Receipt also prevents a delayed double-tap repeating a second failure.
            def retry(paths):
                writing.retry_audio(study.pk, request.user)
                return url(study)
            return saved(request, submit_once(request, dictionary, f'writing-audio:{study.pk}', retry))
        elif choice == 'discard':
            with transaction.atomic():
                capture.locks()
                capture.discard(PictureCapture.objects.filter(pk=study.pk, user=request.user))
            return redirect('community_dictionary:writing-start', pk=pk)
        else:
            raise Conflict(_('Choose an action shown on this page.'))
        return saved(request, url(study))
    except Conflict as exc:
        return fail(request, exc, 409)
