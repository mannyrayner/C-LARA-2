"""Frozen provider trials with independent human sessions; no provider calls here.

The versioned rubric uses existing evaluation tables. Clip correctness is stored
as EvaluationRating; preference responses and private random orders live in the
session's versioned evaluator_metadata. No dictionary audio is replaced.
"""
from collections import Counter, defaultdict
from itertools import combinations
import secrets

from django.db import transaction
from django.http import Http404
from django.utils import timezone

from . import evaluation as ev, homograph_experiments as exp, porting
from .audio_review_data import ReviewData
from .models import (Dictionary, EvaluationItem, EvaluationProgress, EvaluationRating,
                     EvaluationSession, EvaluationSet, EvaluationUnit, PortItem, PortRun)
from .permissions import require_owner
from .services import Conflict

RUBRIC = 'word-audio-provider-study-v1'
METHODS = ['openai', 'google_wavenet', 'google_neural2']
PREFERENCE = [('choose','One preferred version'), ('tie','Two or more equally preferred'),
              ('none','None suitable for learning'), ('cannot','Cannot choose')]


def is_study(batch):
    return batch.rubric == RUBRIC


def clip_snapshot(clip):
    return {k:clip.get(k) for k in ['id','method','status','path','failure','word_id','repeat','cost','report']}


def available(batch, records):
    """One request-local source projection, also used by media and exports."""
    records = list(records)
    run = PortRun.objects.select_related('port__source','port__user').filter(
        pk=batch.pk, port__source_id=batch.dictionary_id).first()
    if not run or run.status != 'complete' or not run.settled or run.options.get('evaluation_study',{}).get('rubric') != RUBRIC:
        return {}
    try:
        porting.authority(run.port)
    except (Conflict, Http404):
        return {}
    source_ids = [r.snapshot['word']['id'] for r in records]
    loaded = ReviewData(run.port.source, source_ids)
    items = {i.pk:i for i in run.items.filter(pk__in=[r.snapshot['port_item'] for r in records])}
    result = {}
    for record in records:
        snap = record.snapshot
        part = loaded.selected.get(snap['word']['id'])
        item = items.get(snap['port_item'])
        if not part or not item or item.invalidated:
            continue
        if exp.candidate(part, comparison=True, loaded=loaded) != snap['word']:
            continue
        clips = {c['id']:clip_snapshot(c) for c in item.result.get('clips',[])}
        if all(clips.get(c['id']) == c for c in snap['clips']):
            result[record.pk] = record
    return result


@transaction.atomic
def freeze(user, run):
    Dictionary.objects.select_for_update().get(pk=run.port.source_id)
    run = PortRun.objects.select_for_update().select_related('port__source','port__user').get(pk=run.pk)
    require_owner(user, run.port.source)
    old = EvaluationSet.objects.filter(pk=run.pk).first()
    if old:
        if not is_study(old) or old.dictionary_id != run.port.source_id:
            raise Conflict('The study identifier is already in use.')
        return old
    spec = run.options.get('evaluation_study',{})
    if run.status != 'complete' or not run.settled or spec.get('rubric') != RUBRIC:
        raise Conflict('Finish generation and accounting before opening evaluation.')
    if spec['allow_visitors'] and (not run.port.source.public_browsing_enabled or run.port.source.hidden):
        raise Conflict('Enable public browsing before inviting signed-in visitors.')
    if run.port.source.evaluation_sets.filter(closed_at__isnull=True).count()>=10:
        raise Conflict('Close an existing evaluation first (maximum ten open sets).')
    batch = EvaluationSet.objects.create(id=run.pk,dictionary=run.port.source,created_by=user,
        name=spec['name'],scope='word_audio',sampling='random',seed=run.options['sampling_seed'],
        population_ids=run.options['population_ids'],language=run.port.language,
        explanation_language=run.port.explanation_language,rubric=RUBRIC,allow_visitors=spec['allow_visitors'])
    position = 0
    for item in run.items.order_by('pk'):
        for word in item.snapshot['words']:
            for take in range(1,run.options['repeats']+1):
                clips = [clip_snapshot(c) for c in item.result.get('clips',[])
                         if c['word_id']==word['id'] and c['repeat']==take]
                # Invalidated source rows remain in the generation denominator.
                # They are explicitly omitted from evaluation, never replaced.
                if len(clips)!=len(METHODS) or any(c['status'] not in {'ready','failed'} for c in clips):
                    continue
                position += 1
                snapshot = {'word':word,'take':take,'port_item':item.pk,'clips':clips,
                    'protocol':spec,'cohort':run.options['sampling'],'prices':run.prices,
                    'voice':run.port.voice,'generation_model':run.model}
                record = EvaluationItem.objects.create(evaluation_set=batch,entry_id=word['entry'],
                    position=position,snapshot=snapshot,fingerprint=ev.digest(snapshot))
                EvaluationUnit.objects.bulk_create([EvaluationUnit(evaluation_set=batch,item=record,
                    dimension='word_audio',key=c['id'],word_index=index,missing=c['status']!='ready')
                    for index,c in enumerate(clips)])
    return batch


