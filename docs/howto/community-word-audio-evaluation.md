# Independent English word-audio evaluation

This first cut adds **Evaluate → Compare English word audio**. It compares the
current OpenAI word-audio pipeline with Google WaveNet and Neural2, using newly
generated recordings shared by independent evaluators. It does not replace
dictionary recordings or change the dictionary's synthesis default.

## Install and smoke-test

No new migration, dependency, credential or service configuration is required.
Use the prepared release in the private deployment-control repository:

1. Run **Install Community Dictionaries on laptop** on `main`, with the existing
   laptop runner active. Wait for a successful receipt.
2. Open an English dictionary as its owner and go to **Evaluate**. Prepare a
   random study of **3–5 items** first. Creating an estimate makes no provider
   calls and reserves no credit. Google generation remains restricted to a site
   administrator who owns the dictionary and can authorise project charges.
3. Inspect the voices and allowance, then explicitly approve generation. This
   generates new audio and incurs the normal OpenAI/Google charges. Refresh uses
   saved progress counts rather than rendering every word. Unstarted work can
   resume; interrupted attempts are recorded as failures, not silently repeated.
4. When generation and accounting finish, choose **Freeze recordings and open
   evaluation**. Failed recordings remain in the denominator. The study never
   searches among multiple candidates for the best output.
5. Declare English reading/listening competence, dialect and experience through
   the existing language profile. Start a session, recording involvement,
   prior exposure and listening equipment, with consent.
6. Listen to one word at a time. Judge A/B/C pronunciation separately, then give
   a preference. Check saving, returning, ties and Cannot judge. A/B/C and item
   order are independently shuffled per evaluator and retained on return.
7. Optionally use a second test account to check independent judgments. Other
   participants' answers remain hidden. Once everyone has finished, the owner
   closes the set and receives summaries and JSON/CSV downloads. Closing is final;
   later edits cannot contaminate the blinded ratings.
8. If the laptop check is satisfactory, run **Accept laptop and deploy AWS**.
   Repeat the small smoke test before beginning the main annotation exercise.

Judging, pausing and downloading make no AI calls. Preparing/generating a study
is separate from judging it. No workflow is dispatched merely by committing the
code or updating the release request.

## Initial English protocol

Use a new study of **100 randomly sampled lexical items**, or all eligible items
if the dictionary has fewer. Each item receives one planned recording per
method. The sampling seed, eligible contribution IDs, actual selected sources,
source texts/meanings and recipe/voice/model identifiers are frozen. Repeated
occurrences with identical spelling, meaning and kind are deduplicated by the
existing provider sampler. Lemmas and sentence forms remain distinct units.

Random vocabulary is the primary cohort. A separate expressions-only or
forms-only study can stress challenging material, but must be reported separately;
pooling selected difficult words into the random sample changes the estimand.
No class-balancing or automatic picture holdout is performed in this release.

The English study supplements the existing voice catalogue with
`en-GB-Neural2-F` if no Neural2 selection is already configured. WaveNet uses
the existing configured/default English trial voice, normally `en-GB-Wavenet-F`.
Google lists these in its [supported voice catalogue](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types),
checked 3 November 2026. Access to the exact selected voices is checked before
approval. The study supplement does not alter existing comparison configurations.
The OpenAI voice is selected explicitly, defaulting to the normal pipeline voice.

This compares **specified voices and pipelines**, not all possible outputs of
three providers. OpenAI keeps its normal guidance/carrier and bounded-retry
strategy; Google uses plain text without automatic retries. Record the exact
configuration and generation date when reporting results. Accept legitimate
regional pronunciations; an accent difference is not automatically an error.

Recruit at least two independent evaluators with appropriate English competence.
Both evaluate the **same clips**, rather than regenerating audio for each person.
Avoid discussing cases until judgments are complete. Labels and other people's
ratings are hidden, but recognisable voices mean perceptual blinding cannot be
guaranteed. Involvement and prior exposure are recorded for interpretation.

## Two separate questions

**Correctness:** acceptable / minor pronunciation problem / major pronunciation
problem / cannot judge. Wrong sounds, word stress and missing or added material
belong here. A flat but correctly pronounced recording can be acceptable.

**Preference:** one preferred version / two or three tied / none suitable for
learning / cannot choose, with an optional explanation. A preference is not
proof that the other recordings are incorrect. If any provider fails, preferences
are retained as incomplete comparisons and excluded from the main three-way
preference totals. Failed generations are not counted as listener pronunciation
judgments or silently replaced.

Use the same equipment in a quiet setting where possible. Ratings are per
item/take; multiple ratings of a recording are not independent lexical samples.

## Results and exports

Only the owner can obtain results after closure. The JSON includes:

- Sample/cohort metadata, planned/frozen/available counts and unavailable totals.
- Per-method acceptable/minor/major/cannot/unsubmitted counts, correctness rates,
  distinct generation failures, paired correctness counts, exact agreement and
  ordinal Krippendorff alpha where overlapping ratings permit it.
- Sole and tied preferences for complete triplets; None suitable and Cannot
  choose; incomplete preferences separately.
- Individual pseudonymous rater judgments, comments, randomized labels, word/form
  and context, stable source IDs, model/voice/recipe identifiers, generation attempt
  counts, self-reported competence, involvement, equipment and prior exposure.

CSV has one row per rater × recording, with preference fields repeated for the
associated item. Do not count those repeated preference cells as new preference
votes. Formula-like text is escaped. JSON is the preferred complete analysis file;
it retains study-level counts even if no rater joined or no sources remain available.
Neither export includes audio bytes, storage paths, credentials or raw responses.

Summaries use scored judgments as denominators, not independent words. Exports
permit per-rater and paired analyses; pooled totals and agreement should be
reported alongside evaluator count and sampling scope. Undefined agreement is
not zero agreement. There is no automatic significance claim or power guarantee.

Every page, media request, rating and export rechecks access and live source
availability. Withdrawn or changed material is omitted without substituting new
items. Its ratings remain in the database but are not disclosed through exports.
Such omissions must be reported. This is the same privacy-first limitation as
existing dictionary evaluations.

## Development/evaluation separation

Decide the development picture subset before further lexical/MWE tuning. Keep
all copies and translated versions of a picture in one group, and put close
duplicates from the same scene together where practical. Freeze the evaluation
groups and do not inspect their output while tuning. Existing heavily reviewed
pictures are development material; fresh images make a stronger final holdout.
An English conversion of an inspected picture is not automatically unseen data.

This implementation supports the audio comparison; it does not partition images,
implement a new MWE policy, recruit participants, or establish a learning benefit.

## Implementation and offline validation

The versioned `word-audio-provider-study-v1` rubric uses existing EvaluationSet,
Item, Unit, Session, Rating and Progress tables. Immutable item snapshots link to
durable generation items. Correctness uses ordinary rating rows; per-rater order
and preference records are versioned JSON inside session metadata. Saving locks
the dictionary, set and session and checks the per-item revision. Closing uses
the existing set lock, so it serializes with concurrent saves.

Provider generation continues through existing quote approval, task claims,
accounting, recovery and source-withdrawal handling. Old owner-only reveal/media
routes cannot reveal a new study's clips. No application schema change is needed.

Run the focused tests with:

```bash
python manage.py test community_dictionary.tests.test_audio_evaluation \
  community_dictionary.tests.test_provider_comparison \
  community_dictionary.tests.test_evaluation
```

All provider calls in tests are mocked. A successful offline test run is not a
live pronunciation evaluation or proof of phone/browser audio behaviour.
