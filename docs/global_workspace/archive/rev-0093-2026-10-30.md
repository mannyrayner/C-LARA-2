# C-LARA-2 current project state

> This file is generated from `current_state.json`; do not edit it directly.

- **Workspace revision:** 93
- **As of:** 2026-10-30
- **Assessed commit:** `863e401bf1dec9dfb59f730976f56fb88699ff96`
- **Approved proposal:** `None`
- **Approved run:** None (no recorded run)
- **Persistent goals:** `GOAL-1`, `GOAL-2`, `GOAL-3`, `GOAL-4`, `GOAL-5`

## Current focus

Writing practice has a successful laptop deployment and one positive user-reported example. A complementary guided-picture workflow is now prepared: private photo capture, explanation-language confirmation, then automatic enrichment. Persistent personal modes and four dictionary language levels support different learners while retaining central image content. Tests pass with mocked providers; physical-phone, live-model and learner acceptance remain next. The two new preference tables require an explicit bounded schema-preparation step before the unchanged code-only deployment workflow; this boundary is preserved.

## Factual observations

### OBS-0001

The end-to-end pipeline runner exists and is regularly used, but its implemented workflow needs canonical documentation; systematic UI-regression tracking remains important and has been revived.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0003.json`](../issues/issues/ISSUE-0003.json), [`docs/issues/issues/ISSUE-0025.json`](../issues/issues/ISSUE-0025.json)

### OBS-0002

Segmentation phase 1 remains important but is not delivering acceptable results and appears amenable to a bounded prompt/few-shot fix; the older segmentation phase 2 failure is now closed as previously resolved.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0005.json`](../issues/issues/ISSUE-0005.json), [`docs/issues/issues/ISSUE-0006.json`](../issues/issues/ISSUE-0006.json)

### OBS-0003

The picture-dictionary and subset workflows appear resolved and have positive initial feedback, but focused verification is required before Sophie’s 24 August community visit.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0037.json`](../issues/issues/ISSUE-0037.json), [`docs/issues/issues/ISSUE-0039.json`](../issues/issues/ISSUE-0039.json)

### OBS-0004

The project-understanding Assistant is complete for now, the project-manager/archive loop is operational, and the Sprint task remains critical and in progress.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0034.json`](../issues/issues/ISSUE-0034.json), [`docs/issues/issues/ISSUE-0042.json`](../issues/issues/ISSUE-0042.json), [`docs/roadmap/agent-autonomy-and-global-workspace.md`](../roadmap/agent-autonomy-and-global-workspace.md)

### OBS-0005

Manny’s issue-by-issue review corrected stale registry state, revived dropped work, and supplied concrete sequencing evidence; roadmap cleanup itself is now active as both practical maintenance and an autonomy test.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/index.json`](../issues/index.json), [`docs/issues/issues/ISSUE-0033.json`](../issues/issues/ISSUE-0033.json), [`docs/issues/overview.md`](../issues/overview.md)

### OBS-0006

Legacy registration and migration mechanisms are nearly complete and remain low-hanging completion work; the next completion attempt will reveal whether stage-artifact performance/timeouts still persist.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0001.json`](../issues/issues/ISSUE-0001.json), [`docs/issues/issues/ISSUE-0010.json`](../issues/issues/ISSUE-0010.json), [`docs/issues/issues/ISSUE-0013.json`](../issues/issues/ISSUE-0013.json)

### OBS-0007

Community-recorded audio is urgently needed for Indigenous-language work and a planned ComputEL-10 paper; an initial workflow before the 24 August visit would be valuable.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/global_workspace/project-intentions.md`](../global_workspace/project-intentions.md), [`docs/issues/issues/ISSUE-0026.json`](../issues/issues/ISSUE-0026.json), [`docs/roadmap/low-resource-languages.md`](../roadmap/low-resource-languages.md)

### OBS-0008

Community-judging autosave has similar pre-visit value to recorded audio, is likely much easier, and has been promoted from an expired deferral to active P0 work.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0029.json`](../issues/issues/ISSUE-0029.json), [`docs/roadmap/community-judging-autosave.md`](../roadmap/community-judging-autosave.md)

### OBS-0009

The image-generation selection flow and compiled-content access/navigation issues remain annoying user-facing problems and are judged likely to be bounded low-hanging fixes.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0030.json`](../issues/issues/ISSUE-0030.json), [`docs/issues/issues/ISSUE-0031.json`](../issues/issues/ISSUE-0031.json)

### OBS-0010

Learned annotation prompts remain a major promising research thread; discussion with Francis Bond about collaboration and an AI-authorship-compatible publication path is urgent.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0036.json`](../issues/issues/ISSUE-0036.json), [`docs/issues/issues/ISSUE-0044.json`](../issues/issues/ISSUE-0044.json)

### OBS-0011

Mobile delivery before 24 August is not realistic, but a mid-September browsing-and-exercises slice could contribute to the planned ComputEL-10 paper due in early October.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/global_workspace/project-intentions.md`](../global_workspace/project-intentions.md), [`docs/issues/issues/ISSUE-0045.json`](../issues/issues/ISSUE-0045.json), [`docs/roadmap/mobile-access.md`](../roadmap/mobile-access.md)

### OBS-0012

Two weeks have passed without further substantive EuroCALL committee information; the original submissions remain unresolved while rapid AI capability changes are making their technical accounts stale.

- **Observed:** 2026-08-14
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0043.json`](../issues/issues/ISSUE-0043.json), [`docs/global_workspace/project-intentions.md`](../global_workspace/project-intentions.md)

### OBS-0013

The intermittent Codex PR update-branch refusal recurred on 12 August and wasted substantial time; fully exiting Codex, restarting, and creating a new task restored progress but did not identify the cause.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0035.json`](../issues/issues/ISSUE-0035.json), [`docs/roadmap/codex-pr-update-branch-inconsistencies.md`](../roadmap/codex-pr-update-branch-inconsistencies.md)

### OBS-0014

The generic AI-review-gates issue has no active work or clear way forward and has been downgraded to P3.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/issues/issues/ISSUE-0004.json`](../issues/issues/ISSUE-0004.json)

### OBS-0015

The archive now preserves ordered human-input messages for each post-baseline revision, with revisions 2 and 3 backfilled from Manny’s supplied copies and future updates requiring input capture during installation.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/global_workspace/README.md`](../global_workspace/README.md), [`docs/global_workspace/archive/inputs/README.md`](../global_workspace/archive/inputs/README.md), [`docs/global_workspace/archive/inputs/rev-0002/input-001.md`](../global_workspace/archive/inputs/rev-0002/input-001.md), [`docs/global_workspace/archive/inputs/rev-0003/input-001.md`](../global_workspace/archive/inputs/rev-0003/input-001.md)

### OBS-0016

The existing authenticated Assistant now provides a restricted Project Manager mode through the same read-only Codex worker, preserving collaborator identity/role, exact request and response, trusted commit/run metadata, and material-evidence/workspace-review classification.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`src/core/project_understanding.py`](../src/core/project_understanding.py), [`platform_server/projects/views.py`](../platform_server/projects/views.py), [`platform_server/projects/templates/projects/project_understanding.html`](../platform_server/projects/templates/projects/project_understanding.html), [`docs/roadmap/platform-self-knowledge-assistant.md`](../roadmap/platform-self-knowledge-assistant.md)

### OBS-0017

The first natural laptop Project Manager query returned a plausible, repository-grounded prioritization of Sophie’s Indigenous-community work in 36 seconds; per-user Admin Tools access control is now implemented with non-staff access off by default.

- **Observed:** 2026-08-13
- **Confidence:** high
- **Evidence:** [`docs/roadmap/platform-self-knowledge-assistant.md`](../roadmap/platform-self-knowledge-assistant.md), [`platform_server/projects/views.py`](../platform_server/projects/views.py), [`platform_server/projects/templates/projects/admin_tools.html`](../platform_server/projects/templates/projects/admin_tools.html), [`platform_server/projects/tests/test_admin_tools.py`](../platform_server/projects/tests/test_admin_tools.py)

### OBS-0018

The EuroCALL C-LARA-2 paper needs no separate update because the first ResearchGate progress report subsumes it; a new Voice Mode report now preserves the submitted paper while extending it with the URL-based integration and Assistant-queryable session evidence.

- **Observed:** 2026-08-14
- **Confidence:** high
- **Evidence:** [`docs/publications/clara2_voice_mode_initial_experiments/README.md`](../publications/clara2_voice_mode_initial_experiments/README.md), [`docs/publications/clara2_voice_mode_initial_experiments/latex/clara2_voice_mode_initial_experiments.tex`](../publications/clara2_voice_mode_initial_experiments/latex/clara2_voice_mode_initial_experiments.tex), [`docs/issues/issues/ISSUE-0043.json`](../issues/issues/ISSUE-0043.json)

### OBS-0019

The new Voice Mode report draft now explains the system-selection rationale, adds Jumpspeak as a cautious commercial comparison, uses consistent product terminology, and distinguishes the original pedagogical limitations from Manny’s anecdotal observation that ChatGPT version 5.6 corrected French gender and article errors more effectively.

- **Observed:** 2026-08-14
- **Confidence:** high
- **Evidence:** [`docs/publications/clara2_voice_mode_initial_experiments/latex/clara2_voice_mode_initial_experiments.tex`](../publications/clara2_voice_mode_initial_experiments/latex/clara2_voice_mode_initial_experiments.tex), [`docs/publications/clara2_voice_mode_initial_experiments/latex/references.bib`](../publications/clara2_voice_mode_initial_experiments/latex/references.bib), [`docs/issues/issues/ISSUE-0043.json`](../issues/issues/ISSUE-0043.json)

### OBS-0020

The revised report now presents Jumpspeak as a plausible generative but tutoring/role-play-centered comparator, explicitly treats the interaction-type distinction as an untested hypothesis, explains why no firsthand comparison was completed, and marks its new web sources as provisional pending verification.

- **Observed:** 2026-08-14
- **Confidence:** high
- **Evidence:** [`docs/publications/clara2_voice_mode_initial_experiments/README.md`](../publications/clara2_voice_mode_initial_experiments/README.md), [`docs/publications/clara2_voice_mode_initial_experiments/latex/clara2_voice_mode_initial_experiments.tex`](../publications/clara2_voice_mode_initial_experiments/latex/clara2_voice_mode_initial_experiments.tex), [`docs/publications/clara2_voice_mode_initial_experiments/latex/references.bib`](../publications/clara2_voice_mode_initial_experiments/latex/references.bib), [`docs/issues/issues/ISSUE-0043.json`](../issues/issues/ISSUE-0043.json)

### OBS-0021

Manny has reviewed the Voice Mode report; its conclusion now frames commercial cost limits as a testable hypothesis, cites a reported greater-than-280-fold fall in GPT-3.5-level inference cost, and argues conditionally that affordable multimodal free-conversation tutors may soon be feasible.

- **Observed:** 2026-08-14
- **Confidence:** high
- **Evidence:** [`docs/publications/clara2_voice_mode_initial_experiments/latex/clara2_voice_mode_initial_experiments.tex`](../publications/clara2_voice_mode_initial_experiments/latex/clara2_voice_mode_initial_experiments.tex), [`docs/publications/clara2_voice_mode_initial_experiments/latex/references.bib`](../publications/clara2_voice_mode_initial_experiments/latex/references.bib), [`docs/issues/issues/ISSUE-0043.json`](../issues/issues/ISSUE-0043.json)

### OBS-0022

Manny requested a mobile community picture/audio dictionary in C-LARA-2, construction/discussion before practice, Swedish first, human camera/voice input with partnerships and no AI content generation initially. He supplied successful bootstrap application/commit/push output for bc21188595bae9f2ee89c080243a76fdd4a960b1.

- **Observed:** 2026-09-23
- **Confidence:** high
- **Evidence:** [`docs/roadmap/community-dictionary.md`](../roadmap/community-dictionary.md)

### OBS-0023

The first functional patch has 20 passing Django workflow/access tests and a passing local Chromium two-account workflow including simulated microphone recording, draft reload, deliberately lost confirmation/retry, discussion, acceptance and playback. Focused legacy regressions have the same two failures observed on the clean pre-feature base. Physical phones, production deployment, PostgreSQL concurrency and a full operational backup rehearsal remain unverified.

- **Observed:** 2026-09-23
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/iteration-001.md`](../experiments/community_dictionary/iteration-001.md), [`platform_server/community_dictionary/tests/test_workflow.py`](../platform_server/community_dictionary/tests/test_workflow.py), [`docs/howto/community-dictionary.md`](../howto/community-dictionary.md)

### OBS-0024

The previous derived state is dated 14 August and treats the 14–16 August Sprint and 24 August visit as upcoming. Their dates have passed; this task has no new outcome evidence for those commitments. Their older assessments are preserved but no longer presented as verified current urgency.

- **Observed:** 2026-09-23
- **Confidence:** high
- **Evidence:** [`docs/global_workspace/archive/rev-0011-2026-08-14.json`](../global_workspace/archive/rev-0011-2026-08-14.json), [`docs/global_workspace/project-intentions.md`](../global_workspace/project-intentions.md)

### OBS-0025

Manny reports two Swedish entries with uploaded pictures and MP3 audio and successful image browsing. Browser recording still fails after Audacity began working again. He then confirms that words, translations and categories can be added after explanation, correcting the initial impression of missing functionality. The input cause is unresolved.

- **Observed:** 2026-09-24
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/iteration-002.md`](../experiments/community_dictionary/iteration-002.md)

### OBS-0026

Iteration 2 exposes optional word/translation/category fields and adds named microphone selection, live input testing and silence detection that preserves an earlier take. All 21 app tests pass; the controlled Chromium rehearsal verifies nonzero decoded samples, permission-error recovery, rejection of a deliberately silent retake, media preservation after adding searchable Swedish/English text, and the existing collaborative workflow. Real Windows capture and physical-phone acceptance are still unverified.

- **Observed:** 2026-09-24
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/iteration-002.md`](../experiments/community_dictionary/iteration-002.md), [`experiments/community_dictionary/browser_workflow.cjs`](../experiments/community_dictionary/browser_workflow.cjs), [`platform_server/community_dictionary/tests/test_workflow.py`](../platform_server/community_dictionary/tests/test_workflow.py)

### OBS-0027

Manny confirms that direct recording now works and attributes the earlier failure to the browser defaulting to the wrong input. He requests check-in of the material. GitHub’s feature branch still points to bootstrap bc211885; the agreed workflow is to commit the installed implementation and repair from Manny’s tested laptop checkout. This is human-reported recording success, not a new automated or phone test.

- **Observed:** 2026-09-24
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/laptop-trial-2026-09-24.md`](../experiments/community_dictionary/laptop-trial-2026-09-24.md)

### OBS-0028

The implementation/repair commit 692e44d is on main, followed by archive-only 8811849. Manny reports successful shared AWS deployment and the suggested laptop workflow, then an initial physical-phone contribution trial: Cathy took and saved a photograph and he added a recording. Phone/browser, recording device and separate-account/registered-partnership details are not recorded. Kate and Axel have been invited to test Icelandic; no result is available.

- **Observed:** 2026-09-25
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/aws-phone-trial-2026-09-25.md`](../experiments/community_dictionary/aws-phone-trial-2026-09-25.md)

### OBS-0029

Reviewed main commit a7e8870 disables DEBUG in the shared settings. Manny confirms redeployment and effective DEBUG=False. check --deploy reports W004, W008, W012 and W016. HTTPS/200 MB nginx preflight is known, but full redirect/header policy remains unverified. Secure-cookie settings and wildcard ALLOWED_HOSTS need production review; functional success is not a security sign-off.

- **Observed:** 2026-09-26
- **Confidence:** high
- **Evidence:** [`platform_server/platform_server/settings.py`](../platform_server/platform_server/settings.py), [`experiments/community_dictionary/aws-phone-trial-2026-09-25.md`](../experiments/community_dictionary/aws-phone-trial-2026-09-25.md)

### OBS-0030

Manny shows an Assistant answer accurately describing the feature but retaining the obsolete pending-phone-trial status from repository documents. Current status pages, a dated AWS/phone trial record and an initial stakeholder LaTeX report are prepared. Until these changes are committed and pulled to the Assistant server, it cannot retrieve the new evidence from its checkout. Reported development times are participant estimates, not audited totals.

- **Observed:** 2026-09-26
- **Confidence:** high
- **Evidence:** [`docs/publications/community_dictionaries_initial/latex/community_dictionaries_initial.tex`](../publications/community_dictionaries_initial/latex/community_dictionaries_initial.tex), [`docs/howto/community-dictionary.md`](../howto/community-dictionary.md), [`experiments/community_dictionary/aws-phone-trial-2026-09-25.md`](../experiments/community_dictionary/aws-phone-trial-2026-09-25.md)

### OBS-0031

Manny reports that the previous documentation update was installed on AWS and supplies an Assistant answer accurately distinguishing app tests, controlled browser checks, actual laptop/phone reports and remaining deployment/user-trial questions. Main is now e3b94b0. This is positive evidence for repository-backed continuity, not a new runtime test or autonomous maintenance result.

- **Observed:** 2026-09-26
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/direction-review-2026-09-26.md`](../experiments/community_dictionary/direction-review-2026-09-26.md)

### OBS-0032

Manny requests optional AI image generation and TTS as the next increment, plus a staged reduction in his required technical work from daily intervention to several times weekly and then monthly. He reports Cathy supports the goal while doubting feasibility. Sophie highlights data sovereignty and proposes examining harder image meanings; an early-afternoon discussion is planned for 1 October. These are new directions and planned discussion, not implemented functionality or community approval.

- **Observed:** 2026-09-26
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/direction-review-2026-09-26.md`](../experiments/community_dictionary/direction-review-2026-09-26.md), [`docs/roadmap/community-dictionary-ai-and-maintenance.md`](../roadmap/community-dictionary-ai-and-maintenance.md)

### OBS-0033

Source inspection confirms reusable image/TTS adapters and user-key/accounting components, with integration still required for dictionary policy, private storage, provenance, jobs and costs. Existing audio can fall back to a test-tone stub. The explanation Assistant launches read-only Codex execution. A next-stage roadmap and revised paper specify proposed acceptance checks and staged operations; no live provider calls, execution permissions or runtime code are changed.

