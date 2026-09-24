import json
import re
import uuid
import zipfile

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ContributionForm, DictionaryForm, DictionarySettingsForm, NoteForm, RequestForm
from .models import Contribution, Dictionary, Entry, Membership, Partner, Partnership, Request
from .permissions import dictionaries_for, get_dictionary, is_editor, require_editor, require_owner
from .services import Conflict, accept, add_contributions, entry_url, event, submit_once
from .storage import delete_file, path_for, write_upload


def context(request, dictionary=None, **extra):
    return {'dictionary': dictionary, 'editor': bool(dictionary and is_editor(request.user, dictionary)), 'owner': bool(dictionary and dictionary.owner_id == request.user.pk), 'submission_id': uuid.uuid4(), **extra}


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
    return get_object_or_404(Entry.objects.select_related('selected_image', 'current_text').prefetch_related('contributions__author'), dictionary=dictionary, pk=pk)


def summary(entry):
    contributions = list(entry.contributions.all())
    visible = [c for c in contributions if c.status in {'accepted', 'pending'} and c.kind != 'note']
    return {'entry': entry, 'image': entry.selected_image or next((c for c in visible if c.kind == 'image'), None), 'sample_audio': next((c for c in visible if c.kind == 'audio'), None), 'accepted': any(c.status == 'accepted' for c in visible), 'pending': sum(c.status == 'pending' for c in visible)}


@login_required
def home(request):
    form = DictionaryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        dictionary = form.save(commit=False)
        dictionary.owner = request.user
        dictionary.save()
        event(dictionary, request.user, 'create_dictionary')
        return redirect('community_dictionary:dictionary', pk=dictionary.pk)
    return render(request, 'community_dictionary/home.html', {'dictionaries': dictionaries_for(request.user), 'invitations': Membership.objects.filter(user=request.user, accepted=False).select_related('dictionary'), 'form': form})


@login_required
@require_POST
def join_dictionary(request, pk):
    membership = get_object_or_404(Membership, dictionary_id=pk, user=request.user, accepted=False)
    membership.accepted = True
    membership.save(update_fields=['accepted'])
    event(membership.dictionary, request.user, 'join_dictionary')
    return redirect('community_dictionary:dictionary', pk=pk)


@login_required
def dictionary(request, pk):
    item = get_dictionary(request.user, pk)
    entries = item.entries.select_related('selected_image', 'current_text').prefetch_related('contributions__author')
    show = request.GET.get('show', 'accepted')
    if show == 'accepted':
        entries = entries.filter(contributions__status='accepted', contributions__kind__in=['text', 'image', 'audio'])
    elif show == 'review':
        entries = entries.filter(contributions__status='pending')
    query = request.GET.get('q', '').strip()[:200]
    category = request.GET.get('category', '')[:80]
    if query:
        entries = entries.filter(Q(word__icontains=query) | Q(meaning__icontains=query) | Q(contributions__word__icontains=query) | Q(contributions__meaning__icontains=query))
    if category:
        entries = entries.filter(category=category)
    page = Paginator(entries.distinct(), 24).get_page(request.GET.get('page'))
    categories = item.entries.exclude(category='').values_list('category', flat=True).distinct().order_by('category')
    return render(request, 'community_dictionary/dictionary.html', context(request, item, cards=[summary(e) for e in page], page=page, show=show, query=query, category=category, categories=categories))


@login_required
def contribute(request, pk, entry_id=None, request_id=None):
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
    editing = bool(entry and request.GET.get('wording') == '1' and not response_to)
    initial = {'publish_now': is_editor(request.user, dictionary), 'base_version': entry.text_version if entry else 0}
    if editing:
        initial.update(word=entry.word, meaning=entry.meaning, category=entry.category, edit_text=True)
    form = ContributionForm(request.POST or None, request.FILES or None, initial=initial, dictionary=dictionary)
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
    return render(request, 'community_dictionary/contribute.html', context(request, dictionary, entry=entry, response_to=response_to, editing=editing, form=form))


