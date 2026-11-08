# Community Dictionaries: word-extraction policy v2

This is the working policy for the second extraction experiment, revised after
the first 20-page English/French pilot. It applies to **the language being
learned**, with contextual glosses in the dictionary's explanation language.
It guides both new picture descriptions and vocabulary rebuilt from accepted
sentences. It is a development policy, not a gold-standard PARSEME corpus guide.

## What to select

| Material | Default treatment |
| --- | --- |
| Central entities, lexical actions, informative properties | Include. Prioritise important content over optional grammatical material. |
| Explicit cardinal quantities | Include consistently. A written multiword numeral can be one teaching item; preserve the value. This is a teaching convention, not a claim of idiomaticity. |
| Spatial and temporal relations | Include useful relational words/expressions in their contextual senses. |
| Ordinary standalone articles, pronouns, conjunctions | Omit. Include them when they are required components of a lexical expression. |
| Ordinary auxiliaries and copulas | Omit as standalone teaching items and exclude from other lexical items' source spans. This does not exclude main verbs with lexical meaning, such as possessive *have*. |

The generator can return **up to 12 distinct headword/sense items**, matching the
existing editing limit. This replaces the six-item ceiling. Twelve is a safety
bound, not a target: do not pad a short sentence. If a sentence exceeds it,
prioritise central nouns/lexical verbs, quantities, informative properties and
meaningful relations. Do not select several modifiers and low-value grammatical
items while omitting their salient content noun. Repeated uses of the same
headword and sense need not create duplicate dictionary entries.

## What belongs together

Use [PARSEME 2.0](https://parsemefr.lis-lab.fr/parseme-st-guidelines/2.0/) as the
reference for lexicalisation and linguistic idiosyncrasy. Meaningful restrictions
on substitution or grammatical flexibility support lexical unity. Frequency,
adjacency, or translation by a single word do not establish it.

- Preserve lexical expressions, idiomatic phrasal verbs and established compounds.
  For example, *look after* in its care-for sense and *in front of* are whole units.
- Leave ordinary descriptive phrases such as literal *white house* and *wooden
  table* compositional. Productive count/material phrases such as literal *ball
  of yarn* are not automatically lexical MWEs because their French translation
  happens to be a single word.
- Ordinary auxiliary + verb, copula + adjective/participle, passive and productive
  causative constructions are compositional. Thus *is sleeping* contributes
  *sleep*, with surface *sleeping*; productive *get + object + past participle*
  does not make the two verbs a lexical MWE.
- This is a default, not a ban on lexicalised constructions containing auxiliaries
  or copulas. Check the particular expression and sense.
- Preserve normal written words and compounds. English hyphenation, German closed
  compounds and Japanese/Chinese segmentation must not be made to imitate the
  explanation language. These learner-unit choices are not all formal MWE labels.

## Headwords, senses and source boundaries

Use the language's normal citation forms: English count nouns normally singular,
verbs normally base form, and lexical plurals retained when required (*glasses*
meaning spectacles). Keep the actual sentence form separately. Choose a consistent
headword for comparable occurrences, without merging distinct senses.

Distinguish an adjective/state from a verbal event when the context supports that
distinction. *Parked* can be an adjective headword for a car's state; it is not
automatically the event verb *park*. French *est garé* and *est accroché* do not
become lexical units just because they contain *être*. A passive/event reading
may instead require the verbal lemma. Likewise, *couché* is not automatically
*se coucher*, an event of entering a position or going to bed.

The source span contains the lexical unit's actual components, including required
particles/reflexives, but not ordinary auxiliaries or variable complements.
For genuinely discontinuous expressions, retain exact components in sentence
order separated by ` … `: Swedish *sträcker långsamt ut sig* can give
*sträcker … ut sig* / *sträcka ut sig*; German *zieht seine Jacke an* can give
*zieht … an* / *anziehen*. Discontinuity by itself does not prove lexicalisation.
Korean particles/endings remain in the written surface form; Japanese/Chinese
lexical units need not be bounded by spaces.

French glosses (or other explanation-language glosses) identify the contextual
sense and word class, rather than listing unrelated meanings. Do not replace a
source word with a synonym that is absent from the sentence. Minor stylistic
preferences in a gloss alone are outside an extraction-only evaluation, unless
they reveal a wrong sense. Existing dictionary entries are reuse candidates,
not authority for an obsolete grouping or sense; reuse requires the canonical
headword and sense both to fit the current policy.

### Explicit English existential convention

Treat existential *there is / there are / there was* as one teaching unit, with
canonical headword **there be** and the actual finite construction as its surface.
The English/French gloss is **il y a**. *There be* is an abstract dictionary
headword, not a form to insert into the example sentence. Do not alternate between
bare *be* and the whole construction for the same use. This convention does not
apply to locative *there*, ordinary copulas, or every other language's existential
construction. Other languages keep their own citation forms and lexical analysis.

This supersedes v1's provisional preference for *there is* as the headword.
The original pilot's ratings and comments remain unchanged. A presentation
preference should not be reported as a new linguistic error without an agreed
convention.

## How we annotate the second experiment

Select **Extracted vocabulary** only. Judge the complete displayed list against
this policy; this is rating an existing extraction, not making an independent
span annotation. Use these comments to distinguish problems:

| Diagnostic label | What it covers |
| --- | --- |
| Selection | Important omissions, inconsistent quantities, inappropriate grammatical items or priorities. |
| Grouping | Missing lexical units or overgrouped productive combinations. |
| Headword/sense | Wrong or inconsistent canonical form, word class or contextual meaning. |
| Boundary | Wrong source span despite a suitable headword/sense. |

**Acceptable** means no necessary correction under this policy. **Minor problem**
means a local correction improves an otherwise usable list. **Major problem**
means a materially misleading sense, loss of an essential unit, extensive
omission/overgrouping or comparable serious defect. Use **Cannot judge** when
context or policy does not support a confident decision. Base severity on learner
impact, not the number of technical deviations; a small boundary issue does not
automatically make the lexical item wrong. Mention unresolved policy in a comment
even when accepting the page.

Rate independently before comparing comments. Identify assistant ratings explicitly
as AI judgments; the current normal-user form stores both under its default
evaluator kind, so separate the assistant account in analysis. Twenty development
items do not establish population accuracy. Changing both policy and prompts
means score changes cannot be attributed solely to model performance.

## Running the follow-up

Installation changes prompts and future processing; it does not rewrite saved
content or start paid calls. Use the normal vocabulary-from-accepted-sentences
workflow to estimate, approve, regenerate and review vocabulary. Existing
sentences/translations remain authoritative. Recipes are versioned; old pending
vocabulary estimates/previews must be replaced with a fresh estimate.

Keep the first evaluation closed and its CSV. After the desired vocabulary
revision, open that evaluation's overview and choose **Repeat these sentence
pages**. Give the follow-up a new name, for example **Word extraction pilot 2 —
policy v2**, so the original set's v1 title does not describe the new round.
It makes no AI calls: it freezes the same sentence entry IDs in the same
order with their current vocabulary, links the two sets, and starts with no
ratings. Missing/withdrawn original pages cause an explicit refusal; no substitute
is silently drawn. Evaluate this new set under v2 with hidden independent ratings.
It does not itself regenerate vocabulary. No new database migration is required.
