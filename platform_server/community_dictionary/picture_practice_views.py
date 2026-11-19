"""Describe an existing picture, without creating dictionary content."""
from datetime import timedelta
from urllib.parse import urlencode
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy as L_
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from . import capture, capture_limits, picture_practice as practice, tts, writing
from .models import PictureCapture, CaptureSpeech, Participation
from .permissions import get_dictionary
from .port_views import no_store
from .services import Conflict, submit_once
from .storage import path_for, prepare_upload, write_upload
from .views import context, fail, saved
from .voices import VOICE_CHOICES

SALT = 'picture-practice-1'


class PracticeForm(forms.Form):
    mode = forms.ChoiceField(label=L_('How would you like to answer?'),
        choices=[('voice', L_('Speak')), ('text', L_('Type'))], widget=forms.RadioSelect)
    description = forms.CharField(required=False, max_length=255, label=L_('My description'),
        widget=forms.Textarea(attrs={'rows': 3, 'dir': 'auto', 'spellcheck': 'true'}))
    audio = forms.FileField(required=False)
    feedback_language = forms.ChoiceField(label=L_('Language for explanations'))
    voice = forms.ChoiceField(choices=VOICE_CHOICES, label=L_('AI voice'))
    permission = forms.BooleanField(label=L_(
        'I agree to send this picture and my text or recording to OpenAI and pay the estimated cost.'))
    quote = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, dictionary, transcript=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.transcript = transcript
        self.fields['feedback_language'].choices = [(x, x) for x in dict.fromkeys([
            dictionary.explanation_language or 'English', dictionary.language])]
        self.fields['description'].widget.attrs['lang'] = tts.language_code(dictionary.language)
        if self.is_bound:
            self.data, self.files = self.data.copy(), self.files.copy()
            if transcript or self.data.get('mode') == 'text':
                self.files.pop('audio', None)
            else:
                self.data.pop('description', None)

    def clean(self):
        data = super().clean()
        if self.transcript or data.get('mode') == 'text':
            if not data.get('description'):
                self.add_error('description', _('Write a short description first.'))
        elif data.get('mode') == 'voice':
            if data.get('audio'):
                data['prepared_audio'] = prepare_upload(data['audio'], 'audio')
            else:
                self.add_error('audio', _('Record or upload your description.'))
        return data


def url(study):
    return reverse('community_dictionary:picture-practice-detail', args=[study.dictionary_id, study.pk])


def setup(user, dictionary):
    try:
        values = practice.quote(user, dictionary)
        return dict(estimate=practice.estimate(values), personal=values['personal'],
            quote=signing.dumps(values, salt=SALT), setup_error='')
    except Conflict as exc:
        return dict(estimate=None, personal=False, quote='', setup_error=str(exc))


def approved(form, user, dictionary):
    try:
        values = signing.loads(form.cleaned_data['quote'], salt=SALT, max_age=600)
    except signing.BadSignature:
        raise Conflict(_('Reload this page to confirm the current estimate.'))
    if values != practice.quote(user, dictionary):
        raise Conflict(_('The AI settings changed. Reload this page.'))
    return values


