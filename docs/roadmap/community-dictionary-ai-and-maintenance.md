# Community Dictionaries: optional AI media and reduced operational dependence

Discussion and implementation plan, 26 September 2026. Reviewed source:
`e3b94b08d0d493e88e6966781323df2753f0bdfa`. This document proposes the next
increment; it does not implement generation or an autonomous operator. The later
26 September sentence-learning proposal below was reviewed against `6ad49ee`.

## Direction and current boundary

Manny now requests optional image generation, optional TTS for suitable languages,
and a serious experiment in reducing his routine technical involvement. These
supersede the earlier deferral of AI media beyond the next increment. Camera,
human recording, construction and discussion remain central. Sentence-based learning
is now a proposed extension; a full practice system and video remain later work. Sophie identifies data sovereignty as central and proposes
testing difficult-to-illustrate meanings; a discussion is planned for early
afternoon on Thursday 1 October. No new community approval is inferred.

The human-media prototype is deployed, with positive laptop and initial phone
reports. Its explanation Assistant now retrieves the updated trial evidence.
Both new AI media functions and a write-capable maintenance workflow are still
absent. The platform's existing Assistant uses `codex exec --sandbox read-only`
in `src/core/project_understanding.py`; its prompt also prohibits mutation.
That boundary remains in force. A future authorised execution service must
enforce its own permissions rather than treating a request as permission to
override the existing Assistant's restrictions.

## Later 26 September direction: sentences grounded in experience

Manny proposes extending picture entries with spoken sentences, optional text and
translations. A human partner must be able to contribute a sentence without AI or
mandatory transcription. Where permitted, sentence generation and TTS could reuse
familiar vocabulary, and C-LARA-2 annotations could link words or expressions to
earlier dictionary entries. Encounter history is not evidence of mastery; personal
learning records should remain distinct from shared dictionary content.

Start with explicit sentences attached to pictures and their recordings. Guided
replay, earlier-entry thumbnails and an optional picture-first speaking attempt are
interface proposals to test. Continuous word/audio synchronisation needs timing
information in addition to text annotation. These are not existing app features.

Describing an actual scene requires the image or a human description. External
processing of photographs or learning history needs its own authorised scope; the
image-generation permission below does not automatically permit either. Retain the
complete human-only path and community control over data.

The [two-page stakeholder paper](../publications/community_dictionaries_initial/README.md)
connects this situated-learning proposal with maintenance driven by non-technical
user requests. Motivation, spoken-language gains and reduced technical mediation are
hypotheses to evaluate, not demonstrated outcomes. A small Italian trial using Manny's
own photographs is proposed; no trial result is recorded. Detailed AI-media and
operational acceptance criteria below remain applicable when those components are built.

## 1. Product behaviour for the next increment

### AI pictures

- Keep taking/uploading a photograph as a normal path. Add an optional Generate
  picture action only where the dictionary's policy allows it.
- Ask for the intended meaning and relevant context, possibly in the explanation
  language. Another partner can provide this guidance; typing an AI prompt must
  not become a prerequisite for picture/audio participation.
- Show what content will be sent, the provider and estimated/bounded cost before
  the user invokes generation. Do not automatically attach the existing photo,
  audio, dictionary contents or discussion history.
- Produce one previewable candidate per request. Save generated media privately,
  preserve the current accepted picture, and use explicit review before promotion.
- Record origin, requesting user, provider/model, original/revised prompt where
  available, creation time and review decisions. Treat prompts as dictionary data,
  not public repository records or unrestricted logs.

### TTS

- Generate from text the user has confirmed, with an approved language/voice.
  Record the source text and version so later wording edits do not silently
  relabel an older recording.
- Provide listening before submission, explicit synthetic-audio labelling, and
  the normal review step. Never imitate a member's voice in this increment.
- Start validation with Swedish; ask a suitable speaker to assess any Icelandic
  voice before treating it as an option for the pilot. Provider language listings
  alone do not establish adequate pronunciation or dialect coverage.
- Missing credentials, unsupported language, rejected content or provider failure
  must produce a clear failure and retain the human-recording path. No silent
  fallback to another provider, language, or the existing offline test tone.

## 2. Reuse confirmed by source inspection

