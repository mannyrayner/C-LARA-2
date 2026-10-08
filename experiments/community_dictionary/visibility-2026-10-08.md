# Dictionary visibility — 8 October 2026

Manny reports that the preceding allowance change appeared to work. Discussion
with Cathy identified a concrete navigation problem: both the original Swedish
dictionary and its newer image-only-derived version were presented as ordinary
choices, and she was unsure which to use. He requests an owner-only Visible/Hidden
control under Settings before further testing.

The prepared implementation defaults every dictionary to visible. Hiding moves
its card and invitations into a collapsed Hidden dictionaries section for its
existing audience. Authorized direct access remains available with a hidden label;
contribution withdrawal/restore and source-image dependencies remain intact. The
owner can make it visible again from Settings. This changes presentation, not
privacy or participation. Migration 0017 adds only a Boolean field.

GitHub main observed at `fc7efff5a4959030f8b16e0101a019263ec1f12f`
(“Configure picture-description allowances with cost approval”). This is repository
evidence, not independently verified AWS HEAD. The user has not specified the
environment of his latest allowance acceptance.

## Verification

- **356 Community Dictionary tests pass** on Python 3.12 / Django 5.2.17 / SQLite.
  Seven new regressions cover hide/restore and retained policy revisions; owner
  permissions including ownership changes; POST/CSRF and invalid requests; hidden
  member media access plus actual withdrawal/restore; inactive members, hidden
  invitations and outsider exclusion; visible image copies and provenance; and
  archived/personal/withdrawn restrictions.
- `manage.py check` passes and `makemigrations --check --dry-run` reports no changes.
- Isolated Chromium with two synthetic Swedish dictionaries: owner hides original;
  member sees only current version in normal list; hidden section starts collapsed;
  opening history shows its hidden label and withdrawal control; owner restores
  visibility via Settings. Layout checked at 390 and 1280 CSS pixels with no
  overflow or JavaScript errors; mobile-sized screenshot visually inspected.

No AI requests, remote deployment or messages were sent. This new feature still
needs human laptop/AWS acceptance; no physical-phone acceptance is inferred from
browser viewport checks. The change implements Cathy's specific navigation issue,
not a claim that systematic fresh-eye testing has finished. Broader MWE work stays
deferred.