@login_required
@require_http_methods(['GET', 'POST'])
def start(request, pk):
    dictionary = get_dictionary(request.user, pk)
    if not practice.available(dictionary):
        return fail(request, _('The owner needs to enable Picture descriptions for a supported language.'), 409)
    category = request.GET.get('category', '')[:80]
    candidates = practice.images(dictionary, category)
    image_id = request.POST.get('image') if request.method == 'POST' else request.GET.get('image')
    if image_id:
        image = get_object_or_404(candidates, pk=image_id)
    else:
        skip = candidates.filter(pk=request.GET.get('skip')).first() if request.GET.get('skip', '').isdigit() else None
        remaining = candidates.exclude(file_path=skip.file_path) if skip else candidates
        image = remaining.order_by('?').first() or candidates.order_by('?').first()
    if request.method == 'GET' and image and not image_id:
        # Pin the picture in the URL, so a recovered device draft cannot silently
        # be paired with a newly chosen random image after a reload.
        return redirect(reverse('community_dictionary:picture-practice', args=[pk]) + '?' +
            urlencode({'image': image.pk, 'category': category}))
    config = setup(request.user, dictionary)
    initial = {'mode': 'voice', 'feedback_language': dictionary.explanation_language or 'English',
        'voice': tts.VOICE, **practice.choices(request.user, dictionary), 'quote': config['quote']}
    if request.GET.get('from'):
        try:
            previous = practice.own(request.user, dictionary, request.GET['from'])
            if image and previous.source_image_id == image.pk:
                initial['description'] = previous.result['practice'].get('original_text', '')
        except (Conflict, forms.ValidationError, ValueError):
            pass
    form = PracticeForm(request.POST or None, request.FILES or None, dictionary=dictionary, initial=initial)
    if request.method == 'POST' and image and form.is_valid():
        try:
            def create(paths):
                capture.locks()
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                current = get_dictionary(request.user, pk)
                if not practice.available(current):
                    raise Conflict(_('Practice settings changed. Reload this page.'))
                values = approved(form, request.user, current)
                source = get_object_or_404(practice.images(current, category), pk=image.pk)
                capture_limits.enforce(current, request.user)
                photo = write_upload((path_for(source.file_path).read_bytes(), 'image/jpeg', '.jpg'), pk, paths)
                audio = write_upload(form.cleaned_data['prepared_audio'], pk, paths) if form.cleaned_data['mode'] == 'voice' else {}
                study = PictureCapture.objects.create(dictionary=current, user=request.user, source_image=source,
                    input_mode='practice', status='waiting', expires_at=timezone.now()+timedelta(days=30),
                    language=current.language, input_language=current.language,
                    explanation_language=current.explanation_language or 'English', file_path=photo['file_path'],
                    recording_path=audio.get('file_path', ''), model=values['model'], personal_key=values['personal'],
                    voice=form.cleaned_data['voice'], revision=current.capture_revision, membership_revision=current.membership_revision,
                    participation_revision=Participation.objects.filter(dictionary=current, user=request.user).values_list('revision', flat=True).first() or 0,
                    usage={'practice_request': {'cost_usd': '0', 'tokens': {}}},
                    result={'practice': {'quote': values, 'mode': form.cleaned_data['mode'], 'category': category,
                        'stage': 'transcribe' if audio else 'review', 'original_text': form.cleaned_data.get('description', ''),
                        'feedback_language': form.cleaned_data['feedback_language']}})
                study.sources.add(source)
                practice.permitted(study, payment=True)
                practice.save_choices(request.user, current, {key: form.cleaned_data[key] for key in ['mode', 'feedback_language', 'voice']})
                transaction.on_commit(lambda: practice.queue(str(study.pk)))
                return url(study)
            return saved(request, submit_once(request, dictionary, 'picture-practice', create, ignore_fields=('quote',)))
        except (Conflict, forms.ValidationError, OSError) as exc:
            form.add_error(None, _('The picture file is unavailable.') if isinstance(exc, OSError) else str(exc))
    if request.method == 'POST' and 'application/json' in request.headers.get('Accept', ''):
        return fail(request, form.errors.as_text() or _('Choose an available picture.'), 409)
    recent = PictureCapture.objects.filter(dictionary=dictionary, user=request.user, input_mode='practice',
        expires_at__gt=timezone.now()).exclude(status='discarded').order_by('-created_at')[:8]
    return no_store(render(request, 'community_dictionary/picture_practice_start.html', context(request, dictionary,
        form=form, image=image, recent=recent, category=category, **config,
        submission_id=request.POST.get('submission_id') or context(request)['submission_id'])))


