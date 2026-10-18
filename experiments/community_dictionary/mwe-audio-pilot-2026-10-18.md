# MWE carrier regeneration: first application pilot

## Evidence and rationale

The preceding standalone Swedish/French listening experiment contained 40 MWE
recordings. The supplied manifest and ratings matched. Manny rated 36 acceptable
and four minor; no major pronunciation errors or bad extraction boundaries were
reported. Thirty succeeded on the first request, seven on the second and three on
the third: 53 requests total. This run therefore did not demonstrate a benefit
from fourth/fifth attempts. Of 35 new MWEs, 31 were acceptable; five repeated MWEs
were all acceptable. There was no concurrent direct-generation baseline, so these
figures do not quantify the improvement over ordinary generation.

Manny approved trying the three-way hybrid collection and proposed Swedish/French
dictionary evaluations restricted to word audio. This patch supplies an optional
owner-approved regeneration batch and same-word follow-up evaluation snapshots.
The single-word pathways remain unchanged. Broader language support/default
routing should follow application-level listening evidence.

## Prepared implementation

See `docs/howto/community-mwe-audio.md`. The application reuses durable PortSpeech
claims, bounded dispatch, source permission checks, once-only credit settlement and
frozen evaluation records. The acoustics and French/Swedish short-carrier payloads
are adapted from the tested `carrier-mwe-v1` harness. Old audio remains available
until replacement success; superseded versions can be restored subject to current
permissions and content. No human recording is replaced.

## Verification

- Full Community Dictionaries suite: 643 tests passed on Linux/Python 3.12,
  Django 5.2.18, including the first 16 new tests.
- Additional focused tests cover the owner HTTP approval/restoration path, CSV
  audio identity, real contribution withdrawal, and following up an older sentence
  evaluation's exact word units. The final focused run passed 58 tests (19 new MWE/follow-up tests and 39 existing evaluation tests).
- Synthetic PCM tests cover exact retained samples/padding, five-call ceiling,
  rejected extra gaps/short carriers, silence retry and no network-error retry.
- Batch tests cover human/single-word exclusions, current-source checks, cancellation,
  duplicate delivery/approval, competing jobs, failed replacement, refunds and undo.
- Django check, migration consistency and patch whitespace validation pass.

No paid provider requests, production changes or independent linguistic evaluation
were performed during this implementation. The attempted browser rehearsal could
not run because this environment had no browser binary and its browser download
failed. Server-rendered pages and their actions are covered through Django's test
client; actual laptop/phone presentation and live audio remain acceptance work.
Raw user ratings and dictionary media are not included in the patch.
