"""Member-scoped credit for accepted human photographs and explicit copies."""
from collections import Counter

from django.db.models import Exists, OuterRef
from django.db.models.functions import Coalesce

from .models import Contribution, Participation, WithdrawalHold
from .permissions import dictionaries_for


# Match the defensive depth limit used by lexicon.image_family_roots. Unknown or
# broken provenance earns no credit rather than guessing an original contributor.
MAX_COPY_DEPTH = 32
IMAGE_FIELDS = (
    'pk', 'kind', 'status', 'shared_from_id', 'author_id', 'controlled_by_id',
    'author__username', 'controlled_by__username', 'provenance', 'file_path',
    'entry__dictionary__personal', 'held', 'departed',
)


def _images():
    departed = Participation.objects.filter(dictionary_id=OuterRef('entry__dictionary_id'),
        user_id=Coalesce(OuterRef('controlled_by_id'), OuterRef('author_id')), withdrawn=True)
    return Contribution.objects.annotate(
        held=Exists(WithdrawalHold.objects.filter(contribution_id=OuterRef('pk'))),
        departed=Exists(departed),
    )


def _human(row):
    source = row['provenance']
    return isinstance(source, dict) and source.get('origin', '') in ('', 'human') and (
        source.get('role') != 'dictionary_style' and not source.get('source_style_id'))


def _shared(row):
    # Moderation/archiving of an original is local to that dictionary. An
    # independently accepted copy may still count, even when the original is
    # pending, superseded or hidden. Withdrawal/custody always wins, however.
    return not (row['entry__dictionary__personal'] or row['held'] or row['departed'] or
                row['status'] in {'withdrawn', 'removed'})


def image_ladder(user):
    """Return rank/username/count/author_id rows, restricted to this member's view.

    A family counts once if an accepted instance is available in any non-hidden
    dictionary the viewer can currently open as a member. The root's custodian
    (controlled_by, falling back to author) receives credit, including delegated
    uploads. Anonymous/public browsing never supplies contributor identities.
    ``previous_revision`` and matching filenames are not evidence of image reuse.
    """
    if not user.is_authenticated:
        return []
    candidates = list(_images().filter(
        entry__dictionary__in=dictionaries_for(user).filter(hidden=False),
        entry__archived=False, kind='image', status='accepted', held=False, departed=False,
    ).exclude(file_path='').order_by('pk').values(*IMAGE_FIELDS))
    records = {row['pk']: row for row in candidates}
    frontier = {row['shared_from_id'] for row in candidates if row['shared_from_id']} - records.keys()
    # One query per ancestry layer for all images, rather than a separate lazy
    # ORM lookup for every picture/copy. Never read media files or compare pixels.
    for _ in range(MAX_COPY_DEPTH):
        if not frontier:
            break
        ancestors = list(_images().filter(pk__in=frontier).order_by('pk').values(*IMAGE_FIELDS))
        records.update({row['pk']: row for row in ancestors})
        frontier = {row['shared_from_id'] for row in ancestors if row['shared_from_id']} - records.keys()

    roots = {}
    for candidate in candidates:
        row, seen = candidate, set()
        while row['pk'] not in seen and _shared(row) and _human(row):
            seen.add(row['pk'])
            if not row['shared_from_id']:
                roots[row['pk']] = row
                break
            parent = records.get(row['shared_from_id'])
            # shared_from also links generated pictures to their style. Those
            # dependencies are not copies of a human photograph.
            if not parent or parent['kind'] != 'image' or len(seen) > MAX_COPY_DEPTH:
                break
            row = parent

    counts = Counter((row['controlled_by_id'] or row['author_id']) for row in roots.values())
    names = {(row['controlled_by_id'] or row['author_id']):
             (row['controlled_by__username'] if row['controlled_by_id'] else row['author__username'])
             for row in roots.values()}
    ordered = sorted(counts, key=lambda pk: (-counts[pk], names[pk].casefold(), names[pk], pk))
    ladder, previous, rank = [], None, 0
    for position, author_id in enumerate(ordered, 1):
        if counts[author_id] != previous:
            rank = position
        ladder.append({'rank': rank, 'username': names[author_id], 'count': counts[author_id],
                       'author_id': author_id})
        previous = counts[author_id]
    return ladder
