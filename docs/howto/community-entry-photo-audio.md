# Existing-image interpretation and saved spoken audio

28 September 2026 follow-up. Apply after the original photo patch, its SDK import
repair, and `community_dictionary_photo_trial_notes.patch`. This increment adds
migration `0003_entry_photo_and_saved_audio`. No new Python dependency is required.
Manny subsequently reports this increment is working. The later
[defaults and named-voice follow-up](community-voices-and-defaults.md) changes
new-dictionary defaults, adds a voice menu and migration 0004, and brings the
suite to 64 tests. The installation below describes the preceding increment;
do not reapply its patches if they are already installed.

## Laptop installation: Windows Python under Cygwin

Stop `runserver` with Ctrl-C. Save both patches in `/home/github`, beside the
`c-lara-2` directory. Apply the documentation patch once:

```bash
cd /home/github/c-lara-2
git apply --check --whitespace=nowarn ../community_dictionary_photo_trial_notes.patch &&
git apply --index --whitespace=nowarn ../community_dictionary_photo_trial_notes.patch
```

`--whitespace=nowarn` preserves a trailing space in an archived verbatim user
message without printing a cosmetic warning. It does not relax patch matching.
If this documentation patch is already applied, skip that block.

Then apply the functional follow-up:

```bash
git apply --check ../community_dictionary_entry_photo_audio.patch &&
git apply --index ../community_dictionary_entry_photo_audio.patch
```

Stop if either patch check fails; do not force or reverse it. The two patches can
be applied to staged or committed earlier work; `--index` requires the affected
working files to match their staged versions.

Before migration, retain the usual local database/private-media backup. For a
default SQLite laptop with the server stopped, a timestamped copy of
`platform_server/db.sqlite3` preserves the existing database. If the laptop is
configured for PostgreSQL, use its usual database backup instead.

```bash
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

The suite now has 58 tests. Deliberately simulated TimeoutError/JSONDecodeError
messages may appear; the final result should be **OK**. Tests use a separate test
database. `-E` retains the laptop import-path workaround established earlier.
`--insecure` serves static CSS/JavaScript on this local development server with
`DEBUG=False`; it is not an AWS/Gunicorn option.

## Try an existing entry, including one uploaded earlier

1. Open the dictionary's **People → Dictionary settings**. Leave **Learn from a
   photo (OpenAI)** checked. Also check **Enable saved spoken audio (OpenAI)**,
   then press **Save settings**. Audio generation has separate permission.
2. Open your existing horse entry. Below its picture, choose **Learn from this
   photo**. The saved picture is already selected; no upload is needed.
3. Confirm permission and press **Identify this object**, then confirm the
   proposed object. Edit *en häst* to *häst* if desired and save the wording.
   As an editor, leave immediate acceptance checked if you want to use it now.
4. Back on that same entry, choose **Create spoken audio**. Check the displayed
   wording, consent to the request, and choose **Create audio preview**.
5. Listen, confirm sharing, and choose **Save audio to entry**. The recording is
   now an ordinary private dictionary contribution labelled as synthetic.
6. Leave the page and return. Both interpretation and audio generation remain
   available. The saved recording plays without another synthesis request.

You can skip interpretation when an entry already has the correct accepted
wording: create audio directly. You can also upload a photo normally, leave it
without wording, and return later to interpret it. The original Browse shortcut
for a new photo remains available.

Members' proposed wording needs editor acceptance before TTS can use it. Members
can generate from accepted wording and submit audio for normal review; they
cannot force immediate acceptance. Article/headword conventions remain editable.
An intervening wording change blocks saving or accepting an outdated generated
recording. The later [current-audio repair](community-current-audio.md) also hides
already accepted TTS from normal playback when its wording/language differs from
the entry. It remains labelled in contribution history; nothing is regenerated
or relabelled as different speech.

## Provider, cost, privacy and cleanup

- Saved TTS uses the existing real `OpenAITTSEngine`, explicitly selecting
  `gpt-4o-mini-tts`, WAV output and the configured language. This increment used
  `marin`; the later voice-menu patch keeps it as the default and adds choices.
  It sends only the accepted wording and language, not the photograph, dictionary
  history or human recordings. It never falls back to a test tone or another
  language/provider. The later voice-menu patch hides the separate, unsaved
  browser/device preview when saved TTS is enabled, to avoid switching voices.
- The initial language allowlist uses the provider's documented names or ISO
  codes, including Swedish/sv, Icelandic/is and Italian/it. It is a configuration
  gate, not a pronunciation-quality guarantee. Unsupported languages retain the
  human-recording workflow. Local dictionary lookup is deferred until discussion
  with Sophie; it is not implemented here.
- Server-key requests follow existing C-LARA credit settings; personal-key
  requests are paid through that user's OpenAI account. Empty personal keys do
  not silently switch to the server key.
- This binary-audio adapter returns no provider token counts. The application
  therefore records a clearly labelled **estimate**, using $0.015 per output
  minute plus UTF-8 input bytes at $0.60/million. The minute rate is an application
  approximation, not a quoted provider tariff. Official pricing checked on
  28 September lists $12/million output audio tokens and $0.60/million input text
  tokens; the provider invoice is authoritative. Usage records leave token
  counters at zero instead of inventing measured usage.
- `C_LARA_COMMUNITY_TTS_DAILY_LIMIT` defaults to 20 attempts per rolling 24 hours,
  independently per user across dictionaries and per dictionary across users.
  Failed/discarded attempts count. This is separate from the existing photo limit.
  Set it to zero to stop new synthesis globally, or uncheck the dictionary setting.
- A committed submission receipt prevents repeat POSTs from repeating a provider
  call. Automatic SDK retries are disabled. An interrupted/failed request can
  still incur a provider charge even without a recovered result; do not assume
  that no local usage row means no provider charge. Recovery pages never resend.
- Audio previews are creator-only and expire after 24 hours. Saving makes a
  separate contribution file and deletes the temporary copy after commit.
  Existing `expire_photo_studies` and its daily AWS timer now clean expired audio
  drafts as well. Saved contribution files remain. Provider and backup retention
  are separate from this local cleanup.

## Verification and deployment boundary

Development checks: 58 Django app tests pass with OpenAI SDK 2.8.1 and 3.19.2;
six existing offline audio-pipeline tests pass. The Chromium browser rehearsal
passes at iPhone 13 and Pixel 7 viewport profiles, including saved-image reuse,
same-entry updates, edited-word audio preview/playback/save, and replay after
reload. Provider calls are mocked and the audio fixture is a tone. Screenshots
were inspected. This is not a physical-device or live-TTS quality test.

For AWS after laptop acceptance and check-in: use the existing deployment runbook,
including `migrate`, `collectstatic --noinput`, and restarting Gunicorn. No extra
service is needed. Ensure the previously provided daily cleanup timer is enabled
and request timeouts allow at least 60 seconds. The TTS HTTP timeout is 30 seconds
per phase, not a guaranteed total wall-clock deadline. Migration 0003 is additive;
do not reverse it merely to disable these features.

References: [speech guide](https://developers.openai.com/api/docs/guides/text-to-speech),
[speech endpoint](https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create),
[model](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts),
[pricing](https://developers.openai.com/api/docs/pricing).
