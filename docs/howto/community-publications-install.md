# Install the first report and publication links

Patch: `community_dictionary_publications.patch`.
Base: `176df90` (fully automatic processing).

This is a complete patch containing the final paper sources and screenshots,
the ResearchGate source variant, publication records, and About-page links.
It replaces earlier **unapplied** `community_dictionaries_first_report.patch`
files. Do not apply both. If an earlier paper patch has already been applied,
stop when the check below fails and ask for an incremental patch; do not force it.

Only the About template and its existing test change application files. There
are no database, requirements, static-file, queue or environment changes.
Local verification: Django check and all 28 discovery/profile tests pass.
The two five-page PDFs were compiled and visually checked when prepared.

## Laptop

Download the patch to `/home/github/`, alongside the checkout. Start with a clean
working tree; if `git status --short` shows unrelated work, preserve it before
proceeding.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_publications.patch &&
git apply --index ../community_dictionary_publications.patch &&
git diff --cached --check
```

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary.tests.test_discovery_profiles
```

After the final `OK`, start or restart the usual laptop server and inspect
**About → Publications**. Both links should be visible even when logged out.

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git commit -m "Publish Community Dictionaries report and About links"
git push
```

The patch is already staged by `git apply --index`; no broad `git add` is needed.

## AWS

After the laptop commit is pushed, use the existing server checkout. Stop if the
tree is not clean or if the pull/check fails.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git status --short
git pull --ff-only
```

Run the existing management wrapper, or define it in this shell as follows:

```bash
clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu \
    --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}
clara_manage check &&
sudo systemctl restart gunicorn-clara2 &&
sudo systemctl status --no-pager gunicorn-clara2
```

Open About on the deployed site and follow both publication links. This patch
does not require `migrate`, `collectstatic`, a worker restart or an nginx restart.
