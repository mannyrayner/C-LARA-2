# Carrier-audio language extension: installation

```text
Community Dictionaries: carrier audio in additional languages
18 October 2026

Patch: community_mwe_audio_languages.patch
Base: 15b87f3e57bc40ced11acb3da2962d3208d18e4d
      Add optional MWE audio regeneration and paired evaluations

This is an INCREMENTAL patch after community_mwe_audio_pilot.patch. Do not apply
that older patch again. Migration 0025 must already be installed.
No new migration, Python dependency, static file, environment or queue change.
Installing this update does not itself regenerate audio or send paid requests.

WHAT CHANGES

- German, Italian and Icelandic use the existing owner-only batch for accepted
  multi-word entries with current AI audio. Selection uses spaces; single-word
  compounds and unspaced lemmas such as German "anziehen" are not selected.
- Japanese has an explicit checkbox list of eligible word entries, with nothing
  checked by default. Choose only entries you want to try. No automatic MWE
  classification or segmentation is attempted. Compound words such as 対局 and
  対岸 can be selected deliberately, but satisfactory audio can simply be kept.
- The estimate page can create a baseline evaluation of exactly its entries.
- French/Swedish prompts, extraction parameters, cost estimates and recipe ID
  stay unchanged. Existing successful carrier replacements are skipped.
- Human recordings, sentences, old files, withdrawal controls and restoration
  remain protected. Five completed attempts maximum; no automatic network retry.
- Ordinary future word generation and English-homograph treatment are unchanged.
  This is an optional regeneration batch, not a new global generation default.

1. LAPTOP: apply and check

Stop the development server first. Save the patch next to the repository:
/home/github/community_mwe_audio_languages.patch

cd /home/github/c-lara-2
git branch --show-current
git status --short
git log -1 --oneline

Expect main and a clean checkout containing the previous MWE pilot commit above.
If there are unrelated changes, preserve them and stop before applying.

cd /home/github/c-lara-2
git apply --check ../community_mwe_audio_languages.patch &&
git apply --index ../community_mwe_audio_languages.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check

Expected: 653 tests, final OK. Simulated failure messages during tests are normal.
The migration check should succeed without applying anything. Stop on an error.

Start the local server as usual:

../.venv/Scripts/python.exe -E manage.py runserver 127.0.0.1:8000 --insecure

--insecure is for laptop development static files only.

2. CHECK IN

After the laptop checks, review the intended app/docs/experiment changes:

cd /home/github/c-lara-2
git diff --cached --check
git diff --cached --stat
git status --short

Then, on main:

git commit -m "Extend carrier audio trials to four additional languages" &&
git push origin main
git rev-parse HEAD

Keep the commit ID to compare with AWS. Do not commit databases, credentials or
local media. The patch includes aggregate and paired French/Swedish evaluation
evidence and a new global-workspace assessment; original ratings remain intact.

3. AWS: deploy

Wait for running AI jobs to finish before stopping services. Use one block at a
time and stop on any failure. There is no database migration or media rewrite in
this update, so it does not require a new full media archive. Keep normal backups.

sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git branch --show-current
git status --short

Expect main and a clean checkout. Define the helper in this shell:

clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu \
    --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}

Stop the three application services, then update:

sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git pull --ff-only &&
clara_manage check &&
clara_manage migrate --check &&
clara_manage community_queue_check --tasks 20

The existing bounded local Django Q adapter is valid. Do not change USE_REAL_DJANGO_Q.
Expected queue check: 20/20 probes, peak at or below the configured limit, zero
remaining task connections. If any check fails, stop and preserve its output.

No pip install, collectstatic, daemon-reload or nginx restart is needed for this
patch. Once the checks succeed:

sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD

All three services should be running, and HEAD should match the laptop commit.

4. LISTENING TRIAL

Start with Finley's Italian, then German. For each dictionary separately:

A. Open Evaluate, choose Word audio only, tick Only multi-word entries in French,
   Swedish, German, Italian or Icelandic, and select all eligible pages (or a
   random sample). Finish, close and export before replacing recordings.
B. Settings -> Regenerate AI expression audio -> Show estimate.
C. Review the count and allowance; Approve and regenerate sends paid requests.
D. On the closed baseline, choose Repeat these word-audio items, then rate, close
   and export the follow-up. Keep both CSVs, including failed/unchanged entries.
E. If needed, Restore earlier audio from this job restores earlier recordings
   where there have been no later edits, new recordings or withdrawal.

Alternatively, the free estimate has Create word-audio baseline for these entries.
This is particularly useful in Japanese: select a few entries, prepare the
estimate, create the exact-entry baseline, finish/close/export, then approve.
If the estimate expires during evaluation, prepare a new one and select the same
Japanese entries. After regeneration, repeat the original closed evaluation.
The Japanese baseline is labelled as selected word audio, not automatic MWE data.

If you already judge Japanese recordings satisfactory, leave them unselected.
Icelandic and Japanese pronunciation gains remain untested; limited listener
proficiency should be recorded with the results. New native-language carriers may
need revision after listening. Structural extraction checks do not certify speech.

After a batch, this optional read-only check reports outstanding credit holds:

clara_manage community_credit_audit --username 'mannyrayner'

5. VERIFICATION HERE

- All 653 Community Dictionaries tests passed on Linux.
- Focused carrier/batch/evaluation run: 65 tests passed.
- Django checks and migration consistency passed; no schema changes.
- French/Swedish requests, full instructions, estimates and recipe ID were
  compared with the previous commit and are unchanged.
- Provider calls were mocked. No paid generation, AWS deployment or physical-phone
  acceptance test was performed here for this extension.
```
