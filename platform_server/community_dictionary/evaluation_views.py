"""Small, server-rendered evaluation workflow, including phone use without JS."""
import csv
import io
import uuid
from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from . import evaluation as ev
from .models import (Dictionary, EvaluationItem, EvaluationProgress, EvaluationRating,
                     EvaluationSession, EvaluationSet, LanguageCompetence)
from .permissions import dictionaries_for, is_editor, require_owner
from .services import Conflict
from .views import fail, private_media_response


def page(methods):
    def decorate(view):
        @wraps(view)
        def safe(request, *args, **kwargs):
            try:
                return view(request, *args, **kwargs)
            except Conflict as exc:
                return fail(request, str(exc), 409)
        return never_cache(login_required(login_url='community_dictionary:login')(require_http_methods(methods)(safe)))
    return decorate


def context(request, dictionary, member, **extra):
    return {'dictionary': dictionary, 'public_browsing': not member,
            'owner': dictionary.owner_id == request.user.pk,
            'editor': member and is_editor(request.user, dictionary),
            'evaluation_available': True, 'evaluation_page': True, **extra}


class CompetenceForm(forms.ModelForm):
    class Meta:
        model = LanguageCompetence
        fields = ['language', 'reading', 'listening', 'variety', 'experience']
        labels = {'reading': 'Reading competence', 'listening': 'Listening competence',
                  'variety': 'Language variety / dialect (optional)',
                  'experience': 'Relevant teaching or linguistic experience (optional)'}
        widgets = {'language': forms.TextInput(attrs={'list': 'evaluation-languages'}),
                   'experience': forms.Textarea(attrs={'rows': 2})}

    def clean_language(self):
        value = ' '.join(self.cleaned_data['language'].split())
        if not value:
            raise forms.ValidationError('Supply a language name.')
        return value


@page(['GET', 'POST'])
def competences(request):
    existing = LanguageCompetence.objects.filter(user=request.user, language_key=ev.language_key(request.GET.get('language', '')[:80])).first()
    form = CompetenceForm(request.POST if request.method == 'POST' else None, instance=existing)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        LanguageCompetence.objects.update_or_create(user=request.user,
            language_key=ev.language_key(data['language']), defaults={**data, 'updated_at': timezone.now()})
        messages.success(request, 'Language competence saved. Earlier evaluation sessions keep the profile you used when starting them.')
        return redirect('community_dictionary:evaluation-languages')
    allowed = Dictionary.objects.filter(Q(pk__in=dictionaries_for(request.user)) |
        Q(public_browsing_enabled=True, hidden=False, personal=False, archived=False))
    names = set()
    for target, explanation in allowed.values_list('language', 'explanation_language'):
        names.update([target, explanation])
    return render(request, 'community_dictionary/evaluation_languages.html', {
        'form': form, 'competences': LanguageCompetence.objects.filter(user=request.user),
        'language_names': sorted(names - {''})})


class SetForm(forms.Form):
    token = forms.UUIDField(widget=forms.HiddenInput)
    name = forms.CharField(max_length=160, initial='Initial quality evaluation', label='Evaluation name')
    scope = forms.ChoiceField(choices=[('sentences', 'Sentence pages and their vocabulary'), ('words', 'Standalone word pages')])
    sampling = forms.ChoiceField(choices=[('random', 'Random sample'), ('all', 'All eligible pages')])
    size = forms.IntegerField(min_value=1, max_value=ev.MAX_SAMPLE, initial=30,
                              label='Number of pages (random sample only)')
    allow_visitors = forms.BooleanField(required=False,
        label='Allow signed-in visitors to evaluate this set when public browsing is enabled')