@login_required
def entry_detail(request, pk, entry_id):
    dictionary = get_dictionary(request.user, pk)
    entry = get_entry(dictionary, entry_id)
    contributions = [c for c in entry.contributions.all() if c.status not in {'withdrawn', 'rejected'} or c.author_id == request.user.pk or is_editor(request.user, dictionary)]
    members_requests = entry.requests.select_related('partnership', 'created_by', 'completed_with').prefetch_related('responses')
    return render(request, 'community_dictionary/entry.html', context(request, dictionary, **summary(entry), contributions=contributions, audio=[c for c in contributions if c.kind == 'audio' and c.status == 'accepted'], notes=[c for c in reversed(contributions) if c.kind == 'note' and c.status != 'removed'], requests=members_requests, form=NoteForm(), can_request=Partnership.objects.filter(dictionary=dictionary, partners__user=request.user, partners__accepted=True).exists(), events=dictionary.events.filter(entry=entry).select_related('actor')[:30]))


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
        if contribution.author_id != request.user.pk or contribution.status != 'pending':
            raise Http404
    elif action == 'remove' and contribution.kind == 'note' and contribution.author_id == request.user.pk:
        pass
    else:
        require_editor(request.user, dictionary)
    try:
        with transaction.atomic():
            entry = Entry.objects.select_for_update().get(pk=contribution.entry_id)
            contribution.refresh_from_db()
            if action == 'accept':
                accept(contribution, request.user)
            elif action in {'reject', 'withdraw'}:
                if contribution.status != 'pending':
                    raise Conflict('This contribution is no longer awaiting review.')
                contribution.status = 'rejected' if action == 'reject' else 'withdrawn'
                contribution.save(update_fields=['status'])
                event(dictionary, request.user, action, entry, f'Contribution {contribution.pk}: {request.POST.get("reason", "")}'[:400])
            elif action == 'restore':
                if contribution.kind != 'text' or contribution.status != 'accepted':
                    raise Conflict('Only an accepted wording version can be restored.')
                if str(entry.text_version) != request.POST.get('version'):
                    raise Conflict('The wording changed. Reload before restoring a version.')
                restored = Contribution.objects.create(entry=entry, author=request.user, kind='text', word=contribution.word, meaning=contribution.meaning, category=contribution.category, base_version=entry.text_version)
                accept(restored, request.user)
                event(dictionary, request.user, 'restore_text', entry, f'Restored contribution {contribution.pk} as {restored.pk}')
            elif action == 'select':
                if contribution.kind != 'image' or contribution.status != 'accepted':
                    raise Conflict('Choose an accepted picture.')
                entry.selected_image = contribution
                entry.save(update_fields=['selected_image'])
                event(dictionary, request.user, 'select_image', entry, f'Contribution {contribution.pk}')
            elif action == 'remove':
                if entry.current_text_id == contribution.pk:
                    entry.current_text = None
                    entry.word = entry.meaning = entry.category = ''
                    entry.text_version += 1
                if entry.selected_image_id == contribution.pk:
                    entry.selected_image = None
                entry.save()
                old_path = contribution.file_path
                contribution.status = 'removed'
                contribution.file_path = ''
                contribution.file_size = 0
                contribution.word = contribution.meaning = contribution.category = ''
                contribution.body = contribution.label = contribution.mime_type = ''
                contribution.save()
                Request.objects.filter(completed_with=contribution).update(completed_with=None)
                transaction.on_commit(lambda: delete_file(old_path))
                event(dictionary, request.user, 'remove_contribution', entry, f'Contribution {contribution.pk}')
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
    paths = list(entry.contributions.exclude(file_path='').values_list('file_path', flat=True))
    with transaction.atomic():
        event(dictionary, request.user, 'remove_entry', detail=f'Entry {entry.pk}')
        entry.delete()
        for path in paths:
            transaction.on_commit(lambda path=path: delete_file(path))
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
            if form.cleaned_data.get('prepared_audio'):
                media = write_upload(form.cleaned_data['prepared_audio'], dictionary.pk, paths)
                Contribution.objects.create(entry=entry, author=request.user, kind='note', status='accepted', body='Spoken request', request=req, **media)
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
        rows.append({'request': req, 'state': state, **summary(req.entry)})
    return render(request, 'community_dictionary/queue.html', context(request, dictionary, rows=rows, groups=groups, show=show, selected=selected))


@login_required
@require_POST
def request_action(request, pk, request_id):
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
    return get_user_model().objects.filter(Q(pk=dictionary.owner_id) | Q(membership__dictionary=dictionary, membership__accepted=True)).distinct().order_by('username')


