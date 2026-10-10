# Email password recovery, 10 October 2026

## Human evidence and scope

Manny reports the batch-description/rename/count update working on both laptop
and AWS. He returns to Cathy's email-recovery request, identifies the mailbox
provider as Google Workspace, and reports obtaining an app password. The password
itself was not supplied to the agent and is not retained here.

Manny also proposes owner-enabled anonymous read-only dictionary access, disabled
by default. That remains a separate proposed increment; this patch changes no
anonymous content permissions. Publication consent and withdrawal behaviour need
to remain explicit when that increment is implemented.

## Prepared implementation

Email reset links use Django's one-time tokens and password policy, with a fixed
operator-configured origin, one-hour lifetime, matching Community Dictionaries /
C-LARA screens, CSRF protection and no automatic login after reset. A database
counter table limits requests across processes; email lookup and sending use the
existing bounded dispatcher. An explicit diagnostic command can validate settings
without network activity, or send one harmless test email when requested.

There is one additive projects migration, 0044, and no package/static changes.
The disabled default preserves deployment order: migrate, configure protected
SMTP credentials, check real delivery, then restart to expose the controls.

## Verification

Baseline: main `9947c9667e2086b96faddf49bf2d86d74d94b68a`.
Local Python 3.12 / Django 5.2.17 / disposable SQLite:

- Full `projects.tests.test_email_reset projects.tests.test_admin_tools
  projects.tests.test_profile community_dictionary`: **514 tests passed**.
- Final focused recovery suite: **28 tests passed**, including known/unknown /
  inactive/unusable accounts, duplicate emails, shared case-normalized quotas,
  expiry/reuse, password and email changes, session invalidation, CSRF, fixed-origin
  links, secret-free error logging, disabled mode and diagnostic mail.
- System check and migration-drift check pass.
- Browser rehearsal at **320, 390 and 1280 pixels** for both interfaces: follow
  Forgotten password, dispatch a captured email, open link, reject a mismatch,
  save a new password, log in, and reject the consumed link in a fresh browser.
  The real local fallback dispatcher is used; SMTP is intercepted. Screenshots
  were visually inspected. Browser testing caught an overly restrictive referrer
  header that caused Chromium's form POST to fail CSRF; `same-origin` fixes this,
  preserves cross-origin referrer privacy, and the final browser/focused tests pass.

Reproduce the optional browser rehearsal with the app's Python environment,
Node Playwright and a Chromium executable:

```bash
COMMUNITY_CHROMIUM_PATH=/path/to/chromium \
python experiments/community_dictionary/email_reset_browser_rehearsal.py /tmp/email-reset-browser
```

No actual SMTP messages, paid API calls, AWS operations or changes to user
accounts were performed by the agent. Google acceptance/delivery, Windows and
physical-phone recovery remain for Manny and Cathy. The full regression suite
preceded the final referrer-header correction; the final focused suite and both
browser flows cover that correction. This is supervised implementation evidence,
not a claim of long-run autonomous operations.

## Operational boundaries

The fallback queue remains in-memory: restarts may lose unsent requests, and busy
AI jobs can delay them. A request queued for more than 15 minutes is dropped; users
can request another. SMTP timeouts do not cause automatic retries. The diagnostic
command distinguishes configuration validation from an actual send, and backend
acceptance from inbox delivery. Counter locking is coded for PostgreSQL and SQLite;
production PostgreSQL acceptance of this increment has not yet occurred.

See [behaviour](../../docs/howto/email-password-reset.md) and
[installation/runbook](../../docs/howto/email-password-reset-install.md).
