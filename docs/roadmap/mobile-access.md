# Roadmap: mobile access

Many C-LARA-2 users will access the platform from phones and tablets rather than desktop or laptop browsers. Mobile access should therefore be a first-class delivery goal, starting with the lowest-risk learner-facing use cases and then extending to selected creation and review workflows.

## Goals

- Make published/compiled texts readable and usable on common mobile devices.
- Support learner exercises on touch screens with accessible controls and clear feedback.
- Preserve the full desktop workflow while progressively improving responsive layouts.
- Avoid requiring a native app for the initial rollout; a responsive web experience should cover the core use cases.
- Keep mobile performance acceptable on ordinary networks by controlling page weight, media preloading, and image/audio loading behavior.

## Scope by user role

### Learners and general readers

Primary mobile support should target learners first:

- Browse the public/published content catalogue.
- Open compiled texts and move between pages.
- Use gloss, translation, lemma, audio, image, and MWE interactions with touch-friendly affordances.
- Play generated audio and view generated images without layout overflow.
- Complete published exercises such as cloze items and flashcards.

### Teachers and project authors

Some creation/review work may also be practical on tablets or large phones, but should come after the browsing path:

- Review project status and published content.
- Make small metadata edits.
- Preview compiled pages and exercises before publishing.
- Perform simple regeneration or publish/unpublish actions where the risk of accidental destructive changes is low.

Full manual annotation, bulk import, image-pipeline repair, and large JSON/artifact inspection should remain desktop-first until the editing UI is explicitly redesigned for small screens.

### Administrators

Admin workflows may be technically accessible on mobile but are not an initial target. Server-side imports, bundle-library maintenance, billing adjustments, and migration diagnostics should remain desktop-first unless a specific operational need emerges.

## Initial development path: browsing compiled texts first

The first mobile milestone should focus narrowly on browsing compiled texts because this is the most common learner-facing case and carries the least risk to project data.

### Phase 1: mobile audit for compiled output

- Inventory the HTML/CSS/JS used by compiled text pages.
- Test representative texts on common viewport widths: small phone, large phone, tablet portrait, and tablet landscape.
- Check that page navigation, audio controls, gloss popups/tooltips, translations, images, and MWE interactions are usable with touch rather than hover-only interaction.
- Record known overflow, tap-target, media-loading, and font-size problems.

### Phase 2: responsive compiled-text baseline

- Add or update viewport metadata where required.
- Ensure compiled pages use responsive width constraints rather than fixed desktop layouts.
- Make images scale within the viewport while preserving captions and page-level context.
- Provide touch-safe interaction for word/MWE annotations, such as tap-to-open/tap-outside-to-close behavior.
- Keep minimum tap targets large enough for reliable phone use.
- Ensure audio controls are reachable and do not overlap text or navigation.

### Phase 3: mobile content browsing

- Make the public/published content list usable on phones.
- Provide compact cards or list rows for title, language, author/owner, and key actions.
- Keep search/filter controls reachable without requiring horizontal scrolling.
- Ensure the path from catalogue → content detail → first compiled page is short and clear.

### Phase 4: exercises on mobile

- Adapt cloze and flashcard players for one-handed/touch use.
- Ensure answer options, submit/next buttons, feedback messages, and score summaries fit small screens.
- Avoid hover-only explanations; every hint, feedback note, and media control must be touch accessible.
- Preserve exercise state across accidental orientation changes or page reloads where practical.

### Phase 5: selected author workflows

After mobile browsing and exercises are stable, evaluate a limited authoring subset:

- Project dashboard summaries.
- Preview compiled output.
- Publish/unpublish toggles with confirmation for risky actions.
- Small metadata edits.
- Review-only views for generated exercises and images.

## UX and accessibility requirements

- Use responsive design rather than a separate mobile site where possible.
- Prefer progressive enhancement so compiled pages remain usable with limited JavaScript.
- Avoid tiny inline controls for annotation interactions; touch targets should be visibly tappable.
- Provide keyboard and screen-reader paths for interactions that are also touch-enabled.
- Use `lang` and `dir` metadata consistently so mobile browsers handle text shaping and bidirectionality correctly.
- Test mixed-script pages, long tokens, and right-to-left languages for wrapping and overflow.

## Performance requirements

- Lazy-load large images and non-current-page media where possible.
- Avoid loading every page image/audio file when the learner opens the first page of a long text.
- Keep compiled output cacheable and static-friendly for published content.
- Measure page weight and time-to-interactive for representative small, medium, and large texts.
- Define warning thresholds for unusually large images, audio files, or per-page annotation payloads.

## Compatibility targets

Initial testing should cover:

- iOS Safari on recent iPhones.
- Android Chrome on common phone sizes.
- Tablet Safari/Chrome in portrait and landscape.
- Desktop browser responsive emulation as a fast regression check, while still doing real-device spot checks.

## Regression checklist

For each mobile milestone, verify:

- No horizontal scrolling on normal compiled pages.
- Page navigation is reachable at the top and/or bottom of the page.
- Gloss/translation/lemma interactions work by touch.
- Audio can be played, paused, and replayed.
- Images fit within the viewport.
- Exercise choices and feedback are readable without zooming.
- Authentication redirects and published-content links behave correctly on mobile browsers.
- RTL and mixed-script content remains legible.

## Open questions

- Should compiled texts support offline/PWA caching for fieldwork or low-connectivity classroom use?
- Which authoring operations are safe enough for phones, and which should remain tablet/desktop-only?
- Should mobile exercise sessions be optimized for anonymous public learners, logged-in learners, or both?
- How much analytics should be collected to identify common mobile failures without compromising privacy?
