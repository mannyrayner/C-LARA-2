"""Private, owner-approved paired TTS experiments; no dictionary publication.

The existing durable batch records and credit ledger hold the experiment. One
worker claims one clip at a time; redelivery cannot repeat a paid attempt. The
comparison is current enriched guidance versus native carrier + extraction,
not carrier + guidance. Ratings never enter either generation prompt.
"""
import csv
import secrets
import uuid
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from projects.billing import get_user_balance_usd
from . import google_tts, carrier, photo_ai, port_costs, port_tasks, porting, sentence_forms as sf, tts
from .collections import content_digest
from .evaluation_views import page
from .models import Contribution, LanguagePort, PortItem, PortRun
from .permissions import get_dictionary, require_owner
from .services import Conflict
from .storage import delete_file, write_upload
from .views import context, private_media_response

VERSION = 'homograph-comparison-1'
STAGE = 'homographs'
METHODS = {'guidance': _('Current pronunciation guidance'),
           'carrier': _('Carrier phrase with extraction')}
RATINGS = [('', _('Not rated')), ('acceptable', _('Acceptable')),
           ('minor', _('Minor problem')), ('major', _('Major problem')),
           ('cannot', _('Cannot judge'))]
MAX_SELECTION = 20
COMPARISON_VERSION = 'word-provider-comparison-1'
COMPARISON_METHODS = {'openai': _('OpenAI current word-audio pipeline'),
    'google_wavenet': _('Google WaveNet'), 'google_neural2': _('Google Neural2'),
    'google_standard': _('Google Standard'), 'google_chirp3': _('Google Chirp 3 HD')}
MAX_COMPARISON = 60


def is_comparison(run):
    return run.options.get('suite') == 'providers'


def methods_for(run):
    return ({k: COMPARISON_METHODS[k] for k in run.options['methods']}
            if is_comparison(run) else METHODS)


def comparison_recipes(run):
    if is_comparison(run):
        google_tts.require_access(run.port.user)
        if (run.options.get('comparison_version') != COMPARISON_VERSION or
                any(run.prices.get(k) != v for k, v in google_tts.comparison_prices(run.port.source).items())):
            raise Conflict('Google comparison configuration changed. Create a fresh estimate.')


def comparison_homograph(row, language):
    from .audio_review import single_word
    from .pronunciation import homographs
    return single_word(row) and bool(homographs(row['word'], tts.language_code(language)))


def record_clip_usage(item, clip, cost):
    method = clip.get('method', '')
    google = method.startswith('google_')
    porting.record_usage(item, audio=True, cost_override=cost, suffix=':'+clip['id'],
        provider='google' if google else 'openai',
        model=item.run.prices['google_voices'][tts.language_code(item.run.port.language)][method] if google else tts.MODEL)



def candidate(part, *, for_review=False, comparison=False, loaded=None):
    entry = part.entry
    from .pronunciation import homographs
    code = tts.language_code(entry.dictionary.language)
    eligible = (bool(code) and len(part.word) <= 255 and bool(homographs(part.word, code))
                if for_review else carrier.homograph_eligible(part.word, entry.dictionary.language))
    if comparison:
        eligible = bool(code) and 0 < len(part.word) <= 255
    if (entry.archived or part.status != 'accepted' or not eligible):
        return None
    context_text = ''
    if part.kind == 'form':
        link = sf.current(part, loaded=loaded)
        if not link:
            return None
        ids = [part.pk] + [link.sentence_text_id, link.word_text_id]
        ids += [pk for pk in [entry.current_meaning_id, link.word_entry.current_meaning_id] if pk]
        meaning, context_text, kind = part.meaning, link.sentence_text.word, 'form'
    elif part.kind == 'text' and part.text_field == 'word' and entry.entry_type == 'word' and entry.current_text_id == part.pk:
        meaning_part = entry.current_meaning
        if meaning_part and (meaning_part.status != 'accepted' or meaning_part.entry_id != entry.pk):
            return None
        ids = [part.pk] + ([meaning_part.pk] if meaning_part else [])
        meaning, kind = entry.meaning, 'word'
    else:
        return None
    from .public_browsing import contributions
    parts = ([loaded.parts[pk] for pk in sorted(set(ids)) if pk in loaded.parts] if loaded is not None
             else list(contributions(entry.dictionary).filter(pk__in=ids).distinct().order_by('pk')))
    if len(parts) != len(set(ids)):
        return None
    return {'id':part.pk, 'entry':entry.pk, 'word':part.word, 'meaning':meaning,
            'context':context_text, 'kind':kind, 'ids':sorted(set(ids)),
            'digests':[[p.pk, content_digest(p)] for p in parts]}


