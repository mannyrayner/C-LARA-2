# Working entry/photo/audio trial and a small voice/defaults follow-up

## Human evidence

On 28 September Manny reports that the preceding entry-photo/saved-audio patch is
"all working". His two remaining requests are to enable the AI options by default
and make TTS voice choice consistent, preferably with a menu and gender choice.
This is a broad success report during the ongoing laptop trial, not a new
instrumented action-by-action result or a report of AWS/physical-phone deployment
of the AI additions. No new timing, provider bill, pronunciation rating or device
details were supplied. The original horse recognition/device-speech report remains
separate evidence in `photo-laptop-trial-2026-09-28.md`.

## Implemented follow-up

- New-dictionary forms show photo interpretation and saved TTS checked, with
  independent opt-outs and explicit external-processing information. Existing
  dictionaries retain their saved choices. Unsupported TTS languages fail form
  validation with an instruction to use human recording.
- Thirteen named OpenAI voices are offered. Marin remains the default. A submitted
  choice is remembered per user and dictionary in a small database table and
  survives private-draft cleanup. The actual voice is attached to the attempt,
  provider request and saved contribution provenance, then shown on the entry.
- The catalogue does not assert undocumented gender labels. The provider exposes
  named voices; choosing and hearing a preview is the supported preference path.
- Saved-TTS-enabled photo confirmation uses the final-wording/saved-audio path,
  avoiding a different browser voice. Device preview is still available when
  saved TTS is disabled. Previously saved recordings are not regenerated.
- Migration 0004 changes creation defaults and adds preferences; it performs no
  data update of existing dictionaries. Per-request consent and existing review,
  private storage, source-version checks, quota and retry protections remain.

This changes image *interpretation*, not image generation. Human microphone
recording was already available without enabling AI. Commenting-language lookup
remains deferred until the discussion with Sophie. Broader runtime functionality
is not part of this patch.

## Development evidence

The working tree includes the previous entry/audio patch, whose baseline tree is
`e6ea3b5235feda305522a2b04b0922f0c1feeb34`; upstream base remains
`b7cb356e0a548b730c159bdf48a9bcb7dd31ced8`. This is an incremental patch, not a
claim that the new changes are already committed or on the server.

- 64 Django app tests pass under Python 3.12.14, Django 5.2.17 and OpenAI SDK
  3.19.2. Provider responses are mocked. Added checks cover default/opt-out
  behaviour, existing settings, unsupported languages, named-voice propagation
  through the actual adapter, saved provenance, personal preference persistence
  after draft expiry, invalid voices and changed-voice receipt replay.
- `makemigrations --check --dry-run` reports no missing migrations.
- Chromium 153, using Playwright's iPhone 13 and Pixel 7 viewport profiles, passes
  the saved-image interpretation and edited-word audio preview/playback/save
  workflow. It selects Cedar and confirms that the menu remembers Cedar on a
  later visit. Screenshots of the menu and saved entry were inspected; no
  horizontal overflow was observed. This is Chromium on Linux, not physical
  iPhone/Safari or Android/Chrome. The photo response is mocked and the audio is
  a short test tone, not a voice-quality sample.

No paid API call, remote push or AWS deployment was performed during development.
The new defaults/voices patch still needs Manny's installation and live listening
test. The earlier broad success report does not by itself establish quality for
all voices/languages, cross-device playback or unfamiliar-user uptake.

[Installation and trial](../../docs/howto/community-voices-and-defaults.md).
