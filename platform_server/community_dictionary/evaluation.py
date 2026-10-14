"""Versioned, human evaluation. No provider calls or changes to learning material.

Snapshots are internal records, never unconditional copies for publication. Every
view/export/media request rechecks live permissions and source withdrawal. New
ratings require an unchanged snapshot; old ratings describe their original version.
"""
from collections import Counter, defaultdict
from itertools import combinations
import hashlib
import json
import random
import unicodedata
import uuid

from django.db import transaction
from django.http import Http404
from django.utils import timezone

from . import public_browsing as public
from .models import (Contribution, Dictionary, Entry, EvaluationItem, EvaluationSet,
                     EvaluationUnit, LanguageCheck, LanguageCompetence, Participation,
                     SentenceWord)
from .permissions import dictionaries_for, require_owner
from .services import Conflict

RUBRIC = 'community-quality-v1'
DIMENSIONS = {
    'image': ('Sentence and image', 'Does the picture support the description? Several different descriptions can be valid.'),
    'language': ('Sentence language', 'Is the sentence grammatical and reasonably natural? Accept legitimate regional varieties.'),
    'sentence_audio': ('Sentence audio', 'Listen: does it say the displayed sentence with acceptable pronunciation?'),
    'translation': ('Sentence translation', 'Does the translation preserve the meaning of this sentence in its pictured context?'),
    'vocabulary': ('Extracted vocabulary', 'Check the complete list: lemmas, senses, multi-word expressions and important omissions. Not every function word needs its own entry.'),
    'word_translation': ('Word translation', 'Is the translation appropriate for this word or expression in the example sentence?'),
    'word_audio': ('Word audio', 'Listen: does it pronounce the displayed word or expression correctly in this language?'),
}
AI_ORIGINS = {'language-port', 'picture-description', 'sentence-vocabulary', 'synthetic', 'generated'}
MAX_SAMPLE = 500