@page(['GET', 'POST'])
def home(request, pk):
    dictionary, member = ev.access(request.user, pk)
    form = SetForm(request.POST if request.method == 'POST' else None, initial={'token': uuid.uuid4()})
    if request.method == 'POST':
        require_owner(request.user, dictionary)
        if form.is_valid():
            batch = ev.create_set(request.user, dictionary, form.cleaned_data)
            return redirect('community_dictionary:evaluation-set', pk=pk, set_id=batch.pk)
    batches = dictionary.evaluation_sets.annotate(item_count=Count('items', distinct=True))
    if not member:
        batches = batches.filter(allow_visitors=True)
    sessions = {s.evaluation_set_id: s for s in EvaluationSession.objects.filter(user=request.user, evaluation_set__dictionary=dictionary)}
    rows = [{'batch': b, 'session': sessions.get(b.pk)} for b in batches[:100]]
    return render(request, 'community_dictionary/evaluation_home.html', context(request, dictionary, member,
        rows=rows, form=form))


class SessionForm(forms.Form):
    dimensions = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
        label='What would you like to evaluate?')
    involvement = forms.ChoiceField(label='Did you help create or correct this dictionary?',
        choices=[('', 'Choose…'), ('no', 'No'), ('yes', 'Yes'), ('unsure', 'Not sure')])
    consent = forms.BooleanField(label='I agree to share these ratings, comments and relevant self-reported language competences with the dictionary owner for evaluation. They are not automatically published.')

    def __init__(self, *args, eligible, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dimensions'].choices = [(key, ev.DIMENSIONS[key][0]) for key in eligible]


def competence_display(snapshot):
    """Label both skills without changing the competence record used for a session."""
    levels = dict(LanguageCompetence.LEVELS)
    return [{'role': label, 'language': skill.get('language') or 'Not set',
             'reading': levels.get(skill.get('reading'), 'Not declared') if skill.get('reported_at') else 'Not declared',
             'listening': levels.get(skill.get('listening'), 'Not declared') if skill.get('reported_at') else 'Not declared'}
            for role, label in [('target', 'Target language'), ('explanation', 'Commenting language')]
            for skill in [snapshot.get(role, {})]]


@page(['GET', 'POST'])
def detail(request, pk, set_id):
    batch = get_object_or_404(EvaluationSet, pk=set_id, dictionary_id=pk)
    dictionary, member = ev.access(request.user, pk, batch)
    existing = EvaluationSession.objects.filter(evaluation_set=batch, user=request.user).first()
    competence = ev.competence_snapshot(request.user, batch)
    eligible = ev.eligible_dimensions(competence, batch.scope)
    form = SessionForm(request.POST if request.method == 'POST' else None, eligible=eligible)
    if request.method == 'POST':
        with transaction.atomic():
            Dictionary.objects.select_for_update().get(pk=pk)
            batch = EvaluationSet.objects.select_for_update().get(pk=batch.pk)
            ev.access(request.user, pk, batch)
            if batch.closed_at:
                raise Conflict('This evaluation set is closed. No further ratings can be added.')
            if existing:
                return redirect('community_dictionary:evaluation-session', pk=pk, set_id=batch.pk)
            if form.is_valid():
                EvaluationSession.objects.get_or_create(evaluation_set=batch, user=request.user,
                    defaults={'dimensions': form.cleaned_data['dimensions'], 'competences': competence,
                              'involvement': form.cleaned_data['involvement'],
                              'evaluator_metadata': {'consent': 'evaluation-v1', 'rubric': batch.rubric}})
                return redirect('community_dictionary:evaluation-session', pk=pk, set_id=batch.pk)
    return render(request, 'community_dictionary/evaluation_set.html', context(request, dictionary, member,
        batch=batch, session=existing, eligible=eligible, form=form,
        competence_rows=competence_display(existing.competences if existing else competence),
        item_count=batch.items.count(), participant_count=batch.sessions.count()))


@page(['GET'])
def session(request, pk, set_id):
    batch = get_object_or_404(EvaluationSet, pk=set_id, dictionary_id=pk)
    dictionary, member = ev.access(request.user, pk, batch)
    attempt = get_object_or_404(EvaluationSession, evaluation_set=batch, user=request.user, evaluator_kind='human')
    items = list(batch.items.all())
    available = ev.available_items(items, dictionary)
    live = ev.graph(dictionary)
    progress = {p.item_id: p for p in attempt.progress.all()}
    next_item = None
    rows = []
    for item in items:
        current = item.pk in available and ev.is_current(item, live)
        saved = progress.get(item.pk)
        if current and saved is None and not next_item:
            next_item = item
        rows.append({'item': item, 'title': item.snapshot['entry']['text'] if current else 'Page changed or no longer available',
                     'current': current, 'saved': saved, 'skipped': saved and saved.skipped})
    if request.GET.get('next') == '1' and next_item and not batch.closed_at:
        return redirect('community_dictionary:evaluation-item', pk=pk, set_id=batch.pk, item_id=next_item.pk)
    return render(request, 'community_dictionary/evaluation_session.html', context(request, dictionary, member,
        batch=batch, session=attempt, rows=rows, next_item=next_item,
        competence_rows=competence_display(attempt.competences),
        completed=sum(bool(row['saved']) for row in rows), total=len(items)))


def unit_word(unit, snapshot):
    return snapshot['words'][unit.word_index] if unit.word_index is not None else snapshot['entry']


class RatingForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, units, ratings, **kwargs):
        super().__init__(*args, **kwargs)
        for unit in units:
            if unit.missing:
                continue
            previous = ratings.get(unit.pk)
            self.fields[f'score_{unit.pk}'] = forms.ChoiceField(
                label=ev.DIMENSIONS[unit.dimension][0],
                choices=[('', 'Choose a judgement…'), *EvaluationRating.SCORES],
                initial=previous.score if previous else '')
            self.fields[f'comment_{unit.pk}'] = forms.CharField(label='Comment (optional)', required=False,
                max_length=1000, initial=previous.comment if previous else '', widget=forms.Textarea(attrs={'rows': 2}))


