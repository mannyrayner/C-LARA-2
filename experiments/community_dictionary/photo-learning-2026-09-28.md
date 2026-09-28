# Single-object photo learning — 28 September 2026

Base: main `b7cb356e0a548b730c159bdf48a9bcb7dd31ced8`.
Status: implementation patch prepared; not yet installed on AWS or accepted on a phone.

Manny approves a small photo → identification/confirmation → target word → optional
save flow. One vision call returns structured feedback and wording; a second text-only
call is unnecessary for this first trial. A subject need not be geometrically central.
No boxes, multiobject picker, video, sentences/history, generated pictures or saved TTS
are added. This is the targeted exception to Manny and Cathy's shift toward operational
autonomy rather than runtime elaboration. The operational agent and funding ideas
remain discussion topics; no external messages or financial actions were performed.

The patch adds opt-in dictionary policy, explicit user consent, private 24-hour drafts,
one durable provider attempt per submission, per-user/dictionary daily quotas, existing
account/key and token-accounting integration, confirmation, editable words, optional
device-voice preview and idempotent contribution saving. Members cannot publish their
own proposals. Text provenance survives export/restore. Draft deletion has a command
and an AWS systemd timer; access expiry and physical cleanup are distinct.

## Executed evidence

- Django 5.2.17: **40 tests pass**, including the existing 21 and 19 new tests.
  These cover confirmation/review, membership and private draft access, CSRF and
  owner-only policy, exact and changed receipt replays, save rollback, export origins,
  consent, quota after discard, expiry/cleanup, credit gate and single charging,
  BYOK/no server fallback, malformed/refused/incomplete results, failure/unknown
  attempts, outbound request shape, image resizing and absent EXIF. All AI responses
  are mocked; tests spend no provider credit.
- Django `check` passes; `makemigrations --check --dry-run` reports no missing migration.
- Chromium **153.0.8010.0**, iPhone 13 and Pixel 7 **viewport profiles**: upload with
  browser resizing, confirmation without premature target-word display, editing/saving,
  invalid-file recovery and discard all pass; no uncaught JavaScript errors or horizontal
  overflow on checked result pages. Screenshots were visually inspected. These are
  Chromium/Linux runs, not Safari, Android Chrome or physical cameras. Device voices
  were unavailable; the no-matching-voice message appeared, and audio pronunciation
  was not exercised.
- The browser fixture is a solid-colour synthetic image with a fixed mocked teapot
  answer. It tests the interface and explicitly provides **no recognition evidence**.
- During setup, two rehearsal harness errors (settings override and autoreloader
  argument) were corrected. The cached Chromium executable was truncated and was
  re-extracted before the passing run. They are not user-app defects or phone results.

Reproduce backend checks using the [how-to](../../docs/howto/community-photo-learning.md).
For the optional browser rehearsal, install Playwright/Chromium, set
`COMMUNITY_PLAYWRIGHT_MODULE` / `COMMUNITY_CHROMIUM_PATH` if needed, then run:

```bash
python experiments/community_dictionary/photo_browser_rehearsal.py /tmp/community-photo-evidence
```

## Remaining evidence

No live OpenAI call or physical-phone trial was made in this implementation session.
First test account/model availability, then familiar clear objects, off-centre subjects
and ambiguous scenes. Record the real confirmation language, correctness of word/article,
latency, cost, camera format and pronunciation. The model is allowed to decline, but its
willingness to do so is not yet measured. `store=False` does not promise zero provider
retention. Worker termination can leave an unknown provider outcome and incomplete local
accounting; there is deliberately no automatic retry. Existing production security,
backup/restore and broader user-trial questions remain open.

Human-owned project intentions and the prior paper were not rewritten. Global workspace
revision 18 records this implementation and the changed priority, keeping deployment,
provider quality and long-term autonomy claims separate from local software tests.
