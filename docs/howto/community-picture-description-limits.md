# Daily AI allowances

Updated 28 November 2026 (Adelaide): distinguish entry/practice attempts from newly
generated pictures in one Settings panel. Human acceptance of this clarification
remains pending.

## For dictionary owners

Open **Settings → Daily AI allowances → Entry creation and practice**. Enter the number of attempts
allowed in 24 hours, choose **Preview daily cost**, then approve the estimate and
choose **Confirm**. Going back without confirming changes nothing. Owners and co-owners
can change this shared setting; members can see usage when starting a description.

- Newly created, image-only copied and language-ported dictionaries start at **50**.
  Existing dictionaries keep their stored limits, including the old default of 10. The allowance is shared by all
  members of that dictionary. For example, raising it to 50 when 10 attempts have
  been made leaves 40 attempts available.
- The window is the preceding 24 hours, not a midnight reset. Failed and discarded
  attempts count. Retrying the same receipt does not create a second attempt.
- Lowering the allowance below current usage blocks new requests until enough
  attempts age out. Existing work and requests already running remain available.
- The shared allowance covers guided picture creation (including starting with words),
  picture descriptions, writing checks and **Describe a picture** practice. The older
  **Learn from a photo**, manual audio generation and standalone image-generation
  tools retain their independent limits.
- Changing this setting starts no generation, reserves no credit and does not
  invalidate saved previews or change dictionary feature/privacy policy.

## When the allowance is exhausted

The activity shows **Daily allowance used up**, with a short explanation. Owners
and co-owners get **Add N more**, leading directly to the existing signed cost
preview and confirmation. The proposal is at least 50, or 25 beyond the current
limit/usage, bounded by the server ceiling. It never automatically raises a limit,
resets usage, starts an AI call, or retries a blocked submission. Members are told
to ask an owner or try again later. Server/account ceilings are explained separately;
a dictionary increase is not offered when it cannot help. JSON errors include a
stable `allowance_exhausted` code and recovery details.

An actual blocked request from a member who cannot manage the allowance queues
one notification to the primary owner's registered email address, at most once
per dictionary per rolling 24 hours. Merely viewing an exhausted allowance sends
nothing. The message names the dictionary and links to its allowance page; it
contains no learner text, image, recording or identity. Owner/co-owner requests
and server/account-limit blocks do not send notices. Increasing the allowance
before queued delivery suppresses a stale notice.

Mail uses the site's configured Django email backend, sender and fixed
`PUBLIC_BASE_URL`, plus its existing Django-Q task queue. No assistant mailbox or
request Host header supplies the link. An existing dictionary event reserves the
notification under the dictionary lock; the worker claims it once before sending.
Failures record a bounded status without addresses or credentials and do not
retry automatically. There is no new schema or email configuration setting.

## New AI pictures have a separate allowance

The same Settings panel shows **New AI pictures** first, with the remaining normal
picture allowance and an explanation of how owners approve extra pictures. Account
and dictionary usage for the preceding 24 hours is available under **How the picture
allowance is counted**. This covers new scene illustrations, style samples
and word pictures. The server's ordinary image limit defaults to 20; changing the
creation/practice setting above does not change it. Both limits are shown when
starting with words, so the available language-work allowance is not mistaken for
available image capacity. Creating an entry with a new AI picture uses both
allowances. Describing an uploaded picture or practising with an existing one uses
the entry/practice allowance; any automatic word pictures also count towards the
picture allowance. For example, 100 entry/practice attempts and 20 new
AI pictures do not permit 100 new illustrations without explicit extra-picture
approval. The editable field is labelled **Entry or practice attempts per 24 hours**.

Owners and co-owners can explicitly approve **this picture above the normal daily
image limit, for this request only**, at the displayed cost. This is available for
Start with words and ordinary picture/style previews, matching the existing explicit
word-picture batch allowance. It leaves the normal limits unchanged and cannot
override a server pause, credit checks, or the creation/practice allowance. Queued
approval expires after 24 hours, is bound to its requester and private attempt,
and is checked again before image generation. A recovered local draft never restores
this approval automatically. No failed paid request is repeated automatically.

Image quota is checked before saving a new words-first attempt, with a clear message
when unavailable. If quota changes while a request waits, its private failure page
identifies the image allowance rather than implying the language-work setting is
exhausted. No database migration is needed for this clarification and scoped approval.

## Language-work cost estimate

The preview multiplies the proposed allowance by the existing short-description
planning estimate: 16,000 input tokens and 4,096 output tokens at the configured
photo-model rates, plus US$0.30 for associated audio, pronunciation guidance and
spoken input. This plans for a short sentence and up to twelve vocabulary items
with lemma/form audio. Practice normally needs less processing; each activity
provides its own estimate. The daily preview is labelled as the cost if every
request creates a new entry.
The UI exposes these assumptions and explicitly states that new AI pictures cost
extra and use their own allowance; no API call is needed to calculate the preview.

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
ceiling is clamped. The application creation policy now supplies 50 explicitly. The historical model
and migration fallback stays 10 for legacy/deserialised data; no schema migration
or bulk alteration of existing allowances is required. Check an existing
operator override if the Settings form offers a smaller maximum than expected.

The cost approval is signed, expires after ten minutes, and is bound to the owner,
dictionary, proposed and previous allowance, capture-policy revision, ceiling,
model, rates and estimate version. Changed terms require a new preview; duplicate
confirmation is harmless. Owner changes are recorded in the dictionary event log.
The separate allowance endpoint has normal membership/withdrawal/archive and CSRF
checks. Posting an allowance directly to the general settings form cannot bypass
approval. Dictionary and user row locks protect quota checks and attempt creation.

See [test evidence](../../experiments/community_dictionary/capture-limits-2026-10-08.md).
