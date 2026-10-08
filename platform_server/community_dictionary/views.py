import json
import re
import uuid
import zipfile

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import serializers, signing
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from .forms import ContributionForm, DictionaryForm, DictionarySettingsForm, EntryAudioForm, EntryPictureForm, LinkWordForm, NoteForm, RequestForm
from .models import Contribution, Dictionary, Entry, ImageWordLink, Membership, Partner, Partnership, Participation, Request
from .lexicon import linked_words, outdated_tts, valid_links, vocabulary, word_row
from .permissions import entitled_dictionaries, dictionaries_for, get_dictionary, is_editor, is_coordinator, require_editor, require_owner
from .services import Conflict, accept, add_contributions, entry_url, event, submit_once
from .storage import delete_file, path_for, write_upload


def context(request, dictionary=None, **extra):
    return {'dictionary': dictionary, 'editor': bool(dictionary and is_editor(request.user, dictionary)), 'owner': bool(dictionary and dictionary.owner_id == request.user.pk), 'coordinator': bool(dictionary and is_coordinator(request.user, dictionary)), 'submission_id': uuid.uuid4(), **extra}


def fail(request, message, status=400):
    if 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({'error': str(message)}, status=status)
    return render(request, 'community_dictionary/error.html', {'message': message}, status=status)


def saved(request, url):
    if 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({'url': url, 'saved': True})
    return redirect(url)


def perform(request, dictionary, scope, callback):
    try:
        return saved(request, submit_once(request, dictionary, scope, callback))
    except Conflict as exc:
        return fail(request, exc, 409)


def get_entry(dictionary, pk):
    return get_object_or_404(Entry.objects.select_related('selected_image', 'current_text').prefetch_related('contributions__author'), dictionary=dictionary, pk=pk, archived=False)


def summary(entry, dictionary):
    contributions = list(entry.contributions.all())
    visible = [c for c in contributions if c.status in {'accepted', 'pending'} and c.kind != 'note']
    return {'entry': entry, 'image': entry.selected_image or next((c for c in visible if c.kind == 'image'), None), 'sample_audio': next((c for c in visible if c.kind == 'audio' and not outdated_tts(c, entry, dictionary)), None), 'accepted': any(c.status == 'accepted' for c in visible), 'pending': sum(c.status == 'pending' for c in visible)}


@login_required
def home(request):
    form = DictionaryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        dictionary = form.save(commit=False)
        dictionary.owner = request.user
        dictionary.save()
        event(dictionary, request.user, 'create_dictionary')
        return redirect('community_dictionary:dictionary', pk=dictionary.pk)
    from .participation import controls
    projects = [controls(request.user, d) for d in entitled_dictionaries(request.user)]
    invitations = list(Membership.objects.filter(user=request.user, accepted=False,
        status='invited', dictionary__personal=False, dictionary__archived=False).select_related('dictionary'))
    return render(request, 'community_dictionary/home.html', {
        'projects': [row for row in projects if not row['dictionary'].hidden],
        'hidden_projects': [row for row in projects if row['dictionary'].hidden],
        'invitations': [invite for invite in invitations if not invite.dictionary.hidden],
        'hidden_invitations': [invite for invite in invitations if invite.dictionary.hidden],
        'form': form})


@login_required
@require_POST
@transaction.atomic
def join_dictionary(request, pk):
    Dictionary.objects.select_for_update().get(pk=pk)
    membership = get_object_or_404(Membership, dictionary__archived=False, dictionary_id=pk, user=request.user, accepted=False, status='invited', dictionary__personal=False)
    membership.accepted = True
    membership.status = 'active'
    membership.save(update_fields=['accepted', 'status'])
    from django.db.models import F
    Dictionary.objects.filter(pk=pk).update(membership_revision=F('membership_revision') + 1)
    event(membership.dictionary, request.user, 'join_dictionary')
    return redirect('community_dictionary:dictionary', pk=pk)


