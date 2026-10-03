"""Read-only practice from the dictionary's current, accepted presentation.

No saved exercise copies, provider calls, or learner records. A content digest
lets open games detect edits/withdrawal before their next interaction.
"""
import hashlib
import json
import random
import unicodedata

from django.db.models import Prefetch
from django.urls import reverse

from core.picture_games import _build_crossword_item, _generate_word_scramble_items, _exercise_near_duplicate
from .lexicon import outdated_tts, valid_links
from .models import Contribution, Entry


MODES = (
    ('image-text', 'Picture → words'), ('text-image', 'Words → picture'),
    ('audio-text', 'Recording → words'), ('text-audio', 'Words → recording'),
    ('audio-image', 'Recording → picture'), ('image-audio', 'Picture → recording'),
)
GRID_SIZE = 12


def media_url(dictionary, contribution):
    return reverse('community_dictionary:practice-media', args=[dictionary.pk, contribution.pk])


def catalogue(dictionary, category=''):
    entries = list(Entry.objects.filter(dictionary=dictionary, archived=False)
        .select_related('current_text', 'current_meaning', 'current_category')
        .prefetch_related(Prefetch('contributions', queryset=Contribution.objects.filter(
            status='accepted', kind__in=['image', 'audio']).exclude(file_path=''), to_attr='practice_media'))
        .order_by('pk'))
    by_id = {entry.pk: entry for entry in entries}
    images = {entry.pk: [c for c in entry.practice_media if c.kind == 'image'] for entry in entries}
    accepted_images = {c.pk: c for parts in images.values() for c in parts}
    for image_id, word_id in valid_links(dictionary).values_list('image_id', 'word_entry_id'):
        if word_id in by_id and image_id in accepted_images:
            images[word_id].append(accepted_images[image_id])

    rows, categories = [], set()
    for entry in entries:
        # Current pointers, when present, must still be shared accepted revisions.
        # Pointer-less accepted fields remain compatible with legacy imports.
        values = {}
        for field, pointer in [('word', entry.current_text), ('meaning', entry.current_meaning), ('category', entry.current_category)]:
            values[field] = getattr(entry, field) if pointer is None or (
                pointer.entry_id == entry.pk and pointer.status == 'accepted') else ''
        if values['category']:
            categories.add(values['category'])
        if category and values['category'] != category:
            continue
        pictures = sorted(images[entry.pk], key=lambda c: (c.pk != entry.selected_image_id, c.entry_id != entry.pk, -c.pk))
        audio = [c for c in entry.practice_media if c.kind == 'audio' and not outdated_tts(c, entry, dictionary)]
        picture, recording = next(iter(pictures), None), next(iter(audio), None)
        rows.append({'id': entry.pk, 'text': values['word'], 'meaning': values['meaning'],
            'category': values['category'],
            'picture_ids': sorted({c.pk for c in pictures}),
            'image': media_url(dictionary, picture) if picture else '',
            'audio': media_url(dictionary, recording) if recording else '',
            'image_generated': bool(picture and picture.provenance.get('origin') == 'generated'),
            'audio_synthetic': bool(recording and recording.provenance.get('origin') == 'synthetic'),
            'word_url': reverse('community_dictionary:word', args=[dictionary.pk, entry.pk]) if values['word'] else '',
            'entry_url': reverse('community_dictionary:entry', args=[dictionary.pk, entry.pk])})
    # Membership changes also invalidate a game even if its content is unchanged.
    snapshot = [dictionary.pk, dictionary.membership_revision, dictionary.language, rows]
    digest = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return rows, sorted(categories, key=str.casefold), digest


def eligible(rows, mode):
    prompt, answer = mode.split('-')
    return [row for row in rows if row[prompt] and row[answer]]


def normalized(value):
    return ' '.join(unicodedata.normalize('NFC', value).casefold().split())


def related_answers(left, right):
    """Conservative known-confusion checks, not a semantic understanding claim."""
    if left['id'] == right['id']:
        return True
    if set(left.get('picture_ids', [])) & set(right.get('picture_ids', [])):
        return True
    for key in ('image', 'audio'):
        if left.get(key) and left[key] == right.get(key):
            return True
    a, b = normalized(left['text']), normalized(right['text'])
    if a and b and (_exercise_near_duplicate(a, b) or f' {a} ' in f' {b} ' or f' {b} ' in f' {a} '
                    or _exercise_near_duplicate(max(a.split(), key=len), max(b.split(), key=len))):
        return True
    a, b = normalized(left['meaning']), normalized(right['meaning'])
    return bool(a and b and a == b)


def choice_cards(rows, mode, rng=None):
    """Up to four real choices, with no invented filler or paid AI calls."""
    rng = rng or random.SystemRandom()
    _, answer = mode.split('-')
    prompts = eligible(rows, mode)
    rng.shuffle(prompts)
    pool = [row for row in rows if row[answer]]
    cards = []
    for row in prompts:
        candidates = [other for other in pool if not related_answers(row, other)]
        rng.shuffle(candidates)
        candidates.sort(key=lambda other: other['category'] != row['category'])
        options = [row]
        for candidate in candidates:
            if not any(related_answers(candidate, existing) for existing in options):
                options.append(candidate)
            if len(options) == 4:
                break
        if len(options) < 2:
            continue
        rng.shuffle(options)
        cards.append(dict(row, options=options))
        if len(cards) == 10:
            break
    return cards


def grid_answer(value):
    """Keep accents; omit only word separators, never silently discard letters.

    The reused builders use one Unicode code point per square. Uncomposed marks,
    numbers and other unsupported scripts/symbols stay available in flashcards.
    """
    value = unicodedata.normalize('NFC', value)
    if any(not (ch.isalpha() or ch.isspace() or ch in "-'’‐‑") for ch in value):
        return ''
    answer = ''.join(ch.upper() for ch in value if ch.isalpha())
    return answer if 2 <= len(answer) <= GRID_SIZE and all(ch.isalpha() for ch in answer) else ''


def puzzle_candidates(rows):
    seen, result = set(), []
    for row in rows:
        answer = grid_answer(row['text'])
        if row['image'] and answer and answer not in seen:
            seen.add(answer)
            result.append(row)
    return result


def puzzle(rows, game, seed):
    candidates = puzzle_candidates(rows)
    random.Random(seed).shuffle(candidates)
    candidates = candidates[:8]
    data = [{'source_word': row['text'], 'target_gloss': row['meaning'],
        'dictionary_entry_id': row['id'], 'page_number': 1, 'segment_index': 0,
        'segment_text': row['text']} for row in candidates]
    by_id = {row['id']: row for row in candidates}
    if len(data) < 2:
        return None
    if game == 'crossword':
        built = _build_crossword_item(data, item_count=8, max_grid_size=GRID_SIZE)['rationale']
        clues = [clue for group in built['clues'].values() for clue in group]
        grid = [[cell['letter'] for cell in line] for line in built['grid']]
    else:
        items, built = _generate_word_scramble_items(data, item_count=8, rows=GRID_SIZE, cols=GRID_SIZE, seed=seed)
        clues = [dict(item['rationale'], answer=item['answer'], number=i + 1, direction='') for i, item in enumerate(items)]
        grid = [list(line) for line in built['grid']]
    if len(clues) < 2:
        return None
    return {'grid': grid, 'clues': [dict(by_id[clue['dictionary_entry_id']],
        answer=clue['answer'], path=clue['path'], number=clue['number'],
        direction=clue['direction']) for clue in clues]}
