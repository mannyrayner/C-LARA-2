# Community picture/audio dictionary app — initial specification

Version 0.4 · 23 September 2026 · Historical discussion draft

**Direction update, 26 September:** following successful initial AWS/phone use,
Manny requests optional AI image generation and TTS as the next increment and a
staged reduction in his routine operational involvement. The
[new implementation and maintenance roadmap](community-dictionary-ai-and-maintenance.md)
supersedes the priority ordering below for future work. It retains the original
human-media path and external-data safeguards. Neither AI media nor an autonomous
operator is implemented by this documentation pass; practice and video remain deferred.

> This preserves the version 0.4 discussion specification used as the first build brief. Current status (26 September 2026): the implementation is on `main`, shares the AWS deployment, and has successful human-reported laptop and initial physical-phone use. See the [setup guide](../howto/community-dictionary.md), [AWS/phone trial](../../experiments/community_dictionary/aws-phone-trial-2026-09-25.md) and [initial report](../publications/community_dictionaries_initial/README.md). Broader device coverage, remaining production configuration and the invited Icelandic pilot are still pending. The proposal/history below describes the original discussion, not the current deployment state.

This draft proposes a small first release and an explicit experiment in AI-led software development. It is not yet an agreed implementation contract. Inspection of the C-LARA-2 layout, contributor instructions, Django configuration, test conventions and CI supports the proposal to implement a separate Django app within that repository. Detailed model/service reuse and production deployment have not yet been checked.

Agreed direction in this revision: start with constructing and discussing the dictionary; attempt dedicated practice activities after that workflow works. Swedish is the first test language. Icelandic is a possible second pilot, with Kate and Axel and perhaps Branislav; their participation is not confirmed. Other implementation choices below remain proposals.

Revision 0.3 incorporates Manny's proposed direction: use the C-LARA-2 repository and existing server; make phone camera and voice recording the primary inputs; omit all AI content-generation features from the first prototype; prioritise TTS and image generation for a later increment. It also proposes a minimal registered partnership and request queue for people sharing the work. Exact partnership mechanics below remain open for discussion.

**1. Purpose**

Help a small community build, discuss, improve and learn from a shared picture/audio dictionary, using ordinary mobile phones. The community might be speakers maintaining a language, learners and a teacher, or a group learning together.

The central activity is contributing useful language material: take or choose a picture, record a word or short phrase, share it, and respond to other people's contributions. Construction and discussion come first: they are the harder problem and supply the material needed for later practice. Dedicated learning activities will follow after this first workflow is usable.

Support both languages for which useful AI assistance is available and languages where it is unavailable or inappropriate. Indigenous languages remain a main priority. The first prototype uses human contributions throughout and requires no AI provider credentials. Neither literacy in the target language nor an agreed spelling system is a prerequisite for contributing.

The two goals are a useful app with a low burden on contributors and maintainers, and an honestly documented test of whether a high-end model can build the agreed pilot in a few substantial development iterations.

**2. Pilot boundary**

Start with small, invited groups. Each dictionary has one target language, an optional language for explanations, and a few optional categories. Members can use more than one dictionary. Public discovery, open registration and a social network are outside the first release.

Use Swedish for Manny's first tests: he is completely confident in the language and can assess the linguistic content as well as the software. Test the human camera/recording workflow first, including contributions divided between partners. An AI-enabled comparison belongs to the later AI increment. A Swedish trial does not establish suitability for Indigenous communities.

Once the construction/discussion workflow works, consider Icelandic as a second target. Kate has been trying to improve her Icelandic, and she and Axel might enjoy constructing a dictionary together. Branislav may also be interested. Treat this as a possible small-group pilot, without assuming participation or assigning anyone editorial duties. It would test whether contributing and discussing material is useful and enjoyable for people with different levels of knowledge.

Proposed initial scale: one small Swedish dictionary, approximately 30 entries, and two or three adult testers. Include at least one partnership sharing image and audio contributions. A second dictionary can support the later Icelandic pilot. These are evaluation targets, not limits built into the data model.

**3. Dictionary entries**

An entry represents a word or short expression in a particular sense. The same spelling may therefore occur in several entries with different meanings. Do not require a universal list of concepts or one-to-one translation equivalents.

| Element | First-release behaviour |
| --- | --- |
| Picture | A prominent “Take photo” action, with choosing an existing image as an alternative; one selected picture in the normal entry view. |
| Audio | A prominent “Record” action, followed by listening and rerecording before submitting; allow additional contributed recordings without destroying the earlier ones. |
| Written form | Optional word or short phrase in the target language. |
| Meaning/context | Optional explanation in the group's chosen language; enough context to distinguish senses when needed. |
| Category | Optional simple tag such as food, home or actions. |
| Contribution record | Contributor and date for each picture, recording and text contribution, plus review status. Preserve distinct contributors to the same entry; allow AI origin to be recorded when that later feature arrives. |
| Discussion | Short text or recorded comments; proposals to correct or add material. |

