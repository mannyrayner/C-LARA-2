# Entry recordings and direct logout

30 September 2026. Apply after the saving UX and account-password patches.
Manny confirms that admin password recovery worked and laptop testing resumed.

## What changes

An entry's **Listen and explore → Record audio** now opens a focused form showing
the entry's picture, word and meaning. Record, stop, listen, then **Save audio**.
There are Save audio buttons at the top and immediately below the recorder.
Either click explicitly confirms permission to share the recording. Audio is
saved as an entry contribution, so an editor's accepted recording appears in
Listen and explore. Ordinary members' recordings still await review. Existing
images and wording are preserved; saving the same submission twice is safe.

The old entry-page recorder belongs to Discussion, which explains why it had
**Add comment**, not a pronunciation save action. Spoken discussion remains
available under **Record a spoken comment**, now with **Save comment** and an
explicit one-click permission caption. It is folded initially and clearly
distinguished from the entry's pronunciation. A recovered spoken-comment draft
automatically opens its recorder; existing notes are not reclassified as audio.

**Logout** appears in the Community Dictionaries header. It signs out the shared
account using Django's CSRF-protected POST logout and returns to a dictionary-
branded login form; signing in there returns to the dictionaries. No visit to
the C-LARA project page is required. Other existing account/registration routes
remain available.

Logout participates in the same unsaved-draft warning as links: **Save and
leave**, **Keep editing**, or **Leave without saving**. Save and leave waits for
server confirmation before submitting Logout. A failed save keeps the session
and draft open. Live recording must be stopped before leaving. Leaving without
saving retains the best-effort recovery draft for the same account/browser;
browser storage loss or clearing can still remove it.

## Laptop installation

Stop the server. Save `community_dictionary_recording_logout.patch` in
`/home/github`, beside the checkout. The earlier two patches should remain
installed; they can remain staged.

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_recording_logout.patch &&
git apply --index ../community_dictionary_recording_logout.patch
```

Then check and restart:

```bash
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Expect 77 dictionary tests. Intentional mocked-provider error cases may print
TimeoutError/JSONDecodeError before OK. No migration or dependency update is
needed. Refresh the page; CSS/JavaScript version URLs have also been advanced.

Try Cathy's image/English entry → review → Edit words → Save → Record audio →
Stop recording → Save audio → play from Listen and explore. Then try Logout
with an unsaved recording, choosing Keep editing first. After acceptance, review
and commit the staged changes together; AWS uses the usual runbook including
`collectstatic --noinput` and Gunicorn restart. This patch is not yet deployed.

## Verification evidence

- 130 relevant Django tests pass: all 77 dictionary tests plus existing
  password/Profile/Admin tests. The seven new tests cover pronunciation saving,
  idempotency, unchanged wording, review restrictions, media permission,
  dictionary membership, spoken-comment separation, CSRF-protected logout and
  login redirect safety.
- The focused browser rehearsal uses native Chromium microphone capture with a
  synthetic sound file and disposable owner/member accounts. It reproduces the
  photo/English → Swedish → recording → save → playback workflow, plus logout
  during capture, Keep editing, failed save, successful Save and leave, leaving
  without saving, draft restoration, spoken comments and old consent-draft
  compatibility. Phone viewports are Pixel 7 and iPhone 13, not physical devices.
- An initial browser probe raced navigation and set a file on the preceding
  page. Explicit navigation waits corrected the probe. Actual recording and
  save/logout had already passed before that probe failure.
- The earlier saving/recovery browser rehearsal is also checked because logout
  now shares its navigation guard. No paid provider call or real account change
  is part of these tests.

Optional repeat of the focused rehearsal, with Playwright/Chromium configured as
for the existing browser experiments:

```bash
python -c 'from pathlib import Path; from experiments.community_dictionary.browser_rehearsal import main; main(Path("experiments/community_dictionary/record_logout_browser.cjs").resolve())' /tmp/community-record-logout
```

The helper always creates a disposable database. Human acceptance of these new
controls on the laptop and physical phones remains to be reported.
