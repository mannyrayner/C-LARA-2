"""Lightweight batch progress, page-sized live checks and explicit data exports."""
from collections import Counter, defaultdict
import csv
import json
import unicodedata
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from . import audio_review as review
from .audio_review_data import ReviewData
from .evaluation_views import page
from .services import Conflict

PAGE_SIZE = 25
FILTERS = [('all', _('All')), ('awaiting', _('Awaiting review')),
           ('accepted', _('Accepted')), ('rejected', _('Kept existing audio')), ('failed', _('Failed'))]


def review_state(clips):
    if any(c.get('decision') == 'accept' for c in clips):
        return 'accepted'
    if any(c['status'] == 'ready' and not c.get('decision') for c in clips):
        return 'awaiting'
    if all(c['status'] == 'failed' for c in clips):
        return 'failed'
    if all(c.get('decision') or c['status'] == 'failed' for c in clips):
        return 'rejected'
    return 'waiting'


def saved_results(run):
    """Only saved job JSON; no live lexicon queries, validation or media reads.

    This remains linear in saved candidates, with a single database query. Full
    material is validated only for a displayed page or an explicit export.
    """
    rows, counts, methods = [], Counter(), Counter()
    items = run.items.only('id', 'run_id', 'source_entry_id', 'snapshot', 'result', 'invalidated', 'review_values').order_by('pk')
    for item in items:
        item.run = run
        by_word = defaultdict(list)
        for clip in item.result.get('clips', []):
            by_word[clip['word_id']].append(clip)
            counts[clip['status']] += 1
            methods[clip['method']] += 1
        for word in item.snapshot.get('words', []):
            clips = by_word.get(word['id'])
            if clips:
                rows.append({'item':item, 'word':word, 'clips':clips, 'state':review_state(clips)})
    total = sum(counts.values())
    return rows, dict(words=len(rows), total=total, finished=counts['ready']+counts['failed'],
        failures=counts['failed'], remaining=total-counts['ready']-counts['failed'],
        guidance_count=methods['guidance'], carrier_count=methods['carrier'])


def sort_key(row):
    text = row['word']['word']
    folded = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    return folded, text, row['word']['meaning'], row['word']['id'], row['item'].pk


def navigation(request, run):
    source = request.POST if request.method == 'POST' else request.GET
    chosen = source.get('filter', 'all')
    if chosen not in dict(FILTERS):
        chosen = 'all'
    try:
        number = max(1, int(source.get('page', '1')))
    except (TypeError, ValueError):
        number = 1
    return {'page':min(number, 100000), 'filter':chosen,
            'inspect':int(source.get('inspect') == '1' and run.status == 'estimate')}


def return_url(request, dictionary, run):
    base = reverse('community_dictionary:audio-review-run', args=[dictionary.pk, run.pk])
    url = base + '?' + urlencode(navigation(request, run))
    anchor = request.POST.get('part', '')
    return url + ('#word-' + anchor if anchor.isdigit() else '')


def live_rows(run, rows):
    """Validate just these items, including all members of shared recordings."""
    items = {r['item'].pk:r['item'] for r in rows}
    if not items:
        return [], None
    try:
        review.authority(run.port)
    except (Conflict, Http404):
        return [{'unavailable':True} for _ in rows], None
    loaded = ReviewData(run.port.source, [word['id'] for item in items.values()
                                        for word in item.snapshot.get('words', [])])
    valid = set()
    for item in items.values():
        try:
            review.current_item(item, loaded=loaded, authority_checked=True)
            valid.add(item.pk)
        except (Conflict, Http404):
            pass
    result = []
    for record in rows:
        if record['item'].pk not in valid:
            result.append({'unavailable':True})
            continue
        word, item = record['word'], record['item']
        part = loaded.selected[word['id']]
        basis = part.provenance.get('form_basis', {}) if word['kind'] == 'form' else {}
        lemma = loaded.parts.get(basis.get('word_text'))
        meaning = loaded.parts.get(basis.get('word_meaning'))
        clips = []
        for number, saved in enumerate(record['clips'], 1):
            clip = dict(saved)
            clip.setdefault('candidate', number)
            clip['method_label'] = {**review.experiments.METHODS, **review.experiments.COMPARISON_METHODS}.get(clip['method'], clip['method'])
            clip['voice_label'] = clip.get('report', {}).get('voice') or run.options.get('word_audio_policy', {}).get('voice') or word['voice']
            clips.append(clip)
        result.append({**record, 'clips':clips, 'members':review.targets(item, word['id']),
            'token':review.uuid.uuid4(), 'accepted':record['state']=='accepted',
            'lemma':lemma.word if lemma else '', 'lemma_meaning':meaning.meaning if meaning else '',
            'contexts':loaded.contexts(word), 'note':item.review_values.get('audio_notes', {}).get(str(word['id']), '')})
    return result, loaded


