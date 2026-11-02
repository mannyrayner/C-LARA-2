# Compare Google and OpenAI word audio

Open **Tools → Compare word audio providers** in a dictionary you own, using a
site-administrator account. The comparison now supports configured Google voices
for all app languages that Google supports. See [Google word audio](community-google-word-audio.md)
for the current installation, voice selection and reversible batch conversion.
The original French/Swedish pilot procedure is retained below.
It generates private experimental audio only. Existing sentence, lemma, form
and human recordings are unchanged. Provider defaults and bulk conversion are now optional, separately approved operations; the older homograph experiment and repair tool still work.

## Laptop installation and first trial

For the original comparison-only release there were no migrations or new dependencies;
**the newer provider/batch release requires migration 0028 and its separate runbook**.
For the comparison-only installation:
`google-cloud-texttospeech` is already in the project's requirements. Start a
**new** `Install Community Dictionaries on laptop` workflow on `main` in
`mannyrayner/clara-deployment-control`; leave the Windows runner listening.
Do not rerun an older workflow or any schema-preparation helper.

Use the same Windows account in which the standalone Google ADC probe worked.
No new key needs to be pasted into the app. The web process and its worker need
access to that account's gcloud application-default credentials.

1. Open a French dictionary, then **Tools → Compare word audio providers**.
2. Click **Check Google access (no audio)**. This lists available voices; it does
   not synthesize anything. An access failure displays a bounded diagnostic,
   without tokens or credential contents.
3. For the first run, choose **Choose items manually below**, expand **Manual
   item selection**, select a few entries, and keep **1** take per method.
4. Click **Estimate experiment**. Inspect the selected words and the combined
   cost/allowance before approving. Estimation does not contact either provider.
5. Approve generation. Each French item produces three fresh clips: current
   OpenAI, `fr-FR-Wavenet-F`, and `fr-FR-Neural2-F`. Swedish produces two:
   current OpenAI and `sv-SE-Wavenet-F`. The OpenAI voice defaults to marin.
6. Refresh to see progress. At completion, listen to A/B/C (or A/B), choose
   Acceptable / Minor problem / Major problem / Cannot judge, and add notes.
   **Save ratings** keeps partial work; returning restores it. Save before
   leaving the page. No method identity or filenames reveal the allocation.
   Voices themselves may nevertheless be recognisable.
7. **Save and reveal methods** requires a rating for every usable clip. It shows
   method counts and paired comparisons: both acceptable, Google only, OpenAI
   only, neither, generation failure, or unscored. Later edits are marked.
8. Download **ratings (CSV)**. It records wording, meaning, sentence for forms,
   source IDs, sample selection and eligible population, provider, voice/model,
   method, take, rating/note, failure, attempts, recipe and estimated cost.

## Larger comparison

Use separate runs for **Random vocabulary sample**, **English homographs**,
**Multi-word expressions**, and **Sentence forms**, or manual selection. The
random sample defaults to 30 and supports up to 60 items, sampled without
replacement; if fewer are available, all are used. The quote fixes the sample,
so submitting/approving it again cannot silently select different items.
Identical wording, meaning and word/form type is represented once, using the
oldest eligible contribution. Distinct senses are retained. This is a sample of
unique eligible lexical items, not a frequency-weighted sample of occurrences.
Homograph challenges exclude expressions that merely contain an English spelling.

Start with one take; optional two or three takes investigate repeatability.
A run is capped at 450 recordings so its rating form stays within Django's
normal request-field limit. Repeated takes are not independent lexical items.
Keep deliberately difficult samples separate from random ones when reporting
quality. Do not generalise from one voice, language, speaker or small sample.

OpenAI uses the existing production policy: native carrier/extraction for
eligible expressions, and direct lexical synthesis with conditional homograph
guidance otherwise. Its normal bounded silence/extraction retries are retained
and recorded. Google receives the bare text and explicit locale, with no carrier,
phonemes, meaning or automatic synthesis retries. Existing manually selected
recordings and human ratings are not sent to either provider. Thus this compares
usable generation pipelines, not matched model architectures or equal numbers
of underlying API requests. It also tests whether a bare word is insufficient
for genuine within-language pronunciation ambiguity.

## Credentials, payment and recovery

The pilot deliberately uses explicit **user ADC**, not `google.auth.default()`.
It ignores legacy `GOOGLE_APPLICATION_CREDENTIALS` and `GOOGLE_CREDENTIALS_JSON`.
User ADC must have the configured quota project. AWS can instead use the explicit,
validated federation configuration described in the new runbook.
Do not copy old service-account keys, or upload user ADC to the repository.

Windows enables this administrator pilot by default. Optional host configuration:

- `C_LARA_GOOGLE_TTS_ENABLED`: `1` enables; `0` disables (Linux default).
- `C_LARA_GOOGLE_TTS_PROJECT`: defaults to `community-dictionaries-tts`.
- `C_LARA_GOOGLE_TTS_ADC_FILE`: optional explicit path to the user ADC file.
  Otherwise use `CLOUDSDK_CONFIG`, Windows `%APPDATA%/gcloud`, or Linux
  `~/.config/gcloud` and `application_default_credentials.json`.

Google's listed rates checked 2 November 2026 are USD 4/million characters for
WaveNet and USD 16/million for Neural2, before free allowances and tax:
<https://cloud.google.com/text-to-speech/pricing>.
Voice coverage: <https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types>.
The quote pins these rates, the project, voice mapping and recipes. Changed
configuration stops new calls until a fresh quote is made. Provider invoices
remain authoritative; the UI estimate is not a provider spending cap.

Google bills the configured Cloud project. With C-LARA credit payment, combined
estimated usage settles against the existing reservation. With a personal OpenAI
key, OpenAI bills that key and Google still bills the configured Google project;
it is not covered by the personal OpenAI key. This is why the initial pilot is
restricted to administrator owners. Free-tier savings are not inferred from the
server's account. Usage rows correctly distinguish Google from OpenAI.

Each clip has a durable claim. Duplicate task delivery cannot regenerate it.
Network/API errors are not automatically replayed. Other planned clips can
complete after a failed one. **Resume interrupted work** can abandon requests
older than 15 minutes and continue unstarted clips; uncertain calls receive the
approved allowance estimate. Cancellation and source withdrawal retain cost
accounting but discard private content. Editing source text/sense or losing
access invalidates playback/export. Experimental files cannot be published
through generic language-port actions.

Do not deploy expecting laptop ADC to work on AWS. AWS authentication is a
separate next step; this release leaves Google generation disabled there by
default. In particular, do not copy personal refresh-token files to AWS as the
production solution. After annotation supports a provider change, configure an
appropriate server identity and then add reversible bulk regeneration.