Incomplete drafts are allowed. A picture-and-audio contribution must be possible without typing a target-language word. Entries without pictures are allowed. For later practice, only entries with the necessary media will participate in a particular exercise.

Allow more than one acceptable pronunciation or form. A short optional label can explain a variant. Editors choose the default presentation without asserting that all alternatives are wrong. The data model retains media candidates, comments and review decisions; the ordinary learner view stays simple.

**4. Four first-stage activities; practice follows**

| Activity | What a user can do |
| --- | --- |
| Browse and listen | Browse a picture grid, filter by category, search available text, open an entry and play its recordings. Image browsing must remain useful when entries have no written form. |
| Contribute | Photograph or choose an image, record and preview audio, optionally add text, and submit from the phone. Supplying just the picture or just the recording is a normal contribution; a partner may supply the rest. |
| Discuss and improve | Add a comment, offer another recording or picture, or propose a correction. |
| Review | An editor accepts a contribution, requests a change, or rejects it with an optional explanation. |

An incomplete contribution can begin a conversation. For example, a learner adds a photograph and asks what to call the object; another member adds a recording and explanation, and they clarify the intended meaning. Use the existing contribution and comment mechanisms for this; a separate question-and-answer subsystem is unnecessary. This is a proposed use scenario to test, not a newly agreed feature set.

After the first stage works, add simple practice cards: see a picture, try to recall the expression, then reveal text/play audio and choose “again” or “got it”. The proposed activity needs no automatic speech recognition or pronunciation score. “Again” cards recur in the current session; an elaborate long-term spaced-repetition system remains deferred. Accepted entries will supply practice material by default. Practice is outside the first-stage build and acceptance tests.

The contribution form should feel like adding one item, with camera, recording and optional text together. “Take photo” and “Record” are primary actions, not attachments to a required text form. It must not expose the full C-LARA annotation pipeline. Both picture-first and audio-first contributions should lead naturally to requesting the missing material from partners.

**5. Community editing**

Use three simple roles: member, editor and owner. Members browse, discuss and contribute. Editors also review changes. Owners manage membership, editors and dictionary settings. People may have more than one role.

For the invited pilot, submitted contributions are visible to members with a clear “awaiting review” label. Private drafts remain with their author. Acceptance makes a contribution part of the default dictionary and eligible for future practice activities. Editors can publish their own contributions directly, with that action recorded, so a one-person test is practical.

An edit to an accepted entry is a proposal until accepted; the accepted version remains available in the meantime. Store enough history to restore an earlier accepted version. Simultaneous edits must not silently overwrite one another. Members can withdraw their pending proposals; owners/editors can remove published material, including media, through a clear removal action.

Approval expresses this dictionary's editorial decision. It is not a claim to settle all dialect, spelling or cultural questions. Avoid voting, reputation points, automated arbitration and elaborate moderation machinery in the pilot.

**5a. Partnerships and outstanding requests — proposed first-stage feature**

A partnership is a small named group of two or more people within one dictionary. Members keep their own accounts and contribution credit. A person can belong to more than one partnership. The minimum setup is choosing a name and inviting existing dictionary members to join; they accept within the app. External messaging and contact discovery are outside this feature.

Any member of the partnership can supply pictures, recordings or both; no fixed photographer/speaker roles are required. A partnership organises work inside the existing dictionary membership and editor permissions. Joining it does not grant editorial authority or access to another dictionary.

An entry can carry a request addressed to one partnership: “Please add a recording” or “Please add a picture”, with an optional spoken or written explanation. Requests refer to the existing entry; answering adds media to that entry rather than creating a duplicate. The same mechanism can request a better or additional contribution even when some media already exists.

Show a simple “For our group” queue, with filters for needs audio, needs a picture, and replies awaiting review. It should be easy to reach after opening the dictionary. Each request shows a picture thumbnail or playable recording where available, who asked, and when. A member can respond directly from the queue. Push notifications, deadlines, points and task claiming are deferred.

Keep request progress distinct from dictionary acceptance: open → reply awaiting review → complete. The editor marks a request complete when accepting a contribution that fulfils it; an editor's directly accepted contribution can complete it immediately. A rejected reply leaves the request open. The requester or editor can withdraw or reopen a request. Several partners may respond; retain their contributions rather than silently overwriting one with another.