@login_required
def dictionary(request, pk):
    from .participation import controls
    item = get_object_or_404(entitled_dictionaries(request.user), pk=pk)
    participation = controls(request.user, item)
    if not participation['can_browse']:
        return render(request, 'community_dictionary/participation_status.html', {'project': item, 'participation': participation})
    mode = request.GET.get('view') if request.GET.get('view') in {'words', 'sentences'} else 'pictures'
    show = request.GET.get('show', 'accepted') if mode == 'pictures' else 'accepted'
    query = request.GET.get('q', '').strip()[:200]
    category = request.GET.get('category', '')[:80]
    if mode == 'words':
        entries = vocabulary(item).order_by('word', 'pk')
        if query:
            entries = entries.filter(Q(word__icontains=query) | Q(meaning__icontains=query))
    else:
        entries = item.entries.filter(archived=False).select_related('selected_image', 'current_text').prefetch_related('contributions__author')
        if mode == 'sentences':
            entries = entries.filter(entry_type='sentence')
        else:
            entries = entries.exclude(entry_type='word', selected_image__isnull=True, current_text__provenance__origin='picture-description')
        if show == 'accepted':
            entries = entries.filter(contributions__status='accepted', contributions__kind__in=['text', 'image', 'audio'])
            if mode == 'pictures':
                from .lexicon import described_picture_sources
                entries = entries.exclude(pk__in=described_picture_sources(item).values('pk'))
        elif show == 'review':
            entries = entries.filter(contributions__status='pending')
        if query:
            linked_sources = valid_links(item).filter(Q(word_entry__word__icontains=query) | Q(word_entry__meaning__icontains=query)).values('image__entry_id')
            entries = entries.filter(Q(word__icontains=query) | Q(meaning__icontains=query) | Q(contributions__word__icontains=query, contributions__status__in=['accepted', 'pending']) | Q(contributions__meaning__icontains=query, contributions__status__in=['accepted', 'pending']) | Q(pk__in=linked_sources))
    if category:
        entries = entries.filter(category=category)
    page = Paginator(entries.distinct(), 24).get_page(request.GET.get('page'))
    categories = item.entries.filter(archived=False).exclude(category='').values_list('category', flat=True).distinct().order_by('category')
    cards = [summary(e, item) for e in page] if mode != 'words' else []
    words = [word_row(e, item) for e in page] if mode == 'words' else []
    return render(request, 'community_dictionary/dictionary.html', context(request, item, participation=participation, cards=cards, words=words, mode=mode, page=page, show=show, query=query, category=category, categories=categories))


@login_required
def contribute(request, pk, entry_id=None, request_id=None, audio_only=False, picture_only=False):
    dictionary = get_dictionary(request.user, pk)
    entry = get_entry(dictionary, entry_id) if entry_id else None
    response_to = None
    if request_id:
        response_to = get_object_or_404(Request.objects.select_related('entry', 'partnership'), pk=request_id, entry__dictionary=dictionary)
        if not Partner.objects.filter(partnership=response_to.partnership, user=request.user, accepted=True).exists():
            raise Http404
        if request.method == 'GET' and response_to.progress in {'complete', 'withdrawn'}:
            return fail(request, 'This request is closed. You can still contribute directly to the entry.', 409)
        entry = get_entry(dictionary, response_to.entry_id)
    editing = bool(entry and request.GET.get('wording') == '1' and not response_to and not audio_only and not picture_only)
    initial = {'publish_now': is_editor(request.user, dictionary), 'base_version': entry.text_version if entry else 0}
    if entry:
        from .text import field_snapshot
        initial['text_snapshot'] = signing.dumps({'entry': entry.pk, 'fields': field_snapshot(entry)}, salt='community-text-fields')
    if editing:
        initial.update(word=entry.word, meaning=entry.meaning, category=entry.category, edit_text=True)
    if picture_only:
        form = EntryPictureForm(request.POST or None, request.FILES or None, initial=initial)
    elif audio_only:
        form = EntryAudioForm(request.POST or None, request.FILES or None, initial=initial)
    else:
        form = ContributionForm(request.POST or None, request.FILES or None, initial=initial, dictionary=dictionary, user=request.user)
    if request.method == 'POST':
        if not form.is_valid():
            return fail(request, form.errors.as_text())
        if response_to and not form.cleaned_data.get('prepared_' + ('photo' if response_to.kind == 'image' else 'audio')):
            return fail(request, 'Please add the requested picture or recording.')
        def create(paths):
            if response_to:
                response_to.refresh_from_db()
                if response_to.progress in {'complete', 'withdrawn'}:
                    raise Conflict('This request has closed. Reload the entry before contributing.')
            target = entry or Entry.objects.create(dictionary=dictionary, created_by=request.user)
            publish = bool(is_editor(request.user, dictionary) and form.cleaned_data.get('publish_now'))
            add_contributions(target, request.user, form.cleaned_data, paths, publish=publish, response_to=response_to)
            return entry_url(target)
        scope = f'contribute:{entry.pk if entry else 0}:{request_id or 0}'
        return perform(request, dictionary, scope, create)
    template = ('community_dictionary/add_picture.html' if picture_only else
        'community_dictionary/record_audio.html' if audio_only else 'community_dictionary/contribute.html')
    image = summary(entry, dictionary)['image'] if audio_only or picture_only else None
    return render(request, template, context(request, dictionary, entry=entry, image=image, response_to=response_to, editing=editing, form=form))