@page(['GET', 'POST'])
@transaction.atomic
def item(request, pk, set_id, item_id):
    # All mutating paths take dictionary then set lock, including close and withdrawal.
    if request.method == 'POST':
        Dictionary.objects.select_for_update().filter(pk=pk).first()
    batches = EvaluationSet.objects.select_for_update() if request.method == 'POST' else EvaluationSet.objects
    batch = get_object_or_404(batches, pk=set_id, dictionary_id=pk)
    dictionary, member = ev.access(request.user, pk, batch)
    attempt = get_object_or_404(EvaluationSession, evaluation_set=batch, user=request.user, evaluator_kind='human')
    record = get_object_or_404(EvaluationItem, pk=item_id, evaluation_set=batch)
    if record.pk not in ev.available_items([record], dictionary):
        raise Http404
    if not ev.is_current(record, ev.graph(dictionary)):
        raise Conflict('This page has changed since it was sampled. Earlier ratings are preserved. Return to your session and continue with another page; use a new set to assess the changed version.')
    if batch.closed_at:
        raise Conflict('This evaluation set is closed. Your saved ratings are retained.')
    units = list(record.units.filter(dimension__in=attempt.dimensions))
    ratings = {r.unit_id: r for r in attempt.ratings.filter(unit__item=record)}
    progress = attempt.progress.filter(item=record).first()
    revision = progress.revision if progress else 0
    form = RatingForm(request.POST if request.method == 'POST' else None, units=units, ratings=ratings,
                      initial={'revision': revision})
    if request.method == 'POST':
        try:
            supplied = int(request.POST.get('revision', ''))
        except ValueError:
            supplied = -1
        if supplied != revision:
            raise Conflict('This page was saved in another tab. Reload before changing your answers.')
        skip = request.POST.get('action') == 'skip'
        if request.POST.get('action') not in {'save', 'skip'}:
            return fail(request, 'Choose Save and next, or Skip for now.')
        if skip or form.is_valid():
            # One transaction: either all the page's judgements are recorded or none are.
            if skip:
                attempt.ratings.filter(unit__item=record).delete()
            else:
                for unit in units:
                    if not unit.missing:
                        EvaluationRating.objects.update_or_create(session=attempt, unit=unit,
                            defaults={'score': form.cleaned_data[f'score_{unit.pk}'],
                                'comment': form.cleaned_data[f'comment_{unit.pk}'], 'updated_at': timezone.now()})
            EvaluationProgress.objects.update_or_create(session=attempt, item=record,
                defaults={'revision': revision + 1, 'skipped': skip})
            messages.success(request, 'Page skipped; you can return to it from your session.' if skip else 'Your judgements were saved.')
            return redirect(reverse('community_dictionary:evaluation-session', args=[pk, batch.pk]) + '?next=1')
    root = record.snapshot['entry']
    rows = []
    for unit in units:
        word = unit_word(unit, record.snapshot)
        rows.append({'unit': unit, 'label': ev.DIMENSIONS[unit.dimension][0],
            'help': ev.DIMENSIONS[unit.dimension][1], 'word': word,
            'word_task': unit.dimension.startswith('word_'),
            'show_image': unit.dimension in {'image', 'translation', 'vocabulary', 'word_translation'},
            'audio_task': unit.dimension in {'sentence_audio', 'word_audio'},
            'score': form[f'score_{unit.pk}'] if not unit.missing else None,
            'comment': form[f'comment_{unit.pk}'] if not unit.missing else None})
    return render(request, 'community_dictionary/evaluation_item.html', context(request, dictionary, member,
        batch=batch, item=record, root=root, words=record.snapshot['words'], rows=rows, form=form,
        total=batch.items.count(), session=attempt))


