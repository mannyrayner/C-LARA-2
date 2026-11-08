"""Versioned learner-vocabulary policy, shared by capture and re-extraction.

These are model instructions, not a deterministic linguistic classifier.
Keep the annotation guide in docs/howto/community-word-extraction-policy.md aligned.
"""

VERSION = 'learner-vocabulary-v2'
MAX_WORDS = 12
MAX_OUTPUT_TOKENS = 4096

COMMON = '''
Apply learner-vocabulary policy v2 to the TARGET language, independently of how
many words its translation uses. PARSEME-style lexicalization/idiosyncrasy is the
baseline for MWEs; frequent co-occurrence or a one-word translation is not enough.

SELECTION: Cover the central entities, lexical actions, informative properties,
and useful spatial/temporal relations. Include every explicit cardinal quantity
in the sentence, preserving its value; a multiword numeral is one teaching item,
not a claim that the numeral is an idiom. Select at most 12 distinct lemma/sense
items. Twelve is a safety ceiling, not a target: do not pad a short sentence.
If the ceiling is reached, prioritize content nouns/verbs, quantities, properties
and meaningful relations over optional grammatical material. Do not omit a salient
noun while retaining its modifiers and less useful grammatical items.

FUNCTION WORDS: Normally omit standalone articles, pronouns, conjunctions,
grammatical auxiliaries and copulas. Preserve them inside a lexicalized expression
when required. Include a main verb with lexical meaning (e.g. possessive have);
do not confuse it with an auxiliary. Spatial/temporal adpositions used as useful
relations are eligible. Do not remove attached morphology or force English word
boundaries on another language. Follow that language's segmentation conventions.

GROUPING: Keep genuine lexical expressions, idiomatic verb-particle combinations
and established lexical compounds together. Leave productive descriptive phrases,
ordinary auxiliary + verb, copula + adjective/participle, and productive causative
or passive constructions compositional. An independently lexicalized expression
can be an exception. A state/adjective and the event of entering that state are
not interchangeable. Preserve normal written words/compounds; do not split them
merely to imitate the spacing of the translation.

HEADWORD AND SENSE: Use consistent dictionary forms appropriate to the language:
base verbs, citation forms of nouns/adjectives, and lexical plurals when required
by the intended sense. Keep the contextual sense and word class in the gloss.
Do not substitute a synonymous verb that is absent from the sentence. Do not
absorb ordinary auxiliaries into a lexical item's surface, even if its lemma is
correct. For a real separated expression, select only its lexical components in
sentence order, excluding variable complements; join exact spans with " … ".
Return the actual inflected surface separately from its dictionary lemma.

CONSISTENCY: Existing vocabulary is a reuse resource, not authority for grouping,
selection or an inappropriate sense. Reuse only an item whose canonical lemma AND
sense conform to this policy, copying its lemma and meaning exactly. Otherwise
return existing_id=0. Before returning, check quantities, core-word coverage,
overgrouping, surface boundaries and lemma/sense consistency. Do not output this
analysis or extra fields: use only the requested schema.
'''

LANGUAGE_NOTES = {
    'en': '''
English conventions: Normalize count nouns to singular and verbs to the base form,
but keep lexical plurals such as glasses (spectacles). Ordinary is sleeping ->
surface sleeping, lemma sleep; is hanging -> hanging, hang. For an adjectival state
such as a parked car / the car is parked, parked can be the adjective headword;
do not automatically replace it by the event verb park. Productive get + object +
past participle (gets his hair cut) is not a lexical get cut item: select cut and
hair, omitting grammatical get. Literal white house and wooden table are separate
items; in front of is a complete relational expression without its noun complement.
Explicit teaching exception: existential there is / there are / there was uses
canonical lemma there be, meaning il y a when the commenting language is French
(otherwise its equivalent). Surface is the actual there + finite be in the sentence;
do not emit bare be or locative there for that occurrence. There be is an abstract
headword, not a form to substitute into the sentence. This exception does not
extend to every copula or to other languages' existential constructions.
''',
    'fr': '''
French conventions: Ordinary est garé / est accroché is compositional. Select
garé / accroché for an adjectival state reading, or the appropriate verbal lemma
for a verbal/passive reading, without absorbing ordinary être into its surface.
Retain se and other clitics only when required by the lexical verb/expression;
do not confuse a state with an event (couché is not automatically se coucher).
Lexical constructions such as avoir faim are different from grammatical avoir.
Use normal French citation forms and fixed-expression boundaries, not literal
translations of English headwords or English there be conventions.
''',
    'sv': '''
Swedish conventions: Use normal Swedish citation forms, including infinitives
and appropriate noun/adjective base forms. Keep lexical particles and required
reflexives: sträcker långsamt ut sig -> surface sträcker … ut sig, lemma sträcka ut sig.
Ordinary är + adjective/participle does not automatically form a lexical unit.
Preserve Swedish compounds as words; do not split them to match a translation.
''',
}


def guidance(code):
    return COMMON + LANGUAGE_NOTES.get(code, '')
