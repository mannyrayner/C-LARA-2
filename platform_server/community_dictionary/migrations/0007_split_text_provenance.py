from django.db import migrations, models


def split_text(apps, schema_editor):
    Entry = apps.get_model('community_dictionary', 'Entry')
    Contribution = apps.get_model('community_dictionary', 'Contribution')
    Membership = apps.get_model('community_dictionary', 'Membership')
    Membership.objects.filter(accepted=True).update(status='active')
    Contribution.objects.filter(controlled_by__isnull=True).update(controlled_by_id=models.F('author_id'))
    fields = ('word', 'meaning', 'category')
    for entry in Entry.objects.all().iterator():
        bundles = list(Contribution.objects.filter(entry=entry, kind='text').order_by('base_version', 'created_at', 'pk'))
        snapshots = {0: {field: None for field in fields}}
        bundle_parts = {}
        for bundle in bundles:
            if bundle.status == 'removed':
                continue
            baseline = snapshots.get(bundle.base_version, {})
            parts = {}
            values = {field: getattr(bundle, field) for field in fields}
            metadata = dict(bundle.provenance or {})
            # Never duplicate a translation into the provenance of a word, or vice versa.
            for field in fields:
                previous = baseline.get(field)
                value = values[field]
                unchanged = (previous is not None and getattr(previous, field) == value) or (previous is None and not value)
                if unchanged:
                    parts[field] = previous
                    continue
                provenance = {**metadata, 'legacy_bundle_id': bundle.pk, 'attribution_basis': 'earliest surviving field history'}
                for key in ('proposed_word', 'proposed_meaning'):
                    if key != 'proposed_' + field:
                        provenance.pop(key, None)
                kwargs = dict(entry_id=entry.pk, author_id=bundle.author_id,
                    controlled_by_id=bundle.author_id,
                    kind='text', text_field=field, status=bundle.status,
                    base_version=bundle.base_version, created_at=bundle.created_at,
                    previous_revision_id=previous.pk if previous else None, provenance=provenance,
                    **{field: value})
                if field == 'word':
                    Contribution.objects.filter(pk=bundle.pk).update(**kwargs, meaning='', category='')
                    part = Contribution.objects.get(pk=bundle.pk)
                else:
                    part = Contribution.objects.create(**kwargs)
                parts[field] = part
            if parts.get('word') is None or parts['word'].pk != bundle.pk:
                Contribution.objects.filter(pk=bundle.pk).update(word='', meaning='', category='', status='removed',
                    text_field='word', provenance={'legacy_split': True})
            bundle_parts[bundle.pk] = parts
            if bundle.status == 'accepted':
                snapshots[bundle.base_version + 1] = parts
        accepted = bundle_parts.get(entry.current_text_id, {})
        # Empty / partially lost history remains honestly unattributed. Do not
        # manufacture a contributor from the creator of the whole entry.
        update = {'meaning_version': entry.text_version, 'category_version': entry.text_version}
        for field, pointer in [('word', 'current_text'), ('meaning', 'current_meaning'), ('category', 'current_category')]:
            part = accepted.get(field)
            update[pointer + '_id'] = part.pk if part else None
        Entry.objects.filter(pk=entry.pk).update(**update)
        AudioStudy = apps.get_model('community_dictionary', 'AudioStudy')
        for study in AudioStudy.objects.filter(entry=entry):
            source = bundle_parts.get(study.source_text_id, {}).get('word')
            if source:
                AudioStudy.objects.filter(pk=study.pk).update(source_text_id=source.pk)
        for audio in Contribution.objects.filter(entry=entry, kind='audio'):
            provenance = audio.provenance or {}
            if provenance.get('origin') == 'synthetic':
                source = bundle_parts.get(provenance.get('source_text_id'), {}).get('word')
                if source:
                    Contribution.objects.filter(pk=audio.pk).update(shared_from_id=source.pk)
    Request = apps.get_model('community_dictionary', 'Request')
    for req in Request.objects.exclude(note='').iterator():
        Contribution.objects.create(entry_id=req.entry_id, author_id=req.created_by_id,
            controlled_by_id=req.created_by_id, kind='note', status='accepted', body=req.note,
            label='Partner request', request_id=req.pk, created_at=req.created_at)
    # Already withdrawn proposals must also become private, never editor-readable.
    # Their migration is done using historical models only.
    Dictionary = apps.get_model('community_dictionary', 'Dictionary')
    for item in Contribution.objects.filter(status='withdrawn').select_related('entry__dictionary').iterator():
        old = item.entry
        source = old.dictionary
        private, _ = Dictionary.objects.get_or_create(owner_id=item.controlled_by_id, personal=True, collection_source_id=source.pk,
            defaults={'name': ('My collection · ' + source.name)[:160], 'language': source.language,
                      'explanation_language': source.explanation_language, 'photo_ai_enabled': False, 'tts_enabled': False})
        target, _ = Entry.objects.get_or_create(dictionary_id=private.pk, collection_source_id=old.pk, defaults={'created_by_id': item.controlled_by_id})
        Contribution.objects.filter(pk=item.pk).update(entry_id=target.pk, withdrawn_from_id=old.pk, status='accepted', request_id=None)
        if item.text_field:
            pointer = {'word': 'current_text', 'meaning': 'current_meaning', 'category': 'current_category'}[item.text_field]
            Entry.objects.filter(pk=target.pk).update(**{item.text_field: getattr(item, item.text_field), pointer + '_id': item.pk})
        elif item.kind == 'image':
            Entry.objects.filter(pk=target.pk, selected_image__isnull=True).update(selected_image_id=item.pk)


class Migration(migrations.Migration):
    dependencies = [('community_dictionary', '0006_contribution_control')]
    operations = [migrations.RunPython(split_text)]