def language_key(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def access(user, pk, evaluation_set=None):
    """Membership or explicit visitor invitation; withdrawal always takes precedence."""
    dictionary = Dictionary.objects.filter(pk=pk, personal=False, archived=False).first()
    if dictionary is None or Participation.objects.filter(dictionary=dictionary, user=user, withdrawn=True).exists():
        raise Http404
    member = dictionaries_for(user).filter(pk=pk).exists()
    if not member:
        allowed = dictionary.public_browsing_enabled and not dictionary.hidden
        allowed = allowed and (evaluation_set.allow_visitors if evaluation_set else
                               dictionary.evaluation_sets.filter(allow_visitors=True).exists())
        if not allowed:
            raise Http404
    if evaluation_set and evaluation_set.dictionary_id != dictionary.pk:
        raise Http404
    return dictionary, member


def competence_snapshot(user, dictionary):
    rows = {c.language_key: {'language': c.language, 'reading': c.reading,
            'listening': c.listening, 'variety': c.variety, 'experience': c.experience,
            'reported_at': c.updated_at.isoformat()} for c in LanguageCompetence.objects.filter(user=user)}
    return {role: rows.get(language_key(language), {'language': language, 'reading': 0, 'listening': 0,
            'variety': '', 'experience': ''}) for role, language in
            [('target', dictionary.language), ('explanation', dictionary.explanation_language)]}


def eligible_dimensions(competences, scope):
    read = competences['target']['reading'] >= 2
    listen = competences['target']['listening'] >= 2
    translation = read and competences['explanation']['reading'] >= 2
    selected = set()
    if read:
        selected.update(['image', 'language', 'vocabulary'])
    if read and listen:
        selected.update(['sentence_audio', 'word_audio'])
    if translation:
        selected.update(['translation', 'word_translation'])
    if scope == 'words':
        selected &= {'word_audio', 'word_translation'}
    return [key for key in DIMENSIONS if key in selected]


def signature(part):
    # Include content values as well as IDs: imports must not silently mutate a frozen version.
    return {'id': part.pk, 'entry_id': part.entry_id, 'kind': part.kind,
            'field': part.text_field, 'word': part.word, 'meaning': part.meaning,
            'path': part.file_path, 'mime': part.mime_type, 'size': part.file_size,
            'author': part.author_id, 'controller': part.controlled_by_id or part.author_id,
            'origin': str(part.provenance.get('origin', 'unknown')),
            'model': str(part.provenance.get('model', '')),
            'previous_revision': part.previous_revision_id}


def graph(dictionary):
    """Bounded-query accepted projection, independent of public-browsing enablement."""
    parts = list(public.contributions(dictionary).exclude(kind='note').order_by('-created_at', '-pk'))
    part_map = {c.pk: c for c in parts}
    by_entry = defaultdict(list)
    for c in parts:
        by_entry[c.entry_id].append(c)
    checked = set(LanguageCheck.objects.filter(entry__dictionary=dictionary).values_list('text_id', 'meaning_id'))
    rows = {}
    for entry in Entry.objects.filter(dictionary=dictionary, archived=False).order_by('pk'):
        text = part_map.get(entry.current_text_id)
        meaning = part_map.get(entry.current_meaning_id)
        if not text or text.entry_id != entry.pk or text.kind != 'text' or text.text_field != 'word' or not text.word:
            continue
        if meaning and (meaning.entry_id != entry.pk or meaning.kind != 'text' or meaning.text_field != 'meaning'):
            meaning = None
        media = by_entry[entry.pk]
        images = [c for c in media if c.kind == 'image' and c.file_path]
        image = next((c for c in images if c.pk == entry.selected_image_id), images[0] if images else None)
        audios = [c for c in media if c.kind == 'audio' and c.file_path and (
            c.provenance.get('origin') != 'synthetic' or (
                c.provenance.get('source_text') == text.word and
                c.provenance.get('language') == dictionary.language and
                (c.provenance.get('source_meaning_id') is None or
                 c.provenance.get('source_meaning_id') == (meaning.pk if meaning else None))))]
        audio = audios[0] if audios else None
        rows[entry.pk] = {'id': entry.pk, 'kind': entry.entry_type, 'text': text.word,
            'meaning': meaning.meaning if meaning else '',
            'text_part': signature(text), 'meaning_part': signature(meaning) if meaning else None,
            'image': signature(image) if image else None, 'audio': signature(audio) if audio else None,
            'checked': (text.pk, meaning.pk if meaning else None) in checked,
            'origin': 'AI' if text.provenance.get('origin') in AI_ORIGINS else
                      'human' if text.provenance.get('origin') == 'human' else 'unknown'}
    links = defaultdict(list)
    for link in SentenceWord.objects.filter(sentence_text__entry__dictionary=dictionary).order_by('pk'):
        word = rows.get(link.word_entry_id)
        sentence_part = part_map.get(link.sentence_text_id)
        sentence = rows.get(sentence_part.entry_id) if sentence_part else None
        if (word and sentence and sentence['kind'] == 'sentence' and word['kind'] == 'word' and
            sentence['text_part']['id'] == link.sentence_text_id and word['text_part']['id'] == link.word_text_id):
            # Word-page pictures are not the sentence's context and need not enter this snapshot.
            word = {**word, 'image': None, 'surface': link.surface}
            links[sentence['id']].append(word)
    return {entry_id: {'entry': row, 'words': links[entry_id], 'language': dictionary.language,
            'explanation_language': dictionary.explanation_language} for entry_id, row in rows.items()}


def references(snapshot):
    result = {}
    for row in [snapshot['entry'], *snapshot['words']]:
        for key in ['text_part', 'meaning_part', 'image', 'audio']:
            part = row.get(key)
            if part:
                result[part['id']] = part
    return result


def available_items(items, dictionary):
    """Historical ratings can survive edits, but never disclose withdrawn sources."""
    all_refs = {pid for item in items for pid in references(item.snapshot)}
    departed = set(Participation.objects.filter(dictionary=dictionary, withdrawn=True).values_list('user_id', flat=True))
    parts = {c.pk: c for c in Contribution.objects.filter(pk__in=all_refs,
        entry__dictionary=dictionary, entry__archived=False, status__in=['accepted', 'superseded'],
        withdrawal_holds__isnull=True).distinct() if (c.controlled_by_id or c.author_id) not in departed}
    active_entries = set(Entry.objects.filter(dictionary=dictionary, archived=False).values_list('pk', flat=True))
    return {item.pk for item in items if item.entry_id in active_entries and all(
        pid in parts and signature(parts[pid]) == saved for pid, saved in references(item.snapshot).items())}


def is_current(item, live):
    return item.entry_id in live and digest(live[item.entry_id]) == item.fingerprint


@transaction.atomic
def create_set(user, dictionary, data):
    dictionary = Dictionary.objects.select_for_update().get(pk=dictionary.pk)
    require_owner(user, dictionary)
    previous = EvaluationSet.objects.filter(pk=data['token'], dictionary=dictionary, created_by=user).first()
    if previous:
        return previous
    if EvaluationSet.objects.filter(pk=data['token']).exists():
        raise Conflict('This form has already been used. Reload Evaluate.')
    if data['allow_visitors'] and (not dictionary.public_browsing_enabled or dictionary.hidden):
        raise Conflict('Visitor evaluation requires public browsing to be enabled.')
    if dictionary.evaluation_sets.filter(closed_at__isnull=True).count() >= 10:
        raise Conflict('Close an existing evaluation set before creating another (maximum ten open sets).')
    live = graph(dictionary)
    kind = 'sentence' if data['scope'] == 'sentences' else 'word'
    ids = sorted(pk for pk, snap in live.items() if snap['entry']['kind'] == kind)
    if not ids:
        raise Conflict('There are no accepted pages of this kind to evaluate yet.')
    if data['sampling'] == 'all' and len(ids) > MAX_SAMPLE:
        raise Conflict(f'Use a random sample for a collection larger than {MAX_SAMPLE} pages.')
    seed = uuid.uuid4().hex
    selected = ids if data['sampling'] == 'all' else random.Random(seed).sample(ids, min(data['size'], len(ids)))
    batch = EvaluationSet.objects.create(id=data['token'], dictionary=dictionary, created_by=user,
        name=data['name'], scope=data['scope'], sampling=data['sampling'], seed=seed, population_ids=ids,
        language=dictionary.language, explanation_language=dictionary.explanation_language,
        allow_visitors=data['allow_visitors'], rubric=RUBRIC)
    seen = set()
    for position, pk in enumerate(selected, 1):
        snapshot = live[pk]
        item = EvaluationItem.objects.create(evaluation_set=batch, entry_id=pk, position=position,
                                            snapshot=snapshot, fingerprint=digest(snapshot))
        row = snapshot['entry']
        candidates = []
        if kind == 'sentence':
            for dim, missing in [('image', not row['image']), ('language', False),
                    ('sentence_audio', not row['audio']), ('translation', not row['meaning']),
                    ('vocabulary', not snapshot['words'])]:
                candidates.append((dim, digest([pk, dim, item.fingerprint]), None, missing))
        words = list(enumerate(snapshot['words'])) if kind == 'sentence' else [(None, row)]
        for index, word in words:
            for dim in ['word_translation', 'word_audio']:
                # Sense is the word entry, not spelling. Each exact translation/audio is rated once.
                value = word['meaning_part'] if dim == 'word_translation' else word['audio']
                key = digest([word['id'], word['text_part'], value, dictionary.language,
                              dictionary.explanation_language if dim == 'word_translation' else ''])
                missing = not word['meaning'] if dim == 'word_translation' else not word['audio']
                candidates.append((dim, key, index, missing))
        for dim, key, index, missing in candidates:
            if (dim, key) in seen:
                continue
            seen.add((dim, key))
            EvaluationUnit.objects.create(evaluation_set=batch, item=item, dimension=dim,
                key=key, word_index=index, missing=missing)
    return batch


def agreement(units):
    """Pairwise exact agreement and ordinal Krippendorff alpha on complete rating pairs.

    Coincidences weight each unit by 1/(m-1). Ordinal distances use pooled
    marginal ranks (not squared numeric label differences). Singleton units and
    abstentions do not contribute. Undefined alpha is reported as None.
    """
    groups = [[{'ok': 0, 'minor': 1, 'major': 2}[s] for s in scores if s != 'cannot'] for scores in units]
    groups = [g for g in groups if len(g) >= 2]
    pairs = [pair for group in groups for pair in combinations(group, 2)]
    exact = sum(a == b for a, b in pairs)
    if not pairs:
        return {'overlap_units': 0, 'pairs': 0, 'exact_percent': None, 'alpha': None, 'reason': 'No overlapping scored items'}
    counts = Counter(v for g in groups for v in g)
    total = sum(counts.values())
    def distance(a, b):
        lo, hi = sorted((a, b))
        return 0 if lo == hi else (sum(counts[v] for v in range(lo, hi + 1)) - (counts[lo] + counts[hi]) / 2) ** 2
    observed = sum(sum(distance(a, b) for a in g for b in g) / (len(g) - 1) for g in groups) / total
    expected = sum(counts[a] * counts[b] * distance(a, b) for a in counts for b in counts) / (total * (total - 1))
    return {'overlap_units': len(groups), 'pairs': len(pairs), 'exact_percent': 100 * exact / len(pairs),
            'alpha': 1 - observed / expected if expected else None,
            'reason': '' if expected else 'No variation in overlapping ratings'}


def result_data(batch):
    items = list(batch.items.all())
    visible = available_items(items, batch.dictionary)
    live = graph(batch.dictionary)
    by_id = {item.pk: item for item in items}
    units = list(batch.units.filter(item_id__in=visible))
    departed = Participation.objects.filter(dictionary=batch.dictionary, withdrawn=True).values('user_id')
    ratings = list(batch.sessions.filter(evaluator_kind='human').exclude(user_id__in=departed).values_list('id', flat=True))
    from .models import EvaluationRating
    scores = list(EvaluationRating.objects.filter(session_id__in=ratings,
        unit__evaluation_set=batch, unit__item_id__in=visible).select_related('session', 'unit'))
    unit_scores = defaultdict(list)
    for rating in scores:
        if not rating.unit.missing:
            unit_scores[rating.unit_id].append(rating.score)
    summaries = []
    for dim, (label, _) in DIMENSIONS.items():
        selected = [u for u in units if u.dimension == dim]
        if not selected:
            continue
        counted = Counter(s for u in selected if not u.missing for s in unit_scores[u.pk])
        scored = sum(counted[s] for s in ['ok', 'minor', 'major'])
        summaries.append({'dimension': dim, 'label': label, 'units': len(selected),
            'missing': sum(u.missing for u in selected),
            'unrated': sum(not u.missing and not unit_scores[u.pk] for u in selected),
            'ok': counted['ok'], 'minor': counted['minor'], 'major': counted['major'],
            'cannot': counted['cannot'], 'scored': scored,
            'acceptable_percent': 100 * counted['ok'] / scored if scored else None,
            **agreement([unit_scores[u.pk] for u in selected if not u.missing])})
    return {'rows': summaries, 'items': by_id, 'units': units, 'ratings': scores,
        'excluded': len(items) - len(visible), 'visible': visible,
        'changed': sum(not is_current(item, live) for item in items if item.pk in visible),
        'sample_count': len(items), 'population_count': len(batch.population_ids),
        'evaluator_count': len({r.session_id for r in scores}),
        'origins': dict(Counter(item.snapshot['entry']['origin'] for item in items if item.pk in visible)),
        'checked': sum(item.snapshot['entry']['checked'] for item in items if item.pk in visible)}
