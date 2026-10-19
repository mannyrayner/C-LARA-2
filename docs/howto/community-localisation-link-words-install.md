# Final word-linking localisation and AWS deployment

19 October 2026

`community_dictionary_localisation_link_words.patch` is incremental after the two
earlier patches, `community_dictionary_localisation.patch` and
`community_dictionary_localisation_followup.patch`. Apply only this new patch to
the laptop version you have just accepted. The earlier changes may be staged or
committed; do not apply them again.

## Final adjustments

- Translate Link more words, its explanatory text, Link word, removable links,
  the pending-picture notice and link/unlink responses.
- Display recognised synthetic-audio language names in the interface language,
  including the contribution history. Spoken wording, voice names and stored
  provenance remain unchanged.

No new dependency, migration, static file or provider request is introduced by this
small patch. The compiled French catalogue is included. Restart the server to
reload it.

## Laptop

Stop the development server. Put the extracted patch next to the repository:

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_localisation_link_words.patch &&
git apply --index ../community_dictionary_localisation_link_words.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expected: **680 tests, OK**, with no migration to apply. Restart as usual:

```bash
../.venv/Scripts/python.exe -E manage.py runserver 127.0.0.1:8000 --insecure
```

In French mode, open the entry from the screenshot and expand **Associer d’autres
mots**. Check its instructions and button, then associate and remove a disposable
word link. Confirm the original picture wording is preserved and the synthetic
voice line displays **anglais**. Switch to English and back.

Once accepted, check in all intended localisation changes and retain the resulting
commit ID. If earlier patches are still staged, they will be included in the same
commit. Review the staged file list first and keep databases, media and credentials
out of Git:

```bash
cd /home/github/c-lara-2
git status --short
git diff --cached --check
git diff --cached --stat
git commit -m "Complete English and French Community Dictionaries localisation" &&
git push origin main
git rev-parse HEAD
```

Use the existing branch/review process if your checkout is not on `main`.

## AWS: install the combined accepted version

The original localisation patch changed JavaScript/CSS, so the combined deployment
**needs collectstatic**, even though the last two small patches do not add static
files. Normal backups suffice; this update does not rewrite content or media.
Let running AI jobs finish before stopping services.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git branch --show-current
git status --short
git rev-parse HEAD
git fetch origin
git log --oneline HEAD..origin/main
```

Expect a clean checkout on the normal deployment branch. Keep the old deployed SHA,
and confirm the incoming commits are the accepted laptop changes. Define the
existing protected-environment helper:

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
git merge --ff-only origin/main &&
clara_manage check &&
clara_manage migrate --check &&
clara_manage collectstatic --noinput &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Stop on any error; do not skip a failing check. If static collection reports a
permission error, the previously documented fix is limited to the generated static
directory:

```bash
sudo install -d -o ubuntu -g www-data -m 0755 /srv/C-LARA-2/platform_server/staticfiles
sudo chown -R ubuntu:www-data /srv/C-LARA-2/platform_server/staticfiles
clara_manage collectstatic --noinput &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Do not apply that ownership command to the repository, database or uploads.
There is no new pip install, environment change, gettext installation, Nginx
configuration or daemon reload required.

```bash
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD
```

Confirm all services are running and the SHA matches the laptop. On the public
site, test French/English switching and persistence, matching explanation-language
defaults, direct access to existing dictionaries, the next-step/People/attention
pages and word linking. Repeat the principal browsing checks on a phone.

## English/French content version

A friendly name is **L’anglais avec Finley**. In the existing **Language versions**
workflow, choose **English** as the target language and **French** for explanations,
then review the estimate and results as usual. Content conversion is a separate
owner-approved operation; installing this UI patch does not start it.

## Verification

All 680 Community Dictionaries tests pass. The existing focused lexicon/entry/photo
run passes 68 tests, and a temporary actual-page English/French smoke check covers
link/unlink messages, picture wording and synthetic-audio provenance. Template and
translation format checks pass; no schema changes are detected. No additional
permanent tests were added for these small display-only changes.

The incremental patch is verified against the exact preceding delivered version.
Manny reports that the earlier screenshot fixes work on the laptop; this last
change and the combined AWS/phone trial still need their human acceptance. No live
AWS deployment or paid provider call was performed here.
