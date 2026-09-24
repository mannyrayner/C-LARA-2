# Iteration 2 — microphone feedback and discoverable words

Date: 24 September 2026. Status: incremental repair prepared and locally tested;
Manny's laptop retest and physical-phone trials remain pending.

## Human feedback and baseline

Manny reports successful installation and local login, dictionary creation,
picture upload, MP3 upload and image browsing. Audacity recording initially also
failed, then began working after a Voice Mode conversation; browser recording
still fails. The cause of this change is unknown. His two Swedish entries each
have an uploaded picture and audio file. He subsequently confirmed that words,
translations and categories work after explanation. That is a discoverability
problem, not missing text storage or search functionality.

The privately supplied M4A is 1,397 bytes: Opus in an MP4 container, 48 kHz mono,
container duration 2.420958 seconds. Local FFmpeg decoding produced 114,240 mono
samples, all exactly zero. This establishes silence in that file; it does not
establish which device, permission, driver or browser behavior caused it. The
recording itself is not included in the repository or patch.

- Base: the exact delivered `community_dictionary_prototype_01.patch` applied to
  bootstrap `bc21188595bae9f2ee89c080243a76fdd4a960b1`. Prototype 1 SHA-256:
  `9a25630818a86c80356c075b38d4b7eae4fbf6082defc5420a6e6ff4355ebc77`.
- Delivered artifact: `community_dictionary_repair_02.patch`. This is incremental,
  not a replacement for prototype 1. Its checksum is supplied at delivery.
- Manny's resulting implementation commit is not yet supplied. Packaging uses a
  local snapshot of the delivered file tree, not an invented upstream commit.
- Same assistant in the Codex work environment; no delegated agent. Exact model
  identifier, billed cost and total elapsed work were not independently measured.
- Manny describes iteration 1 as taking 45 minutes. Preserve that as a human
  estimate, not an independently timed result or a claim of one model invocation.
  This iteration also includes multiple implementation and test passes.

## Changes

- A named microphone selector, explicit **Check microphone** action, live level
  meter and selected-input feedback. The preferred device is remembered locally.
- Specific guidance for denied permissions, unavailable devices and capture
  failures. The check stops after 30 seconds; recordings retain the 90-second cap.
- Capture requests disable echo cancellation, noise suppression and automatic
  gain adjustment. This avoids requesting call-oriented processing for short
  pronunciations; it is not a confirmed fix for Manny's Windows input issue.
- Prefer explicit AAC/MP4 when the browser supports recording it, otherwise
  supported Opus/WebM/Ogg or the browser's available format. No transcoding.
- Inspect the recorded samples where decoding is available; otherwise use the
  live signal measurement. A detected silent take is rejected while preserving
  any previous take. Very quiet audio gets a warning. If neither check can verify
  sound, the app asks the user to listen; it does not claim verified audio.
- Separate the recorder from draft/submission code, keep sharing blocked during
  capture/checking, and release microphone tracks when finished or leaving.
- Show optional word, translation/meaning and category fields without expanding
  a hidden section. Labels use dictionary language settings. Entries prominently
  offer **Add words** or **Edit words**; browsing names words and translations in
  its search prompt. Existing text storage, search, review and history are reused.

No migration, dependency, AI service or practice feature is added. Existing
entries, media and text remain compatible. Media contributions to an existing
entry link to the explicit word-edit form rather than submitting empty text.

## Verification

Environment: Linux, Python 3.12.14, Django 5.2.17, Pillow 12.3.0, SQLite;
Node 24.19.0 and Chromium 153.0.8010.0. Manny's earlier installation trace also
reported all 20 version-1 app tests passing on Windows/Python 3.11; the repair
has not yet been tested there.

```bash
# From platform_server, with the development environment active:
python manage.py test community_dictionary --verbosity 1
python manage.py check
python manage.py makemigrations --check --dry-run community_dictionary
# From the repository root, with optional Playwright/Chromium configured:
python experiments/community_dictionary/browser_rehearsal.py
```

Results: **21 Django tests pass**, system checks pass, no missing migrations.
The added workflow test attaches and accepts words after media, searches Swedish
and English with a category, verifies media identity/status preservation, and
checks that a member's later proposal still requires review. Existing access,
retry, review, removal and recovery tests remain passing.

The browser rehearsal uses real browser capture/MediaRecorder/Web Audio with a
synthetic 440 Hz input file. Its iPhone 13 and Pixel 7 presets are **Chromium on
Linux at mobile dimensions**, not physical devices or Safari. It verifies:

- visible optional fields and language labels;
- picture draft recovery and a deliberately lost-response retry;
- a simulated permission rejection followed by successful recovery;
- selection of a specific microphone, a moving meter, named input and released
  tracks after the check;
- recorded WebM audio with decoded peak amplitude 0.1878666 and duration about
  1.02 seconds, not merely a nonempty file or moving playback position;
- native capture with its audio track deliberately muted: the silent retake is
  rejected, and the prior audible file survives both immediately and on reload;
- group request, response, discussion, acceptance and playback. The served file
  has the same SHA-256 digest as the original browser recording;
- adding `katt`, `cat` and `Animals` after media, with picture and audio URLs
  preserved; either search term finds the entry;
- no uncaught JavaScript errors or horizontal overflow on the checked pages.

The new-contribution and microphone-check mobile screenshots were visually
inspected. JavaScript syntax, patch whitespace/application and the global state
are checked during packaging. One rehearsal initially stopped on an incorrect
image selector in the probe; correcting it to the existing `.entry-image` class
allowed the full rehearsal to pass. The application did not need that repair.

The old picture-dictionary tests were not rerun: this patch changes the separate
community app and its experiment/docs, not the shared legacy integration. The
same two pre-existing legacy failures remain documented in iteration 1. This is
not a claim that the entire repository suite passes.

## Remaining question and next trial

Can Manny select the input that works in Audacity, see a moving meter, record,
and hear the result inside this app? Until that succeeds, the Windows browser
capture issue remains open. A zero meter points to input reaching the browser;
a moving meter with a silent or rejected take points to the later capture path.
Neither result alone identifies the underlying Windows/browser cause.

Install this repair, hard-refresh, test a short recording, then report the input
name, browser/version, meter behavior and exact message if it still fails.
After laptop confirmation, deploy over HTTPS and conduct actual iPhone/Safari
and Android/Chrome trials, including cross-device playback. Controlled desktop
checks do not establish those results, community suitability or learning value.
