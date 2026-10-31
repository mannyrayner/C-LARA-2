"""Contextual forms are attributed contributions, not extra dictionary entries.

The sentence-word relation identifies the occurrence. Dependencies retain the
normal withdrawal/restore semantics; exact input revisions prevent stale use.
No provider calls or writes happen during presentation.
"""
import re
from .models import Contribution, ContributionDependency, SentenceWord
from .capture_vocabulary import aligned_surface, identity
from .services import Conflict

VERSION = 'sentence-forms-1'
INSTRUCTIONS = '''For each vocabulary item also return form_meaning: a short translation of
surface AS USED IN THIS SENTENCE in explanation_language. Preserve its tense,
person, number, definiteness and intended sense where relevant. E.g. Italian
vanno -> aller (lemma meaning), vont (French form_meaning). This is a contextual
gloss, not a grammar lesson or a translation of the entire sentence. Keep lemma
and its dictionary meaning unchanged. For separated expressions interpret all
their parts together. Do not invent an occurrence or translate source-language
lemmas in place of the actual target-language forms.'''


def different(surface, lemma):
    return bool(surface and identity(surface, '') != identity(lemma, ''))


def separated(surface):
    return bool(re.search(r'…|\.{3}', surface))


def links(entry):
    from .capture import sentence_links
    return sentence_links(entry.dictionary).filter(sentence_text=entry.current_text).select_related(
        'sentence_text__entry__dictionary', 'word_entry__dictionary', 'word_entry__current_meaning', 'word_text')


def basis(link):
    sentence, word = link.sentence_text.entry, link.word_entry
    return {'sentence': link.sentence_text_id, 'sentence_meaning': sentence.current_meaning_id,
        'word_entry': word.pk, 'word_text': link.word_text_id, 'word_meaning': word.current_meaning_id,
        'surface': link.surface, 'language': sentence.dictionary.language,
        'explanation_language': sentence.dictionary.explanation_language}


def current(part):
    if part.kind != 'form' or part.status != 'accepted' or part.entry.archived:
        return None
    source = part.provenance.get('form_basis', {})
    link = links(part.entry).filter(word_entry_id=source.get('word_entry')).first()
    if not link or basis(link) != source or part.word != link.surface:
        return None
    ids = [pk for name, pk in source.items() if name in {
        'sentence', 'sentence_meaning', 'word_text', 'word_meaning'} and pk]
    from .public_browsing import contributions
    # Same accepted/contributor/withdrawal checks for private and public readers.
    if contributions(part.entry.dictionary).filter(pk__in=[part.pk, *ids]).distinct().count() != len(set([part.pk, *ids])):
        return None
    return link


def find(link, parts=None):
    candidates = parts if parts is not None else link.sentence_text.entry.contributions.filter(kind='form', status='accepted')
    wanted = basis(link)
    return next((p for p in candidates if p.kind == 'form' and p.status == 'accepted'
                 and p.provenance.get('form_basis') == wanted and current(p)), None)


def audio(part):
    if not current(part):
        return None
    return part.entry.contributions.filter(kind='audio', status='accepted',
        shared_from=part, provenance__sentence_form=part.pk).exclude(file_path='').first()


def audio_current(clip):
    if not clip.shared_from_id or clip.provenance.get('sentence_form') != clip.shared_from_id:
        return False
    part = clip.shared_from
    return bool(part.entry_id == clip.entry_id and current(part) and
        clip.provenance.get('source_text') == part.word and
        clip.provenance.get('language') == part.entry.dictionary.language)


def publish(link, meaning, user, provenance, *, replace=None):
    """Caller holds dictionary lock. Reusing a result never changes attribution."""
    meaning = str(meaning or '').strip()
    if not different(link.surface, link.word_text.word) or not meaning:
        return None
    if len(meaning) > 300 or not aligned_surface(link.surface, link.sentence_text.word):
        raise Conflict('Check the form and its translation against the sentence.')
    old = find(link)
    if old and replace is None:
        return old
    if replace is not None and (not old or old.pk != replace):
        raise Conflict('This sentence form changed. Reload before editing.')
    source = basis(link)
    part = Contribution.objects.create(entry=link.sentence_text.entry, author=user,
        controlled_by_id=(old.controlled_by_id or old.author_id) if old else user.pk,
        kind='form', status='accepted', word=link.surface, meaning=meaning,
        shared_from=link.sentence_text, previous_revision=old,
        provenance={**provenance, 'form_recipe': VERSION, 'form_basis': source})
    ids = [source[k] for k in ('sentence', 'sentence_meaning', 'word_text', 'word_meaning') if source[k]]
    ContributionDependency.objects.bulk_create([
        ContributionDependency(source_id=pk, derived=part) for pk in set(ids)])
    if old:
        old.status = 'superseded'; old.save(update_fields=['status'])
    return part


def presentation(link, *, public=False):
    if not different(link.surface, link.word_text.word):
        return {}
    part = find(link)
    recording = audio(part) if part and not separated(link.surface) else None
    in_sentence = separated(link.surface)
    if in_sentence:
        from .lexicon import recordings
        available = recordings(link.sentence_text.entry, link.sentence_text.entry.dictionary)
        recording = available[0] if available else None
    result = {'surface': link.surface, 'meaning': part.meaning if part else '',
        'id': part.pk if part else None, 'link_id': link.pk, 'in_sentence': in_sentence}
    if public:
        from .public_browsing import media_row, contributions
        if recording and not contributions(link.sentence_text.entry.dictionary).filter(pk=recording.pk).exists():
            recording = None
        result['audio'] = media_row(recording) if recording else None
    else:
        result['audio'] = recording
    return result


def capture_speech(study, entry):
    from .models import CaptureSpeech
    for link in links(entry):
        part = find(link)
        if part and not separated(part.word) and not audio(part):
            CaptureSpeech.objects.get_or_create(capture=study, kind='form', text_id=part.pk,
                defaults={'entry': entry, 'text': part.word, 'meaning': part.meaning,
                          'language': study.language, 'meaning_id': part.pk})


def port_speech(run, item, entry):
    from .models import PortSpeech
    for link in links(entry):
        part = find(link)
        if part and not separated(part.word) and not audio(part):
            PortSpeech.objects.get_or_create(run=run, entry=entry, text=part,
                defaults={'item': item, 'meaning': part})


def publish_audio(part, user, prepared, paths, provenance):
    if not current(part):
        raise Conflict('The form or its sentence changed. Existing recordings have been kept.')
    existing = audio(part)
    if existing:
        return existing
    from .storage import write_upload
    return Contribution.objects.create(entry=part.entry, author=user, kind='audio', status='accepted',
        shared_from=part, provenance={**provenance, 'origin': 'synthetic',
            'sentence_form': part.pk, 'source_text': part.word,
            'language': part.entry.dictionary.language},
        **write_upload(prepared, part.entry.dictionary_id, paths))