@login_required
def entry_detail(request, pk, entry_id):
    dictionary = get_dictionary(request.user, pk)
    entry = get_entry(dictionary, entry_id)
    presentation = summary(entry, dictionary)
    if 'picture' in request.GET:
        try:
            picture_id = int(request.GET['picture'])
            if not 0 < picture_id < 2**63:
                raise ValueError
        except (ValueError, TypeError):
            raise Http404
        presentation['image'] = get_object_or_404(entry.contributions, pk=picture_id, kind='image', status='accepted')
        if not presentation['image'].file_path:
            raise Http404
    image = presentation['image']
    extra_words = list(linked_words(image, dictionary)) if image and image.status == 'accepted' else []
    link_form = None
    if image and image.status == 'accepted' and is_editor(request.user, dictionary):
        link_form = LinkWordForm(dictionary=dictionary, source_entry_id=entry.pk)
        link_form.fields['word_entry'].queryset = link_form.fields['word_entry'].queryset.exclude(pk__in=[e.pk for e in extra_words])
    contributions = [c for c in entry.contributions.all() if c.status not in {'removed', 'withdrawn', 'rejected'} or (c.status == 'rejected' and (c.author_id == request.user.pk or is_editor(request.user, dictionary)))]
    for contribution in contributions:
        contribution.outdated_tts = outdated_tts(contribution, entry, dictionary)
        from .text import FIELDS
        contribution.component_version = getattr(entry, FIELDS.get(contribution.text_field, ('current_text', 'text_version'))[1])
        contribution.is_current_component = contribution.text_field in FIELDS and getattr(entry, FIELDS[contribution.text_field][0] + '_id') == contribution.pk
    members_requests = entry.requests.select_related('partnership', 'created_by', 'completed_with').prefetch_related('responses')
    from .capture import sentence_context
    sentence_data = sentence_context(entry)
    if image and image.status == 'accepted':
        sentence_data['picture_sentences'] = Entry.objects.filter(dictionary=dictionary, entry_type='sentence', archived=False,
            selected_image__shared_from=image, selected_image__status='accepted').exclude(word='')
        if image.shared_from_id and image.shared_from.entry.dictionary_id == dictionary.pk and image.shared_from.status == 'accepted':
            sentence_data['original_picture'] = image.shared_from
    return render(request, 'community_dictionary/entry.html', context(request, dictionary, **sentence_data, **presentation, linked_words=[word_row(e, dictionary) for e in extra_words], link_form=link_form, contributions=contributions, audio=[c for c in contributions if c.kind == 'audio' and c.status == 'accepted' and not c.outdated_tts], notes=[c for c in reversed(contributions) if c.kind == 'note' and c.status != 'removed' and c.label != 'Partner request'], requests=members_requests, form=NoteForm(), can_request=Partnership.objects.filter(dictionary=dictionary, partners__user=request.user, partners__accepted=True).exists(), events=dictionary.events.filter(entry=entry).select_related('actor')[:30]))


@login_required
@require_POST
def comment(request, pk, entry_id):
    dictionary = get_dictionary(request.user, pk)
    entry = get_entry(dictionary, entry_id)
    form = NoteForm(request.POST, request.FILES)
    if not form.is_valid():
        return fail(request, form.errors.as_text())
    def create(paths):
        media = write_upload(form.cleaned_data['prepared_audio'], dictionary.pk, paths) if form.cleaned_data.get('prepared_audio') else {}
        note = Contribution.objects.create(entry=entry, author=request.user, kind='note', status='accepted', body=form.cleaned_data['body'], **media)
        event(dictionary, request.user, 'comment', entry, f'Comment {note.pk}' + ('; media permission confirmed' if media else ''))
        return entry_url(entry)
    return perform(request, dictionary, f'comment:{entry.pk}', create)