Example to test: Kate submits a picture and asks the partnership for audio. Axel later opens the group queue, listens to any spoken explanation, and records a response. They can discuss the intended meaning before an editor accepts the response and completes the request. This is an illustrative workflow, not a commitment that Kate or Axel will participate or take a particular role. Also test the reverse direction: an audio contribution requesting a picture.

**6. AI assistance — later increment**

The first prototype contains no AI content generation: no TTS, image generation, translation, usage-note generation or transcription. It must work without AI credentials and must not submit community media or text to an AI provider. This supersedes the earlier proposal to include textual AI suggestions initially. Ordinary server storage of members' contributions remains necessary.

When the human contribution and partnership workflows work, prioritise two optional features: generate a spoken recording from supplied text using TTS, and generate a picture from supplied guidance. Reuse C-LARA-2 services where inspection confirms suitable interfaces. Treat each output as another candidate picture or recording, with its origin preserved and the same review process used for human contributions. Generated media must not silently replace accepted human material or complete a request before review.

Enable future assistance per dictionary and per task. TTS suitability is language- and service-dependent. Image generation may be useful from guidance in another language, but its suitability for a community and its subject matter still needs review. Do not presume that either is available or appropriate for an Indigenous-language pilot. AI text suggestions and transcription have no priority over these two features.

AI makes no contribution or editorial decision automatically. When AI features are added, community material is sent to an external service only when that assistance is enabled and a user invokes it. With AI disabled, no dictionary text, recordings or images go to an AI provider. Where a community requires zero data retention, external assistance remains disabled until a suitable service and configuration have been verified.

Distinguish AI's role in building the software from its optional role in producing language content. The app can be AI-built while a dictionary is entirely authored by speakers.

**7. Mobile behaviour and data**

The working proposal is a responsive web app opened from a link, with phone use as the primary design target. Native app-store releases are deferred. Choose and record specific iPhone/Safari and Android/Chrome test devices before implementation; support is an acceptance requirement to verify, not a promise inferred from desktop testing.

Use large touch controls, short forms, visible recording/playback states and minimal typing. Make recording and taking a photo possible without entering target-language text. Spoken comments must be usable for clarifying requests without requiring transcription. Handle microphone/camera permission refusal with an understandable recovery path. Photographs should be resized for normal browsing, and audio should load when needed rather than downloading the whole collection.

For the first release, a connection is required to submit, retrieve new material and collaborate. Preserve an in-progress contribution locally where the browser permits, show whether it is saved locally or on the server, and provide retry after an interrupted upload without duplicating the entry. Do not display “saved” before the server confirms receipt. Full offline collections, automatic background synchronization and concurrent offline editing are deferred. Be explicit about the limits of local draft recovery, particularly if browser data is cleared.

Dictionary access is invitation-only in the pilot. The server enforces membership for text and media. Owners can export a documented package containing entries, media, attribution and review history, and operators can back up and restore the stored data. Record contributor permission to use uploaded media within the dictionary; public publication and new reuse permissions are outside this pilot.

Keep the schema capable of storing Unicode text and language/direction metadata. Broader script and interface-language coverage will need its own testing. Do not claim that a Swedish pilot demonstrates it.

**8. Relationship to C-LARA-2**

The working architectural choice is a separate Django app inside the C-LARA-2 repository, deployed through the existing server. It should have its own routes, templates, entry/request logic and tests. Reuse accounts and suitable infrastructure through a small number of explicit interfaces. Review the existing dictionary models before deciding whether to reuse or extend them; avoid scattering new behaviour through the general project editor.

Keep a documented boundary for shared accounts, media storage and later TTS/image services. Preserve a mapping to the existing one-item-per-page dictionary representation where useful, without making the new entry workflow run the general compilation pipeline. Retain media, contributor attribution, partnerships, requests and review history in exports. A later repository split would require handling data and shared-service dependencies as well as moving source files; this boundary should make that manageable without building a general plugin framework now.

The preliminary inspection covered [README.md](../../README.md), [Django settings](../../platform_server/platform_server/settings.py) and [root routes](../../platform_server/platform_server/urls.py). These support the module proposal, but do not verify the production server configuration or the exact reuse effort.

Before the build experiment, inspect the relevant current models, permissions, media handling and deployment instructions. Reusing the server still requires the normal migration, static-file and service-reload steps as applicable; checking out code alone is not the full deployment plan. Keep the feature under its own route and verify that existing C-LARA-2 workflows still work. No repository changes or deployment are part of this specification revision.