def candidates(dictionary, *, for_review=False, comparison=False):
    parts = Contribution.objects.filter(entry__dictionary=dictionary, entry__archived=False,
        status='accepted', kind__in=['text','form']).select_related(
            'entry__dictionary','entry__current_text','entry__current_meaning')
    result = [row for part in parts if (row := candidate(part, for_review=for_review, comparison=comparison))]
    if comparison:
        # Sample lexical items, not repeated occurrences of the same form/sense.
        unique = {}
        for row in sorted(result, key=lambda r:r['id']):
            unique.setdefault((row['word'], row['meaning'], row['kind']), row)
        result = list(unique.values())
    return sorted(result, key=lambda r:(r['word'].casefold(), r['meaning'], r['id']))


def current_item(item):
    porting.authority(item.run.port)
    if (item.invalidated or item.run.status == 'cancelled' or
            item.run.options.get('experiment_version') != VERSION):
        raise Conflict('This experiment is no longer available.')
    for expected in item.snapshot['words']:
        part = Contribution.objects.select_related('entry__dictionary','entry__current_text',
            'entry__current_meaning').filter(pk=expected['id'], entry_id=item.source_entry_id,
                entry__dictionary_id=item.run.port.source_id).first()
        if not part or candidate(part, comparison=is_comparison(item.run)) != expected:
            raise Conflict('Source wording or access changed. Create a new experiment.')
    return item.source_entry


def clip_allowance(word, language, prices, method):
    if method.startswith('google_'):
        return porting.money(google_tts.estimate(word, method))
    if method == 'carrier' or (method == 'openai' and carrier.eligible(word, language)):
        return porting.money(carrier.estimate(word, language, allowance=True))
    return port_costs.allowance(port_costs.speech(word, language, prices))


