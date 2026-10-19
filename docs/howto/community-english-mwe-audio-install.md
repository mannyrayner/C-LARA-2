# English carrier/extraction audio

19 October 2026

Patch: `community_english_mwe_audio.patch`

Base: `7e7e6d58d33fbf3460a43d6206e59d2e143f7624`
(`Complete English and French Community Dictionaries localisation`), confirmed
identical to the previously delivered code and now reported installed on AWS.

## What changes

English joins the existing optional **Regenerate AI expression audio** batch.
For example, the engine reads:

> We begin. in front of. We are finished.

The English instructions request all three parts, around 600 ms silence between
them, and a coherent middle expression with neutral intonation, natural stress
and linking. The existing structural checks extract the middle part. No British
or American accent is newly imposed; this follows the existing native-English
instruction policy and retains the recording's voice.

The estimate page and MWE evaluation filter include English; the modified controls
have French translations. Existing French/Swedish/other-language prompts, recipe
identifier, extraction parameters and retry rules are unchanged. Previous successful
carrier replacements remain protected.

This extends the optional regeneration batch. Ordinary future word/sentence
generation and language-port audio keep using their existing synthesis route.
Only accepted word entries containing 2–12 space-separated words, up to 120
characters and without sentence-ending punctuation are candidates. This is a
conservative expression-selection heuristic, not automatic linguistic annotation.
Single words, sentence entries, human recordings and current successful carrier
replacements are excluded. Each shared word page is processed once.

Old recordings are retained. Replacement is published only after extraction
succeeds, and the existing guarded restoration action can restore earlier audio.
Up to five completed attempts are allowed; unknown-cost/network failures are not
automatically repeated. Estimates count the full carrier recording, including
failed extraction attempts. No provider call is made by installing this patch or
requesting an estimate.

## Laptop installation

Stop the development server and save the extracted patch next to the repository:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
git apply --check ../community_english_mwe_audio.patch &&
git apply --index ../community_english_mwe_audio.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py makemigrations --check --dry-run community_dictionary &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expect **685 tests, OK**, and no migration changes. Preserve unrelated work if the
patch check fails. Compiled French translations are included, so GNU gettext is
not required to install the update. Restart as usual:

```bash
../.venv/Scripts/python.exe -E manage.py runserver 127.0.0.1:8000 --insecure
```

Open an English dictionary's Settings. Confirm the expression-audio pilot now
accepts English and displays the estimate control. The estimate is free. A listening
trial can be made on AWS after deployment, where *L'anglais de Finley* is available.

Review and commit the patch after the laptop checks:

```bash
cd /home/github/c-lara-2
git diff --cached --check
git diff --cached --stat
git commit -m "Enable English carrier extraction for expression audio" &&
git push origin main
git rev-parse HEAD
```

Use the normal branch/review process if your checkout is not on `main`.

## AWS installation

Let running AI jobs finish. Keep normal backups; this extension does not rewrite
the database or media. It adds no dependency, migration, static file, environment
variable or queue configuration. Since the localisation/static changes are already
installed, **this patch needs no collectstatic**.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git status --short
git rev-parse HEAD
```

Expect a clean checkout. Define the established management helper in this shell:

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
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker

sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD
```

Stop on any error and preserve the output. Confirm the deployed SHA matches the
laptop and all three services are running. No Nginx restart or daemon reload is
needed. Both web and worker services must run the new English recipe code.

## Paired listening trial on L'anglais de Finley

1. Open **Settings → Regenerate AI expression audio**. In French this is
   **Paramètres → Régénérer l’audio des expressions par IA**.
2. Choose **Afficher l’estimation — aucun appel à l’IA à ce stade**. Inspect the
   included expressions, voice, estimate and refundable allowance. Human audio
   and single-word entries should be absent.
3. Before approving replacement, choose **Créer une évaluation de référence de
   l’audio de ces mots**. Rate and close that baseline. This freezes exactly the
   quoted entries with their current audio. If the quote expires while you rate,
   prepare a new estimate and check its entries before approving it.
4. Review the estimate/allowance, then explicitly choose **Autoriser et régénérer**.
   This sends paid requests. Existing audio remains available until each new
   extracted recording succeeds; completed replacements publish automatically.
5. On the closed baseline choose **Réévaluer l’audio de ces mots**, then listen,
   rate, close and export the comparison. Include unsuccessful/unchanged items so
   the result describes the whole trial, not just its best recordings.
6. If needed, **Restaurer l’audio précédent de cette tâche** restores the earlier
   recordings where no later content/permission change prevents it.

The normal Evaluate form also supports an English multi-word-only sample. The
baseline created directly from the estimate is the simplest way to bind the
comparison to precisely this batch.

## Evidence and remaining question

All 685 Community Dictionaries tests pass. The 31 carrier/batch tests include five
new English regressions for phrase selection, actual mocked-WAV extraction,
queue publication/restoration, protected human/single-word recordings and exact
paired evaluation membership. Ordinary English synthesis and the existing
cross-language homograph guidance remain covered and unchanged. Template,
translation-format and migration consistency checks pass.

Provider calls in these tests are simulated. This extension has not yet been
listened to on the real English dictionary; structural extraction checks cannot
certify pronunciation, stress, sense disambiguation or prosodic improvement. The
paired listening trial supplies that evidence. The patch itself has not been
deployed to AWS or used for paid generation here.
