# Review a sample of word pictures

An owner or co-owner opens **Browse → Words → Review a sample of word pictures**.
The evaluation form selects **Word pictures** and a random sample of 20 by
default. Change the size or choose all eligible words, then create the set and
share its link. This draws from the whole dictionary, independently of the browse
page's search, category or pagination. Creating and completing a set makes no AI
calls and changes no pictures or exercise settings.

All evaluators see the same frozen sample. Each word has its currently displayed
dedicated picture and intended meaning. The four independently selectable aspects
are meaning, clarity/style, suitability as a flashcard clue, and cultural fit for
the intended learners. Each uses Acceptable / Minor problem / Major problem /
Cannot judge, with optional comments. A good illustration may be a poor clue.
Judgements concern suitability; they do not establish learning gains.

The population includes current accepted dedicated pictures marked as either
clues or illustrations, including uploaded replacements. It excludes hidden,
withdrawn, missing and outdated pictures and No simple picture symbols. It does
not substitute sentence photographs. The sample therefore estimates quality of
the visible word pictures, not the proportion of all words that can be pictured.
Its seed, population and order are retained. This feature does not generate a
fresh random sample for each evaluator.

Evaluators sign in, report confident reading of the dictionary language and
consent to sharing ratings and relevant competence information with the owner.
Members can participate; signed-in visitors require the owner's explicit
visitor option and continuing public browsing. Use Cannot judge for unfamiliar
meanings or cultural contexts. Sessions can be resumed. No ratings are
preselected, and peers' ratings are hidden. The owner closes collection before
viewing summaries, agreement statistics, comments or CSV.

The separate `community-word-pictures-v1` rubric uses existing word-scope JSON
storage; no schema migration is needed. Existing evaluations retain their
original projection and dimensions. New ratings stop when the sampled text,
meaning or picture changes; unrelated audio changes do not stop image review.
Earlier ratings retain the original picture ID and fingerprint. Withdrawal
withholds affected items, media and results. CSV adds image contribution ID,
origin and model to the existing reproducible sample/anonymous-rater export.
Generation prompts, private job details and account names are not exposed.
