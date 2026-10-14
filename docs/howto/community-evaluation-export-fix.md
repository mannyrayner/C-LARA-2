# Readable evaluation CSV: install and re-export

Apply `community_dictionary_evaluation_export_fix.patch` on top of the original
evaluation patch and its display follow-up, both already deployed. This changes
the CSV export only: no migration, dependency, static-file or environment changes.
Existing sets and ratings remain intact. No AI calls are made.

## Laptop

Stop the local server and download the patch to `/home/github/`, beside the checkout.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_evaluation_export_fix.patch &&
git apply --index ../community_dictionary_evaluation_export_fix.patch &&
git diff --cached --check
```

If the apply check fails, stop and retain local changes.

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary.tests.test_evaluation
```

Expect **39 tests** and final `OK`. No migration command is needed for this patch.
Restart as usual if you want to try the export locally:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Open an existing closed evaluation set, view its results and download the CSV
again. The original columns remain in their original order. New columns at the
right include the sampled entry text and translation, the particular word and
its translation for word judgements, the word's form in the sentence, and the
complete extracted list for vocabulary judgements. Both languages' listening
competences are now included in the export. Text is the original evaluated version.

## Check in

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat
git status --short
git commit -m "Add readable snapshot content to evaluation CSV exports" &&
git push origin main
```

## AWS

This assumes AWS already has migration 0024 and the display fix, as reported.
The web service needs a brief restart; background workers are unchanged.

```bash
sudo -iu ssm-user
umask 022
cd /srv/C-LARA-2
git branch --show-current
git status --short
```

Expect `main` and a clean tree. Define the usual helper:

```bash
clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu \
    --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}
git pull --ff-only &&
clara_manage check &&
clara_manage migrate --check &&
sudo systemctl restart gunicorn-clara2
```

The migration command only checks for unapplied migrations. If a check fails,
stop and report its output before restarting. This update does not require
`collectstatic`, `pip install`, a database migration or an nginx restart.

```bash
sudo systemctl status --no-pager gunicorn-clara2
```

Once the web service is running, return to the closed **Finley's Swedish** evaluation
and download its CSV again. There is no need to repeat the evaluation. Keep the
original CSV as the first export; save the new download separately for comparison.
