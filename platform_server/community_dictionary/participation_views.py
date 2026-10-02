from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .contribution_display import entry_cards
from .models import Entry
from .participation import content_for, controls, restore_all, successors, withdraw_all
from .permissions import entitled_dictionaries
from .services import Conflict
from .views import fail


def project(user, pk):
    return get_object_or_404(entitled_dictionaries(user), pk=pk)


@login_required
def my_content(request, pk):
    dictionary = project(request.user, pk)
    parts = content_for(request.user, dictionary)
    entries = Entry.objects.filter(pk__in=parts.values('entry_id')).select_related('dictionary').order_by('-created_at', '-pk')
    page = Paginator(entries, 12).get_page(request.GET.get('page'))
    return render(request, 'community_dictionary/my_content.html', {
        'project': dictionary, 'participation': controls(request.user, dictionary),
        'viewing_content': True, 'page': page, 'cards': entry_cards(page.object_list, request.user)})


@login_required
@require_http_methods(['GET', 'POST'])
def withdraw_content(request, pk):
    dictionary = project(request.user, pk)
    control = controls(request.user, dictionary)
    if request.method == 'POST':
        if request.POST.get('confirm') != 'yes':
            return fail(request, 'Confirm that you want to withdraw all your content.', 409)
        try:
            withdraw_all(request.user, pk, request.POST.get('revision'), request.POST.get('successor'))
        except Conflict as exc:
            return fail(request, exc, 409)
        messages.success(request, 'Your content is withdrawn and saved privately. You can restore it later to rejoin.')
        return redirect('community_dictionary:dictionary', pk=pk)
    if control['state'].withdrawn:
        return redirect('community_dictionary:dictionary', pk=pk)
    return render(request, 'community_dictionary/withdraw_content.html', {
        'project': dictionary, 'participation': control, 'is_owner': dictionary.owner_id == request.user.pk,
        'successors': successors(dictionary, request.user) if dictionary.owner_id == request.user.pk else []})


@login_required
@require_POST
def restore_content(request, pk):
    project(request.user, pk)
    try:
        count, remaining = restore_all(request.user, pk, request.POST.get('revision'))
    except Conflict as exc:
        return fail(request, exc, 409)
    message = 'Your content is restored and you have rejoined the dictionary. Previous approvals are retained.'
    if remaining:
        message += ' Some dependent material remains private because its source is still withdrawn; you can view your saved material.'
    messages.success(request, message)
    return redirect('community_dictionary:dictionary', pk=pk)