@login_required
@require_POST
def review(request, pk, contribution_id):
    dictionary = get_dictionary(request.user, pk)
    contribution = get_object_or_404(Contribution.objects.select_related('entry'), pk=contribution_id, entry__dictionary=dictionary)
    action = request.POST.get('action')
    if action == 'withdraw':
        return fail(request, 'Use Withdraw my content on the dictionary page.', 409)
    if action == 'remove':
        from .collections import withdraw
        try:
            require_editor(request.user, dictionary)
            if (contribution.controlled_by_id or contribution.author_id) == request.user.pk:
                raise Conflict('Use Withdraw my content on the dictionary page for your own material.')
            withdraw(request.user, [contribution.pk], moderator_dictionary=dictionary)
        except Conflict as exc:
            return fail(request, exc, 409)
        return redirect(entry_url(contribution.entry))
    require_editor(request.user, dictionary)
    try:
        with transaction.atomic():
            Dictionary.objects.select_for_update().get(pk=pk)
            get_dictionary(request.user, pk)
            entry = Entry.objects.select_for_update().get(pk=contribution.entry_id)
            contribution = get_object_or_404(Contribution, pk=contribution.pk, entry=entry)
            contribution.refresh_from_db()
            if action == 'accept':
                accept(contribution, request.user)
            elif action == 'reject':
                if contribution.status != 'pending':
                    raise Conflict('This contribution is no longer awaiting review.')
                contribution.status = 'rejected'
                contribution.save(update_fields=['status'])
                event(dictionary, request.user, action, entry, f'Contribution {contribution.pk}: {request.POST.get("reason", "")}'[:400])
            elif action == 'restore':
                from .text import FIELDS
                if contribution.kind != 'text' or contribution.status != 'accepted' or contribution.text_field not in FIELDS:
                    raise Conflict('Only a shared, accepted text component can be restored.')
                pointer, counter = FIELDS[contribution.text_field]
                if str(getattr(entry, counter)) != request.POST.get('version'):
                    raise Conflict('This component changed. Reload before restoring a version.')
                restored = Contribution.objects.create(entry=entry, author=contribution.author,
                    controlled_by=contribution.controlled_by, kind='text', text_field=contribution.text_field,
                    shared_from=contribution, previous_revision=getattr(entry, pointer),
                    base_version=getattr(entry, counter), provenance={**contribution.provenance, 'restored_by': request.user.pk},
                    **{contribution.text_field: getattr(contribution, contribution.text_field)})
                accept(restored, request.user)
                event(dictionary, request.user, 'restore_text', entry, f'Restored contribution {contribution.pk} as {restored.pk}')
            elif action == 'select':
                if contribution.kind != 'image' or contribution.status != 'accepted':
                    raise Conflict('Choose an accepted picture.')
                entry.selected_image = contribution
                entry.save(update_fields=['selected_image'])
                event(dictionary, request.user, 'select_image', entry, f'Contribution {contribution.pk}')
            else:
                return fail(request, 'Unknown review action.')
    except Conflict as exc:
        return fail(request, exc, 409)
    return redirect(entry_url(contribution.entry))


@login_required
@require_POST
def remove_entry(request, pk, entry_id):
    dictionary = get_dictionary(request.user, pk)
    require_editor(request.user, dictionary)
    entry = get_entry(dictionary, entry_id)
    from .collections import withdraw
    with transaction.atomic():
        ids = list(entry.contributions.exclude(status='removed').values_list('pk', flat=True))
        if ids:
            withdraw(request.user, ids, moderator_dictionary=dictionary)
        entry.archived = True
        entry.save(update_fields=['archived'])
        entry.requests.update(withdrawn=True)
        ImageWordLink.objects.filter(word_entry=entry).delete()
        event(dictionary, request.user, 'archive_entry', entry, 'Contributions retained in personal collections')
    return redirect('community_dictionary:dictionary', pk=pk)