A full live integration with every C-LARA-2 feature is outside the pilot. Hosting and authentication details must be concrete before the timed implementation experiment starts. AI provider configuration is unnecessary for the first prototype.

**9. Acceptance scenarios**

These are observable pass/fail checks for the proposed first release; implementation may involve many internal tests.

| Scenario | Evidence of success |
| --- | --- |
| Contribute entirely on a phone | A member adds a photo and recording without entering target-language text, reloads, and finds the server-saved contribution. |
| Collaborate | A second account on another device finds the pending contribution, listens, and comments or adds another recording. |
| Share work through a partnership | Two members register/join a partnership. One supplies a picture and requests audio. Another retrieves it from the group queue and records a reply on the same entry. The reply stays visible as awaiting review; accepting it completes the request. Attribution identifies both contributors. Repeat with audio requesting a picture. |
| Handle multiple partners | A third member can join, see outstanding requests and contribute; concurrent replies remain distinct. Joining the partnership does not change dictionary or editor permissions. |
| Review and revise | An editor accepts it into the default dictionary. A later proposed edit leaves the accepted version intact until review and can be rolled back after acceptance. |
| Recover | An interrupted upload produces an honest status; retry saves one contribution and preserves the user's media within the documented recovery limits. |
| Respect access | A non-member cannot retrieve dictionary entries or their media. |
| Work without AI | All first-stage activities succeed with no AI credentials configured and no requests to AI providers. |
| Preserve data | An operator restores a backup, and the exported package includes the entries, recordings, pictures, contribution credits, partnerships, requests and review records used in the test. |

Run the relevant scenarios on the agreed iPhone and Android devices. Ask testers to perform the core contribution and discussion tasks without live coaching after a short introduction, then repeat after about a week. Record where they need help and the time required from an editor or technical maintainer. Also ask whether they want to continue building the dictionary and what makes the joint activity worthwhile or frustrating. Developer testing alone does not demonstrate ease of use or enjoyment.

**10. The few-iteration experiment**

Proposed target: three substantial implementation iterations for the construction/discussion stage, including the minimal partnership queue, after the specification, reuse boundaries and acceptance scenarios are agreed. AI features and practice are later increments and must be reported separately. This is a hypothesis to test, not a delivery guarantee.

| Iteration | Intended result |
| --- | --- |
| 1 | An end-to-end implementation of the agreed workflows, with persistent storage and deployment instructions. |
| 2 | Repairs following a consolidated report from functional, access-control, persistence and recovery checks. |
| 3 | Repairs and usability refinement following a consolidated report from real-phone use. |

Define an iteration as one development session initiated by a consolidated instruction or feedback packet. The model may inspect code, run tools and repeatedly test/edit within that session. Record those internal calls and repairs separately; “three iterations” must not be reported as “three model calls”. Record specification/design effort as well as coding effort.

Keep prompts, model/version/settings where exposed, code snapshots, reused code and dependencies, elapsed time, available usage/cost data, human interventions, test results and unresolved defects. Record any additional iterations honestly. All software changes are to be AI-written; human code changes, if needed, must be disclosed rather than hidden from the result.

The initial study can establish whether this particular pilot was produced quickly, works on the tested devices and requires little human assistance. It cannot by itself establish sustained vocabulary learning, long-term maintainability, safety at large scale, or fitness for a particular Indigenous community. Those require later use and evaluation.

**11. Decisions for the next revision**

The agreed sequence is construction and discussion first, with Swedish as the first test language. Icelandic is a possible second pilot with Kate, Axel and perhaps Branislav. Dedicated practice follows a usable dictionary-construction workflow; no practice feature is needed to begin the Icelandic pilot.

The revised direction is a mobile web interface in the C-LARA-2 repository, using the existing server and suitable shared components. Phone camera, human voice recording and spoken or written discussion are the first prototype's content mechanisms. Optional TTS and image generation are the first candidates for a later AI increment; textual AI assistance is removed from the initial scope. The simple card activity remains a later proposal.

The main new workflow proposal is a named partnership within a dictionary, with a simple queue of picture/audio requests and replies awaiting review. Confirm those mechanics and inspect the C-LARA-2 reuse boundaries, then turn this discussion draft into a frozen build brief. Add features only when they are essential to the first contribution–discussion–review cycle; record other ideas for later.

**12. Proposed development workflow and directory layout**

Start with Manny and the assistant in this thread as the working team. The assistant handles implementation design, code, migrations, automated checks, documentation and patch preparation. Manny evaluates the workflow and linguistic content, applies and checks in patches using the familiar process, and carries out deployment and real-phone trials. No separate coding-agent handoff is required for every iteration.

