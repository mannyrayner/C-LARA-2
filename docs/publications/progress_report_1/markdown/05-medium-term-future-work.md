# 5. Medium-Term Future Work (Concise Draft Plan)

## 5.1 Framing

- The first progress report must stress that C-LARA-2 is not finished.
- It is an interim report on the first few months of work.
- Future-work priorities should be grounded in the active issue registry and roadmap documents, but the published report should foreground only the most important items.

## 5.2 Highest-priority future work

- **More AI autonomy, self-checking, and self-understanding**: the AI needs stronger tools and workflows for checking its own work, detecting regressions, validating processing quality before humans find problems, and answering project-level questions from repository evidence in ways humans can review.
- **Mobile deployment/support**: mobile access is especially important for learner-facing use and for community work in low-resource-language settings.
- **Audio recording through the platform**: direct/community audio recording is essential where TTS is weak or unavailable, and is therefore especially important for low-resource languages.
- **Self-understanding evidence workflow**: the restricted assistant needs exportable/version-controlled records, reviewer assessment fields, curated report questions, citation sanitization, exact or better-labelled cost accounting, and budget/rate-limit controls before its answers can be used confidently as publication evidence.

## 5.3 Additional user-facing priorities

- **Alignment workflows** for integrating large, high-quality external audio with text.
- **Compiled-content access and presentation improvements**, including configurable anonymous/public access where appropriate.
- **Picture-dictionary extensions**, including better integration with picture glossing, picture flashcards, and other activities.

## 5.4 Additional implementor-facing priorities

- **Autonomous tracking of processing quality** across annotation, image, and exercise stages.
- **Project-understanding evaluation** with repeatable question sets, human ratings, and comparison against repository ground truth.
- **Systematic UI drift/regression detection** for disappearing or unstable controls.
- **Batch legacy-corpus migration tooling** with robust reporting and resumability.
- **Continued publication workflow hardening** to support report and paper production cadence.

## 5.5 Risks and dependencies

- Increased autonomy and self-understanding require stronger safeguards for correctness, policy compliance, prompt-injection resistance, privacy, cost control, and user-facing quality.
- Mobile and audio work are technically important, but also depend on clear user scenarios and low-resource-language priorities.
- Publication deadlines may compete with implementation bandwidth.

## 5.6 Suggested prioritization structure for next draft

- **Now (0–6 weeks):** progress-report completion, high-priority UX fixes, migration tooling increment, clearer self-checking requirements, and a small curated self-understanding evidence set for the report.
- **Next (6–12 weeks):** mobile and platform audio workflow milestones, stronger regression infrastructure, project-understanding export/review workflow, and picture-dictionary/activity refinements.
- **Later:** broader autonomy/evaluation scaling and publication-derived dissemination tasks.

## 5.7 Discussion questions for project members

- Which three priorities are non-negotiable before the next report cycle?
- Are mobile support and audio recording correctly presented as especially important for low-resource languages?
- Which roadmap items should be explicitly de-prioritized to keep the first report short?
- What minimum evidence-log workflow is needed before the report cites self-understanding assistant outputs?
