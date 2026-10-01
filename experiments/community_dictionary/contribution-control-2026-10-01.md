# Contribution control revision — 1 October 2026

Base: verified GitHub main `ffbbef9d24873cd930cb866d979e1bd3a735e41b` (tree
`dba16b5f15014261f2d936da6cfaf5a8a1d0e7fb`). An isolated worktree was used.

Manny authorises implementation after agreeing on persistent inactive memberships,
personal retention and resharing, and independent attribution for word,
translation and category. The policy/UX is described in
[the runbook](../../docs/howto/community-contribution-control.md).

Automated evidence: 118 passing Community Dictionary tests on Python 3.12 / Django
5.2 with a disposable SQLite test database. Intentional provider-failure tests
log TimeoutError/JSONDecodeError; no live provider requests were made. The old
physical-deletion expectations were changed to verify private retention. Existing
picture/word navigation, recording, photo learning and TTS checks remain covered.
Migration 0007 is tested with a reconstructed 0005 schema and surviving/absent
translation history. A blank test database alone uses a no-op reverse of 0007 to
prepare that fixture; production 0007 remains explicitly irreversible.

`contribution_control_browser.cjs`, run through `browser_rehearsal.py`, uses a
fresh database, two accounts and synthetic media. Chromium 153 passes at iPhone
13 and Pixel 7 viewport sizes and a 1360-pixel desktop width. These are Chromium
viewports, not physical iOS/Safari or Android devices. The rehearsal checks:

- contributor photo/English first, editor Swedish/category later;
- attribution remains distinct;
- inactive member cannot open shared entry, can still withdraw own translation;
- original independent Swedish word remains;
- reactivation does not publish private material;
- explicit resharing into the original entry is reviewed and preserves credit;
- no page errors or horizontal overflow on the checked pages.

Visual inspection covers private collection, sharing and entry/history controls.
Screenshots stay outside the repository; the reproducible rehearsal is checked in.
No AWS, real community data or paid API access was used. PostgreSQL concurrency
and physical-phone/laptop acceptance by Manny are not claimed. Global state
records this as a prepared, tested increment awaiting human installation.