def page(request, dictionary, study, form=None):
    info = study.result['practice']
    feedback = info.get('feedback', {})
    config = setup(request.user, dictionary)
    if form is None:
        form = PracticeForm(dictionary=dictionary, transcript=True, initial={
            'mode': 'text', 'description': info.get('original_text', ''), 'feedback_language': info['feedback_language'],
            'voice': study.voice, 'quote': config['quote']})
    clips = study.speech.filter(kind='feedback').order_by('-pk')
    clip = clips.first()
    polling = study.status in {'waiting', 'processing'} or bool(clip and clip.status in {'waiting', 'running'})
    return no_store(render(request, 'community_dictionary/picture_practice_detail.html', context(request, dictionary,
        study=study, info=info, feedback=feedback, form=form, polling=polling, clip=clip,
        highlighted=writing.changes(info.get('original_text', ''), feedback.get('text', '')),
        audio_estimate=tts.estimate_cost(feedback.get('text', ''), 30),
        can_listen=dictionary.tts_enabled and tts.language_code(dictionary.language) in tts.LANGUAGES.values(), **config,
        submission_id=request.POST.get('submission_id') or context(request)['submission_id'])))


@login_required
@require_GET
def detail(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    try:
        return page(request, dictionary, practice.own(request.user, dictionary, study_id))
    except Conflict as exc:
        return fail(request, exc, 409)


@login_required
@require_POST
def action(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk)
    try:
        study = practice.own(request.user, dictionary, study_id)
        choice = request.POST.get('action')
        if choice == 'check':
            form = PracticeForm(request.POST, dictionary=dictionary, transcript=True)
            if not form.is_valid():
                return page(request, dictionary, study, form)
            def confirm(paths):
                capture.locks()
                current = capture.fetch(study.pk, True)
                practice.permitted(current, payment=True)
                approved(form, request.user, dictionary)
                if current.status != 'transcript':
                    raise Conflict(_('This transcript has already been submitted.'))
                current.result['practice'].update(stage='review', original_text=form.cleaned_data['description'],
                    feedback_language=form.cleaned_data['feedback_language'])
                current.voice = form.cleaned_data['voice']
                current.status = 'waiting'
                current.save(update_fields=['result', 'status', 'voice'])
                transaction.on_commit(lambda: practice.queue(str(study.pk)))
                return url(current)
            return saved(request, submit_once(request, dictionary, f'practice-confirm:{study.pk}', confirm, ignore_fields=('quote',)))
        if choice == 'listen':
            if request.POST.get('permission') != 'yes':
                raise Conflict(_('Confirm the new audio request.'))
            def listen(paths):
                capture.locks()
                current = capture.fetch(study.pk, True)
                practice.permitted(current, payment=True)
                feedback = current.result['practice'].get('feedback', {})
                if current.status != 'feedback' or feedback.get('outcome') != 'ready':
                    raise Conflict(_('Read the feedback first.'))
                if not current.dictionary.tts_enabled or tts.language_code(current.language) not in tts.LANGUAGES.values():
                    raise Conflict(_('Saved audio is unavailable for this language.'))
                # One clip per attempt, including uncertain failures. Replaying
                # the player is free; a new practice attempt can request a new clip.
                if not current.speech.exists():
                    CaptureSpeech.objects.create(capture=current, kind='feedback', text=feedback['text'], language=current.language)
                    transaction.on_commit(lambda: practice.queue(str(current.pk)))
                return url(current)
            return saved(request, submit_once(request, dictionary, f'practice-listen:{study.pk}', listen))
        if choice == 'continue':
            practice.queue(str(study.pk))
        elif choice == 'discard':
            with transaction.atomic():
                capture.locks()
                capture.discard(PictureCapture.objects.filter(pk=study.pk, user=request.user))
            return redirect('community_dictionary:picture-practice', pk=pk)
        else:
            raise Conflict(_('Choose an action shown on this page.'))
        return saved(request, url(study))
    except Conflict as exc:
        return fail(request, exc, 409)