@transaction.atomic
def quote(user, dictionary, token, selected, repeats=2, voice=tts.VOICE, *, comparison=False, sampling='manual', sample_size=30):
    porting.locks(); require_owner(user, dictionary)
    old = PortRun.objects.filter(pk=token, port__source=dictionary, port__user=user, stage=STAGE).first()
    if old:
        if is_comparison(old) != comparison:
            raise Conflict('Reload the experiment form.')
        return old
    if PortRun.objects.filter(pk=token).exists():
        raise Conflict('Reload the experiment form.')
    if not 1 <= repeats <= 3 or voice not in tts.VOICE_NAMES:
        raise Conflict('Choose one to three repetitions and a supported voice.')
    if comparison:
        google_tts.require_access(user)
        google_tts.credentials()  # Local validation only; estimates send no API requests.
        if not google_tts.voices_for(dictionary):
            raise Conflict('Choose a Google voice in Word audio settings first.')
    selected = set(map(int, selected))
    available = {r['id']:r for r in candidates(dictionary, comparison=comparison)}
    population = len(available)
    if comparison and sampling != 'manual':
        if sampling not in {'random', 'homographs', 'expressions', 'forms'} or not 1 <= sample_size <= MAX_COMPARISON:
            raise Conflict('Choose a listed sample type and between 1 and 60 items.')
        pool = [r['id'] for r in available.values() if sampling == 'random' or
            (sampling == 'homographs' and comparison_homograph(r, dictionary.language)) or
            (sampling == 'expressions' and carrier.eligible(r['word'], dictionary.language)) or
            (sampling == 'forms' and r['kind'] == 'form')]
        population = len(pool)
        selected = set(secrets.SystemRandom().sample(pool, min(sample_size, population)))
    limit = MAX_COMPARISON if comparison else MAX_SELECTION
    if not 1 <= len(selected) <= limit or not selected.issubset(available):
        raise Conflict(f'Choose between 1 and {limit} currently available words or forms.')
    if comparison and len(selected) * repeats * (1 + len(google_tts.voices_for(dictionary))) > 450:
        raise Conflict('Choose fewer items or takes: at most 450 recordings can be rated in one experiment.')
    model, key, personal, prices = photo_ai.configuration(user)
    port = LanguagePort.objects.create(source=dictionary, user=user, is_audio_batch=True,
        name='Word audio provider comparison' if comparison else 'Homograph audio experiment', language=dictionary.language,
        explanation_language=dictionary.explanation_language, voice=voice)
    porting.authority(port)
    run = PortRun.objects.create(pk=token, port=port, stage=STAGE, model=model,
        source_language=dictionary.language, source_explanation_language=dictionary.explanation_language,
        prices={**{k:str(v) for k,v in prices.items()}, 'speech_recipe':tts.INSTRUCTIONS_VERSION,
                'carrier_recipe':carrier.VERSION}, options={'experiment_version':VERSION,
                'repeats':repeats, 'revealed':False, 'ratings_revision':0},
        payer=porting.payer_now(user), expires_at=timezone.now()+timedelta(hours=1))
    if comparison:
        run.prices.update(google_tts.comparison_prices(dictionary))
        run.options.update(suite='providers', comparison_version=COMPARISON_VERSION,
            methods=['openai', *google_tts.voices_for(dictionary)],
            sampling=sampling, population=population)
    grouped = {}
    for pk in sorted(selected):
        row = available[pk]
        grouped.setdefault(row['entry'], []).append(row)
    for entry_id, words in grouped.items():
        clips, estimated, allowance = [], Decimal('0'), Decimal('0')
        for row in words:
            for repeat in range(1, repeats+1):
                methods = list(methods_for(run))
                secrets.SystemRandom().shuffle(methods)
                for label, method in zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', methods):
                    reserve = clip_allowance(row['word'], dictionary.language, prices, method)
                    estimated += (google_tts.estimate(row['word'], method) if method.startswith('google_') else
                                  carrier.estimate(row['word'], dictionary.language) if method == 'carrier' or
                                  (method == 'openai' and carrier.eligible(row['word'], dictionary.language)) else
                                  port_costs.speech(row['word'], dictionary.language, prices))
                    allowance += reserve
                    clips.append({'id':uuid.uuid4().hex, 'word_id':row['id'], 'repeat':repeat,
                        'label':label, 'method':method, 'status':'waiting', 'allowance':str(reserve),
                        'rating':'', 'note':'', 'cost':'0', 'report':{}})
        item = PortItem.objects.create(run=run, source_entry_id=entry_id, snapshot={'words':words},
            result={'clips':clips}, estimated_usd=porting.money(estimated), allowance_usd=allowance)
        item.sources.set({pk for row in words for pk in row['ids']})
        run.estimated_usd += item.estimated_usd
        run.allowance_usd += item.allowance_usd
    run.save()
    return run


def erase_files(item):
    """Called under dictionary lock, also for completed experiments on withdrawal."""
    for clip in item.result.get('clips', []):
        for field in ('path', 'full_path'):
            if clip.get(field):
                transaction.on_commit(lambda path=clip[field]:delete_file(path))


