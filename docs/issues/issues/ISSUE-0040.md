# ISSUE-0040: Make page-oriented manual annotation saves resilient for large projects

- **Status:** closed
- **Priority:** P1
- **Created:** 2026-07-03T01:15:44Z
- **Updated:** 2026-07-04T01:40:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0025](ISSUE-0025.md)
- **Canonical JSON:** [ISSUE-0040.json](ISSUE-0040.json)

## Notes

Created from human suggestion #31 (submitted by mannyrayner on 2026-07-03). A user made many edits
in the page-oriented manual annotation view at `projects/<id>/annotation/manual/page-oriented/`, but
saving failed before the view could process the form because Django raised `TooManyFieldsSent`: the
number of POST parameters exceeded `settings.DATA_UPLOAD_MAX_NUMBER_FIELDS`. This is a P1
reliability/data-loss risk because the page-oriented editor renders one form field for each editable
translation segment plus MWE, lemma, POS, gloss, and pinyin field for each non-whitespace token
across the whole project, so realistic long projects can exceed Django's default field-count limit
after substantial manual work. Investigate short-term protection, such as increasing
`DATA_UPLOAD_MAX_NUMBER_FIELDS` only if safe and documented, warning users before a page becomes too
large to save, or splitting saves by page/chunk/layer. Prefer a robust design that avoids giant
whole-project POSTs: page-level or incremental saves, dirty-row submission, autosave/draft
persistence, or a JSON payload/API that validates size explicitly and preserves CSRF/security
properties. Include regression coverage using a synthetic large page-oriented project/form that
would previously exceed the field limit, and make sure failed saves return actionable feedback
without discarding user edits.

Follow-up maintainer comment on 2026-07-03: first implementation preference is either autosave or a
per-segment save control at the end of each segment. Recommendation: implement autosave/draft
preservation as the primary protection, because it covers ordinary navigation mistakes, validation
failures, transient server errors, and POST-size failures before the user presses Save. Pair it with
an explicit per-segment or per-page manual save affordance where technically simple, especially as a
visible checkpoint for users doing long review sessions. Avoid relying only on increasing
`DATA_UPLOAD_MAX_NUMBER_FIELDS`: that can be a temporary mitigation, but it does not address the
underlying whole-project-form scalability and recoverability problem.

First implementation cut on 2026-07-03: the page-oriented manual annotation template now includes
browser-local draft autosave for all editable fields in phase 1, phase 2, and full annotation modes.
Edits are saved to `localStorage` under a project/mode/hash-specific key on input/change and again
on submit/before-unload; a visible status panel lets users restore or discard a differing draft;
successful saves clear the draft on the next load. This is intentionally a first safety net for
maintainer testing rather than the final server-side design: it should preserve work after a
large-form submit failure, but follow-up should still consider server-backed drafts,
dirty-field/page-level submission, or per-segment/per-page checkpoints so autosave works across
browsers/devices and reduces giant POST submissions.

Second implementation cut on 2026-07-03: the page-oriented editor now exposes per-segment Save this
segment controls with per-segment status text, plus global autosave/status messaging. Segment
controls submit only the editable controls belonging to the selected segment by disabling other
segment controls just before submit, while the existing server save path reconciles missing fields
from current stage payloads and writes the normal stage artifacts. This should reduce POST field
counts for segment-level checkpoints while preserving the browser-local draft safety net.

UX follow-up on 2026-07-03: per-segment status text is now quiet by default and appears only when a
user edits a segment or clicks its segment-save control. Segment saves now redirect back to an
anchor at the following segment, or the saved segment if it was the final segment, so long
annotation sessions can continue from the next likely work point instead of jumping to the top of
the page.

Additional UX/validation follow-up on 2026-07-03: the full-form Save page-oriented manual
annotations controls were removed from the full annotation screen in favour of segment-level
checkpoints. Global unsaved-change labels now appear at the top and bottom when a user edits segment
fields. Segment saves now validate MWE consistency before writing artifacts: all tokens sharing the
same non-empty MWE annotation must also share the same lemma, POS, and gloss, otherwise the user
gets an informative error identifying the inconsistent locations and values.

MWE error UX follow-up on 2026-07-03: MWE consistency failures now re-render the page-oriented
annotation view with the user's submitted segment edits still present instead of redirecting and
appearing to lose the work. The error is attached directly under the relevant segment save control,
so users can fix the inconsistent MWE/lemma/POS/gloss values in place.

MWE-locality follow-up on 2026-07-03: MWE consistency checking is now scoped to a single segment,
because MWE IDs are meaningful only within the segment in which they occur. Error messages now name
the mismatched component(s), e.g. LEMMA, POS, or GLOSS, and the page scrolls to the position
immediately after the submitted segment so the inline error and next work point are close together.

Large-editor performance follow-up on 2026-07-03: browser-local autosave was turned off for the
page-oriented editor because very large projects appeared to freeze for several seconds, plausibly
due to repeated full-form serialization. The UI now relies on segment-level saves, with more salient
global unsaved-change labels. The view also checks for pre-existing within-segment MWE
inconsistencies on initial load, attaches the first error inline, and scrolls near the affected
segment so annotators can repair existing problems before continuing.

Post-save validation follow-up on 2026-07-03: successful segment-save redirects now include a
`saved_segment` query marker, and initial-load MWE consistency scanning is skipped for that
immediate post-save redisplay. This avoids a confusing loop where a different pre-existing
inconsistency can appear immediately after the annotator has just fixed and saved the current
segment. Directly opening the editor still checks for and scrolls to the first pre-existing
within-segment MWE inconsistency. Continued large-screen freezes after disabling autosave suggest
the remaining bottleneck is likely the size of the rendered DOM rather than draft serialization; if
testing confirms this, the next design should move from one giant page to paginated/windowed segment
rendering.

Page-windowing follow-up on 2026-07-04: the full annotation mode now renders one page at a time
instead of the entire project DOM. Page navigation includes previous/next controls and a go-to-page
input; segment saves carry the current page and redirect to the page containing the next segment
where applicable. MWE pre-checking is scoped to the visible page, while segment-save validation
remains scoped to the submitted segment. This directly targets large-text browser freezes that
persisted after turning off browser-local autosave.

Global-status follow-up on 2026-07-04: the visually salient unsaved-change badge now remains hidden
on initial page load instead of being forced visible by its CSS display rule. The top save-status
panel also lists pages containing segment-local MWE consistency issues, with links to jump directly
to each affected page, so annotators no longer have to page through the whole text sequentially to
find remaining inconsistencies.

Page-jump dirty-state follow-up on 2026-07-04: changing the go-to-page input no longer triggers the
global unsaved-change warning. The dirty-state handler now marks unsaved changes only for controls
associated with an annotatable segment via `data-segment-control`, so navigation-only inputs and
display controls do not look like saveable edits.

Closed on 2026-07-04 after maintainer testing confirmed that page-windowed rendering, per-segment
saves, MWE validation/error navigation, global MWE page listings, and the page-jump dirty-state fix
addressed the reported large-editor save/freeze/data-loss workflow for this round. Future extensions
to apply similar segment/page-save ergonomics to other manual editing views should be tracked as
separate issues if needed.

Post-closure polish on 2026-07-04: the global Unsaved changes labels were made more visually salient
with a warning marker, stronger red styling, heavier font weight, and a high-contrast outline so
annotators are less likely to miss dirty segment state before leaving a page.
