# Pictures and words: manual links

1 October 2026 (Adelaide). Incremental patch based on GitHub `main`
`b945623017bb1c938a9273353a62bec5bd808de5`, including the saving, password and
recording/logout changes accepted on Manny's laptop. Manny now reports that this
increment works first time and the sofa/cat example behaves exactly as intended.
He plans to check it in and test against the larger server dictionary. This is
human laptop acceptance; AWS deployment and phone acceptance of this increment
remain pending.

## Try it

1. Open an accepted picture as a dictionary owner or editor. Under **More words
   for this picture → Link more words**, choose an existing word/phrase and press
   **Link word**. For example, add `katt` to the `soffa` picture.
2. Each extra word has **Listen**, **Translation**, and **Word page →**. Translation
   opens on tap and starts closed; listening stays on the picture. A second
   recording pauses the first. There is no autoplay or AI call.
3. **Word page →** shows the word's original pictures plus pictures linked from
   other entries. Tap a picture to return to that particular picture's entry.
4. **Browse → Pictures / Words** switches between the familiar cards and an
   alphabetical list of accepted words/phrases. Both modes retain search and
   category filters. Picture searches also match linked words and meanings.
5. **Link more words → Remove link to …** removes only the extra association.
   The picture, word, audio and original association remain.

For the first trial, link `katt` to two pictures, and a second existing word to
one of those pictures. Listen and reveal a translation without leaving that
picture; then follow the word page and return through its picture gallery.
Repeat as an ordinary member: browsing/playback should work, link editing should
not be offered. Try this on the laptop before deployment and a physical phone.

## Installation on the laptop

Stop the development server. Save `community_dictionary_picture_word_links.patch`
in `/home/github`, beside the checkout. The current main commit already includes
the preceding patches; do not reapply those older files.

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_picture_word_links.patch &&
git apply --index ../community_dictionary_picture_word_links.patch
```

After a successful apply:

```bash
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

**Migration 0005 is required.** It adds a link table; existing entries/media are
not rewritten. Expect 95 dictionary tests. Mocked TimeoutError/JSONDecodeError
logs test intentional failures and are normal before the final OK. There is no
new package dependency or frontend build. Refresh the browser after restarting.

Review/commit after acceptance:

```bash
cd /home/github/c-lara-2
git diff --cached --check
git diff --cached --stat
git commit -m "Link dictionary pictures and words with inline playback"
git push
```

AWS uses the existing runbook after the commit is on main: normal database and
private-media backup, `git pull --ff-only`, environment loading, `manage.py check`,
**`manage.py migrate`**, **`manage.py collectstatic --noinput`**, and the usual
service restarts. No nginx or service-unit change is needed. A code rollback can
leave the unused link table in place; reversing migration 0005 deletes its link
records, so do not reverse it merely to run the old code.

## Deploy the accepted increment to AWS

The documentation-only `community_dictionary_word_links_acceptance.patch` applies
**after** the functional picture/word-link patch. It records Manny's laptop result
for the repository Assistant and global workspace; it changes no application code.
Apply it with the same `git apply --check` / `git apply --index` sequence before
committing both patches together. There is no need to rerun the app tests solely
for this documentation update; the implementation's 95-test result is unchanged.

On the laptop, check `git branch --show-current` (expected `main`) and
`git status --short`, review the staged diff/stat, commit and push. Preserve any
unrelated work; do not indiscriminately stage the entire checkout. The original
functional patch's `--index` apply already staged its files.

On AWS, start in the normal account and checkout:

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
git branch --show-current
git status --short
```

Expect `main` and an empty status. Use the normal database/private-media backup
procedure before the migration, then deploy:

```bash
git pull --ff-only &&
. .venv/bin/activate &&
python -m pip install -r requirements.txt &&
cd platform_server &&
set -a && . /etc/clara2.env && set +a &&
python manage.py check &&
python manage.py migrate &&
python manage.py collectstatic --noinput &&
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
```

Migration output should include `community_dictionary.0005_image_word_links`.
Neither nginx configuration nor systemd unit files change in this increment, so
nginx restart and `daemon-reload` are unnecessary. The worker restarts retain the
usual shared-platform runbook. Refresh the browser and check both ordinary
C-LARA-2 and Community Dictionaries. Laptop data is not transferred by `git push`;
the existing server entries acquire their original word/picture associations
automatically, and new extra links can be added there.

Repeat the sofa/cat workflow on the larger server dictionary, then a phone: link
two existing words, listen/reveal translations, follow a word's gallery back to a
picture, and remove one extra link. The original word, picture and audio should
remain. Record the phone/browser if reporting new device acceptance.

## Scope and data behaviour

- Extra associations refer to a **specific accepted image contribution** and an
  existing accepted-word entry in the same private dictionary. Selecting a new
  main picture does not move the old picture's links. **Open this picture** in
  contribution history opens another accepted image for linking.
- Each picture's own entry remains its original association automatically. No
  backfill is needed. Words mode includes entries with accepted written forms,
  including phrases; picture/audio-only entries remain accessible in Pictures.
- Owners/editors can link/unlink immediately. Members can explore; this first
  cut has no member proposal/review workflow for extra links. Adding an already
  linked word again is safe, and separate additions do not replace others.
- Words are reused by entry identity, not merged by spelling. Two homographs
  remain separate; the editor's menu includes their meanings. Word edits and
  recordings update their linked appearances on the next page load. Clearing
  accepted wording hides its word page/links until wording is restored.
- Listen uses the newest accepted recording compatible with the current wording
  (existing stale-TTS filtering applies). The word page offers other accepted
  recordings. Human recordings have no automatic transcript-match check.
- Removing a picture removes its extra links. Removing a word entry removes
  incoming links but never deletes another entry's picture. Owner exports now
  use manifest version 2 and include link records and attribution without
  duplicating image/audio files. Existing backup requirements still apply.
- Translation disclosure is a learning convenience, not an access restriction;
  the text is already in the member-authorized page. Native audio and disclosure
  remain usable without JavaScript. Link/unlink navigation protects unsaved
  discussion through the existing Save and leave dialog.

No AI tagging, automatic spelling merge, image regions, or new-word creation is
added here. Phone usability and usefulness with the fifty-entry dictionary still
need human feedback. See the [implementation evidence](../../experiments/community_dictionary/picture-word-links-2026-10-01.md).
