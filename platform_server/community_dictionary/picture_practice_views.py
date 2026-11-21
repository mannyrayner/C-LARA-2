"""Describe an existing picture, without creating dictionary content."""
from datetime import timedelta
from urllib.parse import urlencode
from django import forms
from django.http import Http404
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy as L_
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from . import capture, capture_limits, picture_practice as practice, practice_hints, practice_recognition, tts, writing
from .models import PictureCapture, CaptureSpeech, Participation
from .permissions import get_dictionary
from .port_views import no_store
from .services import Conflict, submit_once
from .storage import path_for, prepare_upload, write_upload
from .views import context, fail, saved, private_media_response
from .voices import VOICE_CHOICES
from .practice_costs import summary as cost_summary
from .learning import LEVELS
from . import practice_history

SALT = 'picture-practice-2'
SESSION_SECONDS = 7200


def consent_key(dictionary):
    return f'picture-practice-consent-{dictionary.pk}'


def session_permission(request, dictionary, values):
    stored = request.session.get(consent_key(dictionary), {})
    return bool(values and stored.get('quote') == values and stored.get('user') == request.user.pk and
                stored.get('expires', 0) > timezone.now().timestamp())


def remember_permission(request, dictionary, values):
    request.session[consent_key(dictionary)] = {'user': request.user.pk, 'quote': values,
        'expires': timezone.now().timestamp() + SESSION_SECONDS}


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
    level = forms.ChoiceField(required=False, label=L_('My proficiency'), choices=[
        ('unspecified', L_('Not specified')), *LEVELS])
    share_log = forms.BooleanField(required=False, label=L_(
        'Share this attempt’s diagnostic log with dictionary owners for improving feedback.'))
    hints_used = forms.CharField(required=False, max_length=100, widget=forms.HiddenInput)

    def clean_hints_used(self):
        try:
            return practice_hints.parse_usage(self.cleaned_data.get('hints_used'))
        except (ValueError, TypeError):
            raise forms.ValidationError(_('Reload this page to start a new practice attempt.'))

    def __init__(self, *args, dictionary, transcript=False, needs_permission=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.transcript = transcript
        self.fields['permission'].required = needs_permission
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
            quote=signing.dumps(values, salt=SALT), consent_values=values, setup_error='')
    except Conflict as exc:
        return dict(estimate=None, personal=False, quote='', consent_values=None, setup_error=str(exc))


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
        if request.method == 'GET':
            practice_history.select(request, dictionary, candidates, image=image)
    else:
        skip = candidates.filter(pk=request.GET.get('skip')).first() if request.GET.get('skip', '').isdigit() else None
        image = practice_history.select(request, dictionary, candidates, skip=skip) if request.method == 'GET' else None
    if request.method == 'GET' and image and not image_id:
        # Pin the picture in the URL, so a recovered device draft cannot silently
        # be paired with a newly chosen random image after a reload.
        return redirect(reverse('community_dictionary:picture-practice', args=[pk]) + '?' +
            urlencode({'image': image.pk, 'category': category}))
    config = setup(request.user, dictionary)
    needs_permission = not session_permission(request, dictionary, config['consent_values'])
    initial = {'mode': 'voice', 'feedback_language': dictionary.explanation_language or 'English',
        'voice': tts.VOICE, 'level': 'unspecified', **practice.choices(request.user, dictionary), 'quote': config['quote']}
    if request.GET.get('from'):
        try:
            previous = practice.own(request.user, dictionary, request.GET['from'])
            if image and previous.source_image_id == image.pk:
                initial['description'] = previous.result['practice'].get('original_text', '')
        except (Conflict, forms.ValidationError, ValueError):
            pass
    form = PracticeForm(request.POST or None, request.FILES or None, dictionary=dictionary,
        initial=initial, needs_permission=needs_permission)
    if request.method == 'POST' and image and form.is_valid():
        try:
            def create(paths):
                capture.locks()
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                current = get_dictionary(request.user, pk)
                if not practice.available(current):
                    raise Conflict(_('Practice settings changed. Reload this page.'))
                values = approved(form, request.user, current)
                if not form.cleaned_data['permission'] and not session_permission(request, current, values):
                    raise Conflict(_('Confirm permission for this practice session.'))
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
                        'level': form.cleaned_data.get('level') or 'unspecified',
                        'share_log': form.cleaned_data['share_log'], 'confirmed': False,
                        'hints_used': form.cleaned_data['hints_used'],
                        'hint_recipe': practice_hints.VERSION,
                        'diagnostics': {'schema': 1, 'prompt_version': practice.practice_review.VERSION, 'events': []},
                        'feedback_language': form.cleaned_data['feedback_language']}})
                study.sources.add(source)
                practice.permitted(study, payment=True)
                practice.save_choices(request.user, current, {key: form.cleaned_data.get(key) for key in
                    ['mode', 'feedback_language', 'voice', 'level', 'share_log']})
                remember_permission(request, current, values)
                transaction.on_commit(lambda: practice.queue(str(study.pk)))
                return url(study)
            return saved(request, submit_once(request, dictionary, 'picture-practice', create, ignore_fields=('quote', 'permission')))
        except (Conflict, forms.ValidationError, OSError) as exc:
            if not capture_limits.show_exhausted(request, exc):
                form.add_error(None, _('The picture file is unavailable.') if isinstance(exc, OSError) else str(exc))
    if request.method == 'POST' and 'application/json' in request.headers.get('Accept', ''):
        return fail(request, form.errors.as_text() or _('Choose an available picture.'), 409)
    recent = PictureCapture.objects.filter(dictionary=dictionary, user=request.user, input_mode='practice',
        expires_at__gt=timezone.now()).exclude(status='discarded').order_by('-created_at')[:8]
    return no_store(render(request, 'community_dictionary/picture_practice_start.html', context(request, dictionary,
        form=form, image=image, hints=practice_hints.material(image, dictionary),
        hint_language=tts.language_code(dictionary.language), recent=recent,
        category=category, needs_permission=needs_permission, **config,
        practice_overview=practice_history.overview(request.user, dictionary),
        submission_id=request.POST.get('submission_id') or context(request)['submission_id'])))


