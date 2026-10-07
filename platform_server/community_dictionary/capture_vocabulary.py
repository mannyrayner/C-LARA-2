"""MWE guidance shared with C-LARA's annotation prompts, and bounded editing.

The capture request already sees the sentence, translation and image together.
Adapt the existing MWE resources inside that request instead of running the full
segmentation/annotation pipeline (and its separate provider/charging lifecycle).
"""
import json
import re
from pipeline import annotation_prompts
from .tts import language_code

MAX_EDITED_WORDS = 12


def mwe_guidance(language):
    code = language_code(language) or 'default'
    root = annotation_prompts.default_prompts_root()
    rules = annotation_prompts.load_template('mwe', code, prompts_root=root)
    examples = []
    for example in annotation_prompts.load_fewshots('mwe', code, prompts_root=root)[:4]:
        output = example.get('output', {})
        if not isinstance(output, dict):
            continue
        expressions = (output.get('annotations') or {}).get('mwes', [])
        examples.append({'sentence': output.get('surface', ''),
                         'expressions': [m.get('tokens', []) for m in expressions]})
    return ('\nBefore selecting vocabulary, identify lexical multi-word expressions using the following '
            'C-LARA linguistic guidance. The examples describe linguistic units, not your output format.\n'
            + rules + '\nExamples: ' + json.dumps(examples, ensure_ascii=False) + '''
Adapt that analysis to the required picture_description schema: each selected MWE becomes ONE words item.
Prefer the complete dictionary form, including fixed particles and reflexive pronouns, over isolated components.
Do not also suggest its component words for the same occurrence. Do not group ordinary compositional noun phrases.
Swedish: Katten sträcker ut sig på soffan -> sträcka ut sig (stretch out), NOT sträcka and ut separately.
Swedish: Katten sträcker långsamt ut sig -> surface "sträcker … ut sig", lemma "sträcka ut sig".
German: Der Mann zieht seine Jacke an -> surface "zieht … an", lemma "anziehen".
For discontinuous expressions, join exact sentence spans in their original order with " … ".
The lemma can have a different word order. Otherwise surface must be an exact whole-word span of the sentence.
Return only the picture_description schema; do not return token annotations or MWE analysis fields.
''')


def aligned_surface(surface, sentence):
    """Exact, ordered, whole-token spans; ellipsis represents omitted material."""
    if not surface:
        return False
    parts = re.split(r'\s*(?:…|\.{3})\s*', surface)
    cursor = 0
    for part in parts:
        if not part:
            return False
        pattern = (r'(?<!\w)' if part[0].isalnum() else '') + re.escape(part)
        pattern += r'(?!\w)' if part[-1].isalnum() else ''
        match = re.search(pattern, sentence[cursor:])
        if not match:
            return False
        cursor += match.end()
    return True