def presentation(request, run):
    records, totals = saved_results(run)
    nav = navigation(request, run)
    show = run.settled or (run.status == 'estimate' and nav['inspect'])
    rows, paging = [], None
    if show:
        selected = sorted((r for r in records if nav['filter']=='all' or r['state']==nav['filter']), key=sort_key)
        paging = Paginator(selected, PAGE_SIZE).get_page(nav['page'])
        rows, _loaded = live_rows(run, paging.object_list)
    return {**totals, 'rows':rows, 'paging':paging, 'show_review':show,
        'unavailable':sum(bool(r.get('unavailable')) for r in rows),
        'review_filter':nav['filter'], 'review_filters':FILTERS, 'inspect':nav['inspect']}


def export_data(run):
    records, totals = saved_results(run)
    rows, loaded = live_rows(run, sorted(records, key=sort_key))
    groups = []
    for row in rows:
        if row.get('unavailable'):
            continue
        members = []
        for word in row['members']:
            part = loaded.selected[word['id']]
            basis = part.provenance.get('form_basis', {}) if word['kind']=='form' else {}
            lemma = loaded.parts.get(basis.get('word_text')) if basis else part
            meaning = loaded.parts.get(basis.get('word_meaning')) if basis else loaded.parts.get(part.entry.current_meaning_id)
            members.append({'part_id':word['id'], 'entry_id':word['entry'], 'kind':word['kind'],
                'text':word['word'], 'meaning':word['meaning'], 'lemma_entry_id':basis.get('word_entry', word['entry']),
                'lemma':lemma.word if lemma else '', 'lemma_meaning':meaning.meaning if meaning else '',
                'contexts':loaded.contexts(word),
                'current_audio':[{'id':a['id'], 'synthetic':a['synthetic'],
                    'provider':loaded.audio[a['id']].provenance.get('provider', ''),
                    'voice':loaded.audio[a['id']].provenance.get('voice', ''),
                    'pronunciation_approved':review.sf.pronunciation_approved(loaded.audio[a['id']])}
                    for a in word['audio']]})
        candidates = []
        for clip in row['clips']:
            report = clip.get('report', {})
            candidates.append({'id':clip['id'], 'candidate':clip['candidate'], 'method':clip['method'],
                'provider':report.get('provider', 'google' if run.options.get('google_batch') else 'openai'),
                'voice':clip['voice_label'], 'model':report.get('model', ''), 'status':clip['status'],
                'decision':clip.get('decision', ''), 'cost_usd':clip.get('cost', '0'),
                'failure':clip.get('failure', ''),
                'accepted_audio_ids':clip.get('accepted_audio_ids', [])})
        groups.append({'item_id':row['item'].pk, 'representative_part_id':row['word']['id'],
            'review_state':row['state'], 'note':row['note'], 'members':members, 'candidates':candidates})
    return {'schema':1, 'exported_at':timezone.now().isoformat(),
        'dictionary':{'id':run.port.source_id, 'name':run.port.source.name,
            'language':run.port.language, 'explanation_language':run.port.explanation_language},
        'run':{'id':str(run.pk), 'status':run.status, 'settled':run.settled,
            'created_at':run.created_at.isoformat(), 'estimated_usd':str(run.estimated_usd),
            'charged_usd':str(run.charged_usd), 'selected_voice':run.options.get('word_audio_policy', {}).get('voice', '')},
        'summary':{**totals, 'exported_groups':len(groups), 'omitted_unavailable_groups':len(rows)-len(groups)},
        'notes':['Review decisions are workflow actions, not independent quality ratings.',
                 'Contexts and current audio reflect the live dictionary at export time.',
                 'Changed, withdrawn or otherwise unavailable items are omitted.',
                 'No audio files, storage paths, credentials or raw provider responses are included.'],
        'groups':groups}


@page(['GET'])
def download(request, pk, run_id, format):
    if format not in {'json', 'csv'}:
        raise Http404
    _dictionary, run = review.owner_run(request, pk, run_id)
    data = export_data(run)
    if format == 'json':
        response = JsonResponse(data, json_dumps_params={'ensure_ascii':False, 'indent':2})
    else:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['run_id', 'language', 'explanation_language', 'item_id', 'part_id', 'entry_id',
            'kind', 'text', 'meaning', 'lemma_entry_id', 'lemma', 'lemma_meaning',
            'contexts_json', 'current_audio_json', 'candidate_id', 'method', 'provider', 'voice',
            'status', 'decision', 'note', 'omitted_unavailable_groups'])
        for group in data['groups']:
            for member in group['members']:
                for candidate in group['candidates']:
                    values = [str(run.pk), run.port.language, run.port.explanation_language, group['item_id'],
                        *[member[k] for k in ('part_id','entry_id','kind','text','meaning','lemma_entry_id','lemma','lemma_meaning')],
                        json.dumps(member['contexts'], ensure_ascii=False), json.dumps(member['current_audio'], ensure_ascii=False),
                        *[candidate[k] for k in ('id','method','provider','voice','status','decision')],
                        group['note'], data['summary']['omitted_unavailable_groups']]
                    writer.writerow([review.experiments.csv_safe(v) for v in values])
    response['Content-Disposition'] = f'attachment; filename="word-audio-review-{run.pk}.{format}"'
    return response
