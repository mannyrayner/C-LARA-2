# Original-entry sharing shortcut — 2 October 2026

Manny reported all contribution-control/display material checked in on 1 October.
GitHub main is verified at `e4153586cb3e0d15e8e7001e79bea6807f3d9722`, tree
`6ddb6a7d58f5d4505bf92a7df879aeef2d9297f0`, matching the delivered patches.

Further laptop testing found that image withdrawal succeeded but the return route
was hard to find. After explanation, Manny confirmed it worked and identified the
missed destination-entry selector. He requested a simple Share back to the original
dictionary control. This qualifies the earlier general acceptance: the existing
mechanism worked but was not sufficiently discoverable.

The new shortcut is prominent on the private entry and private contribution card.
A read-only confirmation shows the recorded original destination and only the
custodian's material. A confirmed POST reuses reviewed sharing and submission
receipts. It cannot silently create a new entry or choose an arbitrary posted
entry ID. Missing access/archived origins fail closed with an explanation; private
copies remain. Already-shared copies are not duplicated by a fresh confirmation.
There are no schema changes or account-form changes.

Validation uses Python 3.12 / Django 5.2 and disposable SQLite:

- **140 app tests pass**, including 12 new shortcut tests: prominent links and
  read-only preview; original target and private retention; editor review;
  receipt retries/fresh confirmations; forged component/destination IDs;
  inactive membership; archived/missing/language-changed origins; CSRF/confirmation;
  earlier versions and repeated withdrawal cycles; transactional text conflicts;
  foreign-source withdrawal; and matching/obsolete synthetic-audio defaults.
- No model changes detected by `makemigrations --check --dry-run`.
- `share_back_browser.cjs` through `browser_rehearsal.py` uses two accounts and
  synthetic media. It checks both shortcut entry points, no destination selectors,
  actual withdrawal/return/acceptance/playback, retained private media, repeat
  protection and inactive access. Chromium 153 phone/desktop viewport checks pass
  without horizontal overflow or JavaScript errors. Screenshots are inspected.
  A cramped mobile permission notice was rearranged during visual checking.

An initial browser assertion matched several status messages; narrowing it to the
page-level success message repaired the rehearsal. It was not an application
failure. Intentional mock provider failures are logged by the full app suite.
No paid API, real user data or production AWS access was used. These are Chromium
viewports, not new physical Safari/Android results. Human acceptance of the new
shortcut remains pending. [Installation and behavior](../../docs/howto/community-share-back.md).

## Subsequent feedback

Manny reports the shortcut is an improvement but still too complicated: he wants
no restore confirmation and no new review for previously reviewed material.
See [the immediate-restoration follow-up](immediate-restore-2026-10-02.md).
The confirmation-based workflow and 140-test count above describe this earlier
revision; the follow-up has its own controlled evidence and awaits human acceptance.
