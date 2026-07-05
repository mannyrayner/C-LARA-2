# ISSUE-0016: Validate no-audio/skip-TTS fallback on Kok Kaper

- **Status:** closed
- **Priority:** P1
- **Created:** 2026-05-18T03:20:16Z
- **Updated:** 2026-05-23T14:00:00Z
- **Origin:** human-suggestion
- **Deadline:** 2026-06-01T00:00:00Z
- **Dependencies:** None
- **Canonical JSON:** [ISSUE-0016.json](ISSUE-0016.json)

## Notes

Suggestion #6 from admin export (submitted by mannyrayner on 2026-05-18). Low-resource languages
such as Kok Kaper may not have usable TTS, so C-LARA-2 needs an audio workflow that does not assume
generated speech is available before Sophie's Kok Kaper community visit on 2026-06-01. Phase A is
the urgent minimum: add a content-owner/project option marking a language or project as non-TTS so
the audio annotation stage can be skipped or run in no-audio mode without inserting unusable TTS
output, and compiled HTML should omit audio controls/references where no audio exists. Phase B is a
larger community-recording workflow: add a community-specific audio dictionary for surface words and
segments, distinct from the lemma-oriented picture dictionary; during the audio stage for non-TTS
projects, record needed words/segments and associate them with all texts where they appear; expose a
community/member text-level view for playing existing recordings and recording/rerecording word and
segment audio via MediaRecorder or a similar browser API; allow multiple recordings or preferred
versions if needed; and make the audio annotation stage insert approved recorded audio into
annotated texts using the same downstream structure as TTS-generated audio. Update
docs/roadmap/low-resource-languages.md immediately so this work is planned alongside manual
annotation, picture dictionaries, and community workflows. Treat Phase A as a before-2026-06-01
readiness item and Phase B as a design/implementation follow-up requiring discussion of data model,
moderation, permissions, storage, and UI details. Phase A implementation started/completed in the
2026-05-18 follow-up: projects now have an audio mode setting with `tts` and `none` choices. In
no-audio mode the pipeline audio stage skips TTS calls, strips any stale audio annotations from the
stage payload, persists an audio-stage artifact without audio references, and compile_html also
strips audio annotations before rendering so final HTML omits page/segment/token audio controls. The
project create form and annotation processing-options UI expose the setting; compile task updates
explicitly tell users that TTS is being skipped. Source bundle export/import and project cloning
preserve the audio mode. Remaining work is Phase B: design and implement the community-recorded
audio dictionary for surface words and segments.

Scope reduced and resolved on 2026-05-23: ISSUE-0016 now tracks only validation of the
no-audio/skip-TTS fallback on Kok Kaper. Follow-on design/implementation for community-recorded
audio workflow is moved to ISSUE-0026.
