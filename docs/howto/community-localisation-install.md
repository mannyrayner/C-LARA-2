# English/French interface: installation and trial

19 October 2026

Patch: `community_dictionary_localisation.patch`

Base: `cae762876b8060592e4d8327d4d107c981cdc2b6`
(`Extend carrier audio trials to four additional languages`)

This patch is incremental after that commit. No localisation code was assumed to
have been installed from the previous thread. It adds no database migration,
production dependency, environment variable, provider request or content rewrite.
It **does** change static JavaScript/CSS, so AWS needs `collectstatic`.

## Behaviour

- The header has an **English / Français** interface selector and an Apply button.
  It works before login and remembers the choice in that browser for one year,
  including across logout. It applies only to Community Dictionaries.
- The home and discovery pages suggest learning dictionaries with explanations in
  the selected interface language. French defaults to English when an English
  dictionary with French explanations is available; English similarly prefers
  French with English explanations. Otherwise another available matching language
  is selected. Free-text language names and common language codes are recognised;
  a blank explanation language follows the existing English fallback.
- A learning-language control changes those suggestions. Explicit choices are
  remembered separately for each interface language in the current login session.
  Existing dictionary lists, search, invitations, hidden-dictionary controls and
  direct dictionary links remain available. No language is inferred from private
  dictionaries that a visitor cannot discover.
- If no dictionary has matching explanations, the page says so and retains the
  existing choices below. New-dictionary forms initially suggest English or French
  explanations according to the interface; owners can edit this before saving.
- Switching language on an unsaved contribution uses the existing Save/leave
  controls. The choice is submitted explicitly rather than changing as soon as the
  selector is touched.

This is a first cut. Shared navigation and the main browsing, word, recording,
contribution, photo, practice, settings/profile and evaluation templates have
French translations, including their principal JavaScript controls. Some group
management, advanced AI/porting, evaluation data labels and private-content pages
still contain English. User-entered text, names, categories, explanations,
pronunciation guidance and recorded/generated audio retain their original language.

The interface selector does not create an English/French content version. If one
is needed, use the existing owner-approved **Language versions** workflow to create
an English dictionary with French explanations, review it, and choose its normal
visibility/discoverability settings. This can send paid provider requests when
explicitly approved in that workflow.

## Laptop

Stop the development server. Extract the download and put the `.patch` next to
the repository, for example `/home/github/community_dictionary_localisation.patch`.
From Git Bash:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
```

Expect a clean checkout containing the base commit above. Preserve any unrelated
work before proceeding. Apply this patch once:

```bash
git apply --check ../community_dictionary_localisation.patch &&
git apply --index ../community_dictionary_localisation.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py makemigrations --check --dry-run community_dictionary &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expected: **668 tests, OK**, no migration changes. Tests simulate provider failures;
some logged failure messages are expected when the final test result is OK.
Compiled `.mo` translation catalogues are included as binary patch entries, so
Windows does not need GNU gettext just to install or run this patch.

```bash
../.venv/Scripts/python.exe -E manage.py runserver 127.0.0.1:8000 --insecure
```

Use `--insecure` only for laptop development static files. Perform the trial
below before committing. Once accepted:

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git diff --cached --check
git commit -m "Add English and French Community Dictionaries interface" &&
git push origin main
git rev-parse HEAD
```

Use your normal branch/review process if the checkout is not on `main`.

## AWS

After laptop acceptance and check-in, deploy that same commit using the established
service account and environment. Keep normal backups; this update does not require
a new media archive or database conversion. Let existing AI jobs finish first.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git status --short
```

Expect a clean checkout. Define the existing management helper in this shell:

```bash
clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu \
    --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}

sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git pull --ff-only &&
clara_manage check &&
clara_manage migrate --check &&
clara_manage collectstatic --noinput &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker

sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD
```

Stop on any error before the service start, preserve the output and resolve it.
No `pip install`, Nginx change or daemon reload is required. Both web and worker
services should run the checked-in version. Confirm HEAD matches the laptop.

## Human acceptance trial

1. Before login, open **Find dictionaries**, choose **Français**, apply, reload,
   and visit another page. Check the French header and retained choice. Log in,
   then log out, and confirm it remains French.
2. If a discoverable English/French dictionary exists, confirm **anglais** is the
   initial learning language and that its link opens the expected dictionary.
   If it is private, its discovery/membership page should open instead. If no
   matching dictionary exists, check the French fallback message and choose an
   existing dictionary below.
3. Try another learning language and **Toutes les langues à apprendre**. Switch
   back to English, check its matching explanation defaults, and open an existing
   Italian/German/Icelandic dictionary directly. Verify words/audio/explanations
   have not changed.
4. On a contribution page, type a disposable unsaved word, then apply another
   interface language. Check the Save/leave dialog and **Keep editing**. Verify
   a recording or photograph is not silently discarded.
5. Check word browsing, an entry, human recording, practice, Profile and Settings
   in French. Repeat the main steps on a phone, checking the header selector and
   long French labels. Note remaining English or awkward translations for the next
   pass. Fresh browser/private-window choices start in English.

## Verification and limits

The unchanged base passed all 653 Community Dictionaries tests. This patch adds
15 regression tests for preference persistence, POST/CSRF/redirect handling,
matching defaults and aliases, hidden/private/withdrawn boundaries, retained
dictionary access, unchanged content, French templates/JavaScript and isolation
from the rest of C-LARA. The combined 668-test suite passes. Django checks,
migration consistency, template parsing, JavaScript syntax and translation format
checks also pass; focused capture/audio and French-render checks cover the added
forms and preview templates.

Provider calls were simulated. No paid generation, live AWS deployment or physical
phone trial was performed. Browser interaction/layout testing could not run here:
Chromium was unavailable and its download failed. The human trial above remains
necessary for layout, recording and unsaved-edit acceptance.

For later translation maintenance, edit the standard French `django.po` and
`djangojs.po` catalogues under `platform_server/community_dictionary/locale/`.
With GNU gettext available, run `manage.py compilemessages -l fr` and commit both
updated source and compiled catalogues. Some dynamic display labels are explicitly
present in the catalogue, so preserve them when refreshing extracted messages.