@login_required
def people(request, pk):
    dictionary = get_dictionary(request.user, pk)
    settings_form = DictionarySettingsForm(instance=dictionary)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'settings':
            require_owner(request.user, dictionary)
            settings_form = DictionarySettingsForm(request.POST, instance=dictionary)
            if not settings_form.is_valid():
                return fail(request, settings_form.errors.as_text())
            settings_form.save()
            event(dictionary, request.user, 'dictionary_settings')
            messages.success(request, 'Dictionary settings saved.')
        elif action == 'invite':
            require_owner(request.user, dictionary)
            user = get_user_model().objects.filter(username=request.POST.get('username', '').strip(), is_active=True).first()
            role = request.POST.get('role', 'member')
            if not user or user.pk == dictionary.owner_id or role not in {'member', 'editor'}:
                return fail(request, 'Choose an existing account other than the owner, and a valid role.')
            Membership.objects.update_or_create(dictionary=dictionary, user=user, defaults={'role': role})
            event(dictionary, request.user, 'invite_or_change_role', detail=f'{user.username}: {role}')
            messages.success(request, 'Invitation or role saved. Invitations appear when the person opens Community dictionaries.')
        elif action == 'remove_member':
            require_owner(request.user, dictionary)
            membership = get_object_or_404(Membership, pk=request.POST.get('member_id'), dictionary=dictionary)
            with transaction.atomic():
                Partner.objects.filter(partnership__dictionary=dictionary, user=membership.user).delete()
                event(dictionary, request.user, 'remove_member', detail=membership.user.username)
                membership.delete()
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
    return render(request, 'community_dictionary/people.html', context(request, dictionary, memberships=dictionary.memberships.select_related('user'), people=member_users(dictionary), group_rows=group_rows, settings_form=settings_form))


@login_required
def media(request, pk, contribution_id):
    dictionary = get_dictionary(request.user, pk)
    item = get_object_or_404(Contribution, pk=contribution_id, entry__dictionary=dictionary)
    if not item.file_path or item.status == 'removed':
        raise Http404
    # Withdrawn material is no longer shared, while editors can inspect rejected proposals.
    if item.status in {'withdrawn', 'rejected'} and item.author_id != request.user.pk and not is_editor(request.user, dictionary):
        raise Http404
    path = path_for(item.file_path)
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
        response = StreamingHttpResponse(chunks(), status=206, content_type=item.mime_type)
        response['Content-Range'] = f'bytes {start}-{end}/{size}'
        response['Content-Length'] = end - start + 1
    else:
        response = FileResponse(path.open('rb'), content_type=item.mime_type)
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Disposition'] = f'inline; filename="contribution-{item.pk}{path.suffix}"'
    return response


@login_required
def export_dictionary(request, pk):
    dictionary = get_dictionary(request.user, pk)
    require_owner(request.user, dictionary)
    sets = [Dictionary.objects.filter(pk=pk), dictionary.memberships.all(), dictionary.partnerships.all(), Partner.objects.filter(partnership__dictionary=dictionary), dictionary.entries.all(), Contribution.objects.filter(entry__dictionary=dictionary), Request.objects.filter(entry__dictionary=dictionary), dictionary.events.all()]
    objects = [obj for queryset in sets for obj in queryset]
    media_items = list(Contribution.objects.filter(entry__dictionary=dictionary).exclude(file_path=''))
    user_ids = {dictionary.owner_id}
    for obj in objects:
        for field in ['user_id', 'author_id', 'created_by_id', 'actor_id']:
            value = getattr(obj, field, None)
            if value:
                user_ids.add(value)
    users = list(get_user_model().objects.filter(pk__in=user_ids).values('id', 'username'))
    # Spool large bundles to a temporary file instead of holding all media in RAM.
    import tempfile
    output = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    try:
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps({'format': 'clara-community-dictionary', 'version': 1, 'dictionary_id': pk, 'origin': 'human', 'users': users}, ensure_ascii=False, indent=2))
            archive.writestr('records.json', serializers.serialize('json', objects, indent=2))
            archive.writestr('README.txt', 'Portable dictionary export. records.json contains Django-labelled records and original IDs; manifest.json maps contributor IDs to usernames. media/ paths match contribution file_path fields. Credentials and submission receipts are excluded. This is an interchange export, not a full server backup. Use database plus private-media backups for operational restoration.\n')
            for item in media_items:
                archive.write(path_for(item.file_path), 'media/' + item.file_path)
        output.seek(0)
    except Exception:
        output.close()
        raise
    response = FileResponse(output, as_attachment=True, filename=f'community-dictionary-{pk}.zip')
    response['Cache-Control'] = 'private, no-store'
    return response
