# Simpler sentence and word pages — 9 October 2026

This incremental patch follows the queue-recovery release. Manny reports that
the resumed AWS conversion completed and that the French sentence/word links
now agree. It simplifies reading pages without changing stored dictionary data.

## What changes

- One **Words for this picture** list combines sentence words and picture tags.
  Sentence words come first. The same word entry appears once; distinct senses
  remain distinct even if their spelling is identical. Playback, translation
  reveals and word-page links remain available.
- **Show more options** contains editing, replacement recordings, photo additions,
  picture description for an already worded entry, pronunciation warnings,
  contribution versions, review and history. It starts closed on each visit and
  works without JavaScript. Pending contributions are counted in its summary.
- Missing wording, translation, pictures and current audio still have visible
  completion actions. Outdated synthetic recordings do not count as current
  audio. The existing wording/language/meaning consistency checks are retained.
- **Flag a problem** remains outside the options; discussion has its own
  expandable heading on entry pages. Related sentences remain visible.
- Word pages follow the same rule. Named voice details and pronunciation warnings
  remain available in the options. Warnings on generation/review screens remain.
- The additional-word menu manages picture tags. Words already used by the
  sentence remain linked through its vocabulary rather than offering a misleading
  picture-tag removal button for them.

This is presentation and list assembly only: no migration, dependency or static
asset change; no new provider calls or changes to credit, ownership or withdrawal.

## Laptop

Stop the development server. Download `community_dictionary_entry_options.patch`
beside the repository. Check the working tree first; stop if there are unrelated
changes that would be mixed into this commit.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_entry_options.patch &&
git apply --index ../community_dictionary_entry_options.patch
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary
```

Start the server with your usual command:

```bash
../.venv/Scripts/python.exe -E manage.py runserver
```

Check a completed sentence and a completed word. Listen, reveal a translation,
follow a word link and expand Show more options. Confirm editing, recording and
pronunciation warnings are still accessible there. An image-only entry should
still offer Describe this picture; a word without current audio should still
offer recording/generation. On a sentence page, a word linked through both routes
should appear just once. Check Flag a problem and Discussion as well.

## Check in after acceptance

The patch is already staged. Review its scope before committing:

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat &&
git commit -m "Simplify dictionary entry and word pages" &&
git push
git status --short
```

## AWS

Finish any active AI job first: fallback background tasks are interrupted by a
Gunicorn restart. This update needs only a brief code/service deployment.

```bash
sudo -iu ssm-user
umask 022
cd /srv/C-LARA-2
git branch --show-current
git status --short
```

Expect `main` and a clean working tree. Then:

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git pull --ff-only
```

Stop if the pull fails. Run the check with the service identity and protected
environment, then start services only if it succeeds:

```bash
sudo systemd-run --wait --pipe --collect \
  --property=User=ubuntu \
  --property=Group=www-data \
  --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
  --property=EnvironmentFile=/etc/clara2.env \
  /srv/C-LARA-2/.venv/bin/python manage.py check &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker

sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

No `migrate`, `pip install`, `collectstatic`, nginx restart or environment-file
permission change is needed for this patch. Refresh an entry in the browser and
repeat the short reading/options check. Keep `DEBUG=False`. If necessary, this
presentation patch can be reverted by reverting its commit and restarting services;
the earlier queue repair and saved dictionary data should remain in place.
