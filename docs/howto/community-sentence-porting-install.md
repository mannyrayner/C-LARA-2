# Sentence language-porting follow-up: installation and trial

8 October 2026. Apply on top of the image-only-copy review release just tested.
No new migration, dependency or stylesheet change. Do not delete the existing
French destination or launch another full conversion before checking its results.

## Laptop

Let active AI jobs finish, then stop runserver. Save
`community_dictionary_sentence_porting.patch` in `/home/github/`.
Previous accepted patches may still be staged; this follow-up can be applied on top.

```bash
cd /home/github/c-lara-2
git status --short
git diff --name-only
```

The unstaged diff should be empty; investigate unexpected changes rather than
resetting them. Then:

```bash
git apply --check ../community_dictionary_sentence_porting.patch &&
git apply --index ../community_dictionary_sentence_porting.patch &&
git diff --cached --check
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expect **391 tests**, ending `OK`; simulated timeout/failure messages are intentional.
No new migrations are added; this baseline already includes migration 0017.
Stop on unexpected failures. Start normally:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

## Small trial and recovery

1. In a small Swedish dictionary containing sentence descriptions, choose
   **Settings → Create a version in another language**. Select French/English.
2. The estimate should include sentences, not only vocabulary entries. Approve it
   after checking the cost. Background processing produces private previews.
3. On the result page, choose **Continue reviewing and saving**. Check the whole
   sentence and its audio, then use **Save and next**. Save its words too.
4. Confirm that Pictures and Sentences show the sentence with its image, Words shows
   its vocabulary, and the links work in both directions. Try playing word audio
   from the sentence page. The source must remain unchanged.
5. **Estimate an update** without changing the source should skip the saved entries.
   This estimate itself makes no paid calls.

For the French attempt already made: open the original Swedish dictionary's
language versions, select that existing version and return to its **Latest job**
or **Previous results**. Finish reviewing existing word results first. Then use
**Estimate an update** on the **same version** to add missing sentences. Check
counts and cost before approval. An owner-only banner in an empty/partly populated
new dictionary also links to pending results. See the full recovery discussion in
`docs/howto/community-sentence-porting.md`.

Do not choose Cancel/discard just to empty the review queue: doing so loses usable
previews and may require paying for those entries again. Already-saved entries
remain intact. If a job is still running, allow it to finish before updating code.

## Check in after laptop acceptance

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git diff --cached --check
git diff --name-only
git status --short
```

Expect only the intended app code/tests, experiment scripts/docs and global-state
records, plus any preceding accepted patches still staged. No databases or keys.
Once that is correct:

```bash
git commit -m "Port picture-description sentences with vocabulary and audio" &&
git push origin main &&
git rev-parse HEAD &&
git status --short
```

## AWS

Let AI jobs finish before stopping workers. This is a code-only release with no
special database/media migration; keep the usual backups. Start from clean main:

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git branch --show-current
git status --short
. .venv/bin/activate
set -a && . /etc/clara2.env && set +a
```

Expect `main` and no status changes. Then:

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git pull --ff-only origin main &&
git rev-parse HEAD
```

Check the SHA matches the accepted laptop commit. Continue only if it does:

```bash
cd /srv/C-LARA-2/platform_server
python manage.py check &&
python manage.py migrate --check &&
python manage.py collectstatic --noinput &&
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Collectstatic also covers any preceding changes not yet deployed. Keep DEBUG=False;
no nginx restart, daemon-reload or pip install is needed for this patch. Confirm all
services remain active, then try the existing French version recovery above.

The patch was verified with mocked translation/speech and Linux Chromium at mobile
and desktop widths. Live French quality, pronunciation, large-dictionary timing,
Windows and physical-phone acceptance remain for your trial.