- **Observed:** 2026-09-26
- **Confidence:** high
- **Evidence:** [`src/core/ai_api.py`](../src/core/ai_api.py), [`src/pipeline/audio.py`](../src/pipeline/audio.py), [`src/core/project_understanding.py`](../src/core/project_understanding.py), [`platform_server/projects/models.py`](../platform_server/projects/models.py), [`docs/roadmap/community-dictionary-ai-and-maintenance.md`](../roadmap/community-dictionary-ai-and-maintenance.md), [`docs/publications/community_dictionaries_initial/latex/community_dictionaries_initial.tex`](../publications/community_dictionaries_initial/latex/community_dictionaries_initial.tex)

### OBS-0034

Manny confirms the previous documentation installation and shows a server-Assistant answer accurately separating current functionality, proposed AI media and staged measures of operational work. Main now contains that documentation at 6ad49ee. This is continuity evidence, not a new app-test or autonomous-operation result.

- **Observed:** 2026-09-26
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/situated-learning-review-2026-09-26.md`](../experiments/community_dictionary/situated-learning-review-2026-09-26.md), [`docs/publications/community_dictionaries_initial/latex/community_dictionaries_initial.tex`](../publications/community_dictionaries_initial/latex/community_dictionaries_initial.tex)

### OBS-0035

Manny proposes spoken sentences about personal photographs, optional translations, human recordings for unsupported languages, AI sentence/TTS assistance where permitted, vocabulary reuse and links to earlier learning episodes. Italian is a proposed personal trial. Motivation and spoken-learning benefits have not been measured.

- **Observed:** 2026-09-26
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/situated-learning-review-2026-09-26.md`](../experiments/community_dictionary/situated-learning-review-2026-09-26.md), [`docs/publications/community_dictionaries_initial/latex/community_dictionaries_initial.tex`](../publications/community_dictionaries_initial/latex/community_dictionaries_initial.tex)

### OBS-0036

Manny requests a short summary connecting language pedagogy, picture dictionaries, Indigenous communities and increasing AI autonomy in response to non-technical requests. Version 3 is a two-page paper, with rapid development described as AI-written application code plus human direction, deployment and testing. Model/mode and elapsed period are participant descriptions; the documentation pass implements none of the proposed extensions.

- **Observed:** 2026-09-26
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/situated-learning-review-2026-09-26.md`](../experiments/community_dictionary/situated-learning-review-2026-09-26.md), [`docs/publications/community_dictionaries_initial/latex/community_dictionaries_initial.tex`](../publications/community_dictionaries_initial/latex/community_dictionaries_initial.tex)

### OBS-0037

Manny and Cathy prioritize keeping the service running over long periods with minimal expert intervention, limiting runtime changes to small user-driven needs. Funding assistance is a discussion topic, not authority to contact donors or commit money. Manny specifically approves a minimal single-object photo-learning implementation for a phone trial.

- **Observed:** 2026-09-28
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/photo-learning-2026-09-28.md`](../experiments/community_dictionary/photo-learning-2026-09-28.md), [`docs/roadmap/community-dictionary-ai-and-maintenance.md`](../roadmap/community-dictionary-ai-and-maintenance.md)

### OBS-0038

The first-cut patch adds dictionary opt-in, a private expiring photo attempt, one structured OpenAI vision call, subject confirmation, editable wording, optional matching device-voice preview, and idempotent saving with provenance/review. It reuses account/key and token-billing infrastructure. Forty backend tests and Chromium 153 rehearsals at iPhone 13 and Pixel 7 viewport profiles pass using a mocked provider. No live-provider access, physical capture/pronunciation or AWS installation of this increment is claimed.

- **Observed:** 2026-09-28
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/photo-learning-2026-09-28.md`](../experiments/community_dictionary/photo-learning-2026-09-28.md), [`docs/howto/community-photo-learning.md`](../howto/community-photo-learning.md), [`platform_server/community_dictionary/photo_views.py`](../platform_server/community_dictionary/photo_views.py), [`platform_server/community_dictionary/tests/test_photo_learning.py`](../platform_server/community_dictionary/tests/test_photo_learning.py)

### OBS-0039

Manny reports a Windows/Cygwin laptop startup failure after the first photo patch: the eager OpenAI 2.8.1 import picks up src/httpx.py instead of installed HTTPX. Reproduced on Linux and fixed using the existing protected lazy SDK loader. Forty-one tests pass under SDK 2.8.1 and 3.19.2; a fresh-process regression constructs the real client without a network call. Global-package visibility in the laptop pip trace remains undiagnosed.

- **Observed:** 2026-09-28
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/photo-import-fix-2026-09-28.md`](../experiments/community_dictionary/photo-import-fix-2026-09-28.md), [`platform_server/community_dictionary/photo_ai.py`](../platform_server/community_dictionary/photo_ai.py), [`platform_server/community_dictionary/tests/test_photo_learning.py`](../platform_server/community_dictionary/tests/test_photo_learning.py)

### OBS-0040

Manny reports successful local installation, login, dictionary opt-in and live recognition of an uploaded horse image, returning en häst quickly with good device-voice playback. He saved edited wording häst, but found entry-point placement confusing and expected saved audio. The implementation provides browser speech preview only. He proposes entry-level analysis and commenting-language identification followed by local community-dictionary lookup for unsupported target languages. These follow-ups are not implemented.

- **Observed:** 2026-09-28
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/photo-laptop-trial-2026-09-28.md`](../experiments/community_dictionary/photo-laptop-trial-2026-09-28.md), [`platform_server/community_dictionary/static/community_dictionary/photo.js`](../platform_server/community_dictionary/static/community_dictionary/photo.js), [`platform_server/community_dictionary/photo_views.py`](../platform_server/community_dictionary/photo_views.py)

### OBS-0041

Manny requests an installable entry-control/saved-audio patch and asks to support returning to older pictures; he explicitly defers commenting-language lookup pending Sophie discussion. The patch implements source-linked same-entry interpretation, separate TTS opt-in, generation from accepted text, private preview, reviewed synthetic contributions and audio cleanup. Fifty-eight app tests pass under SDK 2.8.1 and 3.19.2, six offline audio-pipeline tests pass, and Chromium 153 rehearsals at iPhone 13/Pixel 7 viewports pass with mock photo responses and a tone audio fixture. No paid provider call or production deployment was performed.

- **Observed:** 2026-09-28
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/entry-photo-audio-2026-09-28.md`](../experiments/community_dictionary/entry-photo-audio-2026-09-28.md), [`docs/howto/community-entry-photo-audio.md`](../howto/community-entry-photo-audio.md), [`platform_server/community_dictionary/tests/test_entry_media.py`](../platform_server/community_dictionary/tests/test_entry_media.py), [`platform_server/community_dictionary/audio_views.py`](../platform_server/community_dictionary/audio_views.py)

### OBS-0042

Manny reports the preceding entry/photo/saved-audio patch is all working and requests enabled-by-default AI options plus consistent selectable voices, including interest in gender choice. The follow-up implements visible checked defaults for new dictionaries only and 13 named Speech API voices with per-user/per-dictionary persistence; it does not invent gender labels. Existing settings, recordings and per-request confirmations remain. Sixty-four Django app tests pass under OpenAI SDK 3.19.2; Chromium 153 rehearsals at iPhone 13/Pixel 7 viewport sizes pass with mocked photo responses and tone audio, including Cedar selection and persistence. No paid provider call or deployment was performed during this implementation.

- **Observed:** 2026-09-28
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/voices-and-defaults-2026-09-28.md`](../experiments/community_dictionary/voices-and-defaults-2026-09-28.md), [`docs/howto/community-voices-and-defaults.md`](../howto/community-voices-and-defaults.md), [`platform_server/community_dictionary/tests/test_entry_media.py`](../platform_server/community_dictionary/tests/test_entry_media.py), [`platform_server/community_dictionary/voices.py`](../platform_server/community_dictionary/voices.py), [`platform_server/community_dictionary/migrations/0004_ai_defaults_and_voices.py`](../platform_server/community_dictionary/migrations/0004_ai_defaults_and_voices.py)

### OBS-0043

Manny reports the defaults/voice-menu patch works but old en häst audio remains visible after editing the entry to häst and generating replacement audio. The repair excludes outdated synthetic recordings from normal playback and partnership samples, while retaining labelled history and human recordings. Matching is based on actual spoken wording/language, not revision number; meaning/category edits keep suitable audio and restored wording can reuse it. Sixty-seven app tests pass with mocked providers. No migration, live provider call or deployment was needed/performed in development.

- **Observed:** 2026-09-28
- **Confidence:** high
- **Evidence:** [`docs/howto/community-current-audio.md`](../howto/community-current-audio.md), [`platform_server/community_dictionary/views.py`](../platform_server/community_dictionary/views.py), [`platform_server/community_dictionary/templates/community_dictionary/entry.html`](../platform_server/community_dictionary/templates/community_dictionary/entry.html), [`platform_server/community_dictionary/tests/test_entry_media.py`](../platform_server/community_dictionary/tests/test_entry_media.py)

### OBS-0044

Manny confirms that after the current-audio patch he sees only the recording matching the entry text. He asks to check everything in and plans to deploy on AWS and test on a mobile on 29 September. This supplies human laptop acceptance of the reported stale-TTS repair, not AWS or phone acceptance of the new AI features. The reviewed development tree retains the 67-test result; the check-in pass changes evidence documentation only.

- **Observed:** 2026-09-28
- **Confidence:** high
- **Evidence:** [`docs/howto/community-current-audio.md`](../howto/community-current-audio.md), [`experiments/community_dictionary/README.md`](../experiments/community_dictionary/README.md), [`platform_server/community_dictionary/tests/test_entry_media.py`](../platform_server/community_dictionary/tests/test_entry_media.py)

### OBS-0045

Manny reports that the AWS update sequence worked. Kate and Axel asked how to start and were given minimal advice with a walkthrough available. Stéphanie expressed interest but expects to wait for Anne-Laure before trying it. This is human-reported deployment/onboarding progress, not a detailed device test or completed external pilot.

- **Observed:** 2026-09-29
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/save-ux-2026-09-30.md`](../experiments/community_dictionary/save-ux-2026-09-30.md), [`docs/howto/community-saving-and-invitations.md`](../howto/community-saving-and-invitations.md)

### OBS-0046

Cathy reports difficulty identifying and reaching Share, requests Save with a combined permission affirmation, and lost an unsaved image after leaving. Manny requests an existing-account invitation menu. A prepared patch implements these bounded UX changes, retaining media consent and owner-only invitation access. Source inspection found local draft persistence/restoration incorrectly suppressed unsaved-server warnings. Seventy Django tests and Chromium 153 iPhone 13/Pixel 7 viewport saving/recovery checks pass. The recording/partnership rehearsal also passes after an initial synthetic-meter timeout. No physical-device acceptance or production installation of this patch is claimed.

- **Observed:** 2026-09-30
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/save-ux-2026-09-30.md`](../experiments/community_dictionary/save-ux-2026-09-30.md), [`docs/howto/community-saving-and-invitations.md`](../howto/community-saving-and-invitations.md), [`platform_server/community_dictionary/tests/test_save_ux.py`](../platform_server/community_dictionary/tests/test_save_ux.py), [`experiments/community_dictionary/save_ux_browser.cjs`](../experiments/community_dictionary/save_ux_browser.cjs)

### OBS-0047

Manny reports installing the saving UX patch but cannot test as his normal account because the saved password was lost; admin login is still available. At his request, an incremental patch adds Admin account reset and Profile self-service password change, using Django password forms, eligibility checks, CSRF, session invalidation and password-free audit records. Fifteen new password tests plus existing Profile/Admin and all 70 dictionary tests pass (123 total). A controlled Chromium Pixel 7 viewport rehearsal completes reset, login, personal change and subsequent login. This is a prepared recovery path, not evidence of real account recovery or production deployment.

- **Observed:** 2026-09-30
- **Confidence:** high
- **Evidence:** [`docs/howto/account-passwords.md`](../howto/account-passwords.md), [`platform_server/projects/account_views.py`](../platform_server/projects/account_views.py), [`platform_server/projects/tests/test_passwords.py`](../platform_server/projects/tests/test_passwords.py), [`experiments/community_dictionary/password_browser_workflow.cjs`](../experiments/community_dictionary/password_browser_workflow.cjs)

### OBS-0048

Manny confirms the password-management patch worked and he can log in as himself on the laptop. Joint testing with Cathy reports missing apparent save for entry audio and no direct logout. Source inspection shows the visible entry recorder belongs to Discussion. The prepared incremental patch adds a focused pronunciation-recording page with explicit Save audio, folds and labels spoken discussion, and adds POST/CSRF-protected logout that preserves unsaved-draft choices and returns to dictionary login. Seven new backend tests bring the relevant set to 130 passing tests. A controlled Chromium rehearsal reproduces member photo/English, editor Swedish, recording/save/playback, failed-save/logout protection, recovery and spoken comments. Actual human acceptance of this increment is not yet reported.

- **Observed:** 2026-09-30
- **Confidence:** high
- **Evidence:** [`docs/howto/community-recording-and-logout.md`](../howto/community-recording-and-logout.md), [`platform_server/community_dictionary/tests/test_record_and_logout.py`](../platform_server/community_dictionary/tests/test_record_and_logout.py), [`experiments/community_dictionary/record_logout_browser.cjs`](../experiments/community_dictionary/record_logout_browser.cjs), [`experiments/community_dictionary/save_ux_browser.cjs`](../experiments/community_dictionary/save_ux_browser.cjs)

### OBS-0049

Manny confirms the preceding controls work on his laptop and requests check-in/deployment instructions. His next report describes about fifty working Swedish entries: Cathy contributed everyday/earlier photos and English meanings, Manny supplied Swedish wording and human audio. GitHub main b945623 is verified and includes saving, passwords, recording and logout. This supplies acceptance and meaningful joint-use evidence, without a detailed new AWS/device trace or learning-outcome evaluation.

- **Observed:** 2026-10-01
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/picture-word-links-2026-10-01.md`](../experiments/community_dictionary/picture-word-links-2026-10-01.md)

### OBS-0050

After considering multiple labels for a sofa/cat image, Manny requests manual menu-based extra links to existing dictionary words, complementary picture/word browsing, and inline listening/translation with separate navigation. The prepared increment implements specific-picture links with editor permissions, accepted-word/media filtering, original associations preserved, gallery navigation and export version 2. Migration 0005 adds a link table without rewriting existing entries. All 95 dictionary tests and a Chromium phone/desktop viewport rehearsal pass. AI tagging is deferred. No remote push/deployment, paid provider use or physical-device acceptance is claimed for this increment.

- **Observed:** 2026-10-01
- **Confidence:** high
- **Evidence:** [`docs/howto/community-picture-word-links.md`](../howto/community-picture-word-links.md), [`platform_server/community_dictionary/tests/test_lexicon.py`](../platform_server/community_dictionary/tests/test_lexicon.py), [`experiments/community_dictionary/lexicon_browser.cjs`](../experiments/community_dictionary/lexicon_browser.cjs), [`experiments/community_dictionary/picture-word-links-2026-10-01.md`](../experiments/community_dictionary/picture-word-links-2026-10-01.md)

### OBS-0051

Manny reports the manual picture/word links work first time on his laptop and the sofa/cat example behaves exactly as intended. Because his laptop dictionary is small, he proposes checking in and testing with the larger server dictionary. The documentation-only follow-up records this acceptance and the required AWS migration/static collection. Main remains b945623 at the check; neither a remote feature commit nor server/phone acceptance of this increment has yet been reported.

- **Observed:** 2026-10-01
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/picture-word-links-2026-10-01.md`](../experiments/community_dictionary/picture-word-links-2026-10-01.md), [`docs/howto/community-picture-word-links.md`](../howto/community-picture-word-links.md)

### OBS-0052

Manny reports the picture/word-link increment is installed on AWS and exploratory clicking works correctly. GitHub main ffbbef9 is verified with the exact locally available tree. This closes the deployment/exploratory-use uncertainty for that increment, without adding device-specific or sustained-use evidence.

- **Observed:** 2026-10-01
- **Confidence:** high
- **Evidence:** [`docs/howto/community-dictionary.md`](../howto/community-dictionary.md)

### OBS-0053

Manny clarifies that membership should persist with an inactive status and that word, translation and category require independent attribution. He authorises the agreed provenance/personal-collection/withdrawal/membership revision. The implementation preserves unchanged field credit, dependent source links, private retention and reviewed resharing, and offers optional two-coordinator decisions. 118 app tests pass, including migration/privacy/access checks; a Chromium phone/desktop rehearsal passes. This is a prepared patch, not an installed production release.

- **Observed:** 2026-10-01
- **Confidence:** high
- **Evidence:** [`docs/howto/community-contribution-control.md`](../howto/community-contribution-control.md), [`experiments/community_dictionary/contribution-control-2026-10-01.md`](../experiments/community_dictionary/contribution-control-2026-10-01.md), [`platform_server/community_dictionary/tests/test_contribution_control.py`](../platform_server/community_dictionary/tests/test_contribution_control.py), [`platform_server/community_dictionary/tests/test_provenance_migration.py`](../platform_server/community_dictionary/tests/test_provenance_migration.py)

### OBS-0054

Manny reports that the contribution-control revision installs, the server restarts and adding an entry works. He requests My contributions display complete entry context with other people's components greyed/marked for reference. The follow-up implements entry cards, entry pagination, matching own-component selection, visible history and permission-checked live private context. 128 app tests and a Chromium phone/desktop rehearsal pass; no schema changes. The report does not identify a new AWS or physical-phone trial, and full human workflow acceptance remains pending.

- **Observed:** 2026-10-01
- **Confidence:** high
- **Evidence:** [`docs/howto/community-contributions-by-entry.md`](../howto/community-contributions-by-entry.md), [`experiments/community_dictionary/contribution-display-2026-10-01.md`](../experiments/community_dictionary/contribution-display-2026-10-01.md), [`platform_server/community_dictionary/tests/test_contribution_display.py`](../platform_server/community_dictionary/tests/test_contribution_display.py), [`experiments/community_dictionary/contribution_display_browser.cjs`](../experiments/community_dictionary/contribution_display_browser.cjs)

### OBS-0055

Manny confirms further testing of My contributions and reports that it works as intended. He requests check-in and says he has asked Axel for the missing login-device details. This supplies human laptop acceptance of the entry-context display, without a per-action withdrawal/governance matrix or new AWS/phone claim. GitHub main remains ffbbef9 at the pre-check-in read. The follow-up records acceptance only; runtime code is unchanged and the prior 128-test/browser evidence is retained.

- **Observed:** 2026-10-01
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/contribution-display-2026-10-01.md`](../experiments/community_dictionary/contribution-display-2026-10-01.md), [`docs/howto/community-contributions-by-entry.md`](../howto/community-contributions-by-entry.md)

