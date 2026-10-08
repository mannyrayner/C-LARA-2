# Picture-description allowance and estimated daily cost

8 October 2026. Follow-up to the image + spoken/typed description workflow.
Manny confirms the preceding audio-recovery fix works. This allowance change has
automated and simulated-browser evidence; human laptop/AWS acceptance is pending.

## For dictionary owners

Open **Settings → Picture-description allowance**. Enter the number of descriptions
allowed in 24 hours, choose **Preview daily cost**, then approve the estimate and
choose **Confirm**. Going back without confirming changes nothing. Only the owner
can change this shared setting; members can see usage when starting a description.

- Existing and new dictionaries start at **10**. The allowance is shared by all
  members of that dictionary. For example, raising it to 50 when 10 attempts have
  been made leaves 40 attempts available.
- The window is the preceding 24 hours, not a midnight reset. Failed and discarded
  attempts count. Retrying the same receipt does not create a second attempt.
- Lowering the allowance below current usage blocks new descriptions until enough
  attempts age out. Existing work and requests already running remain available.
- This setting applies to **Picture descriptions**, not the older **Learn from a
  photo**, manual audio generation or image-generation tools. Those retain their
  independent limits.
- Changing this setting starts no generation, reserves no credit and does not
  invalidate saved previews or change dictionary feature/privacy policy.

## What the estimate means

The preview multiplies the proposed allowance by the existing short-description
planning estimate: 12,000 input tokens and 2,600 output tokens at the configured
photo-model rates, plus US$0.08 for associated audio, pronunciation guidance and
spoken input. This plans for a short sentence and up to six new words with audio.
The UI exposes these assumptions; no API call is needed to calculate the preview.

This is **not a hard spending cap or provider quotation**. Actual input size,
vocabulary count, audio duration, reuse, retries and provider prices vary. The app
allows up to twelve vocabulary items; those larger examples may cost more.
Manual retries and other AI tools are extra. Existing stage-by-stage billing and
balance checks remain in force.

Each requesting member uses their own payment settings (personal OpenAI key,
C-LARA credits, or server funding). The owner's allowance approval does not make
the owner pay for every member. Where applicable, the preview displays the owner's
current credit balance and warns if it is below the full estimate. It cannot
inspect the balance behind a personal provider key or aggregate members' funds.

## Operator and implementation notes

Migration **0016_capture_daily_limit** adds one integer field with default 10;
there is no content migration or media rewrite. A database backup is appropriate;
this update does not require a fresh bulk media archive.

`C_LARA_COMMUNITY_CAPTURE_DAILY_LIMIT` sets the server ceiling (Django setting
`COMMUNITY_DICTIONARY_CAPTURE_DAILY_LIMIT`), default **1000**. It limits each
dictionary's effective allowance and each account's total across dictionaries in
24 hours. Zero pauses new attempts. A stored allowance above a subsequently lowered
ceiling is clamped. The normal dictionary default remains ten. Check an existing
operator override if the Settings form offers a smaller maximum than expected.

The cost approval is signed, expires after ten minutes, and is bound to the owner,
dictionary, proposed and previous allowance, capture-policy revision, ceiling,
model, rates and estimate version. Changed terms require a new preview; duplicate
confirmation is harmless. Owner changes are recorded in the dictionary event log.
The separate allowance endpoint has normal membership/withdrawal/archive and CSRF
checks. Posting an allowance directly to the general settings form cannot bypass
approval. Dictionary and user row locks protect quota checks and attempt creation.

See [test evidence](../../experiments/community_dictionary/capture-limits-2026-10-08.md).
