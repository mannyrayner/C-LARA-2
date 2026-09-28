# Existing-entry interpretation and saved TTS: 28 September 2026

Manny approves the preceding proposals, explicitly defers local dictionary lookup
until discussion with Sophie, and requests an installable patch for entry-level
photo interpretation, persistent generated audio, and returning to older pictures.
The full triggering message is archived with global workspace revision 21.

## Scope and implementation

Base: original photo feature, SDK repair and trial-notes patch, staged tree
`a2f938dd8a1b8ab55338270073a39a81b2cac915` on upstream main
`b7cb356e0a548b730c159bdf48a9bcb7dd31ced8`. Delivered as
`community_dictionary_entry_photo_audio.patch`, not pushed or deployed by the agent.

- The visible picture on an entry has a Learn from this photo action when enabled.
  It reuses that private stored picture and records source entry/image/version.
  Saving proposes wording to the same entry, retains its category and picture,
  and rejects stale text or deleted source material. No duplicate entry or image
  contribution is created. An old image works without an earlier AI draft.
- Saved audio has separate owner enablement. Generate from accepted edited
  wording, privately preview, then save through ordinary contribution review.
  Synthetic provenance retains text/version, language, model, voice and requester.
  Later wording edits do not relabel existing recordings; stale unsaved/pending
  generated audio cannot silently become the current wording's recording.
- Real C-LARA TTS engine reuse with a strict option that refuses its legacy
  instruction-dropping retry. Existing callers retain their prior default.
  No test-tone/provider/language fallback in the new path.
- Private range serving is shared with the existing media endpoint. Durable
  attempts/receipts, separate rolling quotas and existing credits/personal keys
  support retry-safe generation. WAV headers are normalized from actual PCM so
  streaming placeholder lengths do not break stored playback.
- New migration 0003 adds dictionary TTS enablement, source-image links and audio
  drafts. The existing cleanup command/timer now removes expired audio drafts.
  Lookup, video, generated pictures and autonomous operations are not implemented.

## Executed checks

- `manage.py test community_dictionary`: **58 passing**, under OpenAI SDK 3.19.2
  and 2.8.1. Includes the original 41 tests and 17 new entry/audio tests.
- `python -m unittest tests.test_10_audio.AudioTests`: **6 passing** offline
  pipeline tests. No API-enabled integration tests were run.
- Chromium **153.0.8010.0**, iPhone 13 and Pixel 7 viewport profiles: new-photo
  capture flow; leave and return to saved entry; interpretation without upload;
  same-entry wording update; generation from edited wording; audio preview
  playback; saving and replay after reload; image validation recovery and discard.
  No horizontal overflow or JavaScript errors. Screenshots inspected.
- System check and migration consistency checked during packaging; patch applies
  cleanly to the stated staged-tree baseline.

Tests use mocked provider responses. Browser screenshots show a solid-colour
fixture, and playable audio is a generated test tone; neither establishes real
recognition or pronunciation quality. The earlier horse result is Manny's live
laptop evidence for the preceding version, not a trial of this new saved-TTS path.

## Remaining acceptance and accounting limits

Manny should try an earlier uploaded photo, edit the article if desired, generate
audio and check it says the edited form, save it, leave the page and replay it.
Then test actual phone capture/playback after AWS deployment. Account access,
voice quality and latency for this particular TTS configuration are untested.

TTS accounting is explicitly estimated from audio duration/input byte count;
the binary endpoint does not return measured token usage here. Failed/interrupted
requests may incur provider charges without local accounting. Per-attempt limits
are not a server-wide budget reservation. These limits are disclosed in the UI and
[installation guide](../../docs/howto/community-entry-photo-audio.md).

This request continues the strategy of small user-driven improvements. It is not
evidence of reduced long-run maintenance work; Manny still installs and tests.