### OBS-0056

Manny reports the prior revisions checked in; main e4153586 and its tree match the delivered patches. Further laptop testing confirms image withdrawal/private retention but exposes a hard-to-find return path. He then confirms the route works and identifies the missed entry selector, requesting a direct original-dictionary sharing control. The prepared shortcut shows a fixed recorded destination and owned material for confirmation, reuses reviewed sharing, refuses unavailable origins and avoids duplicate active copies. 140 app tests and a Chromium rehearsal pass; no schema change or new production deployment is claimed.

- **Observed:** 2026-10-02
- **Confidence:** high
- **Evidence:** [`docs/howto/community-share-back.md`](../howto/community-share-back.md), [`experiments/community_dictionary/share-back-2026-10-02.md`](../experiments/community_dictionary/share-back-2026-10-02.md), [`platform_server/community_dictionary/tests/test_share_back.py`](../platform_server/community_dictionary/tests/test_share_back.py), [`experiments/community_dictionary/share_back_browser.cjs`](../experiments/community_dictionary/share_back_browser.cjs)

### OBS-0057

Manny's laptop feedback qualifies the first shortcut: an improvement, but confirmation and repeat review obstruct immediate visible restoration. The follow-up provides direct POST controls and retains valid same-origin approval, including older withdrawals and pending copies made by the prior patch. It preserves attribution/private copies, avoids duplicates/newer-text overwrites, and does not bypass later rejection/moderation, source custody or inactive membership. 148 app tests and a Chromium rehearsal pass; no migration, human acceptance or new production deployment is claimed.

- **Observed:** 2026-10-02
- **Confidence:** high
- **Evidence:** [`docs/howto/community-immediate-restore.md`](../howto/community-immediate-restore.md), [`experiments/community_dictionary/immediate-restore-2026-10-02.md`](../experiments/community_dictionary/immediate-restore-2026-10-02.md), [`platform_server/community_dictionary/tests/test_share_back.py`](../platform_server/community_dictionary/tests/test_share_back.py), [`experiments/community_dictionary/immediate_restore_browser.cjs`](../experiments/community_dictionary/immediate_restore_browser.cjs)

### OBS-0058

Manny confirms per-item restoration works but asks to replace fine-grained controls with an easily reversible dictionary-wide departure/rejoin model. He confirms withdrawal needs confirmation, owners should choose a successor, and all experimental laptop withdrawals may be restored by migration; he reports no AWS withdrawals. Implementation adds participation state, dependency holds, read-only own material, access enforcement, atomic handover/solo archiving and same-record restoration without overwriting newer shared text. Migrations 0008/0009 establish the schema and reset old collections while retaining attribution/history and avoiding visible identical duplicates. 156 SQLite app tests, including five old-schema migration fixtures, and a Chromium mobile/desktop rehearsal pass. New human acceptance and AWS/physical-phone testing remain pending.

- **Observed:** 2026-10-02
- **Confidence:** high
- **Evidence:** [`docs/howto/community-participation.md`](../howto/community-participation.md), [`experiments/community_dictionary/participation-2026-10-02.md`](../experiments/community_dictionary/participation-2026-10-02.md), [`platform_server/community_dictionary/tests/test_participation.py`](../platform_server/community_dictionary/tests/test_participation.py), [`platform_server/community_dictionary/tests/test_participation_migration.py`](../platform_server/community_dictionary/tests/test_participation_migration.py), [`experiments/community_dictionary/participation_browser.cjs`](../experiments/community_dictionary/participation_browser.cjs)

### OBS-0059

Manny reports that the new version appears fully working, is much better than the previous model, and has an essentially simple/intuitive conceptual structure; Sophie may suggest cosmetic changes. He proposes server deployment for a larger dictionary trial and confirms AWS remains behind the recent revisions. A documentation-only follow-up records this laptop acceptance and gives a deployment path from the older schema, with backups and stopped writers before changes, a forward migration to 0008, an empty-private-content audit before 0009, and controlled server checks. No new application code, production deployment or detailed per-action human evidence is claimed.

- **Observed:** 2026-10-02
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/participation-2026-10-02.md`](../experiments/community_dictionary/participation-2026-10-02.md), [`docs/howto/community-participation-aws.md`](../howto/community-participation-aws.md), [`docs/howto/community-dictionary.md`](../howto/community-dictionary.md)

### OBS-0060

Manny specifically reports that he tested ownership handover on the laptop and it appeared to work correctly. This adds human workflow evidence to the broad laptop acceptance report; it is not yet a server or physical-phone result.

- **Observed:** 2026-10-02
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/participation-2026-10-02.md`](../experiments/community_dictionary/participation-2026-10-02.md), [`docs/howto/community-participation-aws.md`](../howto/community-participation-aws.md)

### OBS-0061

Manny supplies AWS backup, migration and service traces, then reports successful withdrawal/restoration after following the suggested sequence. PostgreSQL 18.3 required version 18 clients (18.6 installed); public media was 22 GB and private media 23 MB. Both uncompressed archives passed source comparison. Migrations 0006–0008 applied, the audit found zero private contributions/entries, and 0009 applied. Services initially failed after code deployment with the backup's umask 077 still active; resetting the mask and source-code permissions restored all three services. Manny could use the new controls, then confirmed the trial worked as intended and planned to notify testers and seek Sophie's feedback. Documentation corrects the client, progress and permission steps; exact deployed SHA, a full restore rehearsal and new physical-device details were not supplied.

- **Observed:** 2026-10-02
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/participation-aws-2026-10-02.md`](../experiments/community_dictionary/participation-aws-2026-10-02.md), [`docs/howto/community-participation-aws.md`](../howto/community-participation-aws.md), [`docs/howto/community-dictionary.md`](../howto/community-dictionary.md)

### OBS-0062

Manny reports successful login to AWS from his laptop after the username-input repair and plans to ask Axel to retry. This confirms laptop access, not resolution of the original iPhone casing behaviour.

- **Observed:** 2026-10-03
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/image-generation-2026-10-03.md`](../experiments/community_dictionary/image-generation-2026-10-03.md)

### OBS-0063

Manny requests optional image generation and relays Sophie's photo-understanding-to-illustration proposal for a later iteration. The prepared text-only implementation adds owner opt-in, editor-approved shared style/sample, private single-candidate previews, contribution review/provenance, source-linked withdrawal, quotas and idempotent paid requests. 181 app tests and a mocked-provider Chromium rehearsal pass. Of 220 combined app/C-LARA image tests, two old page-image failures reproduce on the unchanged base. No paid output, actual quality/cost trial, production installation or physical-phone check is claimed.

- **Observed:** 2026-10-03
- **Confidence:** high
- **Evidence:** [`docs/howto/community-image-generation.md`](../howto/community-image-generation.md), [`experiments/community_dictionary/image-generation-2026-10-03.md`](../experiments/community_dictionary/image-generation-2026-10-03.md), [`platform_server/community_dictionary/tests/test_image_generation.py`](../platform_server/community_dictionary/tests/test_image_generation.py)

### OBS-0064

Manny reports that optional image generation works in laptop testing and requests Settings navigation plus access to manual photos after entering words. Code inspection finds the manual route under Add a contribution, with no AI-based upload restriction. The prepared follow-up adds a Settings page with existing role boundaries and an explicit Add a photo flow for existing entries. 189 app tests pass; Chromium checks text-first camera/upload with AI off/on, preservation of selected media, member controls and 320/390/1280px layouts. No schema change, paid call for this repair, follow-up human acceptance or AWS deployment is claimed.

- **Observed:** 2026-10-03
- **Confidence:** high
- **Evidence:** [`docs/howto/community-settings-and-photos.md`](../howto/community-settings-and-photos.md), [`experiments/community_dictionary/image-generation-2026-10-03.md`](../experiments/community_dictionary/image-generation-2026-10-03.md), [`platform_server/community_dictionary/tests/test_settings_and_pictures.py`](../platform_server/community_dictionary/tests/test_settings_and_pictures.py), [`experiments/community_dictionary/image_browser_workflow.cjs`](../experiments/community_dictionary/image_browser_workflow.cjs)

### OBS-0065

Manny reports successful laptop acceptance of the Settings/manual-photo follow-up, then successful installation and operation on AWS. He requested a photorealistic style and judged two generated images good, while explicitly calling for more user feedback. This closes the deployment question for image generation; it supplies neither a systematic quality/cost series nor device/browser details or an exact deployed SHA.

- **Observed:** 2026-10-03
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/practice-2026-10-03.md`](../experiments/community_dictionary/practice-2026-10-03.md), [`docs/howto/community-image-generation.md`](../howto/community-image-generation.md)

### OBS-0066

Manny proposes all six flashcard directions, picture crosswords and word scrambles in one update as an implementation-scale experiment, guessing 60–90 minutes. The assistant prepares a single Practise tab with self-assessed cards and picture grid games, extracting the existing puzzle builders unchanged into a shared pure module. 205 app tests plus two existing C-LARA puzzle tests pass. Browser trials cover playback, completion, Unicode answers, reverse word-search endpoints, categories, content invalidation, connection failure and mobile layouts. Visual inspection prompts an internal mobile-layout/grid-size refinement. No new requirements handoff, paid call, schema change or production deployment is performed; real-user acceptance remains pending.

- **Observed:** 2026-10-03
- **Confidence:** high
- **Evidence:** [`docs/howto/community-practice.md`](../howto/community-practice.md), [`experiments/community_dictionary/practice-2026-10-03.md`](../experiments/community_dictionary/practice-2026-10-03.md), [`platform_server/community_dictionary/tests/test_practice.py`](../platform_server/community_dictionary/tests/test_practice.py), [`experiments/community_dictionary/practice_browser_workflow.cjs`](../experiments/community_dictionary/practice_browser_workflow.cjs)

### OBS-0067

Manny reports that the first practice increment works, but asks for multiple-choice answers like those users liked in C-LARA-2. The follow-up provides two-to-four real options in all six modes, makes choice the UI default and retains reveal mode. Three existing duplicate-check helpers are extracted unchanged, with community picture-link/translation exclusions added. 215 app tests and three legacy tests pass; browser checks cover all choice modalities, playback versus selection, retries, scoring, reveal/skip/completion, invalidation and phone layouts. Internal tests caught a phrase/inflection distractor edge case and visual review caught feedback overflow; both were corrected before delivery. This records one human requirements correction after initial laptop acceptance, not zero-intervention completion.

- **Observed:** 2026-10-03
- **Confidence:** high
- **Evidence:** [`docs/howto/community-practice-choices.md`](../howto/community-practice-choices.md), [`experiments/community_dictionary/practice-2026-10-03.md`](../experiments/community_dictionary/practice-2026-10-03.md), [`platform_server/community_dictionary/tests/test_practice_choices.py`](../platform_server/community_dictionary/tests/test_practice_choices.py), [`experiments/community_dictionary/practice_browser_workflow.cjs`](../experiments/community_dictionary/practice_browser_workflow.cjs)

### OBS-0068

Manny reports practice deployed and working on AWS and explicitly requests language porting with concurrent entries, cost estimates, approval and insufficient-funds feedback. The prepared additive 0011 increment implements independent languages, multimodal candidates, review, matching TTS reuse, protected corrections, credit reservations/refunds, durable claims and source withdrawal/restoration. 243 tests pass. Chromium rehearsals cover eight items through two real queue worker processes and the laptop adapter, with overlapping simulated calls and no browser errors. Human porting acceptance, live translation/TTS quality and PostgreSQL deployment remain pending.

- **Observed:** 2026-10-04
- **Confidence:** high
- **Evidence:** [`docs/howto/community-language-porting.md`](../howto/community-language-porting.md), [`experiments/community_dictionary/language-porting-2026-10-04.md`](../experiments/community_dictionary/language-porting-2026-10-04.md), [`platform_server/community_dictionary/tests/test_porting.py`](../platform_server/community_dictionary/tests/test_porting.py), [`platform_server/community_dictionary/port_tasks.py`](../platform_server/community_dictionary/port_tasks.py)

### OBS-0069

Manny successfully ports a small Swedish/English dictionary to French/English on the laptop and reports category, pronunciation and image-veto defects. Code inspection confirms categories were tied to the commenting language, uncertain results could not be saved, and TTS already received a language hint. The prepared 0012 follow-up strengthens that hint, adds example-based category decisions and editable uncertainty, repairs old unedited outputs through approved updates, and preserves context withdrawal dependencies. 257 app tests, six shared audio tests and the two-real-worker Chromium rehearsal pass. No assistant-run paid call or post-fix human acceptance is claimed.

- **Observed:** 2026-10-04
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/language-porting-fixes-2026-10-04.md`](../experiments/community_dictionary/language-porting-fixes-2026-10-04.md), [`docs/howto/community-language-porting.md`](../howto/community-language-porting.md), [`platform_server/community_dictionary/tests/test_porting.py`](../platform_server/community_dictionary/tests/test_porting.py), [`platform_server/community_dictionary/port_categories.py`](../platform_server/community_dictionary/port_categories.py), [`src/pipeline/audio.py`](../src/pipeline/audio.py)

### OBS-0070

Manny confirms category and king/roi fixes, supplies multilingual listening ratings, and requests a bounded TTS repair. Prepared homograph guidance uses a local English list and one structured text call, keeps exact spoken input, retries only completed quiet output once, and flags review risks. Cost estimates/accounting include guidance and completed retries; permissions and withdrawal dependencies cover meaning-derived speech. Old estimates/queued jobs require new approval. 275 Django tests and six offline shared audio tests pass; generated start/preview/entry pages show warnings at 390px/1280px. This is simulated-provider verification; no paid call or human acceptance of this integrated version is claimed.

- **Observed:** 2026-10-05
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/tts-guidance-2026-10-05.md`](../experiments/community_dictionary/tts-guidance-2026-10-05.md), [`docs/howto/community-tts-guidance.md`](../howto/community-tts-guidance.md), [`platform_server/community_dictionary/tests/test_tts_guidance.py`](../platform_server/community_dictionary/tests/test_tts_guidance.py), [`platform_server/community_dictionary/tts.py`](../platform_server/community_dictionary/tts.py)

### OBS-0071

Manny reports chat/lit generation succeeded and subsequently that everything worked on the small laptop dictionary. He requests check-in and larger AWS conversion. The intervening unstyled-page report was diagnosed as the supplied runserver command omitting --insecure with DEBUG=False; deployment notes now correct it. A scoped database/private-media backup and forward-only AWS runbook is prepared. No AWS deployment or larger trial has been performed by the assistant.

- **Observed:** 2026-10-05
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/tts-guidance-2026-10-05.md`](../experiments/community_dictionary/tts-guidance-2026-10-05.md), [`docs/howto/community-tts-guidance.md`](../howto/community-tts-guidance.md), [`docs/howto/community-language-porting-aws.md`](../howto/community-language-porting-aws.md)

### OBS-0072

Manny reports AWS entry access recovered after stopping/restarting services, followed by conversion/review of 61 Swedish/English entries to French/English. He identifies four initial TTS problems (curry, mug, lac, bus); lac improves after regeneration and autobus after rewording, while curry/mug remain unsatisfactory. He requests next-item saving, saved-word labels and attention flags. The prepared UX patch adds these with private drafts/notes and migration 0014; 286 app tests and real Django/Chromium workflow checks at 390/1280px pass. AWS trial evidence is human-reported; the assistant made no paid calls and has not deployed the new UI.

- **Observed:** 2026-10-05
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/porting-aws-2026-10-05.md`](../experiments/community_dictionary/porting-aws-2026-10-05.md), [`docs/howto/community-port-review.md`](../howto/community-port-review.md), [`docs/howto/community-language-porting-aws.md`](../howto/community-language-porting-aws.md), [`platform_server/community_dictionary/tests/test_port_review.py`](../platform_server/community_dictionary/tests/test_port_review.py)

### OBS-0073

Manny accepts the new review workflow on his laptop and calls it much faster, then reports AWS deployment and a German/English version of the 61-entry Swedish/English dictionary. He reports noticing only curry as a TTS problem while explicitly qualifying his German listening ability. He requests a short French LaTeX update for Indigenous-language partners, with an informal estimate of about five hours of AI development across about one week and human installation/testing/feedback. A three-page source and compiled, visually checked PDF are prepared; no stakeholder message has been sent.

- **Observed:** 2026-10-05
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/german-port-review-2026-10-05.md`](../experiments/community_dictionary/german-port-review-2026-10-05.md), [`docs/howto/community-port-review.md`](../howto/community-port-review.md), [`docs/publications/community_dictionaries_update_fr/README.md`](../publications/community_dictionaries_update_fr/README.md), [`docs/publications/community_dictionaries_update_fr/latex/community_dictionaries_update_fr.tex`](../publications/community_dictionaries_update_fr/latex/community_dictionaries_update_fr.tex)

### OBS-0074

Manny reports that he mailed the French note to Sophie, Stéphanie and Anne-Laure, then checked in and deployed the documentation. He plans to wait for Indigenous-language partner feedback before updating the wider team; a proposed end-of-week Zoom has no agreed time and no response is yet reported.

- **Observed:** 2026-10-07
- **Confidence:** high
- **Evidence:** [`docs/publications/community_dictionaries_update_fr/README.md`](../publications/community_dictionaries_update_fr/README.md), [`experiments/community_dictionary/picture-capture-2026-10-07.md`](../experiments/community_dictionary/picture-capture-2026-10-07.md)