def process(item_id):
    # Experiments and reviewed repairs share private generation, never publication.
    # One clip, including bounded carrier retries, per queue task. Next clip gets
    # a fresh task. The durable item claim prevents duplicate broker delivery.
    with transaction.atomic():
        porting.locks()
        item = port_tasks.fetch(item_id, True)
        if item.run.stage not in {STAGE, 'audio_repair'} or item.status != 'queued':
            return
        try:
            key = port_tasks.credentials(item)
        except (Conflict, Http404):
            porting.clear_preview(item, 'Source or permission changed; no further requests.')
            transaction.on_commit(lambda:port_tasks.dispatch(str(item.run_id)))
            return
        clip = next((c for c in item.result['clips'] if c['status'] == 'waiting'), None)
        if not clip:
            item.status = 'ready'; item.save(update_fields=['status'])
            transaction.on_commit(lambda:port_tasks.dispatch(str(item.run_id)))
            return
        clip['status'] = 'running'
        clip_id = clip['id']
        word = next(w for w in item.snapshot['words'] if w['id'] == clip['word_id'])
        item.status, item.started_at = 'running', timezone.now()
        item.usage = {'homograph_claim': {'id':clip_id, 'allowance':clip['allowance'], 'method':clip['method']}}
        item.save(update_fields=['status','started_at','result','usage'])
        run, method = item.run, clip['method']

    report, full, prepared, paths = {}, [], None, []
    failure = ''
    def gate():
        with transaction.atomic():
            porting.locks()
            live = port_tasks.fetch(item_id, True)
            active = next((c for c in live.result.get('clips', []) if c['id'] == clip_id), None)
            if live.status != 'running' or not active or active['status'] != 'running':
                raise Conflict('This attempt was stopped.')
            port_tasks.credentials(live)
    try:
        common = dict(language=tts.language_code(run.port.language), model=tts.MODEL,
                      voice=word.get('voice', run.port.voice), api_key=key, report=report, before_request=gate)
        if method.startswith('google_'):
            prepared, duration = google_tts.synthesize(word['word'], language=run.port.language,
                method=method, report=report, before_request=gate,
                selected_voice=run.prices['google_voices'][tts.language_code(run.port.language)][method])
        elif method == 'carrier' or (method == 'openai' and carrier.eligible(word['word'], run.port.language)):
            prepared, duration = carrier.synthesize(word['word'], **common,
                homograph_experiment=method == 'carrier', keep_full=lambda data:full.__setitem__(slice(None), [data]))
        else:
            prepared, duration = tts.synthesize(word['word'], **common, meaning=word['meaning'],
                meaning_language=run.port.explanation_language, guidance_model=run.model,
                guidance_prices=run.prices, speech_kind='entry')
    except Exception as exc:
        tts.record_failure(report, exc)
        failure = ('extraction' if isinstance(exc, carrier.ExtractionFailed) else
                   'stopped' if isinstance(exc, (Conflict, Http404)) else 'generation')
    actual = tts.report_cost(report)
    uncertain = bool(report.get('uncertain_cost'))
    # Preserve the same conservative unknown-cost accounting as other batch jobs.
    cost = max(actual, Decimal(clip['allowance'])) if uncertain else actual
    try:
        with transaction.atomic():
            porting.locks()
            live = port_tasks.fetch(item_id, True)
            active = next((c for c in live.result.get('clips', []) if c['id'] == clip_id), None)
            if not active or active['status'] != 'running':
                # Recovery has already accounted for this abandoned request.
                # A withdrawal may have cleared the result but still needs its cost.
                if live.status == 'running':
                    live.audio_cost += cost
                    live.uncertain_cost |= uncertain
                    live.status, live.usage = 'discarded', {}
                    live.save(update_fields=['audio_cost','uncertain_cost','status','usage'])
                    record_clip_usage(live, clip, cost)
                transaction.on_commit(lambda:port_tasks.dispatch(str(live.run_id)))
                return
            live.audio_cost += cost
            live.uncertain_cost |= uncertain
            record_clip_usage(live, clip, cost)
            try:
                porting.current_item(live)
                active.update(status='failed' if failure else 'ready', failure=failure,
                              cost=str(cost), report=report)
                if not failure:
                    active['path'] = write_upload(prepared, run.port.source_id, paths)['file_path']
                if full:
                    active['full_path'] = write_upload(full[0], run.port.source_id, paths)['file_path']
                live.status = 'waiting' if any(c['status']=='waiting' for c in live.result['clips']) else 'ready'
            except (Conflict, Http404):
                erase_files(live)
                live.result, live.status, live.invalidated = {}, 'discarded', True
            live.usage = {}
            live.save(update_fields=['audio_cost','uncertain_cost','status','result','invalidated','usage'])
            transaction.on_commit(lambda:port_tasks.dispatch(str(live.run_id)))
    except Exception:
        for path in paths:
            delete_file(path)
        raise


@transaction.atomic
def resume(user, run_id):
    porting.locks()
    run = PortRun.objects.select_for_update().get(pk=run_id, port__user=user, stage__in=[STAGE, 'audio_repair'])
    if run.status not in {'running','cancelled'}:
        return run
    cutoff = timezone.now()-timedelta(minutes=15)
    for item in run.items.filter(status='running', started_at__lt=cutoff):
        active = [c for c in item.result.get('clips', []) if c['status']=='running']
        claim = item.usage.get('homograph_claim')
        if not active and claim:
            item.audio_cost += Decimal(claim['allowance'])
            item.uncertain_cost = True
            record_clip_usage(item, claim, Decimal(claim['allowance']))
        for clip in active:
            if clip['status'] == 'running':
                clip.update(status='failed', failure='interrupted', cost=clip['allowance'])
                item.audio_cost += Decimal(clip['allowance'])
                item.uncertain_cost = True
                record_clip_usage(item, clip, Decimal(clip['allowance']))
        item.status = 'waiting' if any(c['status']=='waiting' for c in item.result.get('clips', [])) else 'ready'
        if item.invalidated:
            item.status = 'discarded'
        item.usage = {}
        item.save(update_fields=['status','result','audio_cost','uncertain_cost','usage'])
    for pk in run.items.filter(status='queued').values_list('pk',flat=True):
        transaction.on_commit(lambda pk=pk:port_tasks.send(pk))
    transaction.on_commit(lambda:port_tasks.dispatch(str(run.pk)))
    return run


