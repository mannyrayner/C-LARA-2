"""Manual vocabulary links and the word-focused dictionary page."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import LinkWordForm
from .lexicon import pictures_for_word, recordings, vocabulary, word_row
from .models import Contribution, Dictionary, Entry, ImageWordLink
from .permissions import get_dictionary, require_editor
from .services import event
from .views import context, fail


@login_required
def word_detail(request, pk, entry_id):
    dictionary = get_dictionary(request.user, pk)
    entry = get_object_or_404(vocabulary(dictionary), pk=entry_id)
    return render(request, 'community_dictionary/word.html', context(
        request, dictionary, entry=entry, row=word_row(entry, dictionary),
        word_audio=recordings(entry, dictionary), pictures=pictures_for_word(entry, dictionary)))


@login_required
@require_POST
def image_words(request, pk, entry_id, image_id):
    dictionary = get_dictionary(request.user, pk)
    require_editor(request.user, dictionary)
    action = request.POST.get('action')
    if action not in {'link', 'unlink'}:
        return fail(request, 'Choose a word to link or a link to remove.')
    form = LinkWordForm(request.POST, dictionary=dictionary, source_entry_id=entry_id)
    if not form.is_valid():
        return fail(request, form.errors.as_text())
    target_id = form.cleaned_data['word_entry'].pk
    with transaction.atomic():
        Dictionary.objects.select_for_update().get(pk=pk)
        get_dictionary(request.user, pk)
        require_editor(request.user, dictionary)
        # Lock in a stable order, also coordinating with text/media review and
        # deletion. Incremental add/remove never overwrites another editor's set.
        entries = {e.pk: e for e in Entry.objects.select_for_update().filter(
            dictionary=dictionary, pk__in=[entry_id, target_id]).order_by('pk')}
        if entry_id not in entries or target_id not in entries or not entries[target_id].word:
            raise Http404
        image = get_object_or_404(Contribution.objects.select_for_update(),
                                 pk=image_id, entry=entries[entry_id], kind='image', status='accepted')
        if not image.file_path:
            raise Http404
        if action == 'link':
            link, made = ImageWordLink.objects.get_or_create(image=image, word_entry=entries[target_id], defaults={'created_by': request.user})
            if made:
                event(dictionary, request.user, 'link_picture_word', entries[entry_id], f'Picture {image.pk}; word entry {target_id}')
            messages.success(request, 'Word linked to this picture.')
        else:
            removed, _ = ImageWordLink.objects.filter(image=image, word_entry_id=target_id).delete()
            if removed:
                event(dictionary, request.user, 'unlink_picture_word', entries[entry_id], f'Picture {image.pk}; word entry {target_id}')
            messages.success(request, 'Word link removed. The word and picture are unchanged.')
    url = reverse('community_dictionary:entry', args=[pk, entry_id])
    return redirect(f'{url}?picture={image_id}#picture-words')