### OBS-0075

Manny requests a faster picture-centred AI-supported workflow and authorizes implementation. The prepared, off-by-default first cut supports new/existing images, typed/spoken intended descriptions in either language, bilingual confirmation, contributor-confirmed publication with sentence/word/audio links, background TTS and shared attention/editor checks. 310 tests and a simulated-provider Chromium rehearsal pass. Source withdrawal/restore and edit-sensitive links are covered. No paid API call or new laptop/AWS/physical-phone acceptance is claimed.

- **Observed:** 2026-10-07
- **Confidence:** high
- **Evidence:** [`docs/howto/community-picture-descriptions.md`](../howto/community-picture-descriptions.md), [`experiments/community_dictionary/picture-capture-2026-10-07.md`](../experiments/community_dictionary/picture-capture-2026-10-07.md), [`platform_server/community_dictionary/tests/test_picture_capture.py`](../platform_server/community_dictionary/tests/test_picture_capture.py)

### OBS-0076

Manny reports nearly everything in the first picture-description cut working on the laptop, a much faster/more intuitive workflow and a more useful dictionary. For Katten sträcker ut sig på soffan, however, it offers sträcka and ut rather than sträcka ut sig. He requests MWE reuse, editable suggestions and a temporary image-only copy control before larger AWS tests.

- **Observed:** 2026-10-07
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/picture-vocabulary-2026-10-07.md`](../experiments/community_dictionary/picture-vocabulary-2026-10-07.md)

### OBS-0077

The prepared incremental patch adapts existing MWE templates/examples within the joint interpretation call (not the full annotation pipeline or another paid call), handles discontinuous expressions, permits bounded vocabulary edits/additions/removals, and creates owner-only image test copies retaining original custody and source withdrawal/restoration. 324 app tests pass; no new migration is needed. Real Django/Chromium tests at mobile/desktop widths use simulated providers. No live linguistic accuracy or human acceptance of this follow-up is yet claimed.

- **Observed:** 2026-10-07
- **Confidence:** high
- **Evidence:** [`docs/howto/community-picture-descriptions.md`](../howto/community-picture-descriptions.md), [`docs/howto/community-picture-vocabulary-install.md`](../howto/community-picture-vocabulary-install.md), [`experiments/community_dictionary/picture-vocabulary-2026-10-07.md`](../experiments/community_dictionary/picture-vocabulary-2026-10-07.md), [`platform_server/community_dictionary/tests/test_capture_vocabulary.py`](../platform_server/community_dictionary/tests/test_capture_vocabulary.py)

### OBS-0078

Manny reports that the follow-up works on the small Swedish laptop dictionary, asks to check in and redeploy to AWS, and explicitly defers further MWE work until after a broader functionality trial. The new release notes/runbook change no runtime code. The prior 324-test result is retained, not a new run; migration 0015 is the expected AWS upgrade from 0014. No assistant deployment or new AWS/phone acceptance is claimed.

- **Observed:** 2026-10-07
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/picture-vocabulary-2026-10-07.md`](../experiments/community_dictionary/picture-vocabulary-2026-10-07.md), [`docs/howto/community-picture-descriptions-aws.md`](../howto/community-picture-descriptions-aws.md)

### OBS-0079

Manny reports AWS redeployment succeeded and three examples were tried in an image-only Swedish dictionary. Two described cases produced correct sentences/vocabulary/links, but both exposed retained blank source cards; cat/chess sentence audio failed after repeated page refreshes. The 42-character text is below the app limit of 255. Code inspection confirms source-card duplication and the inappropriate whole-sentence homograph-coaching path triggered by En, but not the specific AWS failure cause. A focused patch has 334 passing mocked-provider tests, passing Chromium progress/playback checks and no migration. GitHub main was observed at 06747ea; actual AWS HEAD and the original provider exception remain unobserved.

- **Observed:** 2026-10-07
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/picture-capture-aws-fixes-2026-10-07.md`](../experiments/community_dictionary/picture-capture-aws-fixes-2026-10-07.md), [`docs/howto/community-picture-capture-aws-fixes.md`](../howto/community-picture-capture-aws-fixes.md), [`platform_server/community_dictionary/tests/test_capture_aws_fixes.py`](../platform_server/community_dictionary/tests/test_capture_aws_fixes.py)

### OBS-0080

Manny reports that AWS use in laptop Chrome works very well for typed/spoken input in English/Swedish; the only obvious error he noticed was an i bakgrunden audio timeout followed by inability to access regenerated audio from its example. He hopes to test with Cathy on 8 October before specifying more UX changes. Code inspection and regressions confirm that fresh server views already use accepted shared replacement audio, but restored pages need refresh after completed jobs and old timeout notices persist. A focused patch passes 338 mocked-provider app tests and Chromium recovery/lifecycle simulation. The actual AWS timeout, browser-cache usage and replacement save/review state remain unobserved. No new phone acceptance or accuracy estimate is claimed.

- **Observed:** 2026-10-07
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/audio-recovery-2026-10-07.md`](../experiments/community_dictionary/audio-recovery-2026-10-07.md), [`docs/howto/community-audio-recovery.md`](../howto/community-audio-recovery.md), [`platform_server/community_dictionary/tests/test_audio_recovery.py`](../platform_server/community_dictionary/tests/test_audio_recovery.py)

### OBS-0081

On 8 October Manny confirms missing audio is now correctly generated and requests a configurable daily image-understanding allowance with estimated cost and confirmation before systematic testing. The ten-request limit is specifically Picture descriptions. An owner-only shared allowance is prepared with default ten per rolling 24 hours, signed expiring cost approval, retained usage, unchanged billing ownership, and additive migration 0016. There are 349 passing app tests and a mocked Chromium Settings/preview/cancel/confirm/member-request-eleven rehearsal. No live API request or production deployment was performed; new allowance acceptance remains pending.

- **Observed:** 2026-10-08
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/capture-limits-2026-10-08.md`](../experiments/community_dictionary/capture-limits-2026-10-08.md), [`docs/howto/community-picture-description-limits.md`](../howto/community-picture-description-limits.md), [`platform_server/community_dictionary/tests/test_capture_limits.py`](../platform_server/community_dictionary/tests/test_capture_limits.py)

### OBS-0082

On 8 October Manny reports the allowance change appeared to work and requests an owner-only visibility toggle after Cathy was confused by original and image-only-derived Swedish dictionary versions. The prepared change hides a dictionary from the normal list for all its existing audience, retaining a collapsed Hidden dictionaries section, direct authorized access and contributor rights. Migration 0017 defaults existing/new dictionaries to visible. There are 356 passing app tests and a synthetic owner/member Chromium hide/open/restore rehearsal. No new live deployment or physical-phone trial is claimed; the environment of allowance acceptance is unspecified.

- **Observed:** 2026-10-08
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/visibility-2026-10-08.md`](../experiments/community_dictionary/visibility-2026-10-08.md), [`docs/howto/community-dictionary-visibility.md`](../howto/community-dictionary-visibility.md), [`platform_server/community_dictionary/tests/test_dictionary_visibility.py`](../platform_server/community_dictionary/tests/test_dictionary_visibility.py)

### OBS-0083

On 8 October Manny reports visibility works (environment unspecified), then explicitly pauses WordPress/email-password-reset work and requests equal Type/Speak/AI description routes. Cathy prefers AI suggestions. The implemented first cut retains common bilingual review, editable vocabulary, confirmation, source provenance and audio, adds mode memory and omits unused inputs. 365 app tests and mocked Chromium 390/1280px workflow checks pass; no new migration or live deployment is claimed. Real AI quality and user acceptance of this increment remain pending.

- **Observed:** 2026-10-08
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/ai-descriptions-2026-10-08.md`](../experiments/community_dictionary/ai-descriptions-2026-10-08.md), [`docs/howto/community-ai-descriptions.md`](../howto/community-ai-descriptions.md), [`platform_server/community_dictionary/tests/test_ai_descriptions.py`](../platform_server/community_dictionary/tests/test_ai_descriptions.py)

### OBS-0084

On 8 October Manny reports the three description modes work (environment unspecified) and requests status selection plus fresh pending review for image-only copies. Code inspection confirms accepted-only copying; it also shows Accepted did not itself block description, whereas pending images previously could not enter capture and copies inherit AI settings. The prepared follow-up creates pending copies from accepted/pending/both sources, and supports owner/editor pending-picture preview, atomic approval/publication and next-picture navigation. 376 app tests and a mocked 390/1280px browser rehearsal pass. No migration, paid call, new live deployment or phone trial is claimed.

- **Observed:** 2026-10-08
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/image-copy-review-2026-10-08.md`](../experiments/community_dictionary/image-copy-review-2026-10-08.md), [`docs/howto/community-image-copy-review.md`](../howto/community-image-copy-review.md), [`platform_server/community_dictionary/tests/test_copy_review.py`](../platform_server/community_dictionary/tests/test_copy_review.py)

### OBS-0085

Manny accepts the image-copy follow-up and reports over 150 image-associated Swedish sentences, with about 90% of AI suggestions accepted unchanged. His French/English port showed progress but no entries. Code inspection finds a word-only selector and a separate preview/save boundary; no production job was inspected. The prepared sentence-port extension preserves types, pictures, sentence speech and reviewed vocabulary links, supports old word previews and incremental updates, and clarifies ready versus saved status. 391 app tests and mocked Chromium 320/390/1280px checks pass; no migration, paid calls or deployment is claimed.

- **Observed:** 2026-10-08
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/sentence-porting-2026-10-08.md`](../experiments/community_dictionary/sentence-porting-2026-10-08.md), [`docs/howto/community-sentence-porting.md`](../howto/community-sentence-porting.md), [`platform_server/community_dictionary/tests/test_sentence_porting.py`](../platform_server/community_dictionary/tests/test_sentence_porting.py)

### OBS-0086

On 9 October Manny reports AWS sentence-port success but mismatched French word links (repose versus être couché ; se trouver). He requests reviewed sentences first, then vocabulary from the final wording, shared lemma/sense pages, contextual review, bulk acceptance and edit tracking. The prepared implementation adds a vocabulary stage, shared capture/MWE/publication logic, bounded audio jobs, separate cost approval, legacy repair and additive migration 0018. 410 mocked-provider app tests and Chromium 320/390/1280px rehearsal pass. No live provider call, production write or physical-phone trial was performed. Conservative gloss-based sense matching and live linguistic quality remain limitations.

- **Observed:** 2026-10-09
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/two-stage-porting-2026-10-09.md`](../experiments/community_dictionary/two-stage-porting-2026-10-09.md), [`docs/howto/community-two-stage-porting.md`](../howto/community-two-stage-porting.md), [`platform_server/community_dictionary/tests/test_port_vocabulary.py`](../platform_server/community_dictionary/tests/test_port_vocabulary.py)

### OBS-0087

Manny reports initial use of the two-stage vocabulary release followed by site-wide HTTP 500s on AWS. A service-identity diagnostic fails with RDS reserved-slot exhaustion; a subsequent diagnostic succeeds, confirms max_connections=79, nine total connections including one clara2 diagnostic, migrations through 0018 applied, USE_REAL_DJANGO_Q=False and the repository fallback selected. The fallback ignored workers and omitted task connection cleanup. Retained-wrapper file-backed SQLite reproduction leaves 20/20 baseline connections open and 0/20 after the patch. Eight new regressions and all 451 Community Dictionaries/admin-tools tests pass locally; no schema change, paid request or production mutation was made. RDS load verification and post-fix browser/conversion acceptance remain pending.

- **Observed:** 2026-10-09
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/queue-recovery-2026-10-09.md`](../experiments/community_dictionary/queue-recovery-2026-10-09.md), [`docs/howto/community-queue-recovery.md`](../howto/community-queue-recovery.md), [`src/django_q/tasks.py`](../src/django_q/tasks.py), [`platform_server/community_dictionary/tests/test_background_queue.py`](../platform_server/community_dictionary/tests/test_background_queue.py)

### OBS-0088

Manny reports successful completion of the resumed AWS French/English conversion and consistent sentence/word links on browsing. He requests merged word lists, completed-content controls and pronunciation warnings hidden behind Show more options, and agrees to the same principle for word pages. The prepared reading-page patch deduplicates by word-entry identity, preserves separate senses and stale-audio guards, keeps missing-content actions and reporting accessible, and retains editing and review under native disclosure controls. All 422 app tests pass locally; Chromium at 320/390/1280px verifies playback, translation reveals, disclosure, missing/stale-content actions and no overflow/JS errors. No production write or provider request was made for this UI patch.

- **Observed:** 2026-10-09
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/entry-options-2026-10-09.md`](../experiments/community_dictionary/entry-options-2026-10-09.md), [`docs/howto/community-entry-options.md`](../howto/community-entry-options.md), [`platform_server/community_dictionary/tests/test_entry_options.py`](../platform_server/community_dictionary/tests/test_entry_options.py), [`platform_server/community_dictionary/templates/community_dictionary/entry.html`](../platform_server/community_dictionary/templates/community_dictionary/entry.html), [`platform_server/community_dictionary/templates/community_dictionary/word.html`](../platform_server/community_dictionary/templates/community_dictionary/word.html)

### OBS-0089

Manny reports that the reading-page cleanup works and is much better, superseding pending human layout acceptance without identifying a new device matrix. He asks for optional-hint batch sentence generation followed by reviewed vocabulary, dictionary renaming and top-level sentence/word counts. The prepared same-dictionary mode shares cost/reservation, bounded queue, recovery and review code with language ports. It preserves existing sentences, contributor ownership and valid previews, includes pending pictures explicitly, and uses final accepted sentences for shared lemma/sense vocabulary. A full 475-test regression run passed; final focused coverage is 26 passing tests. A mocked Chromium 320/390/1280px rehearsal verifies the end-to-end workflow, playback, counts and incremental skips. Migration 0019 was tested on disposable SQLite databases; live provider, Windows, physical-phone and AWS acceptance remain pending.

- **Observed:** 2026-10-10
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/batch-descriptions-2026-10-10.md`](../experiments/community_dictionary/batch-descriptions-2026-10-10.md), [`docs/howto/community-batch-descriptions.md`](../howto/community-batch-descriptions.md), [`platform_server/community_dictionary/tests/test_batch_descriptions.py`](../platform_server/community_dictionary/tests/test_batch_descriptions.py), [`platform_server/community_dictionary/batch_descriptions.py`](../platform_server/community_dictionary/batch_descriptions.py), [`platform_server/community_dictionary/migrations/0019_batch_descriptions.py`](../platform_server/community_dictionary/migrations/0019_batch_descriptions.py)

### OBS-0090

Manny reports that the batch-description update works as expected on the laptop and, after the explicit deployment sequence, on AWS too. This closes the pending initial laptop/AWS acceptance recorded in revision 62; no detailed new device matrix or prolonged unattended reliability evidence is supplied.

- **Observed:** 2026-10-10
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/email-password-reset-2026-10-10.md`](../experiments/community_dictionary/email-password-reset-2026-10-10.md), [`docs/howto/community-batch-descriptions.md`](../howto/community-batch-descriptions.md)

### OBS-0091

Manny resumes email password recovery, corrects the mailbox provider to Google Workspace and reports having an app password; no secret was supplied. The prepared shared account workflow adds branded reset pages, one-hour tokens, fixed-origin links, database-wide request limits and a safe mail diagnostic. Projects migration 0044 adds only counters. 514 regression tests, the final 28 focused tests and both 320/390/1280px browser flows pass. No live SMTP or AWS operation was performed. Manny separately requests optional anonymous browsing, disabled by default and owner-controlled; that remains proposed with existing dictionary permissions unchanged.

- **Observed:** 2026-10-10
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/email-password-reset-2026-10-10.md`](../experiments/community_dictionary/email-password-reset-2026-10-10.md), [`docs/howto/email-password-reset.md`](../howto/email-password-reset.md), [`docs/howto/email-password-reset-install.md`](../howto/email-password-reset-install.md), [`platform_server/projects/tests/test_email_reset.py`](../platform_server/projects/tests/test_email_reset.py), [`platform_server/projects/email_reset.py`](../platform_server/projects/email_reset.py), [`platform_server/projects/migrations/0044_passwordresetlimit.py`](../platform_server/projects/migrations/0044_passwordresetlimit.py)

### OBS-0092

Manny confirms end-to-end AWS password reset and login to the intended dummy account. His earlier difficulty was confusion between accounts sharing an email address, not a reproduced reset defect; the message named the account correctly. This closes the pending initial delivery/recovery outcome from revision 63. Cathy's independent trial is planned but unreported.

- **Observed:** 2026-10-11
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/public-browsing-2026-10-11.md`](../experiments/community_dictionary/public-browsing-2026-10-11.md)

### OBS-0093

Manny requests the previously discussed anonymous browse-only option. The prepared increment adds a default-off owner setting with contributor-permission confirmation, separate accepted-only visitor pages, audio/search/links, and live withdrawal/revocation checks. Hidden/archive/personal dictionaries remain unavailable; hiding disables public access and unhiding does not republish. Migration 0020 is additive. 536 SQLite regression tests and a disposable Chromium rehearsal at 320/390/1280px pass. No live account, AI, SMTP or production operation is performed; human laptop/AWS/phone acceptance remains pending.

- **Observed:** 2026-10-11
- **Confidence:** high
- **Evidence:** [`docs/howto/community-public-browsing.md`](../howto/community-public-browsing.md), [`docs/howto/community-public-browsing-install.md`](../howto/community-public-browsing-install.md), [`experiments/community_dictionary/public-browsing-2026-10-11.md`](../experiments/community_dictionary/public-browsing-2026-10-11.md), [`platform_server/community_dictionary/public_browsing.py`](../platform_server/community_dictionary/public_browsing.py), [`platform_server/community_dictionary/public_views.py`](../platform_server/community_dictionary/public_views.py), [`platform_server/community_dictionary/tests/test_public_browsing.py`](../platform_server/community_dictionary/tests/test_public_browsing.py), [`platform_server/community_dictionary/migrations/0020_public_browsing.py`](../platform_server/community_dictionary/migrations/0020_public_browsing.py)

