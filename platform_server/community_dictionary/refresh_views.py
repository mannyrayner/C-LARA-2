"""One short confirmation page and resumable progress for a sentence refresh."""
from datetime import timedelta
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET, require_POST
from . import capture, capture_limits, refresh
from .models import PictureCapture, Participation
from .permissions import get_dictionary, require_editor
from .services import Conflict, submit_once
from .views import context, fail, get_entry, saved


class ApprovalForm(forms.Form):
    permission = forms.BooleanField(label=_('I approve the estimate and have permission to send this sentence, translation, picture and vocabulary to OpenAI, and the text needed for audio to the configured speech provider.'))
    quote = forms.CharField(widget=forms.HiddenInput)


def location(study):
    return reverse('community_dictionary:refresh-detail', args=[study.dictionary_id, study.pk])


def private(response):
    response['Cache-Control'] = 'no-store'
    return response


@login_required
def start(request, pk, entry_id):
    dictionary = get_dictionary(request.user, pk); require_editor(request.user, dictionary)
    entry = get_entry(dictionary, entry_id)
    form = ApprovalForm(request.POST or None)
    consent = None; error = ''
    try:
        consent = refresh.values(request.user, entry)
        if request.method == 'POST' and form.is_valid():
            def create(paths):
                capture.locks()
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                current = get_entry(get_dictionary(request.user, pk), entry_id)
                fresh = refresh.values(request.user, current)
                try: approved = signing.loads(form.cleaned_data['quote'], salt=refresh.SALT, max_age=600)
                except signing.BadSignature: raise Conflict(_('This estimate expired. Review a fresh estimate.'))
                if approved != fresh: raise Conflict(_('The sentence or settings changed. Review a fresh estimate.'))
                # Different submission IDs/double taps still share one live job.
                active = PictureCapture.objects.filter(dictionary=dictionary, saved_entry=current,
                    input_mode='refresh', expires_at__gt=timezone.now()).order_by('-created_at')
                for old in active:
                    same_input = old.result.get('refresh', {}).get('consent', {}).get('snapshot') == fresh['snapshot']
                    if same_input and old.status in {'waiting', 'processing', 'ready'} and old.user_id != request.user.pk:
                        raise Conflict(_('An update for this sentence is already running. Check the entry again shortly.'))
                    if old.result.get('refresh', {}).get('consent') != fresh: continue
                    if old.status in {'waiting', 'processing', 'ready'} or (old.status == 'saved'
                            and refresh.port_vocabulary.current_state(current) and (
                                old.speech.filter(status__in=['waiting', 'running']).exists()
                                or capture.failed_audio(old) or refresh.audio_complete(current))):
                        return location(old)
                capture_limits.enforce(dictionary, request.user)
                image_id = fresh['snapshot']['image']
                study = PictureCapture.objects.create(dictionary=dictionary, user=request.user,
                    saved_entry=current, source_image_id=image_id, input_mode='refresh',
                    expires_at=timezone.now()+timedelta(days=2), language=dictionary.language,
                    explanation_language=dictionary.explanation_language or 'English',
                    input_language=dictionary.language, description=current.word,
                    model=fresh['model'], personal_key=fresh['personal'], voice=capture.tts.VOICE,
                    revision=dictionary.capture_revision, membership_revision=dictionary.membership_revision,
                    participation_revision=Participation.objects.filter(dictionary=dictionary, user=request.user).values_list('revision', flat=True).first() or 0,
                    result={'refresh': {'version': refresh.VERSION, 'consent': fresh}})
                ids = [i for ref in refresh.port_vocabulary.context(dictionary) for i in (ref['text'], ref['meaning']) if i]
                study.sources.set(set(ids + fresh['snapshot']['ids']))
                capture.allowed(study, payment=True)
                if refresh.port_vocabulary.current_state(current):
                    # Audio can become missing later without invalidating words.
                    # This new, explicitly approved attempt needs no vocabulary call.
                    study.status = 'saved'; study.save(update_fields=['status'])
                    refresh.plan_audio(study, current)
                transaction.on_commit(lambda: refresh.queue(study.pk))
                return location(study)
            return saved(request, submit_once(request, dictionary, f'refresh:{entry.pk}', create))
    except (Conflict, OSError) as exc:
        error = str(exc)
    if not form.is_bound and consent:
        form = ApprovalForm(initial={'quote': signing.dumps(consent, salt=refresh.SALT)})
    return private(render(request, 'community_dictionary/refresh_start.html', context(request, dictionary,
        entry=entry, form=form, setup_error=error,
        estimate=capture_limits.unit_estimate(consent['rates']) if consent else None,
        personal=consent['personal'] if consent else False)))


def own(request, pk, study_id):
    dictionary = get_dictionary(request.user, pk); require_editor(request.user, dictionary)
    study = get_object_or_404(PictureCapture, pk=study_id, dictionary=dictionary,
        user=request.user, input_mode='refresh', expires_at__gt=timezone.now())
    capture.allowed(study)
    return dictionary, study


@login_required
@require_GET
def detail(request, pk, study_id):
    try:
        dictionary, study = own(request, pk, study_id)
        refresh.recover(study)
    except Conflict as exc: return fail(request, exc, 409)
    pending = study.speech.filter(status__in=['waiting', 'running']).exists()
    failed = capture.failed_audio(study)
    vocabulary_current = refresh.port_vocabulary.current_state(study.saved_entry) if study.status == 'saved' else False
    return private(render(request, 'community_dictionary/refresh_detail.html', context(request, dictionary,
        study=study, entry=study.saved_entry, pending=pending, failed_audio=failed,
        vocabulary_current=vocabulary_current,
        complete=study.status == 'saved' and vocabulary_current and not pending and not failed and refresh.audio_complete(study.saved_entry),
        polling=study.status in {'waiting', 'processing', 'ready'} or pending,
        audio_estimate=capture_limits.AUDIO_ALLOWANCE_USD)))


@login_required
@require_POST
def action(request, pk, study_id):
    try:
        dictionary, study = own(request, pk, study_id)
        choice = request.POST.get('action')
        if choice == 'continue':
            refresh.queue(study.pk)
        elif choice == 'retry-audio':
            if not request.POST.get('permission'): raise Conflict(_('Confirm the additional audio costs before retrying.'))
            def retry(paths):
                refresh.retry_audio(study.pk, request.user)
                return location(study)
            return saved(request, submit_once(request, dictionary, f'refresh-audio:{study.pk}', retry))
        else: raise Conflict(_('Choose an action shown on this page.'))
        return saved(request, location(study))
    except Conflict as exc: return fail(request, exc, 409)