| Existing component | Reuse | Work still required |
| --- | --- | --- |
| `src/core/ai_api.py`, `OpenAIClient.generate_image` | Returns image bytes and generation metadata; reports usage through configured callback. | Enforce dictionary provider policy and prompt scope; validate/store privately; attach provenance and candidate review. |
| `src/pipeline/audio.py`, `OpenAITTSEngine` / `GoogleTTSEngine` | Engines synthesize supplied text to a path. | Select an explicitly approved engine/voice; test the actual output format and pronunciation; prohibit stub fallback. |
| `platform_server/projects/views.py`, `_build_ai_client`, `_billing_usage_reporter` | Existing per-user key selection and usage-accounting logic. | Extract an appropriate service boundary rather than import the large views module. Community restrictions override personal-key preferences. Define dictionary budget attribution and TTS accounting. |
| `platform_server/projects/models.py`, `AIUsageCharge` | User-associated usage records with optional project. | Link dictionary job/request IDs and distinguish estimates, reservation and actual charges. Existing project billing is not a complete dictionary cost control. |
| `community_dictionary/storage.py` and `services.py` | Private validated media, contribution review and local submission receipts. | Extend to provider results and generation jobs without breaking human upload/retry behaviour. |

Do not route dictionary generation through the whole text-compilation pipeline,
public image/artifact directories, or a language-wide shared audio cache. Scope
new storage and caches by the dictionary and its policy. No provider quality,
retention eligibility or cost is established by finding a Python adapter.

The audio pipeline normally permits a deterministic test-tone engine; a
`require_real_tts` mechanism exists for callers of that pipeline. Direct dictionary
adapters must enforce real synthesis and validate the produced container themselves.
The Google path and language/voice selection need integration checks; inspection
alone is not a passing runtime test.

## 3. Data policy before external processing

Use a dictionary policy with independent image/TTS capabilities, approved provider
configuration, authorised decision-maker, outbound content scope and cost limit.
Keep both operations disabled until enabled under that policy. Check permission
again at job execution: revocation or membership removal between queuing and
execution must prevent new outbound processing.

Community authority over the data is distinct from possession of an owner account
or control of the EC2 host. Establish who can authorise access, generation,
publication, export and reuse, and who can withdraw material. Include images,
voices, text, prompts, derivatives, browser drafts, diagnostics and backups.
Removing a member cannot retract an earlier download; backup deletion/retention
must be stated honestly. A separate community-controlled deployment is an option
where the shared service cannot satisfy requirements.

Preserve the existing specification's rule: where zero data retention is required,
leave external assistance disabled until the actual provider account, endpoint
and configuration are verified. Do not equate no-training with no-retention, infer
eligibility from a model name, or treat an English translation as inherently safe
to disclose. No provider-retention eligibility claim is made by this plan.

Apply an independent policy to maintenance-agent input. By default it receives
source code, synthetic reproductions and redacted health/error information, not
private dictionary entries, recordings, keys, full logs or database dumps. A
private-data debugging exception needs community-authorised handling. A generated
image being disabled must not be defeated by the debugging channel.