@transaction.atomic
def join(user, batch, values):
    Dictionary.objects.select_for_update().get(pk=batch.dictionary_id)
    batch = EvaluationSet.objects.select_for_update().get(pk=batch.pk)
    ev.access(user,batch.dictionary_id,batch)
    if batch.closed_at:
        raise Conflict('This study is closed.')
    old = batch.sessions.filter(user=user).first()
    if old:
        return old
    skills = ev.competence_snapshot(user,batch)
    if 'word_audio' not in ev.eligible_dimensions(skills,'word_audio'):
        raise Conflict('Declare confident reading and listening competence before evaluating audio.')
    orders, ids = {}, []
    for item in batch.items.all():
        ids.append(item.pk)
        clips = [c['id'] for c in item.snapshot['clips']]
        secrets.SystemRandom().shuffle(clips)
        orders[str(item.pk)] = clips
    secrets.SystemRandom().shuffle(ids)
    return EvaluationSession.objects.create(evaluation_set=batch,user=user,competences=skills,
        dimensions=['word_audio'],involvement=values['involvement'],evaluator_metadata={
            'rubric':RUBRIC,'consent':'audio-study-v1','orders':orders,'item_order':ids,'preferences':{},
            'equipment':values['equipment'],'prior_exposure':values['prior_exposure']})


def ordered_clips(session, record):
    clips = {c['id']:c for c in record.snapshot['clips']}
    return [(label,clips[cid]) for label,cid in zip('ABC',session.evaluator_metadata['orders'][str(record.pk)])]


@transaction.atomic
def save(user, batch, record, values):
    Dictionary.objects.select_for_update().get(pk=batch.dictionary_id)
    batch = EvaluationSet.objects.select_for_update().get(pk=batch.pk)
    ev.access(user,batch.dictionary_id,batch)
    if batch.closed_at:
        raise Conflict('This study is closed; ratings cannot be changed after disclosure.')
    session = EvaluationSession.objects.select_for_update().get(evaluation_set=batch,user=user,evaluator_kind='human')
    if record.pk not in available(batch,[record]):
        raise Conflict('This source changed or was withdrawn. Continue with another item.')
    progress = session.progress.filter(item=record).first()
    revision = progress.revision if progress else 0
    if values['revision'] != revision:
        raise Conflict('This item was saved in another tab. Reload before editing.')
    choices = values['preferred']
    ready = {c['id'] for c in record.snapshot['clips'] if c['status']=='ready'}
    outcome = values['preference']
    if (not set(choices)<=ready or len(choices)!=len(set(choices)) or
        (outcome=='choose' and len(choices)!=1) or (outcome=='tie' and len(choices)<2) or
        (outcome in {'none','cannot'} and choices) or outcome not in dict(PREFERENCE)):
        raise Conflict('Choose one version, at least two for a tie, or no versions for None/Cannot choose.')
    for unit in record.units.all():
        if unit.missing:
            continue
        score,comment = values['score_'+unit.key],values['comment_'+unit.key]
        if score not in dict(EvaluationRating.SCORES) or len(comment)>1000:
            raise Conflict('Choose a listed correctness judgement and a shorter comment.')
        EvaluationRating.objects.update_or_create(session=session,unit=unit,defaults={'score':score,
            'comment':comment,'updated_at':timezone.now()})
    session.evaluator_metadata['preferences'][str(record.pk)] = {
        'outcome':outcome,'choices':choices,'comment':values['preference_comment'],
        'complete_triplet':len(ready)==len(METHODS),'saved_at':timezone.now().isoformat()}
    session.save(update_fields=['evaluator_metadata'])
    EvaluationProgress.objects.update_or_create(session=session,item=record,
        defaults={'revision':revision+1,'skipped':False})


