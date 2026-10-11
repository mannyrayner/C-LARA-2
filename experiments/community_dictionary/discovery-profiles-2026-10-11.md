# Discovery, membership requests, Profile and About — 11 October 2026

## Human evidence and request

Manny reports that anonymous browsing works and is deployed on AWS. This updates
the pending outcome in the earlier public-browsing record; it does not supply a
new physical-device matrix or load test.

In preparation for an accessible introductory paper and wider trials, he requests
default-off dictionary discoverability, membership requests for owner review,
a Community Dictionaries profile with contributor opt-in and dictionary ownership,
and an About page. Earlier discussion calls for a short report with screenshots,
credit-supported trial groups and rapid responses to feedback. The paper, trial
funding terms and any forum are not implemented or published by this patch.

## Implemented

Prepared against main `4d90cf8efaa1ef31f0c79163be85dea619f76d87`.

- Discovery publishes metadata and accepted counts, separately from permission
  to browse contents. A private dictionary can advertise for members.
- Requests are account-based, private to the requester/current owner, bounded and
  reviewed inside the app. Approving a new applicant creates ordinary membership.
  Existing invitations, roles, inactivity and withdrawal retain their own rules.
- Community Profile reuses account/password/credit/timezone/key infrastructure,
  with separately stored, default-off public contributor identity. Explicit key
  removal works even when the password field is omitted from a POST.
- About explains the workflows, public/private choices, project approach,
  publications status, opt-in contributors and email contact. No credit subsidy
  offer or autonomous moderation promise is published.
- Migration 0021 adds fields/tables only. All dictionaries initially remain
  unlisted, including existing public dictionaries; their public links still work.
  Hiding disables both settings. No production settings or content were changed.

## Local verification

- Django system checks and migration-drift check pass.
- **564 tests pass**: the full `community_dictionary` suite plus
  `projects.tests.test_email_reset`, `projects.tests.test_admin_tools`, and
  `projects.tests.test_profile` (Python 3.12, Django 5.2.17, SQLite).
- 28 new tests exercise the four discovery/public-access combinations, accepted
  counts, hidden/personal/archive exclusions, request/approval/cancellation and
  ownership boundaries, stale submissions, CSRF, withdrawal/inactivity, contributor
  opt-in/out, private account data, shared profile preservation and password change.
- Disposable Chromium rehearsal passes at **320, 390 and 1280 px**, including
  private discovery, login/request, owner approval, resulting member access,
  contributor listing/withdrawal, About and no horizontal overflow. Selected
  screenshots were visually inspected.
- The existing public-browsing browser rehearsal also passes after adapting it
  to the explicit discovery setting and new directory cards. It covers public
  search, translations, audio, word/sentence links and access revocation.

No live AI, SMTP, real account or AWS operations were performed. The initial local
test run found two fixture/assertion errors and an explicit-key-removal edge case;
these were corrected before the passing regression run. Browser selectors were
adjusted to match the final button labels. No human or production acceptance is
claimed for the new increment.

The migration and PostgreSQL row-lock behavior still need the normal AWS acceptance.
Lock ordering serializes dictionary membership decisions with existing participation
operations; new-request account limits use a PostgreSQL non-key user lock, and
owner decisions lock the request row rather than the joined user row.

## Reproduce

```bash
cd platform_server
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test community_dictionary projects.tests.test_email_reset projects.tests.test_admin_tools projects.tests.test_profile
```

The browser harnesses use a disposable SQLite database and synthetic test media:

```bash
python experiments/community_dictionary/discovery_browser_rehearsal.py /tmp/discovery-browser
python experiments/community_dictionary/public_browsing_browser_rehearsal.py /tmp/public-browser
```

They require Node/Playwright and Chromium; optional environment variables
`COMMUNITY_PLAYWRIGHT_MODULE`, `COMMUNITY_CHROMIUM_MODULE` and
`COMMUNITY_CHROMIUM_PATH` select installed runtimes. The bundled-Chromium option
uses that bundle's launch arguments. Contexts remain open until browser shutdown.
The server uses local port 8773; run the two harnesses sequentially.

Next: [laptop trial and AWS runbook](../../docs/howto/community-discovery-profiles-install.md),
then the introductory paper using actual accepted behavior and screenshots.
