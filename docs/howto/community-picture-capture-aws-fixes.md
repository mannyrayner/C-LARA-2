# Picture-description browsing and sentence-audio fixes

7 October 2026. Apply this incremental patch on top of the deployed picture-description,
editable-vocabulary and image-only-copy release (GitHub main observed at
`06747ea28008a6303b6f0587490f55217186eeea`). No migration, dependency, environment,
nginx or service-unit change is needed. This patch does not rewrite existing content.

## What changes

- The normal **Pictures → Accepted** view shows a completed sentence card instead
  of also showing its unlabelled source image card. The original remains accessible
  through **Original picture and discussion** and **Pictures → All**. Sources with
  independent wording, discussion, audio, pending work, manual word tags or another
  undescribed image stay visible. A withdrawn/archived description no longer hides
  its source. This is a display query, so existing records benefit immediately.
- Sentences and spoken confirmations use sentence-reading instructions, rather
  than requesting dictionary-word definitions/IPA when a token also occurs in English.
  Swedish `En` triggered that extra path in the reported sentence. Word/MWE audio
  retains its established homograph coaching. The sentence client timeout is 60
  seconds instead of 30; a timeout is not automatically retried. Silence detection
  and its single completed-silent-output retry remain in place.
- Saved audio progress updates in place without repeatedly reloading the page.
  Existing playback, open translations and unsaved vocabulary edits are preserved.
  Failed attempts show a bounded reason where recorded and a link to an explicit
  new audio request. Status polling never starts a paid request.

The cat/chess sentence is **42 characters**, below the application's **255-character**
limit. That limit did not reject this sentence. Without the original AWS exception,
we cannot establish why that particular request failed. The new logs identify the
stage and broad failure category without logging the text or provider message.
These fixes require a new live listening test; mocked tests do not establish TTS quality.

## Laptop: apply and test

Stop the laptop development server. Download
`community_dictionary_picture_capture_aws_fixes.patch` to `/home/github/`.

```bash
cd /home/github/c-lara-2
git status --short
git branch --show-current
```

Expect clean `main` containing the release already deployed to AWS. Investigate
unexpected local changes before applying; do not restore unrelated work.

```bash
git apply --whitespace=nowarn --check ../community_dictionary_picture_capture_aws_fixes.patch &&
git apply --whitespace=nowarn --index ../community_dictionary_picture_capture_aws_fixes.patch &&
git diff --cached --check -- . ':!docs/global_workspace/archive/inputs/**'

cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expect **334 tests**, ending `OK`. Deliberately simulated failures can produce log
messages during tests. No migration is added, and the test database is separate.
Then start your usual server:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Refresh the browser. In an image-only test dictionary, describe an image and save:
only the sentence card should appear in the default Pictures view for that image.
Try the cat/chess sentence; check sentence and word audio. Keep one clip playing or
its translation open while the remaining recordings finish: the page should stay put.
A live generation uses the usual consent and provider charges.

## Check in after laptop acceptance

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git diff --cached --check -- . ':!docs/global_workspace/archive/inputs/**'
git diff --name-only
git status --short
```

The patch is already staged. The whitespace check excludes verbatim archived
messages, which preserve their original trailing spaces. Expect only Community Dictionary code/tests and the
accompanying docs/global-state records. Keep databases, backups, media and credentials
out of Git. If the unstaged diff is empty and the staged files are as expected:

```bash
git commit -m "Fix picture description cards and sentence audio progress" &&
git push origin main &&
git rev-parse HEAD &&
git status --short
```

Keep the commit ID for comparison on AWS.

## AWS: short code/static update

Let any active AI jobs finish and choose a quiet interval. Both apps share these
services. This code-only patch needs no new database/media backup procedure or
schema change; keep the existing normal backups. Do not repeat the old withdrawal
reset or migration-0015 installation sequence.

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git branch --show-current
git status --short
export CLARA_CAPTURE_PREVIOUS_COMMIT="$(git rev-parse HEAD)"
. .venv/bin/activate
set -a && . /etc/clara2.env && set +a
```

Expect clean `main`. Retain the previous commit ID for recovery. Then:

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git pull --ff-only origin main &&
git rev-parse HEAD
```

The printed SHA must match the laptop. If not, stop and inspect. After a match:

```bash
cd /srv/C-LARA-2/platform_server
python manage.py check &&
python manage.py migrate --check &&
python manage.py collectstatic --noinput &&
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

If any check fails, stop there and share the error; do not change DEBUG or reset the
DB. A known duplicate favicon warning from collectstatic is unrelated. No nginx
restart or systemd daemon-reload is required.

```bash
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Check all three remain `active (running)`, then refresh the browser. The script URLs
have new version suffixes; `collectstatic` is essential.

## Retest the already-created AWS examples

1. In the image-only copy, open **Pictures → Accepted**. The redundant blank source
   cards should disappear; the wine and cat/chess sentence cards remain. No cleanup
   or re-description is needed.
2. Open the existing cat/chess **sentence** page, choose **Create spoken audio**,
   create a preview, listen, then **Save audio to entry**. An editor/owner can publish
   it immediately; an ordinary member's manual audio save follows normal review.
3. Describe another image and check progress/audio without repeated page reloads.
4. Continue the broader trial. Record MWE examples; broader MWE refinement remains
   deferred until after this functionality assessment.

If speech fails again, send the displayed reason and these narrowly filtered logs:

```bash
sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 \
  --since "2 hours ago" --no-pager \
  --grep='Capture speech.*failed|Audio study.*failed'
```

For service startup failures instead, use:

```bash
sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 \
  -u project-understanding-worker -n 80 --no-pager
```

Keep DEBUG=False and redact credentials/private content from any unrelated log
lines. Existing failed attempts are retained and never automatically re-billed;
use the explicit retry control for a new paid attempt.