### OBS-0094

Manny reports that anonymous browsing works and is deployed on AWS. He proposes a short illustrated introductory paper, broad dissemination and credit-supported trials to obtain user feedback. Specific outcome rates, claims about author eligibility on dissemination services and funding terms still need substantiation or finalization before publication; current practice games use existing content without paid AI calls. The report is not written or posted in this coding increment.

- **Observed:** 2026-10-11
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/discovery-profiles-2026-10-11.md`](../experiments/community_dictionary/discovery-profiles-2026-10-11.md)

### OBS-0095

The requested discovery/profile/About increment is prepared against main 4d90cf8. Metadata discovery and public content access are independent owner choices, both default off. Requests are private, bounded, owner-decided and cannot bypass existing roles, invitations, inactivity or withdrawal. Public contributor identity is separately opt-in; account credentials and private dictionaries are excluded. Shared account preferences and password change remain available within Community Dictionaries. 564 SQLite tests and two 320/390/1280px Chromium rehearsals pass; migration 0021 is additive. No live SMTP/AI or production actions were performed. Laptop/AWS acceptance of this increment remains pending.

- **Observed:** 2026-10-11
- **Confidence:** high
- **Evidence:** [`docs/howto/community-discovery-profiles.md`](../howto/community-discovery-profiles.md), [`docs/howto/community-discovery-profiles-install.md`](../howto/community-discovery-profiles-install.md), [`experiments/community_dictionary/discovery-profiles-2026-10-11.md`](../experiments/community_dictionary/discovery-profiles-2026-10-11.md), [`platform_server/community_dictionary/tests/test_discovery_profiles.py`](../platform_server/community_dictionary/tests/test_discovery_profiles.py), [`platform_server/community_dictionary/migrations/0021_discovery_profiles.py`](../platform_server/community_dictionary/migrations/0021_discovery_profiles.py)

### OBS-0096

Manny reports the discovery/profile/About increment works and requests anonymous practice without AI calls, proactive suggestions to create missing sentences/word pages with one-click confirmation and a Settings opt-out, plus prominent action indicators on dictionary cards. He authorizes a first implementation. The acceptance message does not specify laptop or AWS; remote main includes the discovery increment at 7cb9a82.

- **Observed:** 2026-10-11
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/practice-guidance-2026-10-11.md`](../experiments/community_dictionary/practice-guidance-2026-10-11.md)

### OBS-0097

The prepared increment reuses accepted-only public projections for six-mode flashcards and both puzzles. Owner cards and Browse show one prioritized next step: membership requests, unflagged reviews, progress, vocabulary, or missing sentences. No GET starts paid work. Signed expiring approval binds scope, snapshots, languages, model, voice, prices and payer; rechecks, app-credit reservation and retry receipts reuse existing transactional jobs. Migration 0022 adds a default-on owner preference; AI/public access remain independent opt-ins. The 591-test local suite passes, followed by 17 guidance checks after the flag-selection refinement; Chromium at 320/390/1280px verifies games, revocation, approval and opt-out. Physical phones, real providers and production PostgreSQL acceptance remain pending.

- **Observed:** 2026-10-11
- **Confidence:** high
- **Evidence:** [`docs/howto/community-practice-guidance.md`](../howto/community-practice-guidance.md), [`docs/howto/community-practice-guidance-install.md`](../howto/community-practice-guidance-install.md), [`experiments/community_dictionary/practice-guidance-2026-10-11.md`](../experiments/community_dictionary/practice-guidance-2026-10-11.md), [`platform_server/community_dictionary/workflow.py`](../platform_server/community_dictionary/workflow.py), [`platform_server/community_dictionary/workflow_views.py`](../platform_server/community_dictionary/workflow_views.py), [`platform_server/community_dictionary/public_practice.py`](../platform_server/community_dictionary/public_practice.py), [`platform_server/community_dictionary/tests/test_workflow_guidance.py`](../platform_server/community_dictionary/tests/test_workflow_guidance.py), [`platform_server/community_dictionary/tests/test_public_practice.py`](../platform_server/community_dictionary/tests/test_public_practice.py), [`platform_server/community_dictionary/migrations/0022_workflow_suggestions.py`](../platform_server/community_dictionary/migrations/0022_workflow_suggestions.py)

### OBS-0098

Manny reports successful AWS installation and useful initial workflow suggestions, after collectstatic permissions were repaired for the generated static directory. Six newly processed Swedish pictures did not prompt an update to the existing French version; he explicitly authorizes the related-dictionary guidance extension. Main now contains the prior guidance release at 5773432. No independent server inspection was performed.

- **Observed:** 2026-10-12
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/port-guidance-2026-10-12.md`](../experiments/community_dictionary/port-guidance-2026-10-12.md), [`docs/howto/community-practice-guidance-install.md`](../howto/community-practice-guidance-install.md)

### OBS-0099

The prepared extension shares the incremental port planner, shows new/changed accepted sentence updates on both authorized dictionary cards/Browse pages, protects destination edits and uses existing signed approval, reservations, review and destination-vocabulary stages. Existing progress/review work and local tasks take priority; destination opt-out suppresses related notices. Category growth retains established decisions while their original evidence is valid. All 609 local tests pass in 131.816 seconds, with 18 new guidance cases and a 320/390/1280px Chromium rehearsal. No migration/static/dependency change, provider calls or AWS operation; production and physical-phone acceptance remain pending.

- **Observed:** 2026-10-12
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/port-guidance-2026-10-12.md`](../experiments/community_dictionary/port-guidance-2026-10-12.md), [`docs/howto/community-port-guidance.md`](../howto/community-port-guidance.md), [`docs/howto/community-port-guidance-install.md`](../howto/community-port-guidance-install.md), [`platform_server/community_dictionary/workflow.py`](../platform_server/community_dictionary/workflow.py), [`platform_server/community_dictionary/porting.py`](../platform_server/community_dictionary/porting.py), [`platform_server/community_dictionary/port_categories.py`](../platform_server/community_dictionary/port_categories.py), [`platform_server/community_dictionary/tests/test_port_guidance.py`](../platform_server/community_dictionary/tests/test_port_guidance.py)

### OBS-0100

Manny reports successful AWS installation of related-version guidance and the expected converted French content, but duplicate image-only cards and typically tens-of-seconds latency on simple navigation, especially the top level. This is mixed acceptance and material regression evidence. Main contains the deployed extension at dbeb917; no direct production inspection was performed.

- **Observed:** 2026-10-12
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/guidance-repair-2026-10-12.md`](../experiments/community_dictionary/guidance-repair-2026-10-12.md)

### OBS-0101

A local 150-sentence Swedish/French fixture reproduces about 6,370 home-route queries without bulk guidance reads, reduced to 53 by request-local bulk loading and memoization. Fresh requests re-read state and action checks remain fresh; 50 ready previews require 20 queries. A lineage fixture reproduces redundant image cards when copies share ancestors; presentation now follows copy provenance while distinguishing AI-style references and preserving independent contributions. The 613-test full suite passed in 150.333 seconds; after the style/capture guard, 72 relevant tests passed in 21.795 seconds. Chromium phone/laptop viewports pass. No schema/static changes, provider calls or production operation. Actual AWS latency and duplicate-row acceptance remain pending.

- **Observed:** 2026-10-12
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/guidance-repair-2026-10-12.md`](../experiments/community_dictionary/guidance-repair-2026-10-12.md), [`docs/howto/community-guidance-repair.md`](../howto/community-guidance-repair.md), [`docs/howto/community-guidance-repair-install.md`](../howto/community-guidance-repair-install.md), [`platform_server/community_dictionary/workflow_data.py`](../platform_server/community_dictionary/workflow_data.py), [`platform_server/community_dictionary/lexicon.py`](../platform_server/community_dictionary/lexicon.py), [`platform_server/community_dictionary/tests/test_guidance_scaling.py`](../platform_server/community_dictionary/tests/test_guidance_scaling.py)

### OBS-0102

Manny reports both guidance regressions fixed after AWS installation. He separately reports unexpectedly large reserved-credit messages and asks for investigation; no exact amount, job state or ledger output is supplied.

- **Observed:** 2026-10-12
- **Confidence:** high
- **Evidence:** [`docs/howto/community-credit-audit.md`](../howto/community-credit-audit.md)

### OBS-0103

Inspection confirms misleading pre-approval and post-settlement reservation labels. Vocabulary allowances reserve twelve possible words per sentence with guidance and two maximum-duration clips each; a 150-sentence no-context example at configured US$2/US$10 token prices estimates US$9.915 but allows US$130.350. Vocabulary review can retain the allowance. The patch corrects labels and adds a read-only per-account job/ledger reconciliation command. All 82 focused tests, system checks and migration-drift checks pass; no production balance or reservation policy was changed.

- **Observed:** 2026-10-12
- **Confidence:** high
- **Evidence:** [`docs/howto/community-credit-audit.md`](../howto/community-credit-audit.md), [`platform_server/community_dictionary/management/commands/community_credit_audit.py`](../platform_server/community_dictionary/management/commands/community_credit_audit.py), [`platform_server/community_dictionary/tests/test_credit_audit.py`](../platform_server/community_dictionary/tests/test_credit_audit.py)

### OBS-0104

Manny reports 150-sentence AWS vocabulary estimates near US$9.9 with a roughly US$130 refundable allowance, awkward Italian audio recovery, one French sentence in an Italian port, and complete Japanese vocabulary rejection. He explicitly requests the combined repair patch. These are operator reports, not a model-quality benchmark.

- **Observed:** 2026-10-12
- **Confidence:** high
- **Evidence:** [`docs/howto/community-port-reliability.md`](../howto/community-port-reliability.md), [`experiments/community_dictionary/port-reliability-2026-10-12.md`](../experiments/community_dictionary/port-reliability-2026-10-12.md)

### OBS-0105

Local code reproduction identifies alphabetic word boundaries as the cause of Japanese/Han span rejection. The repair adds script-aware exact spans, an independent target-language check with flagged review, audio-only recovery from saved current text, smaller fresh allowances, signed additional approvals and once-only per-item refunds. Migration 0023 is additive; existing approved jobs are unchanged. A mocked-provider Linux/SQLite suite passes 634 tests. Actual Japanese quality, provider check reliability, AWS concurrency and new financial-policy acceptance remain unverified.

- **Observed:** 2026-10-12
- **Confidence:** high
- **Evidence:** [`docs/howto/community-port-reliability.md`](../howto/community-port-reliability.md), [`docs/howto/community-port-reliability-install.md`](../howto/community-port-reliability-install.md), [`experiments/community_dictionary/port-reliability-2026-10-12.md`](../experiments/community_dictionary/port-reliability-2026-10-12.md), [`platform_server/community_dictionary/tests/test_port_reliability.py`](../platform_server/community_dictionary/tests/test_port_reliability.py)

### OBS-0106

Manny reports the repaired local queue passed 20/20 production probes with peak two active task bodies and no task connections left open, followed by successful AWS installation and 150-entry Swedish-to-Japanese conversion. He reports six public language versions and explicitly enables Japanese browsing. This supersedes the earlier pending deployment/Japanese outcome; linguistic accuracy, production cost reconciliation and a broad device matrix are not established by that report.

- **Observed:** 2026-10-12
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/automatic-processing-2026-10-12.md`](../experiments/community_dictionary/automatic-processing-2026-10-12.md), [`docs/howto/community-port-reliability-install.md`](../howto/community-port-reliability-install.md)

### OBS-0107

At Manny’s request, the prepared automatic option publishes sentences, derives shared vocabulary from final wording and generates missing audio after one combined estimate/approval. It reuses bounded jobs, preserves human edits/withdrawal, labels automatic publication, supports partial-result recovery and caps the stage-two reservation by the approved pot. The 654-test Linux/SQLite suite and final 20-test focused rerun pass with mocked providers. No schema or environment changes; no live deployment, paid call, human acceptance or independent reviewer trial for this increment.

- **Observed:** 2026-10-12
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/automatic-processing-2026-10-12.md`](../experiments/community_dictionary/automatic-processing-2026-10-12.md), [`docs/howto/community-automatic-processing.md`](../howto/community-automatic-processing.md), [`platform_server/community_dictionary/automatic.py`](../platform_server/community_dictionary/automatic.py), [`platform_server/community_dictionary/tests/test_automatic.py`](../platform_server/community_dictionary/tests/test_automatic.py)

### OBS-0108

Manny reports that everything is working and installed on AWS after the automatic-workflow increment. He now requests the initial paper, an AI/human two-author LaTeX draft acknowledging Cathy, Sophie and Branislav, emphasising iterative redesign over roughly two and a half weeks and inviting wider participation before an empirical follow-up. No detailed new automatic-job accounting or linguistic-quality measurement accompanies the acceptance report.

- **Observed:** 2026-10-13
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/automatic-processing-2026-10-12.md`](../experiments/community_dictionary/automatic-processing-2026-10-12.md), [`docs/publications/community_dictionaries_first_report/README.md`](../publications/community_dictionaries_first_report/README.md)

### OBS-0109

A first four-page, approximately 1,600-word public report is prepared and visually checked after pdfLaTeX compilation. Two anonymous public-site screenshots show a Swedish sentence and its shared word page; six language versions were visible in the directory. The draft describes functioning manual/AI workflows, free practice using existing media, community authority, supervised AI development, proposed bounded trial credit, research consent and appropriate participant credit. It makes no numerical accuracy, learning-gain, model-comparison or autonomous-maintenance claim. It is unapproved and unsubmitted.

- **Observed:** 2026-10-13
- **Confidence:** high
- **Evidence:** [`docs/publications/community_dictionaries_first_report/README.md`](../publications/community_dictionaries_first_report/README.md), [`docs/publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex`](../publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex)

### OBS-0110

Manny considers draft 1 close to posting and requests clearer platform ancestry, contributor attribution, the ChatGPT-5/Codex to Astra development experiment, sub-hour patch experience, AiraXiv rationale and French figures. Draft 2 implements these requests and remains four pages after compilation and visual inspection. The development-speed statement is explicitly a participant observation, not a controlled model comparison; no external posting occurred.

- **Observed:** 2026-10-13
- **Confidence:** high
- **Evidence:** [`docs/publications/community_dictionaries_first_report/README.md`](../publications/community_dictionaries_first_report/README.md), [`docs/publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex`](../publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex)

### OBS-0111

Manny requests five refinements to the introductory report and permits expansion to five pages. Draft 3 implements the conversion history, multimodal translation/TTS explanation, attributed fauteuil/armchair ambiguity, sequence-of-papers plan, indirect community reference and Finley acknowledgement. It compiles without warnings; all five pages are visually checked. No application content, external publication or research enrolment was changed.

- **Observed:** 2026-10-13
- **Confidence:** high
- **Evidence:** [`docs/publications/community_dictionaries_first_report/README.md`](../publications/community_dictionaries_first_report/README.md), [`docs/publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex`](../publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex)

### OBS-0112

Manny requests six editorial refinements and confirms pilot funds for up to ten groups. Draft 4 implements them, retaining five pages and providing full references. Given his description of an armless padded office chair, the AI recommends chaise de bureau / office chair, while documenting both the dictionary definition of fauteuil with arms and broader commercial usage. The PDF compiles without warnings and all pages are visually checked. Public dictionary contents and the application are unchanged. No paper submission or credit issuance occurred.

- **Observed:** 2026-10-13
- **Confidence:** high
- **Evidence:** [`docs/publications/community_dictionaries_first_report/README.md`](../publications/community_dictionaries_first_report/README.md), [`docs/publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex`](../publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex)

### OBS-0113

Manny judges the report nearly ready and supplies five editorial changes, including a rough US$15–20 cost per trial dictionary of about 150 images and 250–400 words and an informal over-95% correctness impression from non-exhaustive browsing. Draft 5 attributes those figures to Rayner, preserves the distinction from systematic evaluation, highlights easy withdrawal/restoration while retaining confirmation, identifies Chua’s relationship, and relocates the publication plan. Five PDF pages compile without warnings and are visually checked. No new financial audit, accuracy study, app change or publication occurred.

- **Observed:** 2026-10-13
- **Confidence:** high
- **Evidence:** [`docs/publications/community_dictionaries_first_report/README.md`](../publications/community_dictionaries_first_report/README.md), [`docs/publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex`](../publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex)

### OBS-0114

Manny proposes an invitation-first abstract distinguishing AI implementation, human strategy and initial content; narrows the screenshot description; and makes further pilot credit conditional on inspection of initial dictionaries. He asks whether these changes suffice for AiraXiv posting. The clean five-page submission candidate implements them and removes discussion-draft labels. It compiles without warnings and all pages are visually checked. AiraXiv public pages confirm an AI-generated track and Application category; the detailed form requires sign-in. No upload, submission, credit allocation or application change occurred.

- **Observed:** 2026-10-13
- **Confidence:** high
- **Evidence:** [`docs/publications/community_dictionaries_first_report/README.md`](../publications/community_dictionaries_first_report/README.md), [`docs/publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex`](../publications/community_dictionaries_first_report/latex/community_dictionaries_first_report.tex)

### OBS-0115

Manny supplies the AiraXiv and ResearchGate publication URLs and reports posting a Goodreads review inviting experimentation, especially by language teachers. These are human-reported publication/outreach outcomes; direct retrieval of the publication pages was unavailable. The prepared patch replaces the About publication placeholder with both links, records publication in documentation and preserves the two minimally differing LaTeX versions. Django check and all 28 discovery/profile tests pass locally. The agent did not post externally or modify dictionary content. No independent empirical results have yet been reported.

- **Observed:** 2026-10-14
- **Confidence:** high
- **Evidence:** [`docs/publications/community_dictionaries_first_report/README.md`](../publications/community_dictionaries_first_report/README.md), [`docs/howto/community-publications-install.md`](../howto/community-publications-install.md), [`platform_server/community_dictionary/templates/community_dictionary/about.html`](../platform_server/community_dictionary/templates/community_dictionary/about.html), [`platform_server/community_dictionary/tests/test_discovery_profiles.py`](../platform_server/community_dictionary/tests/test_discovery_profiles.py)

### OBS-0116

Manny reports installing the publication/About material. A read-only browser check of the deployed About page without login confirmed the paper title/authors, AiraXiv and ResearchGate links, related Vibe Research link and public contributor listing. No deployment was performed by the agent.

- **Observed:** 2026-10-14
- **Confidence:** high
- **Evidence:** [`platform_server/community_dictionary/templates/community_dictionary/about.html`](../platform_server/community_dictionary/templates/community_dictionary/about.html), [`docs/publications/community_dictionaries_first_report/README.md`](../publications/community_dictionaries_first_report/README.md), [`experiments/community_dictionary/evaluation-2026-10-14.md`](../experiments/community_dictionary/evaluation-2026-10-14.md)

### OBS-0117

Manny requests and authorises first evaluation infrastructure after discussion of task-specific self-reported competence, independent human ratings and later AI comparisons. The prepared implementation adds versioned owner-created random/all samples, resumable ratings on seven dimensions, missing/abstention handling, live source withdrawal checks, optional signed-in visitor evaluation, owner-only closed-set results/CSV and ordinal agreement. Django check/migration-drift check passed; the full 685-test regression suite passed and all 34 evaluation tests passed after three additional edge checks. No real evaluator judgements, paid AI requests, production deployment or physical-phone acceptance occurred.

- **Observed:** 2026-10-14
- **Confidence:** high
- **Evidence:** [`platform_server/community_dictionary/evaluation.py`](../platform_server/community_dictionary/evaluation.py), [`platform_server/community_dictionary/evaluation_views.py`](../platform_server/community_dictionary/evaluation_views.py), [`platform_server/community_dictionary/tests/test_evaluation.py`](../platform_server/community_dictionary/tests/test_evaluation.py), [`docs/howto/community-evaluation.md`](../howto/community-evaluation.md), [`docs/howto/community-evaluation-install.md`](../howto/community-evaluation-install.md), [`experiments/community_dictionary/evaluation-2026-10-14.md`](../experiments/community_dictionary/evaluation-2026-10-14.md)

### OBS-0118

Manny reports a successful two-entry laptop evaluation apart from question-context placement and an incomplete competence summary. Inspection confirmed omitted commenting-language listening. The follow-up puts relevant material directly above each question and displays both skills with full labels for both languages, including the saved session profile. All 37 evaluation tests pass. The follow-up is not yet accepted or deployed; independent ratings and physical-phone evidence remain pending.

- **Observed:** 2026-10-14
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/evaluation-2026-10-14.md`](../experiments/community_dictionary/evaluation-2026-10-14.md), [`platform_server/community_dictionary/evaluation_views.py`](../platform_server/community_dictionary/evaluation_views.py), [`platform_server/community_dictionary/tests/test_evaluation.py`](../platform_server/community_dictionary/tests/test_evaluation.py), [`docs/howto/community-evaluation-display-fix.md`](../howto/community-evaluation-display-fix.md)