def results(batch):
    records = list(batch.items.all())
    visible = available(batch,records)
    sessions = list(batch.sessions.filter(evaluator_kind='human').order_by('pk'))
    aliases = {s.pk:f'R{i}' for i,s in enumerate(sessions,1)}
    ratings = {(r.session_id,r.unit.key):r for r in EvaluationRating.objects.filter(
        session__in=sessions,unit__item_id__in=visible).select_related('unit')}
    rows, preferences, summaries, paired = [],[],[],[]
    for session in sessions:
        for record in visible.values():
            snap = record.snapshot
            pref = session.evaluator_metadata.get('preferences',{}).get(str(record.pk))
            if pref:
                preferences.append({'evaluator':aliases[session.pk],'item':record.pk,'word':snap['word']['word'],
                    **pref,'methods':[c['method'] for c in snap['clips'] if c['id'] in pref['choices']]})
            for label,clip in ordered_clips(session,record):
                rating = ratings.get((session.pk,clip['id']))
                rows.append({'evaluator':aliases[session.pk],'item':record.pk,'position':record.position,
                    'clip':clip['id'],'word':snap['word']['word'],'meaning':snap['word']['meaning'],
                    'context':snap['word']['context'],'kind':snap['word']['kind'],'source_part':snap['word']['id'],
                    'source_entry':snap['word']['entry'],'take':snap['take'],'label':label,
                    'method':clip['method'],'status':clip['status'],'failure':clip.get('failure') or '',
                    'score':rating.score if rating else '', 'comment':rating.comment if rating else '',
                    'voice':snap['prices']['google_voices']['en'][clip['method']] if clip['method']!='openai' else snap['voice'],
                    'model':snap['prices']['google_voices']['en'][clip['method']] if clip['method']!='openai' else snap['prices']['speech_model'],
                    'recipe':snap['prices'].get('speech_recipe') if clip['method']=='openai' else 'google-plain-text',
                    'carrier_recipe':snap['prices'].get('carrier_recipe') if clip['method']=='openai' else '',
                    'attempts':len((clip.get('report') or {}).get('attempts',[])),
                    'involvement':session.involvement,'competences':session.competences,
                    'equipment':session.evaluator_metadata['equipment'],
                    'prior_exposure':session.evaluator_metadata['prior_exposure']})
    for method in METHODS:
        method_rows = [r for r in rows if r['method']==method]
        counts = Counter(r['score'] or 'unrated' for r in method_rows if r['status']=='ready')
        scored = sum(counts[k] for k in ['ok','minor','major'])
        by_clip = defaultdict(list)
        for row in method_rows:
            if row['score']: by_clip[row['clip']].append(row['score'])
        source_clips = [c for r in visible.values() for c in r.snapshot['clips'] if c['method']==method]
        summaries.append({'method':method,'name':str(exp.COMPARISON_METHODS[method]),
            **{k:counts[k] for k in ['ok','minor','major','cannot','unrated']},'scored':scored,
            'acceptable_percent':100*counts['ok']/scored if scored else None,
            'problem_percent':100*(counts['minor']+counts['major'])/scored if scored else None,
            'generation_failures':sum(c['status']!='ready' for c in source_clips),
            'distinct_clips':len(source_clips),'agreement':ev.agreement(list(by_clip.values())),
            'sole_preference':sum(p['complete_triplet'] and p['outcome']=='choose' and method in p['methods'] for p in preferences),
            'tied_preference':sum(p['complete_triplet'] and p['outcome']=='tie' and method in p['methods'] for p in preferences)})
    by_item = defaultdict(dict)
    for row in rows: by_item[(row['evaluator'],row['item'])][row['method']] = row
    for a,b in combinations(METHODS,2):
        counts=Counter()
        for item in by_item.values():
            x,y=item[a],item[b]
            if x['status']!='ready' or y['status']!='ready': key='failed'
            elif x['score'] not in {'ok','minor','major'} or y['score'] not in {'ok','minor','major'}: key='unscored'
            elif x['score']=='ok' and y['score']=='ok': key='both'
            elif x['score']=='ok': key='only_a'
            elif y['score']=='ok': key='only_b'
            else:key='neither'
            counts[key]+=1
        paired.append({'a':str(exp.COMPARISON_METHODS[a]),'b':str(exp.COMPARISON_METHODS[b]),
                       **{k:counts[k] for k in ['both','only_a','only_b','neither','failed','unscored']}})
    run = PortRun.objects.get(pk=batch.pk)
    preference_counts=Counter(p['outcome'] for p in preferences if p['complete_triplet'])
    manifest=[{'item':record.pk,'position':record.position,'source_part':record.snapshot['word']['id'],
        'word':record.snapshot['word']['word'],'meaning':record.snapshot['word']['meaning'],
        'kind':record.snapshot['word']['kind'],'context':record.snapshot['word']['context'],
        'take':record.snapshot['take'],'fingerprint':record.fingerprint,
        'clips':[{k:c.get(k) for k in ['id','method','status','failure','cost']} for c in record.snapshot['clips']]}
        for record in visible.values()]
    return {'schema':1,'rubric':RUBRIC,'set_id':str(batch.pk),'language':batch.language,
        'exported_at':timezone.now().isoformat(),'study_created_at':batch.created_at.isoformat(),
        'closed_at':batch.closed_at.isoformat() if batch.closed_at else None,
        'generation_created_at':run.created_at.isoformat(),
        'generation_completed_at':run.completed_at.isoformat() if run.completed_at else None,
        'configuration':{'openai_model':run.prices['speech_model'],'openai_voice':run.port.voice,
            'guidance_model':run.model,'speech_recipe':run.prices['speech_recipe'],
            'carrier_recipe':run.prices['carrier_recipe'],'google_recipe':run.prices['google_recipe'],
            'google_voices':{m:run.prices['google_voices']['en'][m] for m in METHODS[1:]}},
        'sample_manifest':manifest,
        'cohort':run.options['sampling'],'sampling_seed':batch.seed,'population_ids':batch.population_ids,
        'planned_items':sum(len(i.snapshot['words'])*run.options['repeats'] for i in run.items.all()),
        'frozen_items':len(records),'available_items':len(visible),'unavailable_items':len(records)-len(visible),
        'raters':len(sessions),'summaries':summaries,'paired':paired,'ratings':rows,'preferences':preferences,
        'preference_counts':{k:preference_counts[k] for k,_ in PREFERENCE},
        'preferences_not_submitted':len(visible)*len(sessions)-len(preferences),
        'incomplete_preferences':sum(not p['complete_triplet'] for p in preferences),
        'notes':['One clip can receive multiple judgements: pooled counts are not independent items.',
                 'Preferences use complete triplets; incomplete comparisons are exported separately.',
                 'Provider/voice settings and normal generation pipelines are compared, not all voices of a provider.',
                 'Requested model/voice identifiers do not establish the provider internal model build.',
                 'Random dictionary vocabulary is not an untouched picture holdout or representative of English overall.']}
