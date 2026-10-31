"""Mobile guided contribution and durable personal workflow settings."""
from datetime import timedelta
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.http import require_http_methods, require_POST
from . import capture, guided, learning, tts, writing
from .models import Dictionary, PictureCapture, Participation, VoicePreference
from .permissions import get_dictionary
from .port_views import no_store
from .services import Conflict, submit_once
from .storage import path_for, prepare_upload, write_upload
from .views import context, fail, saved
from .writing_views import PictureForm, dictionary_for

SALT = 'guided-consent-1'


class ModeForm(forms.Form):
    mode = forms.ChoiceField(label=gettext_lazy('My way of adding pictures'), choices=[
        ('manual', gettext_lazy('Usual contribution form')),
        ('guided', gettext_lazy('Picture, confirm and finish')),
        ('writing', gettext_lazy('Writing practice'))])
    permission = forms.BooleanField(required=False, label=gettext_lazy(
        'I have permission to contribute the pictures I upload. I agree to send them to OpenAI automatically for descriptions, and to pay for descriptions and the processing I approve.'))
    quote = forms.CharField(required=False, widget=forms.HiddenInput)


class MeaningForm(forms.Form):
    description = forms.CharField(label=gettext_lazy('What I want to say'), max_length=255,
        widget=forms.Textarea(attrs={'rows': 3, 'spellcheck': 'true'}))


def settings_context(request, dictionary):
    error, values = '', None
    try:
        if learning.available(dictionary): values = guided.consent_values(request.user, dictionary)
    except Conflict as exc: error = str(exc)
    return {'mode_form': ModeForm(initial={'mode': learning.preference(request, dictionary)['mode'],
        'quote': signing.dumps(values, salt=SALT) if values else ''}),
        'guided_estimate': guided.estimate(values) if values else None,
        'guided_personal': values['personal'] if values else False, 'guided_setup_error': error}


@login_required
@require_POST
@transaction.atomic
def setting(request, pk):
    get_object_or_404(Dictionary.objects.select_for_update(), pk=pk)
    dictionary = get_dictionary(request.user, pk)
    form = ModeForm(request.POST)
    if not form.is_valid(): return fail(request, form.errors.as_text())
    mode, consent = form.cleaned_data['mode'], {}
    try:
        if mode != 'manual': dictionary_for(request, pk)
        if mode == 'guided':
            if not form.cleaned_data['permission']:
                raise Conflict(_('Confirm permission and automatic AI processing before enabling this mode.'))
            try: consent = signing.loads(form.cleaned_data['quote'], salt=SALT, max_age=600)
            except signing.BadSignature: raise Conflict(_('Reload Settings to see the current cost estimate.'))
            if consent != guided.consent_values(request.user, dictionary):
                raise Conflict(_('The AI settings changed. Reload Settings and confirm the new estimate.'))
        learning.save_preference(request, dictionary, mode, consent)
    except Conflict as exc: return fail(request, exc, 409)
    messages.success(request, _('Your personal workflow is saved across logins.'))
    return redirect('community_dictionary:settings', pk=pk)


def url(study):
    return reverse('community_dictionary:guided-detail', args=[study.dictionary_id, study.pk])


def new_attempt(request, dictionary, paths, prepared, source=None, previous=None):
    consent = learning.preference(request, dictionary)['consent']
    if not consent or learning.mode(request, dictionary) != 'guided':
        raise Conflict(_('Enable Picture, confirm and finish in Settings first.'))
    media = write_upload(prepared, dictionary.pk, paths)
    study = PictureCapture.objects.create(dictionary=dictionary, user=request.user, source_image=source,
        status='draft', input_mode='guided', language=dictionary.language,
        input_language=dictionary.explanation_language or 'English',
        explanation_language=dictionary.explanation_language or 'English',
        expires_at=timezone.now() + timedelta(days=writing.RETENTION_DAYS),
        file_path=media['file_path'], model=consent['model'], personal_key=consent['personal'],
        voice=VoicePreference.objects.filter(user=request.user, dictionary=dictionary).values_list('voice', flat=True).first() or tts.VOICE,
        revision=dictionary.capture_revision, membership_revision=dictionary.membership_revision,
        participation_revision=Participation.objects.filter(dictionary=dictionary, user=request.user)
            .values_list('revision', flat=True).first() or 0,
        result={'guided': {'version': consent['version'], 'level': learning.level(dictionary), 'consent': consent}})
    if source: study.sources.add(source)
    if previous and previous.result['guided'].get('approved_description'):
        study.status = 'feedback'
        study.result['guided']['suggestion'] = {'outcome': 'ready',
            'description': previous.result['guided']['approved_description'], 'question': ''}
        study.save(update_fields=['status', 'result'])
    return study


def begin_saved(study):
    try: guided.begin(study.pk)
    except Conflict as exc:
        # The upload remains private and recoverable even if credit/quota/setup
        # prevents the AI call. Never delete the successfully saved photograph.
        return str(exc)
    return ''