@login_required
def ask(request, pk, entry_id):
    dictionary = get_dictionary(request.user, pk)
    entry = get_entry(dictionary, entry_id)
    form = RequestForm(request.POST or None, request.FILES or None, user=request.user, dictionary=dictionary)
    if request.method == 'POST':
        if not form.is_valid():
            return fail(request, form.errors.as_text())
        def create(paths):
            req = Request.objects.create(entry=entry, partnership=form.cleaned_data['partnership'], kind=form.cleaned_data['kind'], note=form.cleaned_data['note'], created_by=request.user)
            if form.cleaned_data.get('prepared_audio') or form.cleaned_data.get('note'):
                media = write_upload(form.cleaned_data['prepared_audio'], dictionary.pk, paths) if form.cleaned_data.get('prepared_audio') else {}
                Contribution.objects.create(entry=entry, author=request.user, kind='note', status='accepted',
                    body=form.cleaned_data.get('note', ''), label='Partner request', request=req, **media)
            event(dictionary, request.user, 'request', entry, f'Request {req.pk}: {req.kind}' + ('; media permission confirmed' if form.cleaned_data.get('prepared_audio') else ''))
            return entry_url(entry)
        return perform(request, dictionary, f'ask:{entry.pk}', create)
    return render(request, 'community_dictionary/ask.html', context(request, dictionary, entry=entry, form=form))


@login_required
def queue(request, pk):
    dictionary = get_dictionary(request.user, pk)
    groups = Partnership.objects.filter(dictionary=dictionary, partners__user=request.user, partners__accepted=True)
    reqs = Request.objects.filter(partnership__in=groups).select_related('entry__selected_image', 'partnership', 'created_by', 'completed_with').prefetch_related('responses', 'entry__contributions')
    selected = request.GET.get('group', '')
    if selected.isdigit():
        reqs = reqs.filter(partnership_id=int(selected))
    show = request.GET.get('show', 'all')
    rows = []
    for req in reqs:
        state = req.progress
        if state in {'complete', 'withdrawn'} and show != 'history':
            continue
        if show == 'history' and state not in {'complete', 'withdrawn'}:
            continue
        if show in {'audio', 'image'} and req.kind != show:
            continue
        if show == 'awaiting' and state != 'awaiting':
            continue
        rows.append({'request': req, 'state': state, **summary(req.entry, dictionary)})
    return render(request, 'community_dictionary/queue.html', context(request, dictionary, rows=rows, groups=groups, show=show, selected=selected))


@login_required
@require_POST
@transaction.atomic
def request_action(request, pk, request_id):
    Dictionary.objects.select_for_update().get(pk=pk)
    dictionary = get_dictionary(request.user, pk)
    req = get_object_or_404(Request, pk=request_id, entry__dictionary=dictionary)
    if req.created_by_id != request.user.pk:
        require_editor(request.user, dictionary)
    action = request.POST.get('action')
    if action not in {'withdraw', 'reopen'}:
        return fail(request, 'Unknown request action.')
    req.withdrawn = action == 'withdraw'
    if action == 'reopen':
        req.completed_with = None
    req.save()
    event(dictionary, request.user, action + '_request', req.entry, f'Request {req.pk}')
    return redirect(entry_url(req.entry))


def member_users(dictionary):
    withdrawn = Participation.objects.filter(dictionary=dictionary, withdrawn=True).values('user_id')
    return get_user_model().objects.filter(is_active=True).filter(Q(pk=dictionary.owner_id) | Q(membership__dictionary=dictionary, membership__accepted=True, membership__status='active')).exclude(pk__in=withdrawn).distinct().order_by('username')