### OBS-0119

Manny reports AWS deployment and a 30-entry Swedish pilot; the supplied CSV independently confirms 318 judgements from one human, 30/150 randomly sampled pages, and 84 word-translation/audio units. Image, sentence-language and sentence-translation ratings are all acceptable; sentence audio and vocabulary are 29/30, word translations 82/84 and word audio 76/84 acceptable. Manny describes mostly tone errors, one consonant error and missing vocabulary. These are initial developer-led ratings, not independent multi-rater evidence. The requested readable-content export uses saved snapshots and existing access checks; 39 focused tests pass. French evaluation and the prediction of better isolated-word TTS in other languages are still prospective.

- **Observed:** 2026-10-14
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/evaluation-swedish-pilot-2026-10-14.md`](../experiments/community_dictionary/evaluation-swedish-pilot-2026-10-14.md), [`platform_server/community_dictionary/evaluation_views.py`](../platform_server/community_dictionary/evaluation_views.py), [`platform_server/community_dictionary/tests/test_evaluation.py`](../platform_server/community_dictionary/tests/test_evaluation.py), [`docs/howto/community-evaluation-export-fix.md`](../howto/community-evaluation-export-fix.md)

### OBS-0120

Manny approves trying MWE carrier regeneration and proposes word-audio-only Swedish/French dictionary evaluations. The supplied standalone manifest/ratings report 36/40 acceptable, four minor, no major or boundary failures, across 53 requests; all successes occurred by attempt three. The optional app pilot retains human and old recordings, requires cost approval, reuses bounded jobs/settlement, and adds exact-word follow-up snapshots/CSV audio IDs. The existing app suite plus initial new tests passes 643 tests. Further focused HTTP, withdrawal and evaluation checks are recorded in the pilot documentation. No paid call, deployment or live integrated acceptance is claimed.

- **Observed:** 2026-10-18
- **Confidence:** high
- **Evidence:** [`docs/howto/community-mwe-audio.md`](../howto/community-mwe-audio.md), [`experiments/community_dictionary/mwe-audio-pilot-2026-10-18.md`](../experiments/community_dictionary/mwe-audio-pilot-2026-10-18.md), [`platform_server/community_dictionary/tests/test_mwe_audio.py`](../platform_server/community_dictionary/tests/test_mwe_audio.py), [`platform_server/community_dictionary/mwe_audio.py`](../platform_server/community_dictionary/mwe_audio.py)

### OBS-0121

Manny supplied paired AWS exports covering all 58 eligible French and eight Swedish word pages. French acceptable/minor/major changed from 21/26/11 to 54/4/0; 33 improved and none regressed. One French recording is unchanged (entry 2042/audio 7062); 54/57 replacements are acceptable. Swedish changed from 1/7/0 to 5/3/0; all eight recordings changed, four ratings improved, none regressed. These are one involved evaluator’s unblinded sequential ratings with no concurrent regeneration control. The results support continued reversible MWE experiments, not proven single-word or language-general improvement.

- **Observed:** 2026-10-18
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/mwe-audio-languages-2026-10-18.md`](../experiments/community_dictionary/mwe-audio-languages-2026-10-18.md), [`experiments/community_dictionary/mwe-audio-paired-2026-10-18/french.csv`](../experiments/community_dictionary/mwe-audio-paired-2026-10-18/french.csv), [`experiments/community_dictionary/mwe-audio-paired-2026-10-18/swedish.csv`](../experiments/community_dictionary/mwe-audio-paired-2026-10-18/swedish.csv), [`experiments/community_dictionary/mwe-audio-paired-2026-10-18/provenance.json`](../experiments/community_dictionary/mwe-audio-paired-2026-10-18/provenance.json)

### OBS-0122

Manny authorizes a German/Italian/Icelandic/Japanese carrier extension. The prepared code uses native-language carriers, unchanged extraction and five-attempt ceilings, automatic spaced-expression selection for the European languages, and no-default explicit Japanese word selection. A free quote can create an exact-entry word-audio baseline before approval. Human audio, existing replacements, prior files, credit approval and source withdrawal remain protected. No new migration/dependency is required; live new-language quality is not yet established.

- **Observed:** 2026-10-18
- **Confidence:** high
- **Evidence:** [`platform_server/community_dictionary/carrier.py`](../platform_server/community_dictionary/carrier.py), [`platform_server/community_dictionary/mwe_audio.py`](../platform_server/community_dictionary/mwe_audio.py), [`platform_server/community_dictionary/tests/test_mwe_audio.py`](../platform_server/community_dictionary/tests/test_mwe_audio.py), [`docs/howto/community-mwe-audio.md`](../howto/community-mwe-audio.md)

### OBS-0123

Manny requests resumption of English/French localisation after a previous unavailable execution environment, and states that no earlier implementation changes were made. The current environment runs the app tests. The prepared first cut adds an app-scoped English/Français selector with a persistent browser cookie, matching-explanation learning-language defaults and remembered explicit choices, preserving existing dictionary lists and content/permission boundaries. The unchanged base passed 653 tests; the combined 668-test suite, including 15 new localisation regressions, passes after correcting language-name filter and evaluation count integration issues. A focused 98-test rerun and clean-base patch application with its 15 localisation tests also pass. All 94 templates compile, JavaScript syntax and translation formats validate, and no migration changes are detected. Browser layout interaction could not be verified because Chromium was unavailable and its download failed. Main navigation, browsing and supported learning/contribution/evaluation flows have French catalog coverage, while some advanced AI/porting, group-management and private-content pages remain English. No installation, live French-user acceptance or content-language conversion is claimed.

- **Observed:** 2026-10-19
- **Confidence:** high
- **Evidence:** [`platform_server/community_dictionary/localisation.py`](../platform_server/community_dictionary/localisation.py), [`platform_server/community_dictionary/middleware.py`](../platform_server/community_dictionary/middleware.py), [`platform_server/community_dictionary/tests/test_localisation.py`](../platform_server/community_dictionary/tests/test_localisation.py), [`platform_server/community_dictionary/locale/fr/LC_MESSAGES/django.po`](../platform_server/community_dictionary/locale/fr/LC_MESSAGES/django.po), [`platform_server/community_dictionary/templates/community_dictionary/learning_languages.html`](../platform_server/community_dictionary/templates/community_dictionary/learning_languages.html), [`docs/howto/community-localisation-install.md`](../howto/community-localisation-install.md)

### OBS-0124

Manny reports laptop testing of the initial localisation patch, with almost everything already displaying correctly in French, and supplies screenshots of remaining English in the next-step card, Needs attention and People/partnerships. The incremental follow-up translates those templates, dynamic workflow labels/counts/buttons, roles/statuses, cost/approval details, language-check responses, participation controls and known language display headings. All 680 application tests pass, including 12 new rendered-page/workflow regressions. English next-step HTML is unchanged across 144 render combinations. No dictionary content, paid processing, authorization or schema change is made. The new screenshot fixes still await Manny's continued browser review; this does not establish AWS or phone acceptance.

- **Observed:** 2026-10-19
- **Confidence:** high
- **Evidence:** [`docs/howto/community-localisation-screenshots-install.md`](../howto/community-localisation-screenshots-install.md), [`platform_server/community_dictionary/tests/test_localisation_followup.py`](../platform_server/community_dictionary/tests/test_localisation_followup.py), [`platform_server/community_dictionary/templates/community_dictionary/next_step.html`](../platform_server/community_dictionary/templates/community_dictionary/next_step.html), [`platform_server/community_dictionary/templates/community_dictionary/attention.html`](../platform_server/community_dictionary/templates/community_dictionary/attention.html), [`platform_server/community_dictionary/templates/community_dictionary/people.html`](../platform_server/community_dictionary/templates/community_dictionary/people.html), [`platform_server/community_dictionary/workflow.py`](../platform_server/community_dictionary/workflow.py)

### OBS-0125

Manny reports that the earlier screenshot fixes all appear to work well on the laptop, supplies the remaining Link more words screenshot and says fixing it would leave him ready for AWS installation. He also plans to create an English/French version of the existing French/English Finley dictionary and requests a colloquial French title. The new incremental patch localises picture-word linking controls, their relevant validation/confirmation messages and the displayed language in synthetic-voice provenance. Stored words, language metadata, audio and link permissions remain unchanged. The prior combined suite passed 680 tests; final verification is 680 application tests pass, along with 68 existing focused tests and English/French link/unlink and provenance render checks. No new persistent tests are added for the small label change; existing tests and a temporary rendered-page smoke check provide verification. This is positive laptop acceptance of the preceding follow-up, not evidence of AWS installation, phone acceptance or completed English/French content conversion.

- **Observed:** 2026-10-19
- **Confidence:** high
- **Evidence:** [`platform_server/community_dictionary/templates/community_dictionary/picture_word_editor.html`](../platform_server/community_dictionary/templates/community_dictionary/picture_word_editor.html), [`platform_server/community_dictionary/templates/community_dictionary/entry_pronunciation.html`](../platform_server/community_dictionary/templates/community_dictionary/entry_pronunciation.html), [`platform_server/community_dictionary/templates/community_dictionary/entry_versions.html`](../platform_server/community_dictionary/templates/community_dictionary/entry_versions.html), [`platform_server/community_dictionary/lexicon_views.py`](../platform_server/community_dictionary/lexicon_views.py), [`platform_server/community_dictionary/tests/test_localisation_followup.py`](../platform_server/community_dictionary/tests/test_localisation_followup.py), [`docs/howto/community-localisation-link-words-install.md`](../howto/community-localisation-link-words-install.md)

### OBS-0126

Manny reports that the final localisation changes worked as expected and that the English/French version “L'anglais de Finley” is installed on AWS. This supplies the previously missing deployment and content-version evidence. On reviewing English word audio he finds recurring prosody issues with multi-word expressions and requests the carrier/extraction approach if it is not yet enabled. Repository inspection confirms English was excluded from the optional carrier language set. The prepared extension adds English spaced-expression selection with the native carrier “We begin. X. We are finished.”, the same approximately 600 ms pauses, extraction recipe/version and bounded attempts, and English MWE evaluation filtering with French interface coverage. Ordinary TTS and single-word defaults remain unchanged; existing human/earlier audio, approval, budget and withdrawal protections remain in place. Final verification is 685 passing Community Dictionaries tests, including 31 carrier/batch tests and five new English regressions; French/English estimate and evaluation page smoke checks, unchanged existing-language prompts, system checks and migration consistency checks also pass. No paid English generation or measured listening improvement is claimed; the new extension has not been deployed in this session.

- **Observed:** 2026-10-19
- **Confidence:** high
- **Evidence:** [`platform_server/community_dictionary/carrier.py`](../platform_server/community_dictionary/carrier.py), [`platform_server/community_dictionary/mwe_audio.py`](../platform_server/community_dictionary/mwe_audio.py), [`platform_server/community_dictionary/evaluation.py`](../platform_server/community_dictionary/evaluation.py), [`platform_server/community_dictionary/tests/test_mwe_audio.py`](../platform_server/community_dictionary/tests/test_mwe_audio.py), [`docs/howto/community-english-mwe-audio-install.md`](../howto/community-english-mwe-audio-install.md)

### OBS-0127

Manny reports that the English carrier increment worked fine. He then reports a laptop/mobile rendering discrepancy for an English/French dictionary entry, later observes normal rendering in Chrome, and confirms Cathy sees the sample page normally in Firefox too. He suspects access through AdBlock caused the earlier appearance, but the cause is not isolated. A read-only anonymous desktop browser inspection by the agent also shows the public page heading “Several deer are lying under a tree.” in “L'anglais avec Finley”. These observations support sample-page rendering in two mainstream mobile browser configurations and public desktop access; they do not establish all mobile workflows, Safari compatibility, independent learner acceptance or measured English prosody improvement.

- **Observed:** 2026-10-19
- **Confidence:** high
- **Evidence:** [`docs/howto/community-image-ladder-install.md`](../howto/community-image-ladder-install.md), [`docs/howto/community-english-mwe-audio-install.md`](../howto/community-english-mwe-audio-install.md)

### OBS-0128

Manny prefers to focus next on tidying messy or unintuitive workflows, then organise a proper evaluation with inter-rater figures; English/French should help recruitment. A Zoom to discuss this is tentatively scheduled for Monday 26 October. Once that is settled, he proposes finding a school or adult language class to build a first communal dictionary and is considering visiting his local Alliance Française “next Wednesday”. This is exploratory planning, with the visit date left as stated, no appointment or outreach completed by the agent, no recruited class and no settled evaluation protocol. No new external commitment or human-owned intention is inferred.

- **Observed:** 2026-10-19
- **Confidence:** high
- **Evidence:** [`docs/howto/community-image-ladder-install.md`](../howto/community-image-ladder-install.md)

### OBS-0129

Cathy suggests a ladder under People showing images contributed by each person to encourage friendly competition. Manny excludes hidden dictionaries and authorises a first version for her review after agreeing to count accepted human uploads, credit the original contributor once through reuse or language versions and exclude AI images. The prepared implementation calculates this from existing accepted image provenance across active, non-hidden, non-personal dictionaries the viewer can access through existing membership; it does not disclose other dictionary membership or count AI-generated images. Credit uses the root image’s recorded custodian, falling back to its author, so delegated uploads retain their recorded ownership. Separate uploads of the same pixels are not automatically identified as reuse; explicit shared-copy/port ancestry supplies the deduplication evidence. Existing user identities are used. The 701-test Community Dictionaries suite passes, including 16 new ladder regressions. All 95 templates compile; French catalog, system, migration and installation-shell checks pass. Existing French translations are preserved. Local browser preview connectivity was unavailable, so actual new phone presentation remains for Cathy to assess. This preparation changes no schema, sends no paid requests, mutates no existing content and performs no external deployment. Cathy’s acceptance and any effect on participation remain untested.

- **Observed:** 2026-10-19
- **Confidence:** high
- **Evidence:** [`docs/howto/community-image-ladder-install.md`](../howto/community-image-ladder-install.md), [`platform_server/community_dictionary/contribution_ladder.py`](../platform_server/community_dictionary/contribution_ladder.py), [`platform_server/community_dictionary/tests/test_contribution_ladder.py`](../platform_server/community_dictionary/tests/test_contribution_ladder.py)

### OBS-0130

Manny says the preceding image-contribution ladder worked fine, then requests Slovak as another interface language because Ivana is interested in experimenting. He reports already creating a Slovak/English dictionary by converting from French/English and would also like an English/Slovak dictionary. This is acceptance of the preceding increment and reported availability of one content direction; he does not specify a new AWS deployment, supply a separate Cathy verdict, report Ivana’s use, or establish an English/Slovak version. No new browser, inter-rater, classroom or quantitative English-audio result is supplied.

- **Observed:** 2026-10-21
- **Confidence:** high
- **Evidence:** [`docs/howto/community-slovak-localisation-install.md`](../howto/community-slovak-localisation-install.md), [`docs/howto/community-image-ladder-install.md`](../howto/community-image-ladder-install.md)

### OBS-0131

