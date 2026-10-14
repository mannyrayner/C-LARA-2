# Human evaluation infrastructure — 14 October 2026

## Motivation and status

Manny reports the publication/About material installed. The public About page was
also inspected through the browser without authentication: title, authors, both
publication links, Vibe Research and contributor listing were visible.

Manny proposes systematic content evaluation, language competence reporting,
inter-rater statistics and later AI judge comparisons. He authorises a first
implementation after discussion of a human-first workflow and versioned samples.
This increment supports GOAL-1, GOAL-3 and GOAL-5. It does not establish learning
gains or replace independent community trials.

## Delivered locally

- Private per-language reading/listening self-reports, varieties and experience,
  accessible through Community Dictionaries Profile.
- Evaluate tab: owner-created random/all accepted sentence or word samples;
  reproducible population/seed/order; snapshots of exact content components.
- Seven dimensions; three severity levels plus abstention; missing assets reported
  separately; no default scores. Save-and-next, skip/revisit and resume across devices.
- Session-specific competence/involvement/consent records. Competence gates are
  task-specific and explicitly self-reported.
- Results hidden while collecting, including from the owner. Final owner closure
  releases owner-only statistics and CSV, preventing subsequent ratings.
- Exact pairwise agreement and ordinal Krippendorff alpha on overlapping human
  ratings, with denominator/undefined-result explanations. Shared word translations
  and audio versions are offered once per set, preserving the first sampled context.
- Live access, withdrawal, private relocation, archival and source-content checks
  for pages, media, reports and exports. Departed evaluators' ratings withheld.
- Optional visitor evaluation per set; requires login and live public browsing.
  It grants no dictionary edit access. Public listing does not expose competences.
- Additive migration 0024; no existing-data rewrite or provider/queue changes.

AI evaluator kind/metadata are represented in the schema, but no AI judge runner,
majority voting or billing is implemented. The human UI cannot create AI records;
human reports exclude nonhuman records.

## Validation

On Linux, Python 3.12, Django 5.2.17 and disposable SQLite:

- Django system check passed; makemigrations --check --dry-run found no changes.
- Focused evaluation/discovery/public-browsing suite: 81 tests passed.
- Full Community Dictionaries + admin-tools/email-reset/profile suite: 685 tests
  passed in 141.5 seconds (including the first 31 evaluation tests).
- Three additional evaluation edge checks were then added for departed evaluators,
  separation of AI/human records, and bounded report queries. All 34 evaluation
  tests passed. The expected combined suite now contains 688 tests.
- Regression cases include CSRF, anonymous/private/cross-dictionary access,
  source withdrawal/holds/private relocation, source edits, superseded visitor
  media, stale submissions, atomic page saves, sampling, sense-based deduplication,
  standalone words, absent media, abstentions, CSV/XSS escaping and closed-set rules.
- Agreement calculations checked against worked ordinal examples, perfect and
  negative agreement, uneven rater counts, constant labels and missing judgements.
- Accepted-content graph uses at most five queries; report construction at most
  twelve in the scaled fixture. No new workflow computations run on the normal
  member dictionary home page.
- Five fixture pages rendered through Django, including evaluation and results.
  A cloud-browser attempt could not reach the local preview server, so no visual
  browser or physical-phone acceptance is claimed. Laptop/phone inspection remains
  part of the supplied acceptance runbook.

Synthetic fixtures only; no paid calls, production data, actual evaluator ratings,
remote deployment or Git push. The tests exercise expected provider/mail failures
in unrelated regression cases; their final status was OK.

## Limits and next evidence

Try a two-page laptop set with two accounts first. Then deploy and ask suitably
qualified volunteers to rate a common modest sample, agreeing use of results and
credit before publication. Existing initial dictionaries may include human edits;
provenance indicators do not prove a clean automatic-generation baseline.

The first report is judgement-weighted, with raw per-rater data available for a
prespecified analysis. Confidence intervals, proficiency weighting, adjudication,
manual diagnostic-set selection and AI comparisons are deferred. Source withdrawal
can reduce sample coverage and is disclosed. A closed set is not reopened after
results are seen. Nothing here demonstrates long-term autonomous maintenance.

## Laptop feedback and presentation follow-up

Manny subsequently reports installing the patch on his laptop and completing the
recommended two-entry evaluation. Nearly everything worked; he requested that each
question repeat its relevant material immediately above the judgement, and reported
an incomplete competence summary after declaring fluent reading/listening in both
Swedish and English.

Inspection confirmed that the start-page template omitted commenting-language
listening and displayed numeric levels. The follow-up now shows the full labels
for both skills in both languages. Existing sessions show their saved competence
snapshot on the overview and session pages; later Profile changes do not rewrite it.
Missing self-reports say "Not declared" rather than implying a declaration of inability.

Each question now includes its own relevant picture, sentence, translation, word
or audio control. The complete lemma/expression list is inside the vocabulary
question, immediately above its prompt and rating. This is a presentation change:
no new migration, provider calls, changes to scores, or alteration of sampling or
agreement calculations.

All 37 focused evaluation tests pass, including rendered-context checks for all
seven dimensions, both language/skill pairs, absent declarations and saved versus
current competence summaries. This follow-up has not yet been accepted on the
laptop or deployed to AWS. A local screenshot attempt failed while preparing the
browser binary; no visual phone acceptance is claimed. Manny plans to retest, then
deploy and run a larger evaluation. No independent empirical results are reported.
