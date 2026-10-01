"""Independent text revisions. Unchanged fields never acquire a new author."""
from .models import Contribution

FIELDS = {'word': ('current_text', 'text_version'), 'meaning': ('current_meaning', 'meaning_version'), 'category': ('current_category', 'category_version')}


def version(entry, field):
    return getattr(entry, FIELDS[field][1])


def current(entry, field):
    return getattr(entry, FIELDS[field][0])


def field_snapshot(entry):
    return {field: {'value': getattr(entry, field), 'version': version(entry, field)} for field in FIELDS}


def propose(entry, user, data):
    from .services import Conflict
    from django.core import signing
    snapshot = None
    if data.get('text_snapshot'):
        try:
            snapshot = signing.loads(data['text_snapshot'], salt='community-text-fields')
            if snapshot['entry'] != entry.pk:
                raise ValueError
        except (signing.BadSignature, KeyError, ValueError, TypeError):
            raise Conflict('The wording form is invalid. Reload the entry.')
    made = []
    for field in FIELDS:
        # Missing fields mean no change; empty fields are deliberate only in Edit words.
        if field not in data:
            continue
        value = data.get(field, '')
        if not data.get('edit_text') and not value:
            continue
        baseline = snapshot['fields'][field]['value'] if snapshot else getattr(entry, field)
        if value == baseline:
            continue
        base = snapshot['fields'][field]['version'] if snapshot else version(entry, field)
        if not snapshot and data.get('base_version') is not None and field == 'word':
            base = data['base_version']
        if base != version(entry, field):
            raise Conflict(f'The {dict(Contribution._meta.get_field("text_field").choices)[field].lower()} changed. Reload before editing it.')
        previous = current(entry, field)
        made.append(Contribution.objects.create(entry=entry, author=user, kind='text', text_field=field,
            controlled_by=user,
            previous_revision=previous, base_version=base, **{field: value}))
    return made


def split_legacy(contribution):
    """Compatibility for pre-revision pending rows and programmatic callers."""
    entry = contribution.entry
    values = {f: getattr(contribution, f) for f in FIELDS}
    contribution.text_field = 'word'
    contribution.meaning = contribution.category = ''
    contribution.previous_revision = entry.current_text
    contribution.save()
    made = [contribution]
    for field in ('meaning', 'category'):
        if values[field] == getattr(entry, field):
            continue
        previous = current(entry, field)
        made.append(Contribution.objects.create(entry=entry, author=contribution.author,
            controlled_by=contribution.author,
            kind='text', text_field=field, previous_revision=previous,
            base_version=version(entry, field), provenance=contribution.provenance, **{field: values[field]}))
    return made
