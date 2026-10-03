"""Member-only, non-persistent learning games."""
import random
import secrets

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from . import practice
from .lexicon import outdated_tts
from .models import Contribution
from .permissions import get_dictionary
from .views import context, private_media_response


@login_required
@require_GET
def home(request, pk):
    dictionary = get_dictionary(request.user, pk)
    rows, categories, _ = practice.catalogue(dictionary, request.GET.get('category', ''))
    modes = [{'value': mode, 'label': label, 'count': len(practice.eligible(rows, mode))}
             for mode, label in practice.MODES]
    return render(request, 'community_dictionary/practice.html', context(request, dictionary,
        categories=categories, selected_category=request.GET.get('category', ''),
        practice_modes=modes, has_cards=any(mode['count'] for mode in modes),
        puzzle_count=len(practice.puzzle_candidates(rows))))


@login_required
@require_GET
def data(request, pk):
    dictionary = get_dictionary(request.user, pk)
    rows, _, revision = practice.catalogue(dictionary, request.GET.get('category', ''))
    if request.GET.get('validate'):
        return JsonResponse({'valid': request.GET['validate'] == revision})
    game = request.GET.get('game', 'flashcards')
    if game == 'flashcards':
        mode = request.GET.get('mode', 'image-text')
        if mode not in dict(practice.MODES):
            return JsonResponse({'error': 'Choose a flashcard direction.'}, status=400)
        style = request.GET.get('style', 'recall')
        if style not in {'choice', 'recall'}:
            return JsonResponse({'error': 'Choose multiple choice or reveal the answer.'}, status=400)
        if style == 'choice':
            cards = practice.choice_cards(rows, mode)
            if not cards:
                return JsonResponse({'error': 'There are not enough distinct answers for multiple choice in this category. Choose another category or use Reveal the answer.'}, status=400)
        else:
            cards = practice.eligible(rows, mode)
            random.SystemRandom().shuffle(cards)
        content = {'cards': cards[:10], 'mode': mode, 'style': style}
    elif game in {'crossword', 'scramble'}:
        content = practice.puzzle(rows, game, secrets.token_hex(8))
        if content is None:
            return JsonResponse({'error': 'We need at least two different picture words that fit together. Try another category or add some shorter words.'}, status=400)
    else:
        return JsonResponse({'error': 'Choose a game.'}, status=400)
    return JsonResponse({'game': game, 'revision': revision, **content})


@login_required
@require_GET
def media(request, pk, contribution_id):
    dictionary = get_dictionary(request.user, pk)
    part = get_object_or_404(Contribution.objects.select_related('entry'), pk=contribution_id,
        entry__dictionary=dictionary, entry__archived=False, status='accepted', kind__in=['image', 'audio'])
    if not part.file_path or outdated_tts(part, part.entry, dictionary):
        raise Http404
    return private_media_response(request, part.file_path, part.mime_type, f'practice-{part.pk}')