A separate Codex session is a useful optional local test/debugging or review assistant when its access to Manny's configured checkout provides a concrete advantage. That is an environment decision; Codex does not designate a fixed weaker model. If it contributes, record its actual role and changes in the experiment log. The project documents should contain enough current state to support a handoff without writing a second independent specification.

The present session can read repository files, edit local files, run shell commands and prepare patches. Git remote access was verified against commit `82bb185181acf0fa01958a19a3187f6ee8492f4f`. A complete runnable checkout, installed project dependencies and passing baseline tests have not yet been established. Access to Manny's local checkout, production server and physical phones is separate. Report executed tests and unresolved environment limits explicitly.

Use `community_dictionary` as the internal app name and `/community-dictionaries/` as its proposed URL prefix. This is a working technical name, not a branding decision. All paths below are relative to the C-LARA-2 repository root and are proposed, not created.

| Location | Responsibility |
| --- | --- |
| `platform_server/community_dictionary/` | Django app: `apps.py`, `models.py`, `forms.py`, `views.py`, `urls.py`, and small service/permission modules as needed. Keep C-LARA-2-specific service calls behind a small adapter module when needed. |
| `platform_server/community_dictionary/migrations/` | Versioned database migrations for the app. |
| `platform_server/community_dictionary/templates/community_dictionary/` | Mobile pages for browsing, contributing, discussion, partnerships and review. |
| `platform_server/community_dictionary/static/community_dictionary/` | App-specific CSS and JavaScript for camera input, recording, playback and draft/upload handling. |
| `platform_server/community_dictionary/tests/` | Django tests for permissions, contributions, review, requests, persistence and recovery. |
| `docs/roadmap/community-dictionary.md` | Canonical build specification, scope, architecture boundary and acceptance scenarios, adapted from this discussion draft. |
| `docs/howto/community-dictionary.md` | Local setup, verified test commands, deployment, phone-test checklist and recovery instructions. |
| `experiments/community_dictionary/` | Experiment protocol and dated iteration records: base commits, instructions, outcomes, human effort, checks and limitations. Keep operational issue state in the existing issue system. |

User photographs and recordings are runtime data, stored through a permission-protected media arrangement and backed up with the application data; do not commit them to Git. Do not assume the existing public media URL arrangement supplies the privacy this app requires. Small synthetic test fixtures may live with tests.

Expected integration edits are the project's `settings.py` (register the app), root `urls.py` (include its routes), documentation navigation, and CI. The current `pytest.ini` collects only top-level `tests/`; existing Django tests live under `platform_server/projects/tests/`. Add an explicit Django test step for the new app rather than assuming the present pytest job discovers its tests. Select focused existing regressions for the shared behaviour touched by implementation.

Keep new feature logic in the app. Reuse accounts and suitable existing models/services after inspection; avoid enlarging `projects/views.py` with the new workflow or introducing another frontend build system without a demonstrated need. The detailed reuse decision is part of setup, not a reason to postpone a complete first implementation.

The proposed sequence is:

1. Establish a checkout at a named base commit and a feature branch, provisionally `feature/community-dictionary-prototype`. Read the existing repository instructions, inspect relevant models/media handling, install an isolated test environment and record baseline results. Turn the agreed draft into the canonical repository brief. Record this preparation effort separately from the implementation iterations.
2. Implement the bounded first prototype in one substantial iteration, including the full photo → partner request → recording → discussion → acceptance workflow, its reverse direction, persistent storage, agreed access/recovery behaviour and the associated tests and instructions. UI and backend arrive together.
3. Deliver one patch against the recorded base commit, with a changed-file summary, actual check results, installation/migration instructions, known limitations and a short phone-test checklist. Default to the familiar patch workflow; branch/PR delivery can replace it if agreed later. Check patch application against the stated base before delivery and verify Manny's checkout matches before applying.
4. Manny applies and commits the patch, tests it in the intended environment and provides a consolidated report with commit ID, reproduction steps and relevant output/screenshots. Local Codex can help with environment-specific diagnosis if useful. The assistant makes the next coherent repair iteration against the resulting repository commit.

The immediate preparation deliverable is a runnable baseline and an exact first-build brief. The first code delivery should exercise the community contribution workflow; an empty scaffold alone is not the implementation milestone.

Repository orientation for this proposal used `AGENTS.md`, `docs/global_workspace/README.md`, the human-owned intentions and the dated derived state. This thread supplies the current app scope; older August planning dates are historical context. During implementation, follow the existing global-workspace ownership/archive rules and link the new roadmap where relevant, without silently rewriting human intentions or treating experiment logs as canonical project-management state. This specification revision does not modify the repository or its live global workspace.
