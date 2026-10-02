"""One-time reset explicitly requested for the laptop withdrawal experiments.

Use historical models only. Production is expected to have no private content;
run community_withdrawal_audit --expect-empty there before applying this migration.
This cannot safely be reversed: restore the pre-upgrade database/media backup.
"""
from collections import defaultdict
from django.db import migrations

FIELDS = {'word': ('current_text', 'text_version'), 'meaning': ('current_meaning', 'meaning_version'), 'category': ('current_category', 'category_version')}
CONTENT = ('kind', 'text_field', 'word', 'meaning', 'category', 'label', 'body', 'file_path', 'mime_type', 'file_size', 'author_id', 'controlled_by_id')


def restore_experiments(apps, schema_editor):
    Part = apps.get_model('community_dictionary', 'Contribution')
    Entry = apps.get_model('community_dictionary', 'Entry')
    Dictionary = apps.get_model('community_dictionary', 'Dictionary')
    Event = apps.get_model('community_dictionary', 'Event')
    private = list(Part.objects.filter(entry__dictionary__personal=True).exclude(status='removed').select_related('entry__dictionary'))
    if not private:
        return
    affected, restored = set(), set()
    was_shared = set(Part.objects.filter(entry__dictionary__personal=False).values_list('pk', flat=True))
    for part in private:
        collection_entry = part.entry
        target_id = part.withdrawn_from_id or collection_entry.collection_source_id
        if target_id:
            target = Entry.objects.get(pk=target_id)
            if Dictionary.objects.get(pk=target.dictionary_id).personal:
                raise RuntimeError('A private collection has no shared origin. Restore the database backup and inspect it before migrating.')
        else:
            source_id = collection_entry.dictionary.collection_source_id
            if not source_id or Dictionary.objects.get(pk=source_id).personal:
                raise RuntimeError('A private collection has no shared origin. No automatic destination can be chosen.')
            target = Entry.objects.create(dictionary_id=source_id, created_by_id=part.controlled_by_id or part.author_id)
            Entry.objects.filter(pk=collection_entry.pk).update(collection_source_id=target.pk)
            # Later parts of the same private entry must use the same destination.
            for remaining in private:
                if remaining.entry_id == collection_entry.pk:
                    remaining.entry.collection_source_id = target.pk
        metadata = dict(part.provenance or {})
        prior = metadata.get('status_before_withdrawal', 'pending')
        status = prior if prior in {'accepted', 'pending', 'rejected', 'superseded'} else 'pending'
        if metadata.get('withdrawal_mode') == 'moderator':
            status = 'pending'
        metadata['experimental_collection_restored'] = True
        Part.objects.filter(pk=part.pk).update(entry_id=target.pk, status=status,
            withdrawn_from_id=target.pk, provenance=metadata)
        restored.add(part.pk)
        affected.update([target.pk, collection_entry.pk])
        Event.objects.create(dictionary_id=target.dictionary_id, entry_id=target.pk,
            actor_id=part.controlled_by_id or part.author_id, action='migrate_retained_content', detail=f'Contribution {part.pk}; experimental private collection restored')
    # Earlier implementations kept originals plus returned copies. Preserve all
    # provenance nodes, but show one copy of identical content in each lineage.
    for entry in Entry.objects.filter(pk__in=affected):
        parts = list(Part.objects.filter(entry_id=entry.pk).exclude(status='removed'))
        by_id = {p.pk: p for p in parts}
        groups = defaultdict(list)
        for part in parts:
            root, visited = part, set()
            while root.shared_from_id in by_id and root.pk not in visited:
                visited.add(root.pk)
                ancestor = by_id[root.shared_from_id]
                if tuple(getattr(ancestor, f) for f in CONTENT) != tuple(getattr(part, f) for f in CONTENT):
                    break
                root = ancestor
            groups[root.pk].append(part)
        replacements = {}
        for group in groups.values():
            if len(group) < 2 or not any(p.pk in restored for p in group):
                continue
            live = [p for p in group if p.pk in was_shared]
            rejected = [p for p in live if p.status == 'rejected']
            choices = rejected or [p for p in live if p.status == 'accepted'] or live or group
            winner = max(choices, key=lambda p: (p.created_at, p.pk))
            if (not rejected and winner.status == 'pending' and any(p.status == 'accepted' for p in group)
                    and not any((p.provenance or {}).get('withdrawal_mode') == 'moderator' for p in group)):
                winner.status = 'accepted'
                Part.objects.filter(pk=winner.pk).update(status='accepted')
            for part in group:
                if part.pk != winner.pk:
                    Part.objects.filter(pk=part.pk).update(status='superseded')
                    replacements[part.pk] = winner.pk
        update = {}
        for field, (pointer, counter) in FIELDS.items():
            old_id = getattr(entry, pointer + '_id')
            preferred = replacements.get(old_id, old_id)
            current = Part.objects.filter(pk=preferred, entry_id=entry.pk, kind='text', text_field=field, status='accepted').first()
            if current is None:
                current = Part.objects.filter(entry_id=entry.pk, kind='text', text_field=field, status='accepted').order_by('-created_at', '-pk').first()
            new_id = current.pk if current else None
            update[pointer + '_id'] = new_id
            update[field] = getattr(current, field) if current else ''
            if old_id != new_id:
                update[counter] = getattr(entry, counter) + 1
        preferred = replacements.get(entry.selected_image_id, entry.selected_image_id)
        image = Part.objects.filter(pk=preferred, entry_id=entry.pk, kind='image', status='accepted').first()
        if image is None:
            image = Part.objects.filter(entry_id=entry.pk, kind='image', status='accepted').order_by('-created_at', '-pk').first()
        update['selected_image_id'] = image.pk if image else None
        Entry.objects.filter(pk=entry.pk).update(**update)


class Migration(migrations.Migration):
    dependencies = [('community_dictionary', '0008_dictionary_participation')]
    operations = [migrations.RunPython(restore_experiments)]