def page(request, dictionary, study, form=None):
    info = study.result['practice']
    feedback = info.get('feedback', {})
    config = setup(request.user, dictionary)
    needs_permission = not session_permission(request, dictionary, config['consent_values'])
    if form is None:
        form = PracticeForm(dictionary=dictionary, transcript=True, needs_permission=needs_permission, initial={
            'mode': 'text', 'description': info.get('original_text', ''), 'feedback_language': info['feedback_language'],
            'voice': study.voice, 'level': info.get('level', 'unspecified'), 'share_log': info.get('share_log', False),
            'quote': config['quote']})
    clips = study.speech.filter(kind='feedback').order_by('-pk')
    clip = clips.first()
    help_targets = []
    for target in info.get('recognition_help', {}).get('targets', []):
        parts = []
        for part, kind in practice_recognition.KINDS.items():
            parts.append({'part': part, 'text': target[part],
                'clip': study.speech.filter(kind=kind, text_id=target['id']).first(),
                'estimate': tts.estimate_cost(target[part], 5 if part == 'word' else 10)})
        help_targets.append({**target, 'parts': parts})
    polling = study.status in {'waiting', 'processing'} or study.speech.filter(status__in=['waiting', 'running']).exists()
    return no_store(render(request, 'community_dictionary/picture_practice_detail.html', context(request, dictionary,
        study=study, info=info, feedback=feedback, form=form, polling=polling, clip=clip,
        help_targets=help_targets,
        needs_permission=needs_permission, cost_summary=cost_summary(study),
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
        if choice in {'check', 'revise', 'use_suggestion'}:
            config = setup(request.user, dictionary)
            posted = request.POST.copy()
            if choice == 'use_suggestion':
                proposed = study.result['practice'].get('recognition_help', {}).get('proposed_text')
                if not proposed:
                    raise Conflict(_('This suggestion is no longer available.'))
                # Never accept a replacement sentence supplied by the browser.
                posted['description'] = proposed
            form = PracticeForm(posted, dictionary=dictionary, transcript=True,
                needs_permission=not session_permission(request, dictionary, config['consent_values']))
            if not form.is_valid():
                return page(request, dictionary, study, form)
            if choice == 'revise':
                def revise(paths):
                    capture.locks()
                    get_user_model().objects.select_for_update().get(pk=request.user.pk)
                    old = practice.own(request.user, dictionary, study.pk)
                    if old.status not in {'feedback', 'failed'}:
                        raise Conflict(_('Wait for the current attempt to finish.'))
                    values = approved(form, request.user, dictionary)
                    if not form.cleaned_data['permission'] and not session_permission(request, dictionary, values):
                        raise Conflict(_('Confirm permission for this practice session.'))
                    capture_limits.enforce(dictionary, request.user)
                    photo = write_upload((path_for(old.file_path).read_bytes(), 'image/jpeg', '.jpg'), pk, paths)
                    old_info = old.result['practice']
                    new = PictureCapture.objects.create(dictionary=dictionary, user=request.user,
                        source_image=old.source_image, input_mode='practice', status='waiting',
                        expires_at=timezone.now()+timedelta(days=30), language=dictionary.language,
                        input_language=dictionary.language, explanation_language=dictionary.explanation_language or 'English',
                        file_path=photo['file_path'], model=values['model'], personal_key=values['personal'],
                        voice=form.cleaned_data['voice'], revision=dictionary.capture_revision,
                        membership_revision=dictionary.membership_revision, participation_revision=old.participation_revision,
                        usage={'practice_request': {'cost_usd': '0', 'tokens': {}}}, result={'practice': {
                            'quote': values, 'mode': old_info['mode'], 'stage': 'review', 'confirmed': True,
                            'original_text': form.cleaned_data['description'], 'transcript': old_info.get('transcript', ''),
                            'parent_attempt': str(old.pk), 'category': old_info.get('category', ''),
                            'hints_used': old_info.get('hints_used'),
                            'hint_recipe': old_info.get('hint_recipe'),
                            'level': form.cleaned_data.get('level') or 'unspecified', 'share_log': form.cleaned_data['share_log'],
                            'feedback_language': form.cleaned_data['feedback_language'],
                            'diagnostics': {'schema': 1, 'prompt_version': practice.practice_review.VERSION, 'events': []}}})
                    new.sources.add(old.source_image)
                    practice.permitted(new, payment=True)
                    practice.diagnostic(new, 'learner_revision', 'submitted', parent=str(old.pk))
                    new.save(update_fields=['result'])
                    remember_permission(request, dictionary, values)
                    transaction.on_commit(lambda: practice.queue(str(new.pk)))
                    return url(new)
                return saved(request, submit_once(request, dictionary, f'practice-revise:{study.pk}', revise,
                    ignore_fields=('quote', 'permission')))
            def confirm(paths):
                capture.locks()
                current = capture.fetch(study.pk, True)
                practice.permitted(current, payment=True)
                values = approved(form, request.user, dictionary)
                if not form.cleaned_data['permission'] and not session_permission(request, dictionary, values):
                    raise Conflict(_('Confirm permission for this practice session.'))
                if current.status != 'transcript':
                    raise Conflict(_('This transcript has already been submitted.'))
                if choice == 'use_suggestion' and form.cleaned_data['description'] != current.result['practice'].get('recognition_help', {}).get('proposed_text'):
                    raise Conflict(_('This suggestion changed. Reload the page.'))
                method = 'suggestion' if choice == 'use_suggestion' else (
                    'edited' if form.cleaned_data['description'] != current.result['practice'].get('original_text') else 'unchanged')
                current.result['practice'].update(stage='review', original_text=form.cleaned_data['description'],
                    feedback_language=form.cleaned_data['feedback_language'], confirmed=True,
                    confirmed_text=form.cleaned_data['description'], recognition_confirmation={
                        'method': method, 'text': form.cleaned_data['description'], 'at': timezone.now().isoformat()})
                practice.diagnostic(current, 'recognition_confirmation', 'confirmed',
                    method=method,
                    text_changed=form.cleaned_data['description'] != study.result['practice'].get('original_text'))
                remember_permission(request, dictionary, values)
                current.voice = form.cleaned_data['voice']
                current.status = 'waiting'
                current.save(update_fields=['result', 'status', 'voice'])
                transaction.on_commit(lambda: practice.queue(str(study.pk)))
                return url(current)
            return saved(request, submit_once(request, dictionary, f'practice-confirm:{study.pk}', confirm, ignore_fields=('quote', 'permission')))
        if choice == 'listen_help':
            if request.POST.get('permission') != 'yes':
                raise Conflict(_('Confirm the new audio request.'))
            part = request.POST.get('part')
            kind = practice_recognition.KINDS.get(part)
            try:
                target = int(request.POST.get('target', ''))
            except (ValueError, TypeError):
                raise Conflict(_('Choose a suggestion shown on this page.'))
            if not kind or target not in range(1, 4):
                raise Conflict(_('Choose a suggestion shown on this page.'))
            def listen_help(paths):
                capture.locks()
                current = capture.fetch(study.pk, True)
                practice.permitted(current, payment=True)
                spec = practice_recognition.clip_spec(current.result['practice'], kind, target)
                if current.status != 'transcript' or not spec or current.result['practice'].get('mode') != 'voice':
                    raise Conflict(_('Choose a suggestion shown on this page.'))
                if not current.dictionary.tts_enabled or tts.language_code(current.language) not in tts.LANGUAGES.values():
                    raise Conflict(_('Saved audio is unavailable for this language.'))
                # One paid attempt for each displayed word/phrase, including
                # uncertain failures. Duplicate taps can only reuse that attempt.
                if not current.speech.filter(kind=kind, text_id=target).exists():
                    CaptureSpeech.objects.create(capture=current, kind=kind, text_id=target,
                        language=current.language, **spec)
                    practice.diagnostic(current, 'recognition_playback', 'requested', target=target, part=part)
                    current.save(update_fields=['result'])
                    transaction.on_commit(lambda: practice.queue(str(current.pk)))
                return url(current)
            return saved(request, submit_once(request, dictionary, f'practice-help:{study.pk}:{target}:{part}', listen_help))
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
                if not current.speech.filter(kind='feedback').exists():
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


@login_required
@require_GET
def help_audio(request, pk, study_id, clip_id):
    dictionary = get_dictionary(request.user, pk)
    try:
        study = practice.own(request.user, dictionary, study_id)
        clip = get_object_or_404(study.speech, pk=clip_id,
            kind__in=practice_recognition.KINDS.values(), status='ready')
        capture.speech_allowed(clip)
        return private_media_response(request, clip.file_path, 'audio/wav', 'practice-pronunciation')
    except Conflict:
        raise Http404


@login_required
@require_POST
def end_session(request, pk):
    dictionary = get_dictionary(request.user, pk)
    request.session.pop(consent_key(dictionary), None)
    return redirect('community_dictionary:practice', pk=pk)


@login_required
@require_GET
def diagnostic_log(request, pk):
    """Private JSON export; owners see only individually opted-in attempts."""
    from django.http import JsonResponse
    from .permissions import require_owner
    dictionary = get_dictionary(request.user, pk)
    shared = request.GET.get('shared') == '1'
    try:
        limit = min(200, max(1, int(request.GET.get('limit', 200))))
    except ValueError:
        limit = 200
    qs = PictureCapture.objects.filter(dictionary=dictionary, input_mode='practice',
        expires_at__gt=timezone.now()).exclude(status='discarded')
    if shared:
        require_owner(request.user, dictionary)
        qs = qs.filter(result__practice__share_log=True)
    else:
        qs = qs.filter(user=request.user)
    rows = []
    for study in qs.select_related('user', 'dictionary').order_by('-created_at')[:limit]:
        try:
            practice.permitted(study)
        except (Conflict, Http404):
            continue
        info = study.result.get('practice', {})
        rows.append({'attempt_id': str(study.pk), 'created_at': study.created_at.isoformat(),
            'learner_id': study.user_id, 'source_image_id': study.source_image_id,
            'language': study.language, 'feedback_language': info.get('feedback_language'),
            'input_mode': info.get('mode'), 'proficiency': info.get('level', 'unspecified'),
            'hints_used': info.get('hints_used'),
            'hint_recipe': info.get('hint_recipe'),
            'status': study.status, 'model': study.model, 'app_recipe': info.get('quote', {}).get('version'),
            'raw_transcript': info.get('transcript', ''), 'submitted_text': info.get('original_text', ''),
            'normalised_text': info.get('heard', ''), 'confirmed_by_learner': info.get('confirmed', False),
            'confirmed_text': info.get('confirmed_text', ''),
            'recognition_help': info.get('recognition_help', {}),
            'recognition_confirmation': info.get('recognition_confirmation', {}),
            'recognition_audio': [{'target': clip.text_id,
                'part': 'word' if clip.kind == 'help_word' else 'phrase', 'status': clip.status,
                **tts.public_diagnostic(clip.report or {})}
                for clip in study.speech.filter(kind__in=practice_recognition.KINDS.values()).order_by('pk')],
            'recognition_question': info.get('recognition_question', ''), 'feedback': info.get('feedback', {}),
            'review_decision': info.get('review_decision', {}), 'reviews': info.get('review_log', []),
            'diagnostics': info.get('diagnostics', {}), 'user_report': info.get('user_report', {}),
            'user_reports': info.get('user_reports', []), 'parent_attempt': info.get('parent_attempt'),
            'usage': study.usage, 'shared_with_owners': bool(info.get('share_log'))})
        rows[-1]['cost_summary'] = cost_summary(study)
    response = JsonResponse({'schema': 'picture-practice-log-1', 'dictionary_id': dictionary.pk,
        'scope': 'shared_with_owners' if shared else 'my_attempts', 'limit': limit, 'attempts': rows},
        json_dumps_params={'ensure_ascii': False, 'indent': 2})
    if request.GET.get('view') != '1':
        response['Content-Disposition'] = f'attachment; filename="practice-{dictionary.pk}.json"'
    response['X-Content-Type-Options'] = 'nosniff'
    return no_store(response)


@login_required
@require_POST
def report(request, pk, study_id):
    """Learner labels provide tuning evidence; no paid request or text rewriting."""
    dictionary = get_dictionary(request.user, pk)
    try:
        practice.own(request.user, dictionary, study_id)
        label = request.POST.get('problem', '')
        if label not in {'', 'recognition', 'feedback', 'helpful', 'other'}:
            raise Conflict(_('Choose the kind of feedback.'))
        note = request.POST.get('note', '').strip()
        intended = request.POST.get('intended', '').strip()
        if len(note) > 600 or len(intended) > 255:
            raise Conflict(_('Keep the report short.'))
        with transaction.atomic():
            capture.locks()
            study = practice.own(request.user, dictionary, study_id)
            # Lock the attempt and revalidate before editing private diagnostics.
            study = capture.fetch(study.pk, True)
            practice.permitted(study)
            info = study.result['practice']
            if label or note or intended:
                info['user_report'] = {'label': label or 'other', 'note': note,
                    'intended_text': intended, 'at': timezone.now().isoformat()}
                info['user_reports'] = [*info.get('user_reports', []), info['user_report']][-10:]
            info['share_log'] = request.POST.get('share_log') == 'on'
            study.save(update_fields=['result'])
        return saved(request, url(study))
    except Conflict as exc:
        return fail(request, exc, 409)
