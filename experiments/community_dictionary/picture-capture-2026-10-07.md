# Picture descriptions — first implementation, 7 October 2026

## Request and status

Manny asked for a faster, image-centred workflow: camera/upload, a spoken/typed
sentence in either dictionary language, bilingual interpretation, same-language
and same-modality confirmation, immediate publication with linked word/audio
entries, and shared error flags without mandatory expert approval first. Existing
images need the same path. He authorized a first cut while shopping.

The optional implementation is prepared against GitHub main
`2a0a75e21d6bcd75c3890e5bcda752f32fd73106` (accepted French stakeholder documentation).
It is not installed on Manny's laptop or AWS by the assistant. The human-only
community workflow remains available; enabling the new option is an owner decision.

## Evidence

- Django system checks and migration consistency checks pass.
- 310 Community Dictionary tests pass on Linux/Django 5.2.17: the previous 286 and
  24 new tests. New coverage includes contributor publication after confirmation,
  private drafts/access/CSRF, safe retries, distinct senses and reuse, source edits,
  withdrawal/restore and revision-sensitive links, export, shared attention/editor
  checks, expiry, model-output validation, transcription language hints, background
  worker redelivery and existing-picture navigation.
- A real Django development server and Chromium were exercised at 390px and
  1280px. Typed capture, confirmation, saved/linked audio, inline words, attention
  reporting, spoken-input file upload and same-language spoken feedback, existing
  images, Next picture, and retained preferences passed. No horizontal overflow
  or browser JavaScript errors remained. Screenshots were inspected locally.
- The first browser run caught a form `action` button shadowing `form.action`.
  A later layout refinement caught an inline-audio script expecting a heading.
  Both were corrected before the passing rehearsal. Mocked API calls were used
  throughout; no provider credits or real dictionary content were consumed.

The rehearsal used a synthetic image/audio fixture. It does not test physical camera
or microphone hardware, Safari/iPhone behaviour, real translations/lemmatisation,
pronunciation quality, or network/provider latency. Existing microphone recording
is reused. These remain the purposes of the laptop and subsequent phone trials.

## Deliberate bounds

At most six linked vocabulary items per sentence; dictionary-form word reuse is
conservative. Audio runs through the existing background adapter and has an explicit
manual continuation if queuing fails. No automatic retry after an unknown provider
outcome; the existing single retry of demonstrably silent TTS is retained.
Question exercises and spoken-answer grading remain deferred. Sentence-aware
language porting is also outside this first cut; the UI states that current ports
include words only.

The French note has meanwhile been circulated by Manny to Sophie, Stéphanie and
Anne-Laure and its repository update deployed, according to his reports. No reply
or scheduled time for the proposed end-of-week Zoom call is yet recorded. This
separate, expressly requested AI-supported experiment does not establish community
acceptance or long-run autonomous maintenance.