@login_required
@require_http_methods(['GET', 'POST'])
def start(request, pk, image_id=None):
    try: dictionary = dictionary_for(request, pk)
    except Conflict as exc: return fail(request, exc, 409)
    if request.method == 'POST' and learning.mode(request, dictionary) != 'guided':
        return fail(request, _('Enable Picture, confirm and finish in Settings first.'), 409)
    source = get_object_or_404(capture.available_images(request.user, dictionary), pk=image_id) if image_id else None
    form = PictureForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            prepared = ((path_for(source.file_path).read_bytes(), 'image/jpeg', '.jpg') if source else
                prepare_upload(form.cleaned_data['photo'], 'image') if form.cleaned_data.get('photo') else None)
            if prepared is None: raise Conflict(_('Take or choose a picture.'))
            def create(paths):
                current = dictionary_for(request, pk)
                if source: get_object_or_404(capture.available_images(request.user, current), pk=source.pk)
                return url(new_attempt(request, current, paths, prepared, source))
            location = submit_once(request, dictionary, f'guided-picture:{image_id}', create)
            study = guided.own(request.user, dictionary, location.rstrip('/').split('/')[-1])
            error = begin_saved(study)
            if error: messages.warning(request, error)
            return saved(request, location)
        except (Conflict, forms.ValidationError, OSError) as exc:
            form.add_error(None, str(exc) if not isinstance(exc, OSError) else _('The picture file is unavailable.'))
    if request.method == 'POST' and form.errors and 'application/json' in request.headers.get('Accept', ''):
        return fail(request, form.errors.as_text())
    return no_store(render(request, 'community_dictionary/guided_start.html', context(request, dictionary,
        **settings_context(request, dictionary), form=form, image=source,
        recent=PictureCapture.objects.filter(user=request.user, dictionary=dictionary, input_mode='guided',
            expires_at__gt=timezone.now()).exclude(status='discarded').order_by('-created_at')[:8],
        submission_id=request.POST.get('submission_id') or context(request)['submission_id'])))


def page(request, dictionary, study, form=None):
    from .lexicon import word_row
    info = study.result['guided']
    suggestion = info.get('suggestion', {})
    form = form or MeaningForm(initial={'description': suggestion.get('description', '')})
    form.fields['description'].widget.attrs['lang'] = tts.language_code(study.explanation_language)
    rows = capture.sentence_context(study.saved_entry)['sentence_words'] if study.saved_entry_id else []
    sentence = word_row(study.saved_entry, dictionary) if study.saved_entry_id else None
    pending = study.speech.filter(status__in=['waiting', 'running']).exists()
    failed = capture.failed_audio(study)
    return no_store(render(request, 'community_dictionary/guided_detail.html', context(request, dictionary,
        study=study, info=info, suggestion=suggestion, form=form,
        estimate=guided.estimate(info['consent']), personal=study.personal_key,
        sentence_row=sentence, word_rows=rows, pending=pending, failed_audio=failed,
        complete=study.status == 'saved' and not pending and not failed,
        polling=study.status in {'waiting', 'processing', 'approved', 'ready'} or pending,
        submission_id=request.POST.get('submission_id') or context(request)['submission_id'])))


@login_required
@require_http_methods(['GET'])
def detail(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    try: study = guided.own(request.user, dictionary, study_id)
    except Conflict as exc: return fail(request, exc, 409)
    return page(request, dictionary, study)


@login_required
@require_POST
def action(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    try:
        study = guided.own(request.user, dictionary, study_id)
        choice = request.POST.get('action')
        if choice == 'approve':
            form = MeaningForm(request.POST)
            if not form.is_valid(): return page(request, dictionary, study, form)
            guided.approve(study.pk, request.user, form.cleaned_data['description'])
        elif choice == 'continue':
            if study.status == 'draft':
                error = begin_saved(study)
                if error: messages.warning(request, error)
            else: guided.queue(study.pk)
        elif choice == 'retry-audio':
            def retry(paths):
                guided.permitted(capture.fetch(study.pk), payment=True)
                writing.retry_audio(study.pk, request.user)
                return url(study)
            return saved(request, submit_once(request, dictionary, f'guided-audio:{study.pk}', retry))
        elif choice == 'retry':
            if study.status != 'failed': raise Conflict(_('Only a failed attempt can be retried.'))
            def again(paths):
                old = guided.own(request.user, dictionary, study.pk)
                prepared = (path_for(old.file_path).read_bytes(), 'image/jpeg', '.jpg')
                return url(new_attempt(request, dictionary, paths, prepared, old.source_image, old))
            location = submit_once(request, dictionary, f'guided-retry:{study.pk}', again)
            error = begin_saved(guided.own(request.user, dictionary, location.rstrip('/').split('/')[-1]))
            if error: messages.warning(request, error)
            return saved(request, location)
        elif choice == 'discard':
            with transaction.atomic():
                capture.locks(); capture.discard(PictureCapture.objects.filter(pk=study.pk, user=request.user))
            return redirect('community_dictionary:guided-start', pk=pk)
        else: raise Conflict(_('Choose an action shown on this page.'))
        return saved(request, url(study))
    except Conflict as exc: return fail(request, exc, 409)