@page(['GET'])
def media(request, pk, set_id, item_id, contribution_id):
    batch = get_object_or_404(EvaluationSet, pk=set_id, dictionary_id=pk)
    dictionary, member = ev.access(request.user, pk, batch)
    record = get_object_or_404(EvaluationItem, pk=item_id, evaluation_set=batch)
    if (not batch.sessions.filter(user=request.user).exists() and dictionary.owner_id != request.user.pk):
        raise Http404
    if record.pk not in ev.available_items([record], dictionary):
        raise Http404
    # Do not expose retired accepted content to non-members through a saved URL.
    if not member and not ev.is_current(record, ev.graph(dictionary)):
        raise Http404
    part = ev.references(record.snapshot).get(contribution_id)
    if not part or part['kind'] not in {'audio', 'image'} or not part['path']:
        raise Http404
    return private_media_response(request, part['path'], part['mime'], f'evaluation-{contribution_id}')


@page(['GET', 'POST'])
def close(request, pk, set_id):
    batch = get_object_or_404(EvaluationSet, pk=set_id, dictionary_id=pk)
    dictionary, member = ev.access(request.user, pk, batch)
    require_owner(request.user, dictionary)
    if request.method == 'POST':
        if request.POST.get('confirm') != 'yes':
            return fail(request, 'Confirm that you want to close the evaluation set.')
        with transaction.atomic():
            Dictionary.objects.select_for_update().get(pk=pk)
            batch = EvaluationSet.objects.select_for_update().get(pk=set_id)
            dictionary, _ = ev.access(request.user, pk, batch)
            require_owner(request.user, dictionary)
            if not batch.closed_at:
                batch.closed_at = timezone.now()
                batch.save(update_fields=['closed_at'])
        return redirect('community_dictionary:evaluation-results', pk=pk, set_id=batch.pk)
    return render(request, 'community_dictionary/evaluation_close.html', context(request, dictionary, member, batch=batch))


def csv_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else text


