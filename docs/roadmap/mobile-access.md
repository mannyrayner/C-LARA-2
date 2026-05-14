# Roadmap: mobile access

Many C-LARA-2 users will access the platform from phones and tablets rather than desktop or laptop browsers. Mobile access should therefore be a first-class delivery goal, starting with the lowest-risk learner-facing use cases, then supporting default-driven content creation, and finally exploring selected review/editing workflows where small screens are not too painful.

## Goals

- Make published/compiled texts readable and usable on common mobile devices.
- Support learner exercises on touch screens with accessible controls and clear feedback.
- Preserve the full desktop workflow while progressively improving responsive layouts.
- Support simple content creation on mobile when authors are happy to accept default system choices.
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

Default-driven content creation may be quite practical on phones and tablets. If the author is satisfied with the platform's standard choices, a mobile-friendly creation flow can be very short:

- Give an initial description of the text to generate.
- Specify the desired image style, or choose from a small set of presets.
- Confirm language/level defaults and start an automatic end-to-end generation job.
- Leave the job running in the background while C-LARA-2 handles the slow pipeline work.
- Receive an in-app/email/push-style notification when the draft text, images, audio, annotations, compiled HTML, and exercises are ready to review.

Other creation/review work may also be practical on tablets or large phones, but should be introduced after the browsing path and simple generation path:

- Review project status and generation progress.
- Preview compiled pages and exercises before publishing.
- Make small metadata edits.
- Perform simple regeneration or publish/unpublish actions where the risk of accidental destructive changes is low.

The harder part is editing the generated result, especially linguistic annotations. Dense token-level correction of segmentation, lemmas, glosses, MWEs, translations, or alignment on a small screen could be painful and error-prone. Full manual annotation, bulk import, image-pipeline repair, and large JSON/artifact inspection should remain desktop-first until the editing UI is explicitly redesigned for small screens.

### Administrators

Admin workflows may be technically accessible on mobile but are not an initial target. Server-side imports, bundle-library maintenance, billing adjustments, and migration diagnostics should remain desktop-first unless a specific operational need emerges.

## Initial development path: browsing compiled texts first

The first mobile milestone should focus narrowly on browsing compiled texts because this is the most common learner-facing case and carries the least risk to project data. Once mobile reading is reliable, the next major creation milestone should be a default-driven background generation flow rather than a full mobile annotation editor.

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

### Phase 5: default-driven mobile creation

After mobile browsing and exercises are stable, implement a simple creation path for authors who accept defaults:

- Start from a compact prompt form asking for content description, target language, learner level, and image style/preset.
- Show the defaults that will be used for segmentation, linguistic annotation, audio, image generation, exercise generation, and compilation without requiring the author to configure every stage.
- Submit the request as a background task so the user can safely close the browser or continue using the site.
- Provide a progress/status page suitable for mobile, including queued/running/failed/completed states and the currently active pipeline stage.
- Notify the user when the project is ready for review, using the notification channels supported by the platform.
- Open the completed project directly in a mobile preview/review flow.

### Phase 6: selected author workflows

After mobile browsing, exercises, and default-driven generation are stable, evaluate a limited authoring subset:

- Project dashboard summaries.
- Preview compiled output.
- Publish/unpublish toggles with confirmation for risky actions.
- Small metadata edits.
- Review-only views for generated exercises and images.

## Mobile annotation/editing possibilities

Mobile annotation editing should not be dismissed entirely, but it needs a different design from the desktop manual editor. Promising angles include:

- **Triage rather than full editing:** mark a page, segment, token, image, or exercise item as problematic for later desktop review.
- **Single-decision correction cards:** present one small issue at a time, such as choosing between two glosses or accepting/rejecting an MWE analysis.
- **Voice-assisted comments:** let reviewers dictate notes about a bad translation, annotation, or image rather than editing the structured artifact directly.
- **Swipe/tap quality review:** support lightweight approve/reject/needs-work gestures for generated pages, images, audio, or exercise items.
- **Tablet-first editing experiments:** test larger-screen layouts before attempting phone-sized linguistic annotation.

These workflows should complement, not replace, the desktop manual annotation editor. Mobile edits must have strong undo, clear provenance, and safe validation because accidental taps are more likely on small screens.

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
