# Direction review: optional AI media and operational autonomy

Date: 26 September 2026. Documentation and source-inspection pass; no generation
feature, autonomous executor or production-settings change is implemented here.

## New human evidence

Manny confirms installing the previous documentation update on AWS. He supplies
the resulting Assistant answer, which now distinguishes the actual laptop and
first phone trials from broader testing and open deployment questions. This is
human-reported success of repository-based continuity, not a new app-test run.

In the supplied project correspondence Sophie treats data sovereignty as central
to viability and asks to compare current AI images on difficult meanings. Manny
has agreed to an early-afternoon discussion next Thursday, 1 October. He now
requests optional image generation and TTS, followed by an experiment to reduce
his technical involvement from daily work to several times per week and then
per month. He reports Cathy's support for the goal and scepticism about feasibility.

This changes the immediate roadmap: image generation and TTS are the next
proposed implementation increment. Human camera/voice contributions remain core;
practice and video remain deferred. The shared deployment/security follow-up is
still open. No permission for live provider charges, production data transfer,
expanded AWS credentials or unattended deployment is inferred from the paper revision.

## Inspection and documents

- Current `main`: `e3b94b08d0d493e88e6966781323df2753f0bdfa`.
- Source inspection confirms image generation in `src/core/ai_api.py`, TTS engines
  in `src/pipeline/audio.py`, user-key/billing logic in `platform_server/projects`,
  and the separate dictionary's private contribution/review paths.
- Reuse needs a policy/storage/provenance/job/cost adapter. The audio pipeline
  can use a test-tone stub; the dictionary must require real synthesis.
- `src/core/project_understanding.py` launches read-only Codex execution. An
  operational agent requires a separate authorised workflow and infrastructure;
  none is created in this documentation pass.
- [The new roadmap](../../docs/roadmap/community-dictionary-ai-and-maintenance.md)
  sets out proposed behaviour, acceptance checks, governance questions and staged
  reduction of human interventions.
- [Version 2 of the paper](../../docs/publications/community_dictionaries_initial/README.md)
  distinguishes deployed functionality, the proposed AI increment and untested
  maintenance goals. It preserves approximate timing as Manny's estimates.

The prior 21 Django test passes and controlled Chromium results remain historical
implementation evidence. This pass validates document links, LaTeX rendering,
global-workspace consistency and patch application, not provider quality or new
runtime behaviour. No community media, credentials or live provider calls are used.

## Input retention decision

The supplied message contains third-party family/medical and social correspondence,
email addresses and mail-client formatting unrelated to project work. Per the
global-workspace sensitivity rule, those details are excluded from public records.
Revision 16 preserves selected project-relevant excerpts verbatim, in their order:
Manny's confirmation of the Assistant trial, Sophie's project paragraph, and
Manny's final three requested directions. These are explicitly excerpts, not a
complete transcript of the supplied message. The already-recorded Assistant
answer and intervening email discussion are summarised above where relevant.
No full private-mail copy is placed in the repository or paper.