class QuoteForm(forms.Form):
    token = forms.UUIDField(widget=forms.HiddenInput)
    words = forms.MultipleChoiceField(label=_('Words and sentence forms'),
        widget=forms.CheckboxSelectMultiple, help_text=_('Choose up to 20. Nothing is selected automatically.'))
    repeats = forms.TypedChoiceField(label=_('Takes per method and word'), coerce=int,
        choices=[(1,'1'), (2,'2'), (3,'3')], initial=2)
    voice = forms.ChoiceField(label=_('Voice'), choices=[(v,v) for v in tts.VOICE_NAMES], initial=tts.VOICE)

    def __init__(self, *args, rows, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['words'].choices = [(str(r['id']), f"{r['word']} — {r['meaning']}" +
            (f" ({r['context']})" if r['context'] else '')) for r in rows]

    def clean_words(self):
        result = self.cleaned_data['words']
        if len(result) > MAX_SELECTION:
            raise forms.ValidationError(_('Choose at most 20 words or forms.'))
        return result


class ProviderQuoteForm(QuoteForm):
    sampling = forms.ChoiceField(label=_('Sample to compare'), initial='random', choices=[
        ('random', _('Random vocabulary sample')), ('homographs', _('English homographs')),
        ('expressions', _('Multi-word expressions')), ('forms', _('Sentence forms')),
        ('manual', _('Choose items manually below'))])
    sample_size = forms.IntegerField(label=_('Number of items to sample'), min_value=1,
                                    max_value=MAX_COMPARISON, initial=30)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['words'].required = False
        self.fields['words'].help_text = _('Only used for manual selection. Choose up to 60 items.')
        self.fields['repeats'].initial = 1
        self.fields['voice'].label = _('OpenAI voice')
        self.order_fields(['token', 'sampling', 'sample_size', 'repeats', 'voice', 'words'])

    def clean_words(self):
        result = self.cleaned_data['words']
        if len(result) > MAX_COMPARISON:
            raise forms.ValidationError(_('Choose at most 60 words or forms.'))
        return result


@page(['GET', 'POST'])
def provider_start(request, pk):
    dictionary = get_dictionary(request.user, pk); require_owner(request.user, dictionary)
    google_tts.require_access(request.user)
    rows = candidates(dictionary, comparison=True)
    form = ProviderQuoteForm(request.POST if request.method == 'POST' else None, rows=rows,
                             initial={'token': uuid.uuid4()})
    if request.method == 'POST':
        if request.POST.get('action') == 'check':
            for name in google_tts.voices_for(dictionary).values():
                google_tts.check_access(request.user, dictionary.language, selected_voice=name)
            messages.success(request, _('Google access checked. No audio was generated.'))
            return redirect('community_dictionary:word-audio-compare', pk=pk)
        if form.is_valid():
            v = form.cleaned_data
            run = quote(request.user, dictionary, v['token'], v['words'], v['repeats'], v['voice'],
                        comparison=True, sampling=v['sampling'], sample_size=v['sample_size'])
            return redirect('community_dictionary:homographs-run', pk=pk, run_id=run.pk)
    return render(request, 'community_dictionary/provider_comparison_start.html', context(request, dictionary,
        form=form, available=bool(rows), google_project=google_tts.project(),
        google_voices=list(google_tts.voices_for(dictionary).values()),
        runs=PortRun.objects.filter(stage=STAGE, options__suite='providers',
                                   port__source=dictionary, port__user=request.user)[:20]))


@page(['GET','POST'])
def start(request, pk):
    dictionary = get_dictionary(request.user, pk); require_owner(request.user, dictionary)
    rows = candidates(dictionary)
    form = QuoteForm(request.POST if request.method == 'POST' else None, rows=rows,
                     initial={'token':uuid.uuid4()})
    if request.method == 'POST' and form.is_valid():
        values = form.cleaned_data
        run = quote(request.user, dictionary, values['token'], values['words'], values['repeats'], values['voice'])
        return redirect('community_dictionary:homographs-run', pk=pk, run_id=run.pk)
    return render(request, 'community_dictionary/homographs_start.html', context(request, dictionary,
        form=form, available=bool(rows), runs=PortRun.objects.filter(stage=STAGE,
            port__source=dictionary, port__user=request.user)[:20]))


def owner_run(request, pk, run_id):
    dictionary = get_dictionary(request.user, pk); require_owner(request.user, dictionary)
    run = get_object_or_404(PortRun.objects.select_related('port__source','port__user'),
        pk=run_id, stage=STAGE, port__source=dictionary, port__user=request.user)
    return dictionary, run


def visible_items(run):
    for item in run.items.select_related('source_entry').all():
        item.run = run
        try:
            current_item(item)
        except (Conflict, Http404):
            continue
        yield item


@transaction.atomic
def save_ratings(run_id, data, *, reveal=False):
    porting.locks()
    run = PortRun.objects.select_for_update().get(pk=run_id, stage=STAGE)
    if not run.settled or run.status != 'complete':
        raise Conflict('Wait for generation to finish before rating.')
    if str(run.options['ratings_revision']) != data.get('revision'):
        raise Conflict('Ratings were saved in another tab. Reload before editing.')
    updates = []
    for item in visible_items(run):
        for clip in item.result['clips']:
            if clip['status'] != 'ready':
                continue
            rating, note = data.get('rating_'+clip['id'], ''), data.get('note_'+clip['id'], '').strip()
            if rating not in dict(RATINGS) or len(note) > 1000:
                raise Conflict('Choose a listed rating and keep each note below 1,000 characters.')
            if reveal and not rating:
                raise Conflict('Rate every available recording (or choose Cannot judge) before revealing methods.')
            if run.options['revealed'] and (rating, note) != (clip['rating'], clip['note']):
                clip['edited_after_reveal'] = True
            clip.update(rating=rating, note=note)
        updates.append(item)
    for item in updates:
        item.save(update_fields=['result'])
    run.options['ratings_revision'] += 1
    if reveal:
        run.options['revealed'] = True
    run.save(update_fields=['options'])


def table(run):
    methods = methods_for(run)
    rows, summary = [], {method:Counter() for method in methods}
    for item in visible_items(run):
        clips = item.result.get('clips', [])
        for word in item.snapshot['words']:
            for repeat in range(1, run.options['repeats']+1):
                pair = [dict(c) for c in clips if c['word_id']==word['id'] and c['repeat']==repeat]
                pair.sort(key=lambda c:c['label'])
                for clip in pair:
                    summary[clip['method']][clip['rating'] or ('failed' if clip['status']=='failed' else 'unrated')] += 1
                    clip['method_name'] = methods[clip['method']] if run.options['revealed'] else ''
                rows.append({'word':word, 'repeat':repeat, 'clips':pair, 'item':item})
    return rows, [{'method':methods[m], **{k:c[k] for k in ['acceptable','minor','major','cannot','failed','unrated']}}
                  for m,c in summary.items()]


def paired_summary(run, rows):
    if not is_comparison(run) or not run.options['revealed']:
        return []
    totals = {m: Counter() for m in methods_for(run) if m != 'openai'}
    for row in rows:
        clips = {c['method']: c for c in row['clips']}
        baseline = clips.get('openai', {})
        for method, counts in totals.items():
            other = clips.get(method, {})
            if any(c.get('status') != 'ready' for c in (baseline, other)):
                key = 'failed'
            elif any(c.get('rating') not in {'acceptable', 'minor', 'major'} for c in (baseline, other)):
                key = 'unscored'
            else:
                good = tuple(c['rating'] == 'acceptable' for c in (baseline, other))
                key = {(True, True): 'both', (False, True): 'google_only',
                       (True, False): 'openai_only', (False, False): 'neither'}[good]
            counts[key] += 1
    return [{'method': COMPARISON_METHODS[m], **{k: c[k] for k in
        ['both', 'google_only', 'openai_only', 'neither', 'failed', 'unscored']}} for m,c in totals.items()]


@page(['GET','POST'])
def detail(request, pk, run_id):
    dictionary, run = owner_run(request, pk, run_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            if request.POST.get('approve') != 'on':
                raise Conflict('Approve the estimate and permission to send selected text to the listed providers.')
            if is_comparison(run) and run.status == 'estimate':
                comparison_recipes(run)
                google_tts.check_access(request.user, run.port.language)
            porting.approve(request.user, run.pk)
        elif action in {'save', 'reveal'}:
            save_ratings(run.pk, request.POST, reveal=action=='reveal')
            messages.success(request, _('Ratings saved.'))
        elif action == 'resume':
            resume(request.user, run.pk)
        elif action == 'cancel':
            porting.cancel(request.user, run.pk)
        else:
            raise Conflict('Unknown experiment action.')
        return redirect('community_dictionary:homographs-run', pk=pk, run_id=run.pk)
    rows, summary = table(run)
    clips = [c for row in rows for c in row['clips']]
    progress = Counter(c['status'] for c in clips)
    balance = get_user_balance_usd(request.user) if run.payer == 'credits' else None
    return render(request, 'community_dictionary/homographs_run.html', context(request, dictionary,
        run=run, rows=rows, summary=summary, ratings=RATINGS, total=len(clips),
        comparison=is_comparison(run), pairs=paired_summary(run, rows),
        columns=list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'[:len(methods_for(run))]),
        finished=progress['ready']+progress['failed'], failures=progress['failed'], balance=balance,
        unavailable=run.items.count()-len({row['item'].pk for row in rows}),
        enough_funds=balance is None or balance>=run.allowance_usd, expired=run.expires_at<=timezone.now(),
        held=0 if run.settled else run.reserved_usd-run.released_usd))


@page(['GET'])
def media(request, pk, run_id, item_id, clip_id):
    dictionary, run = owner_run(request, pk, run_id)
    item = get_object_or_404(PortItem, pk=item_id, run=run)
    item.run = run
    current_item(item)
    clip = next((c for c in item.result.get('clips', []) if c['id']==clip_id), None)
    full = request.GET.get('full') == '1'
    if not clip or (full and not run.options['revealed']):
        raise Http404
    path = clip.get('full_path' if full else 'path')
    if not path or (not full and clip['status'] != 'ready'):
        raise Http404
    return private_media_response(request, path, 'audio/wav', 'recording.wav')


def csv_safe(value):
    text = str(value)
    return "'"+text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else text


@page(['GET'])
def export(request, pk, run_id):
    dictionary, run = owner_run(request, pk, run_id)
    if not run.options['revealed']:
        raise Conflict('Save ratings and reveal methods before exporting.')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = ('attachment; filename="word-audio-comparison.csv"' if is_comparison(run)
                                       else 'attachment; filename="homograph-audio-ratings.csv"')
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['experiment','language','voice','word','meaning','sentence','kind','take','label',
        'method','status','rating','note','cost_usd_estimate','attempts','failure','after_reveal',
        'entry_id','text_contribution_id','speech_model','guidance_model','recipe',
        'provider','sampling','eligible_population','homograph','expression','strategy','google_project',
        'synthesis_recipe','uncertain_cost','failure_code'])
    for row in table(run)[0]:
        for clip in row['clips']:
            word = row['word']
            google = clip['method'].startswith('google_')
            model = run.prices['google_voices'][tts.language_code(run.port.language)][clip['method']] if google else tts.MODEL
            voice = model if google else run.port.voice
            writer.writerow([csv_safe(v) for v in [run.pk,run.port.language,voice,
                word['word'],word['meaning'],word['context'],word['kind'],row['repeat'],clip['label'],
                clip['method'],clip['status'],clip['rating'],clip['note'],clip['cost'],
                len(clip.get('report',{}).get('attempts', [])),clip.get('failure',''),
                clip.get('edited_after_reveal',False),word['entry'],word['id'],model, clip.get('report',{}).get('guidance_model',''),
                COMPARISON_VERSION if is_comparison(run) else VERSION,
                'google' if google else 'openai', run.options.get('sampling','manual'),
                run.options.get('population',''), comparison_homograph(word, run.port.language),
                carrier.eligible(word['word'],run.port.language), clip.get('report',{}).get('strategy','direct'),
                run.prices.get('google_project','') if google else '',
                clip.get('report',{}).get('instructions_version',''),
                clip.get('report',{}).get('uncertain_cost',clip.get('failure')=='interrupted'),
                clip.get('report',{}).get('failure_code','')]])
    return response
