"""Shared category decisions within a port, grounded in bounded source examples.

No extra provider calls: classification travels with the existing entry request.
Concurrent replies adopt the first usable decision under the dictionary lock.
Only IDs/digests are stored for examples; withdrawal invalidates derived previews.
"""
import hashlib
import json
from .models import Contribution, Entry
from .collections import content_digest
from .services import Conflict
from .text import FIELDS


def key(label):
    return hashlib.sha256(label.encode('utf-8')).hexdigest()


def context_record(entry):
    parts = [getattr(entry, pointer) for pointer, _ in FIELDS.values()]
    parts = [p for p in parts if p and p.entry_id == entry.pk and p.status == 'accepted']
    return {'entry': entry.pk, 'ids': sorted(p.pk for p in parts),
            'digest': hashlib.sha256(json.dumps([(p.pk, content_digest(p)) for p in parts]).encode()).hexdigest()}


def context_ids(group):
    return sorted({pk for example in group['examples'] for pk in example['ids']})


def basis_ids(group):
    basis = group.get('basis')
    if not basis:
        return []
    snap = basis['snapshot']
    if snap.get('entry_type') == 'sentence':
        return snap['ids']
    return list(snap['fields'].values()) + ([snap['image']] if snap['image'] else [])


def valid(group, source):
    from .porting import snapshot
    if group.get('invalidated'):
        return False
    for example in group['examples']:
        entry = Entry.objects.filter(pk=example['entry'], dictionary=source, archived=False).first()
        if not entry or context_record(entry) != example:
            return False
    basis = group.get('basis')
    if basis:
        entry = Entry.objects.filter(pk=basis['entry'], dictionary=source, archived=False).first()
        if not entry or snapshot(entry, sentence_only=basis['snapshot'].get('sentence_only',False)) != basis['snapshot']:
            return False
    return True


def build_plan(entries, port):
    from .port_ai import VERSION
    groups = {}
    for entry in entries:
        if entry.category:
            group = groups.setdefault(key(entry.category), {'examples': [], 'decision': None, 'basis': None, 'version': VERSION})
            if len(group['examples']) < 5:
                group['examples'].append(context_record(entry))
    # Reuse an established label across incremental updates when its evidence is
    # unchanged. The latest run containing each label wins, including invalidation.
    seen = set()
    for previous in port.runs.exclude(category_plan={}).order_by('-created_at').iterator():
        for k, old in previous.category_plan.items():
            if k in seen or k not in groups:
                continue
            seen.add(k)
            if (old.get('version') == VERSION and old.get('decision') and
                    old['examples'] == groups[k]['examples'] and valid(old, port.source)):
                groups[k] = old
    return groups


def group_for(item):
    pk = item.snapshot['fields'].get('category')
    label = Contribution.objects.filter(pk=pk).values_list('category', flat=True).first() or ''
    return key(label), item.run.category_plan.get(key(label)), label


def inputs(item):
    _, group, _ = group_for(item)
    if not group:
        return {}
    parts = Contribution.objects.filter(pk__in=context_ids(group))
    examples = {}
    for part in parts:
        examples.setdefault(part.entry_id, {})[part.text_field] = getattr(part, part.text_field)
    return {'category_examples': list(examples.values()), 'category_decision': group['decision']}


def check(item):
    _, group, _ = group_for(item)
    if group and not valid(group, item.run.port.source):
        raise Conflict('The category examples changed or were withdrawn. Prepare a fresh estimate.')


def digest(snap, group):
    from .port_ai import version_for, speech_version
    return hashlib.sha256(json.dumps([snap['digest'], version_for(snap), speech_version(snap),
        group['examples'] if group else [],
        group['basis']['snapshot']['digest'] if group and group.get('basis') else None,
        group.get('decision') if group else None], sort_keys=True).encode()).hexdigest()


def canonicalize(item, result):
    """Called after access/snapshot checks, with dictionary locks held."""
    from .porting import same_language
    run = item.run
    k, group, label = group_for(item)
    language = result['category_language']
    unchanged = (language == 'target' and same_language(run.source_language, run.port.language)) or (
        language == 'commenting' and same_language(run.source_explanation_language, run.port.explanation_language))
    if unchanged or language == 'uncertain' or not label:
        result['category'] = label
    if label and not result['category']:
        result['category'], result['category_language'] = label, 'uncertain'
    if not group:  # old in-flight jobs and entries without a category
        return
    if not group['decision']:
        group['decision'] = {name: result[name] for name in ['category', 'category_language']}
        group['basis'] = {'entry': item.source_entry_id, 'snapshot': item.snapshot}
        run.category_plan[k] = group
        run.save(update_fields=['category_plan'])
        # Every result using this decision depends on its actual deciding input,
        # including the representative picture, as well as category examples.
        for sibling in run.items.all():
            if group_for(sibling)[0] == k:
                sibling.sources.add(*basis_ids(group))
    result.update(group['decision'])
