# ISSUE-0020: Improve picture-dictionary compile flow for low-resource languages and organiser feedback

- **Status:** closed
- **Priority:** P0
- **Created:** 2026-05-21T01:36:10Z
- **Updated:** 2026-05-28T22:30:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0011](ISSUE-0011.md), [ISSUE-0016](ISSUE-0016.md), [ISSUE-0017](ISSUE-0017.md)
- **Canonical JSON:** [ISSUE-0020.json](ISSUE-0020.json)

## Notes

Suggestion #11 from admin export (submitted by mannyrayner on 2026-05-21), clarified and scoped. The
community-organiser 'Compile dictionary (sync pages + annotation + images)' flow needs better
behavior in low-resource/no-AI contexts and clearer progress feedback in AI-enabled contexts. Scope:
(1) Show explicit post-linguistic-stage progress/status messages for dictionary-driven image
generation so organisers can see when images are being generated and with what outcome counts. (2)
For low-resource languages, allow dictionary compile to produce a useful partial pipeline: reliably
fill segmentation_phase_1/2 and create placeholder stage artifacts for
translation/MWE/lemma/gloss/pinyin with clear 'manual completion required' markers. (3) After
partial compile, provide direct guidance and a link to page-by-page manual annotation so organisers
can complete missing fields efficiently. (4) Preserve current behavior for AI-supported languages
while making fallback behavior deterministic, auditable, and non-blocking.

Closed based on maintainer confirmation in issue update follow-up (2026-05-23).

Reopened on 2026-05-25 after organiser testing with Sophie identified additional gaps: auto-enable
low-resource compile mode for non-AI-enabled languages (Kok Kaper, Iaai, Drehu), block compile with
clear guidance when dictionary entries are missing gloss/translation data in low-resource mode,
auto-copy translation<->gloss when one is missing for picture-dictionary rows, and ensure
compile-to-images uses translations as the text source in this workflow.

Closed on 2026-05-27 per update suggestion #21 (submitter: mannyrayner): maintainer confirmed
requested low-resource picture-dictionary workflow fixes are now in place.

Reopened on 2026-05-28 from issue update suggestion #23 (submitter: mannyrayner) after discussion
with Sophie showed the low-resource picture-dictionary word-addition workflow is still too
cumbersome. Revised urgent scope: in low-resource/non-AI language contexts, replace the simple
comma/newline word entry box on the community organiser page with a tabular entry form capturing
word, lemma, POS, and gloss/translation data; use the submitted rows to update the dictionary and
the annotation/stage information that currently requires a trip through the page-oriented editor;
allow POS to serve as translation when appropriate; and relabel the follow-on compile action as a
clearer image-creation control with a count of pending new images. The goal is for organisers to add
fully annotated dictionary rows and then create images without leaving the community organiser
workflow.

Closed on 2026-05-28 after implementing the low-resource organiser workflow: the community organiser
page now shows a tabular word/lemma/POS/gloss/translation entry form for non-AI languages, writes
the corresponding dictionary annotation stages directly, preserves the simple word-entry flow for
AI-capable languages, and relabels the low-resource compile action as image creation with
pending-image feedback.