@login_required
@require_POST
@transaction.atomic
def dictionary_visibility(request, pk):
    get_object_or_404(Dictionary.objects.select_for_update(), pk=pk)
    dictionary = get_dictionary(request.user, pk)
    require_owner(request.user, dictionary)
    visibility = request.POST.get('visibility')
    if visibility not in {'visible', 'hidden'}:
        return fail(request, 'Choose Visible or Hidden.', 400)
    hidden = visibility == 'hidden'
    # Explicit desired state makes repeated submissions harmless. Hiding does
    # not archive, withdraw, invalidate AI work, or change membership/permissions.
    if dictionary.hidden != hidden:
        dictionary.hidden = hidden
        dictionary.save(update_fields=['hidden'])
        event(dictionary, request.user, 'dictionary_visibility', detail=visibility)
    messages.success(request, 'Dictionary hidden from the main list.' if hidden else
                     'Dictionary visible in the main list again.')
    return redirect('community_dictionary:settings', pk=pk)


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def dictionary_settings(request, pk):
    if request.method == 'POST':
        get_object_or_404(Dictionary.objects.select_for_update(), pk=pk)
    dictionary = get_dictionary(request.user, pk)
    require_editor(request.user, dictionary)
    form = DictionarySettingsForm(instance=dictionary)
    if request.method == 'POST':
        require_owner(request.user, dictionary)
        form = DictionarySettingsForm(request.POST, instance=dictionary)
        if form.is_valid():
            if set(form.changed_data) & {'sentence_capture_enabled', 'tts_enabled', 'language', 'explanation_language'}:
                dictionary.capture_revision += 1
                from .capture import discard
                from .models import PictureCapture
                discard(PictureCapture.objects.filter(dictionary=dictionary).exclude(status='discarded'))
            if 'image_generation_enabled' in form.changed_data:
                dictionary.image_generation_revision += 1
                from .image_generation import discard_studies
                from .models import ImageStudy
                discard_studies(ImageStudy.objects.filter(dictionary=dictionary, status__in=['processing', 'ready']))
            form.save()
            event(dictionary, request.user, 'dictionary_settings')
            messages.success(request, 'Dictionary settings saved.')
            return redirect('community_dictionary:settings', pk=pk)
        # Bound form values survive, but style controls reflect saved policy.
        dictionary.refresh_from_db()
    from .capture_limits import usage
    from .capture_limit_views import AllowanceForm
    return render(request, 'community_dictionary/settings.html', context(request, dictionary, settings_form=form,
        capture_usage=usage(dictionary,request.user),
        capture_allowance_form=AllowanceForm(initial={'daily_limit':dictionary.capture_daily_limit})))