@page(['GET'])
def results(request, pk, set_id, download=False):
    batch = get_object_or_404(EvaluationSet.objects.select_related('dictionary'), pk=set_id, dictionary_id=pk)
    dictionary, member = ev.access(request.user, pk, batch)
    require_owner(request.user, dictionary)
    if not batch.closed_at:
        raise Conflict('Results remain hidden while the set is open. Close it when everyone has finished.')
    data = ev.result_data(batch)
    if download:
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['set_id', 'rubric', 'sampling', 'population_size', 'sample_size', 'seed',
            'item_position', 'entry_id', 'snapshot', 'language', 'explanation_language', 'text_origin',
            'language_checked_at_sampling', 'dimension', 'unit_key', 'missing_material', 'evaluator',
            'evaluator_kind', 'involvement', 'target_reading', 'target_listening', 'explanation_reading',
            'target_variety', 'experience', 'score', 'comment',
            'entry_type', 'entry_text', 'entry_translation', 'word_entry_id', 'word_text',
            'word_translation', 'word_form_in_sentence', 'extracted_vocabulary', 'explanation_listening'])
        by_unit = {}
        for rating in data['ratings']:
            by_unit.setdefault(rating.unit_id, []).append(rating)
        aliases = {sid: f'R{index}' for index, sid in enumerate(sorted(batch.sessions.values_list('pk', flat=True)), 1)}
        for unit in data['units']:
            record = data['items'][unit.item_id]
            snap = record.snapshot
            # Export the material that was judged, not its possibly edited live text.
            # result_data has already applied the source-access/withdrawal checks.
            entry = snap['entry']
            word = unit_word(unit, snap) if unit.dimension.startswith('word_') else None
            vocabulary = ''
            if unit.dimension == 'vocabulary':
                vocabulary = '\n'.join(
                    w['text'] + (f" ({w['surface']})" if w.get('surface') and w['surface'] != w['text'] else '')
                    + (f" — {w['meaning']}" if w.get('meaning') else '') for w in snap['words'])
            for rating in by_unit.get(unit.pk, [None]):
                attempt = rating.session if rating else None
                skills = attempt.competences if attempt else {}
                values = [batch.pk, batch.rubric, batch.sampling, data['population_count'], data['sample_count'], batch.seed,
                    record.position, record.entry_id, record.fingerprint, batch.language, batch.explanation_language,
                    snap['entry']['origin'], snap['entry']['checked'], unit.dimension, unit.key, unit.missing,
                    aliases.get(attempt.pk, '') if attempt else '', attempt.evaluator_kind if attempt else '',
                    attempt.involvement if attempt else '', skills.get('target', {}).get('reading', ''),
                    skills.get('target', {}).get('listening', ''), skills.get('explanation', {}).get('reading', ''),
                    skills.get('target', {}).get('variety', ''), skills.get('target', {}).get('experience', ''),
                    rating.score if rating else '', rating.comment if rating else '',
                    entry['kind'], entry['text'], entry['meaning'], word['id'] if word else '',
                    word['text'] if word else '', word['meaning'] if word else '',
                    word.get('surface', '') if word else '', vocabulary,
                    skills.get('explanation', {}).get('listening', '')]
                writer.writerow([csv_cell(value) for value in values])
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="dictionary-evaluation-{batch.pk}.csv"'
        return response
    observations = []
    aliases = {sid: f'R{index}' for index, sid in enumerate(sorted(batch.sessions.values_list('pk', flat=True)), 1)}
    for rating in data['ratings']:
        if rating.score != 'ok' or rating.comment:
            record = data['items'][rating.unit.item_id]
            word = unit_word(rating.unit, record.snapshot)
            observations.append({'entry': record.snapshot['entry']['text'], 'position': record.position,
                'dimension': ev.DIMENSIONS[rating.unit.dimension][0], 'word': word['text'],
                'rater': aliases[rating.session_id], 'score': rating.get_score_display(), 'comment': rating.comment})
    return render(request, 'community_dictionary/evaluation_results.html', context(request, dictionary, member,
        batch=batch, **data, observations=observations))
