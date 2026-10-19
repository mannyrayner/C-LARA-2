# French interface: screenshot follow-up

19 October 2026

This is an **incremental** patch after `community_dictionary_localisation.patch`,
the English/French version currently being tested on the laptop. Apply only
`community_dictionary_localisation_followup.patch`; do not apply the first patch
again. It works whether that first patch is staged or already committed.

## Changes

- Translate the complete **Next step** card: generated headings and buttons,
  singular/plural counts, estimates, credit and provider/privacy disclosures,
  permissions, progress/review states and settings links.
- Translate **Needs attention**, including the empty states and language-check
  confirmation messages.
- Translate **People & partnerships**, including roles, statuses, invitations,
  partnership controls and empty states.
- Display recognised language names in the interface language on dictionary,
  discovery, word and meaning headers. Stored names, entries and explanations are
  unchanged. Unknown language names keep their original spelling.
- Translate the participation controls below the dictionary, including viewing,
  withdrawing and restoring your contributions.

No database migration, dependency, JavaScript/CSS or provider configuration change.
The compiled French catalogue is included, so GNU gettext is not needed to install
it. No paid requests are made merely by installing or opening these pages.

## Laptop installation

Stop the laptop server. Extract the download and put the patch next to the
repository, for example `/home/github/community_dictionary_localisation_followup.patch`.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_localisation_followup.patch &&
git apply --index ../community_dictionary_localisation_followup.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py makemigrations --check --dry-run community_dictionary &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expect **680 tests, OK**, and no migration changes. Preserve unrelated work if the
patch check fails. If the first patch is still staged, the cached diff will show
both updates; that is expected.

Restart so Django reloads the translation catalogue:

```bash
../.venv/Scripts/python.exe -E manage.py runserver 127.0.0.1:8000 --insecure
```

Reopen the three pages from the screenshots in French mode. Check the one-picture
heading, the expanded cost/privacy details, empty attention report states, and
expanded invitation/partnership forms. Switch to English and back. Dictionary and
partnership names, report notes and collected language material should retain their
original wording. Continue the remaining laptop review before committing and
deploying as usual.

## AWS

If the first localisation patch has not yet reached AWS, deploy the accepted
combined changes using [the original installation instructions](community-localisation-install.md),
including `collectstatic` for that first patch's static-file changes.

If the first patch is already deployed, this follow-up alone needs the normal
clean `git pull --ff-only`, `manage.py check`, `manage.py migrate --check` and restart
of `gunicorn-clara2`, `djangoq-clara2` and `project-understanding-worker`. It adds no
static files to collect. Use the existing service account and environment helper.

## Verification

All 680 Community Dictionaries tests pass, including 12 new rendered-page and
workflow regressions covering the screenshots, French plural counts, credit
disclosures, roles and partnerships, source content, permissions and read-only
GET requests. English next-step HTML was compared with the previous version in
144 render combinations. All 94 templates compile, translation format checks pass,
and no schema changes are detected. The incremental patch is checked against the
exact previously delivered version.

Manny reports that almost all of the first cut already displays correctly in
French on the laptop. These screenshot fixes have automated checks; their new
browser/phone acceptance remains to be confirmed. No live AWS deployment or paid
provider trial was performed here.