@login_required
@transaction.atomic
def people(request, pk):
    if request.method == 'POST':
        get_object_or_404(Dictionary.objects.select_for_update(), pk=pk)
    dictionary = get_dictionary(request.user, pk)
    if dictionary.personal:
        raise Http404
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'settings':
            # Keep forms opened before this update working, with the same checks.
            return dictionary_settings(request, pk)
        elif action == 'invite':
            require_owner(request.user, dictionary)
            user = get_user_model().objects.filter(username=request.POST.get('username', '').strip(), is_active=True).first()
            role = request.POST.get('role', 'member')
            if not user or user.pk == dictionary.owner_id or role not in {'member', 'editor'}:
                return fail(request, 'Choose an existing account other than the owner, and a valid role.')
            from . import membership as membership_service
            with transaction.atomic():
                locked = Dictionary.objects.select_for_update().get(pk=dictionary.pk)
                existing = Membership.objects.filter(dictionary=dictionary, user=user).first()
                if existing:
                    if existing.role != role:
                        try:
                            membership_service.propose(request.user, locked, 'role', existing, role)
                        except Conflict as exc:
                            return fail(request, exc, 409)
                    messages.success(request, 'Membership retained. Use the status controls to reactivate an inactive member.')
                else:
                    # A new coordinator must first join as an ordinary member.
                    if role != 'member' and locked.membership_policy == 'coordinators':
                        return fail(request, 'Invite as a member first, then propose the role change.', 409)
                    Membership.objects.create(dictionary=dictionary, user=user, role=role)
                    locked.membership_revision += 1
                    locked.save(update_fields=['membership_revision'])
                    event(dictionary, request.user, 'invite', detail=user.username)
                    messages.success(request, 'Invitation saved. No email is sent.')
        elif action == 'remove_member':
            return fail(request, 'Use Make inactive. Membership and contribution rights are retained.', 409)
        elif action == 'create_group':
            name = request.POST.get('name', '').strip()[:100]
            ids = set(request.POST.getlist('partners'))
            valid = list(member_users(dictionary).filter(pk__in=[int(i) for i in ids if i.isdigit()]).exclude(pk=request.user.pk))
            if not name or not valid or len(valid) != len(ids - {str(request.user.pk)}):
                return fail(request, 'Name the partnership and choose at least one other dictionary member.')
            with transaction.atomic():
                group = Partnership.objects.create(dictionary=dictionary, name=name, created_by=request.user)
                Partner.objects.create(partnership=group, user=request.user, accepted=True)
                Partner.objects.bulk_create([Partner(partnership=group, user=user) for user in valid])
                event(dictionary, request.user, 'create_partnership', detail=f'{group.pk}: {name}')
        elif action in {'join_group', 'leave_group'}:
            partner = get_object_or_404(Partner, pk=request.POST.get('partner_id'), user=request.user, partnership__dictionary=dictionary)
            if action == 'join_group':
                partner.accepted = True
                partner.save(update_fields=['accepted'])
            else:
                partner.delete()
            event(dictionary, request.user, action)
        elif action == 'invite_partner':
            group = get_object_or_404(Partnership, pk=request.POST.get('group_id'), dictionary=dictionary, partners__user=request.user, partners__accepted=True)
            user = member_users(dictionary).filter(username=request.POST.get('username', '').strip()).first()
            if not user:
                return fail(request, 'Choose someone who has already joined this dictionary.')
            Partner.objects.get_or_create(partnership=group, user=user)
            event(dictionary, request.user, 'invite_partner', detail=f'{group.pk}: {user.username}')
        else:
            return fail(request, 'Unknown membership action.')
        return redirect('community_dictionary:people', pk=pk)
    my_partners = Partner.objects.filter(user=request.user, partnership__dictionary=dictionary).select_related('partnership')
    group_rows = [{'group': p.partnership, 'membership': p, 'members': p.partnership.partners.select_related('user')} for p in my_partners]
    # Match the existing project collaborator picker: usernames only, owner-only.
    # Include current members because this same form also changes their roles.
    invite_accounts = (
        get_user_model().objects.filter(is_active=True).exclude(pk=dictionary.owner_id)
        .order_by('username').values_list('username', flat=True)
        if request.user.pk == dictionary.owner_id else []
    )
    memberships = list(dictionary.memberships.exclude(user_id=dictionary.owner_id).select_related('user'))
    withdrawn_users = set(Participation.objects.filter(dictionary=dictionary, withdrawn=True).values_list('user_id', flat=True))
    for member in memberships:
        member.content_withdrawn = member.user_id in withdrawn_users
    return render(request, 'community_dictionary/people.html', context(request, dictionary, memberships=memberships, people=member_users(dictionary), invite_accounts=invite_accounts, group_rows=group_rows, decisions=dictionary.membership_decisions.select_related('member__user', 'proposed_by', 'approved_by')[:30]))


@login_required
def media(request, pk, contribution_id):
    dictionary = get_dictionary(request.user, pk)
    item = get_object_or_404(Contribution, pk=contribution_id, entry__dictionary=dictionary)
    if not item.file_path or item.status in {'removed', 'withdrawn'}:
        raise Http404
    # Withdrawn material is no longer shared, while editors can inspect rejected proposals.
    if item.status == 'rejected' and item.author_id != request.user.pk and not is_editor(request.user, dictionary):
        raise Http404
    return private_media_response(request, item.file_path, item.mime_type, f'contribution-{item.pk}')


def private_media_response(request, relative, mime_type, filename):
    path = path_for(relative)
    if not path.is_file():
        raise Http404
    size = path.stat().st_size
    range_header = request.headers.get('Range', '')
    if range_header:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
        if not match or not any(match.groups()):
            return HttpResponse(status=416, headers={'Content-Range': f'bytes */{size}'})
        left, right = match.groups()
        start = int(left) if left else max(0, size - int(right))
        end = min(int(right), size - 1) if left and right else size - 1
        if start >= size or end < start or (not left and int(right) == 0):
            return HttpResponse(status=416, headers={'Content-Range': f'bytes */{size}'})
        def chunks():
            with path.open('rb') as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = stream.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        response = StreamingHttpResponse(chunks(), status=206, content_type=mime_type)
        response['Content-Range'] = f'bytes {start}-{end}/{size}'
        response['Content-Length'] = end - start + 1
    else:
        response = FileResponse(path.open('rb'), content_type=mime_type)
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Disposition'] = f'inline; filename="{filename}{path.suffix}"'
    return response