Useful discussion references are the [Maiam nayri Wingara principles](https://www.maiamnayriwingara.org/mnw-principles)
and [CARE principles](https://www.gida-global.org/careprinciples). They inform the
questions; this plan does not certify compliance or substitute for agreement with
the relevant community.

## 4. Jobs, failure handling and acceptance checks

Proposed generation jobs have an ID, dictionary/requester, policy version, source
snapshot, provider, budget reservation, state, attempts and output contribution.
Use bounded background execution rather than holding a phone request open.
Make failure/cancellation visible, clean up rejected temporary output and retain
an audit trail with private content excluded from general logs.

Submission idempotency does not guarantee provider billing idempotency. If a call
times out after the provider may have generated/charged for it, record the uncertain
outcome and reconcile it or require an explicit new request; do not blindly repeat
it. Enforce quotas atomically so concurrent jobs cannot overspend a dictionary's
limit. State estimated and measured cost separately.

Minimum checks for the eventual implementation:

1. With AI disabled, all human workflows still work and no generation route or
   queued job can contact a provider. Cross-dictionary access and revoked access fail.
2. Generated output stays in private storage, retains provenance, and does not
   replace accepted media until reviewed. A request is completed only by accepted
   appropriate media, not merely by successful generation.
3. Repeated submissions yield one local job/result; failed and uncertain provider
   outcomes do not silently trigger additional paid calls.
4. TTS never returns a test tone as speech, never silently switches language or
   provider, and preserves the source text/version and selected voice.
5. Insufficient budget, refusal, timeouts, malformed output and worker restart
   have understandable outcomes and leave existing entries intact.
6. One authorised live sample for each selected provider/language configuration
   is checked for storage, actual playback, cost reporting and appropriate quality.
   Mocked tests do not establish those facts.

## 5. An experiment in reducing Manny's operational work

The aim is to reduce required technical intervention, not to reduce useful
conversation, community authority or visibility. The unit of success is an
ordinary collaborator request or operational incident resolved end to end without
Manny serving as interpreter, command runner or hidden troubleshooter.

| Proposed stage | Routine contact target | What must become dependable |
| --- | --- | --- |
| Baseline | Observe the current daily work for two weeks. | Log interventions, minutes, request volume/complexity, incidents, costs and work done by other people. |
| Batched supervision | Two or three scheduled reviews per week. | Direct collaborator intake; reproduction, meaningful checks, preview and a concise decision/release queue. Complete a safe deployment/rollback and restore rehearsal. |
| Routine delegation | Two scheduled reviews per month. | Standing permission for specified reversible changes; tested automated release, health checks, rollback and capped costs. Observe a representative month plus failure exercises. |
| Exception-led operation | Periodic strategic review, exceptional escalation. | Routine operation during planned absence, dependency/credential renewal, recovery, and a named fallback for failures outside permitted or recoverable scope. |

These are proposed experimental targets, not dates or commitments already accepted
by collaborators. Stay at or return to an earlier stage if service quality,
backlog or total human effort worsens. A quiet month alone is not evidence of
robustness; include safe drills for provider outage, failed deployment, expired
credentials and restoration. Do not deliberately disrupt production users.

Record per task: initiating request, plain-language acceptance criterion, AI/model
version where available, investigated code revision, diagnosis, proposed change,
checks and result, deploy/rollback identifiers, elapsed/resolution time, cost,
human touches/minutes and reason for each escalation. Operational evidence stays
in a restricted store with a redacted summary suitable for the public repository.
The AI can prepare the log; people should only correct missing or misleading work.

Review interruptions, hands-on time, resolution latency, unresolved backlog,
regressions, outages, cost and satisfaction together. A reduction in Manny's work
is not a success if equivalent technical work is pushed to Sophie, Cathy or another
unpaid intermediary. Keep normal scientific/project discussion separate from
required operational interventions.

## 6. Required operating system around the model

1. **Intake and persistent work:** collaborators submit plain-language requests
   directly, including spoken requests if later supported. Clarify desired outcomes
   with them, without routing every exchange through Manny.
2. **Isolated execution:** create a branch/check-out with scoped repository access,
   synthetic test fixtures, bounded commands/network and a record of actions. Treat
   user content, logs and external responses as evidence, never policy instructions.
3. **Preview and release:** use CI and a staging deployment, then an authorised
   release service that can deploy known artifacts, verify health and roll back
   compatible changes. Do not give the explanatory web Assistant unrestricted root.
4. **Operations:** check uptime, certificate/credential renewal, storage, queue
   failures, backups/restoration and dependencies. Separate independent monitoring
   from the component being monitored. Keep releases small and recovery exercised.
5. **Policy and escalation:** authorise routine operation classes in advance;
   reserve access/data-policy changes, budget increases and destructive migrations
   for the designated authority or a previously approved procedure. Policy is
   enforced outside the model, including a pause control and per-action audit.

A chat session cannot by itself provide continuous operation. An accountable
organisation must retain control of infrastructure/provider accounts, funding and
credentials, and name a fallback operator for unrecoverable events. That fallback
need not be Manny; assigning it to someone else is a decision, not an assumption.
Community and linguistic decisions remain with their authorised participants.

## 7. Proposed sequence and discussion with Sophie

1. Close the existing production-settings items and rehearse restoration. Start
   the intervention log now; use this bounded operational task as the first
   request-to-release example. Full nginx/proxy evidence is still needed.
2. Agree the outbound-data policy and first provider/language configurations for
   an ordinary Swedish pilot. Implement the two optional media adapters with the
   acceptance checks above, keeping scope distinct from an operations agent.
3. With Sophie, choose a small set of meanings spanning everyday objects, actions
   and harder contextual cases. Compare photo/AI candidates for the same senses;
   assess recognisability, cultural fit, ambiguity, correction effort and time to
   an acceptable entry. Retain useful negative results and user preference.
4. For TTS, compare confirmed text/voice output with human recordings, judged by
   a suitable speaker. Confirm Icelandic quality before offering it to the pilot.
5. Build direct request intake and one staging/release workflow; run the first
   supervised maintenance cycle, then decide whether the weekly target was met.

A stronger future model may help but cannot substitute for provider agreements,
enforced permissions, deployment infrastructure, backups or evidence that failure
recovery works. Whether the involvement targets are achievable remains an
empirical question. This plan proposes a way to find out without assuming the answer.
