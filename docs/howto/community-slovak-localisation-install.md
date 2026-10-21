# Slovak interface and English/Slovak dictionaries

21 October 2026

Patch: `community_slovak_localisation.patch`

Base: `19fd910157326df7c6977dd5ee5f5984fcb64a4d`
(`Add image contribution ladder under People`). Apply after the accepted image
ladder patch; earlier English/French localisation and carrier changes are included
in this base.

## What changes

The interface selector now offers **English / Français / Slovenčina**. Slovak
uses the same persistent browser preference, pages, JavaScript messages and
permission rules. The new catalogs cover all currently catalogued interface
messages: 1,085 page/server messages and 166 JavaScript messages, including the
image ladder. Slovak's four plural forms match the installed Django locale.

Slovak mode prefers English-learning dictionaries with Slovak explanations when
available, falls back to other available learning languages, and remembers an
explicit learning-language choice separately for each interface language. Existing
dictionary lists remain available. New dictionaries default their explanation
language to the canonical stored name `Slovak`.

The selector changes interface text. It does not rewrite stored words,
explanations, dictionary names or audio, or start AI work. Thus the existing
Slovak/English dictionary remains a Slovak-learning dictionary with English
explanations, usable in any interface language. Create a separate English/Slovak
version using the conversion procedure below.

The translated scope matches the existing French catalog coverage. A few advanced
conversion, AI and administration screens still have their existing English
wording. This is an AI-assisted first Slovak version for Ivana to review in use;
automated format checks do not establish native-language quality.

No new dependency, migration, database rewrite or paid request is needed to
install the patch. Compiled page and JavaScript catalogs are included, so GNU
gettext is not required on the laptop or server. Restart to reload translations.

## Laptop installation

Stop the development server and put the extracted patch next to the repository:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
git apply --check ../community_slovak_localisation.patch &&
git apply --index ../community_slovak_localisation.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py makemigrations --check --dry-run community_dictionary &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expected: **713 tests, OK**, and no migration changes. Stop if the patch
check fails and preserve unrelated work. Restart as usual:

```bash
../.venv/Scripts/python.exe -E manage.py runserver 127.0.0.1:8000 --insecure
```

Choose **Slovenčina**, then **Použiť**. Check the navigation, picture/word pages,
translation reveal, practice, People and recording controls. Reload or sign out
and revisit the public browsing page: the interface choice should remain Slovak.
Switch to English and French and back. Existing dictionary names/content should
remain unchanged. An English/Slovak dictionary should appear among matching
recommendations once it is available through membership or discovery.

Review and commit the patch after acceptance:

```bash
cd /home/github/c-lara-2
git diff --cached --check
git diff --cached --stat
git commit -m "Add Slovak Community Dictionaries localisation" &&
git push origin main
git rev-parse HEAD
```

Use the normal branch/review process if your checkout is not on `main`.

## AWS installation

Let running AI jobs finish. Start with a clean checkout and retain the old SHA.
The normal static-file step below also keeps the earlier ladder styles in sync;
the Slovak JavaScript catalog itself is served dynamically by the application.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git status --short
git rev-parse HEAD

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

Stop on any error and retain its output. Confirm all three services are running
and the deployed SHA matches the accepted laptop commit. Reload and repeat the
Slovak interface checks on the actual laptop/phone.

## Create English/Slovak content

Use the existing **English/French** dictionary as the source. This retains the
English wording and existing accepted audio, translating the explanations. The
original dictionary remains available.

1. As its owner, open **Settings → Language versions → Create a version in another
   language**. The conversion form currently retains its English labels.
2. Give the new dictionary a distinct name. Set **Target language** to `English`
   and **Commenting language** to `Slovak`. Use these canonical field values;
   **Slovenčina** is the interface selector label.
3. Choose the existing step-by-step review or automatic processing mode, then
   **Estimate cost**. Review the scope, estimated cost and allowance before
   explicitly approving. Translation is paid work; no live conversion was run
   while preparing this patch.
4. In step-by-step mode, review and save the sentences, then build/review their
   vocabulary from the accepted English wording using the existing workflow.
   Review any flagged items. Automatic mode publishes without intermediate review
   under the displayed approval terms; inspect its results afterwards.
5. Invite Ivana using the normal membership controls, or enable discovery/public
   browsing with the existing contributor-permission controls as appropriate.
   Choosing an interface language alone grants no dictionary access.

Starting from French/English and changing both fields to English/Slovak is also
supported, but requires new English wording and English audio generation. Starting
from the existing English dictionary avoids that extra work. The existing Slovak
speech configuration is unchanged; this patch does not add Slovak MWE carriers.

## Adding further interface languages

`community_dictionary/localisation.py` now has one `UI_LANGUAGE_CONFIG` entry per
interface: native selector label, canonical explanation-language name and preferred
learning language. Add a row there and any useful language-name aliases; supply
`locale/<code>/LC_MESSAGES/django.po` and `djangojs.po` with appropriate plural
metadata, then compile their `.mo` files. Both domains matter for recording,
practice and asynchronous status controls. Use the current English message IDs as
the source and preserve named interpolation placeholders.

Validate catalog formatting, plural output, language defaults, remembered choices
and representative page/JavaScript rendering before deployment. Existing
languages share the same templates and request middleware. Stored dictionary
content and TTS language support remain separate concerns.

## Evidence and review context

All **713 Community Dictionaries tests pass**, including 12 new Slovak
regressions and the 15 existing localisation tests. They cover selector/cookie
scope and security, canonical defaults, available matching explanations,
per-interface saved choices, access rules, unchanged content, real translated
public/member pages, JavaScript messages and Slovak integer plurals. All 95
templates compile; translation-format, system and migration checks pass. All
existing compiled French translations are preserved.

Two additional disposable mocked-provider conversion checks verify that an
English/French source retains English text/audio when explanations change to
Slovak, and a French/English source supports changing both fields. No production
dictionary, real provider request or AWS deployment was performed here.

Manny reports that the preceding image ladder worked, that Ivana is interested
in experimenting, and that he already converted French/English to Slovak/English.
This is human-reported acceptance and content availability. Ivana's assessment of
the new Slovak interface, creation/quality of English/Slovak content, and broader
learning/evaluation outcomes remain to be established.