@login_required
@transaction.atomic
def export_dictionary(request, pk):
    dictionary = get_dictionary(request.user, pk)
    require_owner(request.user, dictionary)
    Dictionary.objects.select_for_update().get(pk=pk)
    dictionary = get_dictionary(request.user, pk)
    require_owner(request.user, dictionary)
    sets = [Dictionary.objects.filter(pk=pk), dictionary.memberships.all(), dictionary.partnerships.all(), Partner.objects.filter(partnership__dictionary=dictionary), dictionary.entries.all(), Contribution.objects.filter(entry__dictionary=dictionary).exclude(status__in=['withdrawn', 'removed']), Request.objects.filter(entry__dictionary=dictionary), ImageWordLink.objects.filter(image__entry__dictionary=dictionary, word_entry__dictionary=dictionary), dictionary.events.all(), dictionary.membership_decisions.all()]
    from .models import SentenceWord, AttentionReport, LanguageCheck
    from .capture import sentence_links
    sets += [sentence_links(dictionary), AttentionReport.objects.filter(entry__dictionary=dictionary, note__entry__dictionary=dictionary),
             LanguageCheck.objects.filter(entry__dictionary=dictionary, text__entry__dictionary=dictionary)]
    objects = [obj for queryset in sets for obj in queryset]
    media_items = list(Contribution.objects.filter(entry__dictionary=dictionary).exclude(status__in=['withdrawn', 'removed']).exclude(file_path=''))
    user_ids = {dictionary.owner_id}
    for obj in objects:
        for field in ['user_id', 'author_id', 'created_by_id', 'actor_id', 'controlled_by_id', 'proposed_by_id', 'approved_by_id']:
            value = getattr(obj, field, None)
            if value:
                user_ids.add(value)
    users = list(get_user_model().objects.filter(pk__in=user_ids).values('id', 'username'))
    # Spool large bundles to a temporary file instead of holding all media in RAM.
    import tempfile
    output = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    try:
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps({'format': 'clara-community-dictionary', 'version': 3, 'dictionary_id': pk, 'origin': 'mixed' if any(isinstance(obj, Contribution) and obj.provenance for obj in objects) else 'human', 'users': users}, ensure_ascii=False, indent=2))
            records = json.loads(serializers.serialize('json', objects))
            exported_parts = {o.pk for o in objects if isinstance(o, Contribution)}
            exported_entries = {o.pk for o in objects if isinstance(o, Entry)}
            for row in records:
                fields = row['fields']
                if row['model'] == 'community_dictionary.contribution':
                    for field in ['shared_from', 'previous_revision']:
                        if fields.get(field) not in exported_parts:
                            fields[field] = None
                    if fields.get('withdrawn_from') not in exported_entries:
                        fields['withdrawn_from'] = None
                elif row['model'] == 'community_dictionary.entry':
                    fields['collection_source'] = None
                elif row['model'] == 'community_dictionary.dictionary':
                    fields['collection_source'] = None
                    if fields.get('image_style') not in exported_parts:
                        fields['image_style'] = None
            archive.writestr('records.json', json.dumps(records, ensure_ascii=False, indent=2))
            from .models import ContributionDependency
            links = list(ContributionDependency.objects.filter(derived_id__in=exported_parts).values('source_id','derived_id'))
            archive.writestr('provenance-links.json', json.dumps(links, indent=2))
            archive.writestr('README.txt', 'Portable dictionary export. records.json contains Django-labelled records and original IDs; manifest.json maps contributor IDs to usernames. media/ paths match contribution file_path fields. Additional picture-to-word links are included as community_dictionary.imagewordlink records; original picture-to-word associations follow the picture contribution’s entry. Credentials and submission receipts are excluded. provenance-links.json retains IDs of additional sources used by derived contributions; external source records are not included. Cross-dictionary withdrawal links require the full server database. This is an interchange export, not a full server backup. Use database plus private-media backups for operational restoration.\n')
            written = set()
            for item in media_items:
                if item.file_path not in written:
                    archive.write(path_for(item.file_path), 'media/' + item.file_path)
                    written.add(item.file_path)
        output.seek(0)
    except Exception:
        output.close()
        raise
    response = FileResponse(output, as_attachment=True, filename=f'community-dictionary-{pk}.zip')
    response['Cache-Control'] = 'private, no-store'
    return response