The prepared Slovak extension adds Slovenčina to the shared interface-language configuration, Slovak server/JavaScript catalogs with the existing French translation surface, persistent browser preference, recognised Slovak language names and matching-explanation recommendations. The small English/French-specific default assumptions are generalised so Slovak mode prefers available English-learning dictionaries with Slovak explanations and new dictionary forms use the canonical Slovak explanation-language name. Existing explicit learning choices, dictionary selection, content and permission boundaries remain intact. Installation instructions describe creating English/Slovak through the existing owner-approved language conversion flow; the assistant does not make paid conversion calls or create production content. All 713 Community Dictionaries tests pass, including 12 new Slovak regressions and the 15 existing localisation tests. All 95 templates compile. Catalog format/source-key/placeholder audits, four Slovak plural branches, twelve member/visitor route smoke checks plus JavaScript, and two mocked-provider conversion checks pass; all existing French translations are preserved. No new migration, provider configuration or Slovak MWE carrier is part of this interface increment. Native Slovak quality and human acceptance of the new locale remain unverified.

- **Observed:** 2026-10-21
- **Confidence:** high
- **Evidence:** [`docs/howto/community-slovak-localisation-install.md`](../howto/community-slovak-localisation-install.md), [`platform_server/community_dictionary/localisation.py`](../platform_server/community_dictionary/localisation.py), [`platform_server/community_dictionary/tests/test_slovak_localisation.py`](../platform_server/community_dictionary/tests/test_slovak_localisation.py), [`platform_server/community_dictionary/locale/sk/LC_MESSAGES/django.po`](../platform_server/community_dictionary/locale/sk/LC_MESSAGES/django.po), [`platform_server/community_dictionary/locale/sk/LC_MESSAGES/djangojs.po`](../platform_server/community_dictionary/locale/sk/LC_MESSAGES/djangojs.po)

### OBS-0132

Manny proposes staged deployment automation: initially automated laptop installation/restart with his functional acceptance before AWS, then AI laptop checks, then AWS staging. In parallel he requests a draft on AI-led conceptual collaboration with project members. He now explicitly requests the initial functionality patch and first working document. This authorises preparation, not provision of credentials, live production rollout or messages to collaborators.

- **Observed:** 2026-10-21
- **Confidence:** high
- **Evidence:** [`docs/roadmap/community-dictionary-ai-led-collaboration.md`](../roadmap/community-dictionary-ai-led-collaboration.md), [`docs/howto/community-deployment-stage-a.md`](../howto/community-deployment-stage-a.md)

### OBS-0133

Prepared a stdlib code/static-only deployment controller, separate private GitHub control workflow templates, fixed AWS SSM document/role examples, opt-in activity leases for requests/local tasks/assistant worker, frozen release readiness and preceding-code recovery. The controller refuses schema/dependency/controller changes, dirty or unexpected checkouts and undrained work. 24 disposable Linux controller/protocol tests pass; the 758-test Django regression run passed and all 15 focused deployment tests pass after three additions. Native Windows CI is configured but has not run here. No host setup or deployment has been performed. A shareable working draft describes decision rights, consent, durable records, research measures and stages (1a)-(1c).

- **Observed:** 2026-10-21
- **Confidence:** high
- **Evidence:** [`ops/community_deploy/README.md`](../ops/community_deploy/README.md), [`docs/howto/community-deployment-stage-a.md`](../howto/community-deployment-stage-a.md), [`docs/roadmap/community-dictionary-ai-led-collaboration.md`](../roadmap/community-dictionary-ai-led-collaboration.md), [`experiments/community_dictionary/deployment-stage-a-2026-10-21.md`](../experiments/community_dictionary/deployment-stage-a-2026-10-21.md)

### OBS-0134

The Windows laptop and AWS supervised deployment path successfully reinstalled db1557c on both hosts. The assistant inspected successful GitHub logs and downloaded the AWS receipt: installed, expected/current application commits matching, 21 recorded checks passed, including service restart. Manny reports normal browsing. Earlier SendCommand attempts were rejected because the fixed SSM document was absent from the deployment region; creating it there resolved the problem. This establishes a same-version supervised rehearsal, not yet a changed release or AI functional acceptance.

- **Observed:** 2026-10-30
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/deployment-and-tools-2026-10-30.md`](../experiments/community_dictionary/deployment-and-tools-2026-10-30.md)

### OBS-0135

Manny proposes moving batch operations from Settings into a separate tab as the first visible deployment experiment. The prepared owner-only Tools tab groups missing sentences, language versions/vocabulary, expression audio and image-only copies. Configuration stays in Settings. Existing operations, cost approvals and URLs are preserved; French/Slovak labels and return links are supplied. The 85-test focused suite and full 728-test Community Dictionaries suite pass after restoring unchanged resources missing from the fresh local inspection checkout. Live acceptance of the new UI is pending.

- **Observed:** 2026-10-30
- **Confidence:** high
- **Evidence:** [`docs/howto/community-tools.md`](../howto/community-tools.md), [`platform_server/community_dictionary/templates/community_dictionary/tools.html`](../platform_server/community_dictionary/templates/community_dictionary/tools.html), [`platform_server/community_dictionary/tests/test_settings_and_pictures.py`](../platform_server/community_dictionary/tests/test_settings_and_pictures.py)

### OBS-0136

The Tools release 48ad6c3866ba7e633a3f91da3a44a85c1c3cc50f completed laptop run 41034724689 (17 controller steps) and AWS run 41035557064 (21 steps), with the AWS receipt referencing that laptop run and the same exact app commit. Manny accepted the laptop UI and then refreshed AWS and confirmed the new version. This completes one changed-release trial; the separate Windows controller CI checkout failure on an existing long archive path remains unresolved.

- **Observed:** 2026-10-30
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/writing-practice-2026-10-30.md`](../experiments/community_dictionary/writing-practice-2026-10-30.md), [`docs/howto/community-tools.md`](../howto/community-tools.md)

### OBS-0137

Manny requests a first personal writing-practice mode based on learner feedback. The implementation uses private PictureCapture attempts for saved images, short target-language drafts, explained corrections and approval before the existing enrichment/publishing/audio pipeline. Original writing and feedback are omitted from shared provenance; optional style is not applied; the approved sentence is checked for exact preservation. Personal preferences are session-scoped, drafts expire after 30 days, failed audio has a bounded explicit retry, and no migration/dependency/controller change is required. Automated validation uses mocked providers; live model quality, physical-phone usability and learner outcomes remain pending.

- **Observed:** 2026-10-30
- **Confidence:** high
- **Evidence:** [`docs/howto/community-writing-practice.md`](../howto/community-writing-practice.md), [`experiments/community_dictionary/writing-practice-2026-10-30.md`](../experiments/community_dictionary/writing-practice-2026-10-30.md), [`platform_server/community_dictionary/writing.py`](../platform_server/community_dictionary/writing.py), [`platform_server/community_dictionary/tests/test_writing.py`](../platform_server/community_dictionary/tests/test_writing.py)

### OBS-0138

Writing release 863e401 completed laptop workflow 41044395387 successfully. Manny reports one example working and wants further tests before inviting the learner. He proposes a separate beginner flow for Kate: picture, explanation-language description, approval, then automatic remaining processing. This is an initial functional observation, not independent learner acceptance or an AWS deployment report.

- **Observed:** 2026-10-30
- **Confidence:** high
- **Evidence:** [`experiments/community_dictionary/guided-pictures-2026-10-30.md`](../experiments/community_dictionary/guided-pictures-2026-10-30.md)

### OBS-0139

Manny approves guided pictures and four approachable language levels, explicitly retaining core subjects/actions even when learners need unfamiliar words. The implementation adds persistent per-member modes/standing permission, private saved attempts, a confirmation gate, automatic existing enrichment/audio, owner-controlled generation level and English/French/Slovak UI. The full 767-test suite and final 19 guided tests passed with mocked providers. Four schema-helper tests and a real disposable SQLite migration/backup passed. Two additive preference tables are isolated in schema commit 8ee6024719b73de9f702ce4dad2848ffee88a4a7; manual preparation precedes the feature-only release. No host migration, paid provider call or physical-phone test has occurred in this session.

- **Observed:** 2026-10-30
- **Confidence:** high
- **Evidence:** [`docs/howto/community-guided-pictures.md`](../howto/community-guided-pictures.md), [`docs/howto/community-learning-deployment.md`](../howto/community-learning-deployment.md), [`experiments/community_dictionary/guided-pictures-2026-10-30.md`](../experiments/community_dictionary/guided-pictures-2026-10-30.md), [`platform_server/community_dictionary/tests/test_guided.py`](../platform_server/community_dictionary/tests/test_guided.py), [`ops/community_deploy/tests/test_learning_schema.py`](../ops/community_deploy/tests/test_learning_schema.py)

## Project-valence assessments

### ASM-0001

Historical assessment from 14 August, not revalidated in this scoped review: Platform maturity is easier to assess after registry triage: useful quality infrastructure exists, but poor segmentation phase 1 behavior and missing systematic UI-regression coverage remain material, tractable weaknesses.

- **Goals:** `GOAL-1`, `GOAL-5`
- **Grounding observations:** `OBS-0001`, `OBS-0002`
- **Urgency / risk / progress:** not_reassessed_since_2026-08-14 / medium / working_foundation_with_specific_gaps
- **Confidence:** high

### ASM-0002

Historical assessment from 14 August, not revalidated in this scoped review: Picture-dictionary risk has fallen further: the remaining need is short-horizon verification rather than broad implementation, so successful checks should lead to closure before community use.

- **Goals:** `GOAL-1`, `GOAL-5`
- **Grounding observations:** `OBS-0003`
- **Urgency / risk / progress:** not_reassessed_since_2026-08-14 / low / apparently_complete_pending_verification
- **Confidence:** high

### ASM-0003

Historical assessment from 14 August, not revalidated in this scoped review: Useful autonomy now includes an operational, auditable collaborator channel whose first natural laptop query produced a plausible evidence-grounded answer; per-user access can be administered safely while canonical mutation remains outside the web interaction.

- **Goals:** `GOAL-2`, `GOAL-3`
- **Grounding observations:** `OBS-0004`, `OBS-0005`, `OBS-0015`, `OBS-0016`, `OBS-0017`
- **Urgency / risk / progress:** not_reassessed_since_2026-08-14 / medium / laptop_trial_successful_server_collaborator_trial_pending
- **Confidence:** high

### ASM-0004

Historical assessment from 14 August, not revalidated in this scoped review: EuroCALL process risk remains acute, but the Voice Mode report is now human-reviewed and has a stronger, appropriately conditional economic conclusion; source verification, rather than substantive drafting, is the main release blocker.

- **Goals:** `GOAL-3`, `GOAL-5`
- **Grounding observations:** `OBS-0007`, `OBS-0010`, `OBS-0011`, `OBS-0012`, `OBS-0018`, `OBS-0019`, `OBS-0020`, `OBS-0021`
- **Urgency / risk / progress:** not_reassessed_since_2026-08-14 / high / human_reviewed_voice_mode_report_pending_source_verification
- **Confidence:** high

### ASM-0005

Historical assessment from 14 August, not revalidated in this scoped review: Legacy preservation remains near-complete, high-value low-hanging work and should be finished immediately after the Sprint; the attempt also serves as a diagnostic for the uncertain performance issue.

- **Goals:** `GOAL-1`, `GOAL-4`
- **Grounding observations:** `OBS-0006`
- **Urgency / risk / progress:** not_reassessed_since_2026-08-14 / medium / near_complete
- **Confidence:** high

### ASM-0006

Historical assessment from 14 August, not revalidated in this scoped review: The Indigenous-language delivery path is now more urgent than generic mobile work: recorded audio is substantial but important before 24 August, while judging autosave is easier and should be landed quickly if it does not displace the critical Sprint.

- **Goals:** `GOAL-1`, `GOAL-3`, `GOAL-5`
- **Grounding observations:** `OBS-0007`, `OBS-0008`
- **Urgency / risk / progress:** not_reassessed_since_2026-08-14 / high / time_bounded_work_not_started
- **Confidence:** high

### ASM-0007

Historical assessment from 14 August, not revalidated in this scoped review: Mobile access has a realistic mid-September research/user target rather than an impossible August target; scope uncertainty remains, but the ComputEL-10 connection raises its opportunity value.

- **Goals:** `GOAL-1`, `GOAL-3`, `GOAL-5`
- **Grounding observations:** `OBS-0011`
- **Urgency / risk / progress:** not_reassessed_since_2026-08-14 / medium / target_refined_scope_unknown
- **Confidence:** high

### ASM-0008

Historical assessment from 14 August, not revalidated in this scoped review: Learned prompts remain an unusually promising product/research opportunity, but venue authorship policy and the exact Francis Bond collaboration scope are immediate decision dependencies.

- **Goals:** `GOAL-1`, `GOAL-3`
- **Grounding observations:** `OBS-0010`
- **Urgency / risk / progress:** not_reassessed_since_2026-08-14 / medium / promising_pending_collaboration_discussion
- **Confidence:** high

### ASM-0009

Historical assessment from 14 August, not revalidated in this scoped review: The reviewed portfolio is now substantially more trustworthy and actionable: completed/stale items are removed, low-hanging work is visible, and no-path evaluator work is deprioritized. Capacity conflict remains acute through 24 August.

- **Goals:** `GOAL-1`, `GOAL-2`, `GOAL-3`, `GOAL-4`, `GOAL-5`
- **Grounding observations:** `OBS-0005`, `OBS-0008`, `OBS-0009`, `OBS-0014`
- **Urgency / risk / progress:** not_reassessed_since_2026-08-14 / medium / triaged_but_near_term_overloaded
- **Confidence:** high

### ASM-0010

Historical assessment from 14 August, not revalidated in this scoped review: Codex branch-update failures are a continuing operational risk to AI-assisted development. The restart/new-task workaround improves recovery but not predictability or root-cause confidence.

- **Goals:** `GOAL-1`, `GOAL-2`
- **Grounding observations:** `OBS-0013`
- **Urgency / risk / progress:** not_reassessed_since_2026-08-14 / medium / workaround_known_root_cause_unknown
- **Confidence:** high

### ASM-0011

Paired deployed French/Swedish results support the optional carrier batch as a useful practical MWE intervention, with substantial French improvement and partial Swedish improvement. These are one involved evaluator’s unblinded ratings and do not establish language-general improvement or single-word quality. Manny now reports the English carrier increment working, removing its earlier implementation-acceptance uncertainty; English-specific paired listening evidence is still needed before asserting prosody gains or changing defaults. German/Italian/Icelandic outcomes remain pending, and Japanese remains explicit and experimental. Preserve ordinary generation, old recordings and baseline evidence. The deployed English/French interface and content path is accepted by Manny. The sample public entry also renders normally in Chrome and Firefox on Cathy’s mobile, so the reported rendering concern is not currently a demonstrated mainstream-browser blocker. Safari, remaining phone workflows, interface coverage and independent learner outcomes remain open. The suspected AdBlock explanation should not be treated as a diagnosis. Manny’s new request makes a third interface locale a bounded, collaborator-driven extension of the accepted English/French framework. The reported Slovak/English content and Ivana’s interest create a concrete next trial, while English/Slovak content, native Slovak review and actual learner acceptance remain to be established. Keep shared interface configuration, stored content conversion and spoken-audio quality as separate claims.

- **Goals:** `GOAL-1`, `GOAL-2`, `GOAL-3`, `GOAL-5`
- **Grounding observations:** `OBS-0022`, `OBS-0023`, `OBS-0024`, `OBS-0025`, `OBS-0026`, `OBS-0027`, `OBS-0028`, `OBS-0029`, `OBS-0030`, `OBS-0031`, `OBS-0032`, `OBS-0033`, `OBS-0034`, `OBS-0035`, `OBS-0036`, `OBS-0037`, `OBS-0038`, `OBS-0039`, `OBS-0040`, `OBS-0041`, `OBS-0042`, `OBS-0043`, `OBS-0044`, `OBS-0045`, `OBS-0046`, `OBS-0047`, `OBS-0048`, `OBS-0049`, `OBS-0050`, `OBS-0051`, `OBS-0052`, `OBS-0053`, `OBS-0054`, `OBS-0055`, `OBS-0056`, `OBS-0057`, `OBS-0058`, `OBS-0059`, `OBS-0060`, `OBS-0061`, `OBS-0062`, `OBS-0063`, `OBS-0064`, `OBS-0065`, `OBS-0066`, `OBS-0067`, `OBS-0068`, `OBS-0069`, `OBS-0070`, `OBS-0071`, `OBS-0072`, `OBS-0073`, `OBS-0074`, `OBS-0075`, `OBS-0076`, `OBS-0077`, `OBS-0078`, `OBS-0079`, `OBS-0080`, `OBS-0081`, `OBS-0082`, `OBS-0083`, `OBS-0084`, `OBS-0085`, `OBS-0086`, `OBS-0087`, `OBS-0088`, `OBS-0089`, `OBS-0090`, `OBS-0091`, `OBS-0092`, `OBS-0093`, `OBS-0094`, `OBS-0095`, `OBS-0096`, `OBS-0097`, `OBS-0098`, `OBS-0099`, `OBS-0100`, `OBS-0101`, `OBS-0102`, `OBS-0103`, `OBS-0104`, `OBS-0105`, `OBS-0106`, `OBS-0107`, `OBS-0108`, `OBS-0109`, `OBS-0110`, `OBS-0111`, `OBS-0112`, `OBS-0113`, `OBS-0114`, `OBS-0115`, `OBS-0116`, `OBS-0117`, `OBS-0118`, `OBS-0119`, `OBS-0120`, `OBS-0121`, `OBS-0122`, `OBS-0123`, `OBS-0124`, `OBS-0125`, `OBS-0126`, `OBS-0127`, `OBS-0130`, `OBS-0131`
- **Urgency / risk / progress:** workflow_tidy_and_evaluation_preparation / medium / english_french_path_accepted_slovak_locale_prepared_native_review_and_quality_evidence_pending
- **Confidence:** medium

### ASM-0012

The accepted Tools deployment and positive writing laptop trial show useful progress toward reduced installation burden. Persistent learner settings now expose the deliberate limit of the code-only controller: the database must be prepared separately. A bounded, manually invoked helper creates only the reviewed new tables, backs up SQLite, and reuses maintenance/restart/recovery controls without broadening Actions or SSM authority. Successful local tests justify a supervised laptop preparation, not a claim of production migration reliability. Keep exact-release human acceptance before AWS and record the manual burden. Later functional autonomy, staging and governance remain open.

