# Compare homograph word audio

An owner-only **Tools → Compare homograph audio** experiment compares fresh
recordings from two existing strategies:

- Direct lexical TTS with AI-generated pronunciation guidance, including the
  target language and the selected word's meaning.
- A short native-language carrier phrase, followed by silence-based extraction
  of the central word. This condition does not also request pronunciation hints.

The same voice, text, meaning selection and TTS model are used across the pair.
The carrier condition deliberately tests the existing native carrier strategy;
it does not receive the meaning as an additional instruction. This distinction
is retained in the export and should be considered when interpreting results.
Ordinary dictionary TTS and the MWE regeneration tool keep their existing policy.
No experimental recording replaces or becomes a dictionary contribution.

## Using the experiment

1. Open **Tools → Compare homograph audio** in a dictionary you own.
2. Select up to 20 accepted words or current sentence forms whose spelling
   overlaps English. French, Swedish, German, Italian and Icelandic are supported.
   Select **court**, **repose** and **queue** if they are present, or other examples
   relevant to the dictionary. A contextual form and a lemma are separate choices.
3. Choose a voice and one to three takes per method; the default is two.
4. Request the estimate, then explicitly approve the displayed allowance and
   permission to send the selected text/meanings to OpenAI. Nothing is generated
   or reserved by the estimate alone. Insufficient C-LARA credit blocks approval.
5. Leave processing in the background if desired. Return through Tools and
   refresh progress. The listening table becomes available when the run finishes.
6. Listen to each A/B recording and choose Acceptable, Minor problem, Major
   problem or Cannot judge. Add notes, including English pronunciation, unusual
   stress, exaggerated prosody, clipping or uncertainty as appropriate. Save at
   any point. Leaving with unsaved ratings produces the browser's warning.
7. After rating every usable recording, choose **Save and reveal methods**.
   Method names and per-method counts appear. Carrier clips also offer their
   full final completed recording, so pronunciation and extraction problems can
   be distinguished. Later rating changes are marked as such in the export.
8. Download the UTF-8 CSV for comparison. It includes exact text/sense/context,
   source identifiers, take, method, rating, notes, generation outcome, attempts,
   model/recipe identifiers and cost estimates. Failed clips remain visible in
   the results; they are not silently replaced with a different method.

A/B order is independently shuffled for each word/take. Hiding method names
reduces expectation effects but cannot guarantee blinding: the sound itself may
reveal a method. These are small practical comparisons, not a claim of established
pronunciation accuracy. Listening is still needed; the software tests only
establish correct routing, accounting and extraction mechanics.

## Cost, privacy and recovery

Existing batch records and the credit ledger are reused without a database
migration. Estimates use the application's existing prices and duration
assumptions; they are neither provider invoices nor hard provider spending caps.
Personal keys are billed directly, and the app cannot inspect their available
balance. Normal credit reservations are settled automatically after generation,
without waiting for human ratings.

A durable claim precedes each clip. Carrier extraction permits at most five
completed attempts. Silence/ambiguous extraction can trigger those retries;
unknown network/API outcomes are not automatically replayed. Resume can redeliver
unclaimed work and, after 15 minutes, mark abandoned requests as failed with
conservative unknown-cost accounting. Cancelling discards the experiment, including
its private audio; an already-running request may still cost money. Resume also
finishes accounting for abandoned claims after cancellation.

Only the experiment's creator, while still the dictionary owner, can view or play
its results. Existing images and recordings are not sent to the provider. Source
revision, permission and withdrawal checks occur before requests and before files
are stored or served. Withdrawal clears the experimental snapshots/results and
schedules deletion of experimental files. Editing a source makes its old experiment
inaccessible. The experiment does not modify frozen dictionary evaluations.

## Installation and testing

This is a code-only update, with no migration, dependency installation or schema
preparation helper. Use a **new** `Install Community Dictionaries on laptop`
workflow on `main` in the private deployment-control repository. Do not rerun an
old workflow, manually reset Git, or rerun earlier schema helpers.

On the laptop, first check that the Tools link opens and offers the expected
choices. A three-word, two-take comparison creates twelve clips. Approve its
estimate only when ready to incur the shown cost. Test saving partial ratings,
returning to them, revealing methods and downloading the CSV; verify existing
entry recordings are unchanged. Test the mobile layout too if convenient.

After laptop acceptance, use the normal **Accept laptop and deploy AWS** workflow
with the successful laptop run. Exact installed-commit checks remain in force. If
a host changed outside the workflow, inspect its actual revision before updating
the request; do not override a mismatch by resetting the checkout.

Offline tests mock provider requests, including adapter-level checks of exact
word, language, hints, carrier input and extraction. They also cover credit
reservation/settlement, duplicate delivery, interrupted/cancelled claims, source
withdrawal, owner-only media, ratings, CSV export and unchanged dictionary audio.

Validation for the initial implementation: the 835-test Community Dictionaries /
admin-tools regression run passed, followed by all 15 final experiment tests,
including additional cancellation-accounting and publication-route checks.
Django system and migration-drift checks passed, as did JavaScript syntax and
French/Slovak catalogue compilation. No paid provider requests were made.