- **Goals:** `GOAL-1`, `GOAL-2`, `GOAL-3`, `GOAL-5`
- **Grounding observations:** `OBS-0031`, `OBS-0032`, `OBS-0033`, `OBS-0035`, `OBS-0036`, `OBS-0037`, `OBS-0066`, `OBS-0068`, `OBS-0069`, `OBS-0070`, `OBS-0072`, `OBS-0073`, `OBS-0075`, `OBS-0076`, `OBS-0077`, `OBS-0078`, `OBS-0079`, `OBS-0080`, `OBS-0081`, `OBS-0100`, `OBS-0101`, `OBS-0102`, `OBS-0103`, `OBS-0104`, `OBS-0105`, `OBS-0106`, `OBS-0107`, `OBS-0108`, `OBS-0109`, `OBS-0132`, `OBS-0133`, `OBS-0134`, `OBS-0135`, `OBS-0136`, `OBS-0137`, `OBS-0138`, `OBS-0139`
- **Urgency / risk / progress:** support_next_learner_driven_release / medium / writing_laptop_trial_positive_guided_release_and_schema_preparation_ready
- **Confidence:** high

### ASM-0013

Concrete learner needs now motivate complementary personal workflows: writing with explained correction, and guided pictures requiring only confirmation of meaning before enrichment. Four dictionary generation levels simplify phrasing while preserving important visible subjects/actions, consistent with Manny’s view that relevant new vocabulary is motivating. Writing has one positive laptop example; guided pictures remain a prepared experiment. Learner/phone trials should test clarity, overcorrection, object fidelity, level appropriateness and recovery. Keep existing contribution defaults until those trials support a broader change; implementation speed alone does not establish learning benefit.

- **Goals:** `GOAL-1`, `GOAL-3`, `GOAL-5`
- **Grounding observations:** `OBS-0127`, `OBS-0128`, `OBS-0129`, `OBS-0130`, `OBS-0131`, `OBS-0136`, `OBS-0137`, `OBS-0138`, `OBS-0139`
- **Urgency / risk / progress:** prepare_learner_trial / medium / two_personal_workflows_prepared_writing_initial_laptop_acceptance
- **Confidence:** medium

## Reported valence

None. This revision uses neutral factual and assessment language.

## Uncertainties and conflicts

- **UNC-0001:** Carried forward from August; present status unverified: EuroCALL acceptance, rejection, presentation, and travel consequences remain unresolved; the new report must remain clearly distinguished from the immutable Voice Mode submission and requires co-author review before ResearchGate posting.
  - **Assessments:** `ASM-0004`
- **UNC-0002:** Carried forward from August; present status unverified: ISSUE-0037 and ISSUE-0039 appear complete but should not be closed without focused pre-visit verification.
  - **Assessments:** `ASM-0002`
- **UNC-0003:** Carried forward from August; present status unverified: Completing legacy migration will determine whether ISSUE-0013 is obsolete or an active operational blocker.
  - **Assessments:** `ASM-0005`
- **UNC-0004:** Carried forward from August; present status unverified: Sprint work, recorded audio, autosave, picture-dictionary verification, and Francis contact all compete in the short period before 24 August.
  - **Assessments:** `ASM-0003`, `ASM-0006`, `ASM-0008`, `ASM-0009`
- **UNC-0005:** Carried forward from August; present status unverified: The exact ComputEL-10 deadline, paper scope, and which mobile/audio results must be ready for submission are not yet confirmed.
  - **Assessments:** `ASM-0004`, `ASM-0006`, `ASM-0007`
- **UNC-0006:** Carried forward from August; present status unverified: The Codex branch-update refusal remains intermittent and unexplained; the recovery procedure may not work in every recurrence.
  - **Assessments:** `ASM-0010`
- **UNC-0007:** Carried forward from August; present status unverified: The first laptop Project Manager query was plausible and timely, but the mode is not yet deployed or exercised by Sophie or another non-staff collaborator; classification accuracy and whether fresh-turn continuity is sufficient remain unmeasured.
  - **Assessments:** `ASM-0003`, `ASM-0006`
- **UNC-0008:** French and Swedish paired exports show practical gains, but are unblinded ratings by one involved evaluator without a concurrent direct-regeneration control. One French recording remained unchanged for an unknown reason; three changed Swedish expressions retain poor-prosody ratings. Manny reports the English carrier increment working, but supplies no quantitative English listening result. German/Italian/Icelandic/Japanese quality outcomes are also unmeasured. Japanese compounds must not automatically be classed as MWEs; the whitespace selector leaves European single-word compounds untreated. Quality claims and future defaults require language-specific evidence; the proposed formal evaluation also needs independent overlapping ratings and a settled rubric.
  - **Assessments:** `ASM-0011`
- **UNC-0009:** The feasibility and timetable for weekly/monthly intervention targets are unknown. There is no authorised persistent maintenance runner, staging/release/rollback workflow or tested operational recovery baseline yet. Infrastructure account ownership, budgets, fallback contacts and community authority must be assigned without transferring Manny’s technical burden invisibly to another person. Proposed stage targets require comparable workload and failure drills.
  - **Assessments:** `ASM-0012`
- **UNC-0010:** Manny reports the localisation follow-ups and English/French dictionary working on AWS, and the carrier increment working. The public sample page now appears normal in Chrome and Firefox on Cathy’s mobile; the suspected AdBlock cause of the earlier discrepancy remains unconfirmed. This is sample rendering evidence, not complete phone acceptance. Safari, recording/uploading and practice across phones, remaining interface coverage and independent francophone-learner acceptance remain unverified. Interface selection does not translate stored user text or dictionary content automatically. English carrier implementation acceptance remains separate from measured audio-quality improvement. The new Slovak locale is prepared separately, with native-speaker review, deployment environment and end-to-end Slovak use still unverified. The user-reported Slovak/English conversion does not establish English/Slovak content availability.
  - **Assessments:** `ASM-0011`
- **UNC-0011:** The tentative 26 October discussion has not settled evaluation tasks, sample size, rating dimensions, raters, agreement measure or consent/data handling. A school/adult class pilot and a possible Alliance Française visit are prospective; no appointment, willing teacher or recruited group is established. The Wednesday visit date is ambiguous in the supplied discussion. Workflow observations and inter-rater content-quality figures answer different questions and should be recorded separately.
  - **Assessments:** `ASM-0013`
- **UNC-0012:** Manny reports that the image ladder worked fine, resolving its implementation-acceptance uncertainty. The message does not separately establish Cathy’s judgment, a specific deployment environment, class use or a motivational benefit. The scope remains membership-accessible active non-hidden, non-personal dictionaries; totals can differ between viewers. Recorded copy/port provenance supports deduplication while separate reuploads count separately. Counts alone cannot establish participation or learning benefits. Other human-contribution ladders remain later possibilities.
  - **Assessments:** `ASM-0013`
- **UNC-0013:** Slovak catalog and configuration checks can establish coverage, valid placeholders/plurals and selection behaviour, but Ivana or another proficient speaker still needs to review wording and real use. The new locale initially covers the same marked interface surface as French; unmarked advanced strings may remain English. Manny reports a Slovak/English dictionary, whereas English/Slovak content has not yet been created or inspected in this session. Actual conversion needs the existing cost/permission approval and linguistic/audio review. No paid request or new Slovak carrier listening result is implied by interface localisation.
  - **Assessments:** `ASM-0011`, `ASM-0013`
- **UNC-0014:** One same-version rehearsal and one changed-release deployment passed on Windows/AWS with human browsing acceptance. Production rollback under failure, sustained operation and total human effort remain unmeasured. Fresh manual workflow dispatch still needs Manny; AI functional acceptance, AWS staging and stakeholder decision rights remain later steps. The Windows CI checkout failure is separate from passed application tests and successful actual Windows deployment. Code still has app-data access; receipts are not data isolation. The new additive schema helper has local recovery and SQLite evidence but no live PostgreSQL result; it remains a manual step outside the code-only controller.
  - **Assessments:** `ASM-0012`

## Questions for human refinement

- **REQ-0005:** After the current Sprint experiments, which outcomes, rating measures, participant set, and artifact-retention rules should become the initial protocol?
  - **Why this matters:** Historical request, not a blocker for the authorized dictionary prototype. The critical infrastructure now works and experimentation should soon supply enough evidence to make this concrete.
  - **Assessments:** `ASM-0003`
- **REQ-0007:** After contacting Sophie, what exact mobile/audio/exercise scope and ComputEL-10 deadline should govern delivery?
  - **Why this matters:** Historical request, not a blocker for the authorized dictionary prototype. The broad user and publication value is clear, but feasibility and the submission-critical minimum depend on her input.
  - **Assessments:** `ASM-0004`, `ASM-0006`, `ASM-0007`
- **REQ-0008:** After contacting Francis Bond, what collaboration scope and AI-authorship-compatible publication route should be pursued?
  - **Why this matters:** Historical request, not a blocker for the authorized dictionary prototype. This is the main dependency on converting promising learned-prompt results into a strong research programme.
  - **Assessments:** `ASM-0008`

## Proposed next actions

- **ACT-0001:** Carried-forward August proposal; applicability needs a broader review: Keep ISSUE-0042 as the immediate critical task and use the Sprint to settle the smallest useful experimental protocol.
  - **Assessments:** `ASM-0003`
- **ACT-0002:** Carried-forward August proposal; applicability needs a broader review: Verify every provisional Jumpspeak source and claim-to-source match plus the Stanford AI Index citation and 280-fold figure; after final co-author confirmation, post the separately titled report, preserve both EuroCALL submissions, and continue recording any committee response.
  - **Assessments:** `ASM-0004`
- **ACT-0003:** Carried-forward August proposal; applicability needs a broader review: Contact Francis and Sophie promptly, then convert their answers into precise collaboration, ComputEL, mobile, and audio acceptance criteria.
  - **Assessments:** `ASM-0004`, `ASM-0006`, `ASM-0007`, `ASM-0008`
- **ACT-0004:** Carried-forward August proposal; applicability needs a broader review: Before 24 August, prioritize a bounded recorded-audio MVP, quick judging autosave, and focused verification/closure of the picture-dictionary issues, subject to Sprint capacity.
  - **Assessments:** `ASM-0002`, `ASM-0006`, `ASM-0009`
- **ACT-0005:** Carried-forward August proposal; applicability needs a broader review: Immediately after the Sprint, finish legacy migration and use observed performance to close or reactivate ISSUE-0013.
  - **Assessments:** `ASM-0005`
- **ACT-0006:** Carried-forward August proposal; applicability needs a broader review: Document the existing pipeline runner, then take bounded passes on segmentation phase 1 and the revived UI-regression baseline.
  - **Assessments:** `ASM-0001`
- **ACT-0007:** Carried-forward August proposal; applicability needs a broader review: On the next Codex branch-update refusal, try full exit/restart/new-task first and preserve diagnostics if the workaround succeeds or fails.
  - **Assessments:** `ASM-0010`
- **ACT-0008:** Carried-forward August proposal; applicability needs a broader review: Use mandatory ordered input capture for every later workspace revision and compare archived human evidence with the resulting assessment changes during Sprint analysis.
  - **Assessments:** `ASM-0003`
- **ACT-0009:** Carried-forward August proposal; applicability needs a broader review: Configure authoritative collaborator role mappings, deploy the mode, grant access through Admin Tools, and run a natural Sophie-centered trial while reviewing evidence classifications and preserving the no-mutation boundary.
  - **Assessments:** `ASM-0003`, `ASM-0006`
- **ACT-0010:** Retain the accepted optional English carrier route and capture English-specific paired ratings of the same frozen expressions when practical, keeping failed or unchanged entries in overall reporting and preserving old recordings. Do not infer English prosody improvement from installation acceptance alone or broaden defaults without evidence. Continue Italian/German paired trials when practical; Icelandic/Japanese remain experimental and Japanese requires explicit entry selection.
  - **Assessments:** `ASM-0011`
- **ACT-0011:** Start a low-burden intervention log while resolving the current configuration work. Specify direct collaborator intake and one authorised, isolated request-to-preview-to-release path, including monitoring/rollback and a safe restore drill. Use this to evaluate whether two or three weekly reviews can replace daily technical intervention; defer broader autonomous release authority until evidence supports it.
  - **Assessments:** `ASM-0012`
- **ACT-0012:** Preserve the accepted English/French interface and sample-page Chrome/Firefox outcome while adding the authorised Slovak locale through the same shared configuration and catalogs. Keep the suspected AdBlock explanation provisional, obtain Safari and short end-to-end phone checks when suitable devices are available, and tidy the real friction Manny and Cathy identify. Test remembered interface choice and content-language recommendations independently of content conversion, provenance, permissions and audio quality. Obtain an independent francophone learner check when practical.
  - **Assessments:** `ASM-0011`
- **ACT-0013:** Retain the image ladder Manny reports working and gather Cathy’s separate judgment of its explanation, names, totals and phone presentation when practical. Keep accepted human provenance, reuse/port deduplication, exclusion of AI and hidden/personal/archived dictionaries, privacy and translated rendering under regression coverage. Revisit other contribution types or competition mechanics based on actual group feedback; do not infer motivational effects from implementation acceptance.
  - **Assessments:** `ASM-0013`
- **ACT-0014:** Use the tentative 26 October Zoom to identify the short workflows to tidy and agree an evaluation protocol with overlapping independent ratings of a shared frozen sample. Keep usability, linguistic/audio quality and participation outcomes separate. After that protocol is settled, explore whether a teacher and class want to build a small communal dictionary; treat the possible Alliance Française visit as an exploratory contact rather than a booked commitment or authorised outreach action.
  - **Assessments:** `ASM-0013`
- **ACT-0015:** Finish verification and deliver the Slovak locale patch with installation and English/Slovak conversion instructions. Have Ivana or another proficient Slovak speaker review wording, remembered interface preference and the English-learning path. Use the existing owner-approved conversion workflow to create or update an English/Slovak dictionary, checking its estimate and results before accepting content. Record actual trial, linguistic/audio issues and deployment separately; preserve the existing Slovak/English dictionary and all unrelated content.
  - **Assessments:** `ASM-0011`, `ASM-0013`
- **ACT-0016:** Prepare the two new preference tables on the laptop using the exact schema commit and reviewed helper, then run a fresh feature-only laptop workflow. After Manny accepts the combined workflows, repeat the bounded preparation on AWS and deploy the same feature commit through the existing acceptance workflow. Preserve controller restrictions, distinguish migration preparation from code-only installation, and record outcomes/effort. No direct collaborator communication is authorized.
  - **Assessments:** `ASM-0012`
- **ACT-0017:** Test guided pictures and writing practice on a small dictionary and a physical phone. For guided pictures, check a less-common central subject, edited explanation-language meaning, automatic completion, saved private attempts, level choices and missing-audio recovery. For writing, check deliberate/absent errors, optional style and exact approved-text preservation. Then obtain learner feedback; retain manual defaults until evidence supports changing them. Separate usability, linguistic quality and learning outcomes.
  - **Assessments:** `ASM-0012`, `ASM-0013`

## Open predictions

- **PRED-0001:** The issue audit will reduce false project-manager concern by allowing at least four apparently complete or stale issues to remain closed or close after focused verification.
  - **Horizon:** 2026-08-24
  - **Probability / confidence / status:** 85% / high / horizon_passed_outcome_not_verified
  - **Assessments:** `ASM-0002`, `ASM-0009`
- **PRED-0002:** The legacy completion attempt will either close ISSUE-0010 or expose a sharply bounded final operational blocker and determine ISSUE-0013’s state.
  - **Horizon:** next_workspace_review
  - **Probability / confidence / status:** 80% / high / open
  - **Assessments:** `ASM-0005`
- **PRED-0003:** Judging autosave is more likely than the recorded-audio MVP to be completed before 24 August because its roadmap and persistence model already support a bounded extension.
  - **Horizon:** 2026-08-24
  - **Probability / confidence / status:** 75% / medium / horizon_passed_outcome_not_verified
  - **Assessments:** `ASM-0006`
- **PRED-0004:** Contact with Sophie and Francis will materially narrow at least one of the mobile/ComputEL or learned-prompt publication decisions before the next workspace review.
  - **Horizon:** next_workspace_review
  - **Probability / confidence / status:** 80% / medium / open
  - **Assessments:** `ASM-0004`, `ASM-0007`, `ASM-0008`
- **PRED-0005:** If the Codex update-branch failure recurs, full restart and a new task will be tried before extended diagnosis and will shorten recovery relative to the 12 August incident.
  - **Horizon:** next_recurrence
  - **Probability / confidence / status:** 80% / medium / open
  - **Assessments:** `ASM-0010`
- **PRED-0006:** An initial collaborator trial will produce at least one attributed message classified as material project evidence and reveal whether a workspace review can be triggered reliably without conversation history.
  - **Horizon:** 2026-08-24
  - **Probability / confidence / status:** 75% / medium / horizon_passed_outcome_not_verified
  - **Assessments:** `ASM-0003`, `ASM-0006`

## Approval and revision

- **Status:** autonomous_project_manager_update
- **Authorized by / at:** Assistant following AGENTS.md / 2026-10-30
- **Basis:** AGENTS.md reflection on the writing laptop trial and Manny’s authorization of guided pictures and language levels.
- **Comments:** Human-owned intentions unchanged. Guided functionality and schema preparation are tested locally, not deployed or learner-accepted. No paid provider calls or collaborator messages were sent.
- **Change summary:** Recorded initial writing laptop acceptance and prepared complementary guided pictures with persistent preferences and four language levels. Separated the necessary additive schema preparation from the unchanged code-only deployment path.
- **Retired live items:** `REQ-0006`, `OBS-0001@rev-0002`, `OBS-0002@rev-0002`, `OBS-0012@rev-0002`, `ASM-0001@rev-0002`, `ASM-0009@rev-0002`, `PRED-0001@rev-0002`, `PRED-0002@rev-0002`, `PRED-0003@rev-0002`, `PRED-0004@rev-0002`
