# Community dictionary development experiment

## Current evidence — 5 October 2026

[Review acceptance and the German AWS trial](german-port-review-2026-10-05.md)
record Manny's successful faster-review acceptance and 61-entry German/English
conversion. One noticed pronunciation issue is not a controlled accuracy estimate.
The [three-page French stakeholder draft](../../docs/publications/community_dictionaries_update_fr/README.md)
is ready for human review. These reports supersede earlier pending status below.

## Language porting, 4 October 2026

Manny's first Swedish/English → French/English laptop port mostly works. The
[follow-up](language-porting-fixes-2026-10-04.md) adds contextual category translation,
stronger TTS language instructions and editable uncertain results, including old
blocked previews. Updates can repair earlier generated outputs while protecting
human corrections. 257 app tests, six shared audio unit tests and a real-queue
browser rehearsal pass. Human retesting and AWS porting deployment remain pending.



Latest: Manny reports the first practice update works and requests C-LARA-style
[multiple-choice flashcards](../../docs/howto/community-practice-choices.md). Multiple choice is now the default
for all six directions, with reveal mode retained. 215 app tests and a browser
rehearsal pass; this follow-up awaits human acceptance. Practice AWS deployment
remains pending.

Latest prepared feature: [one-request practice update](practice-2026-10-03.md).
Six card directions, picture crosswords and word searches; 205 app tests plus
both legacy puzzle tests and a 320/390/1280px browser trial pass. Human practice
acceptance/deployment remain pending. Manny reports image generation and the
Settings/photo follow-up now installed and working on AWS, with two pleasing
photorealistic examples; this is not a systematic quality trial.

Previous report: Manny reports successful laptop image-generation use. The
[Settings/photo follow-up](../../docs/howto/community-settings-and-photos.md) addresses
configuration discovery and adding manual pictures after words. 189 app tests
and a Chromium rehearsal at 320/390/1280px pass; Manny subsequently reports follow-up laptop and AWS acceptance.

Latest prepared feature: [optional AI pictures, 3 October](image-generation-2026-10-03.md).
Shared-style approval and entry-image previews integrate with contribution
provenance/withdrawal. Provider responses are simulated in verification;
systematic image-quality evaluation remains pending; Manny has subsequently
supplied successful laptop and AWS reports.

Latest: [dictionary-wide participation, 2 October](participation-2026-10-02.md).
Manny's successful use of the prior shortcut exposed excessive conceptual complexity.
The replacement has 156 passing tests and a Chromium rehearsal. Manny now reports
successful laptop use and a much simpler model, followed by successful
[AWS deployment and withdrawal/restoration](participation-aws-2026-10-02.md).
The server record includes backup, client-version and file-permission lessons. Earlier component-selection and share-back browser
scripts record superseded interfaces. The current script is `participation_browser.cjs`.


Latest increment: [clearer saving and invitations](save-ux-2026-09-30.md).
Manny reports successful AWS update on 29 September; Cathy supplies concrete
saving/recovery feedback on 30 September. The prepared UX patch has 70 passing
backend tests and controlled Chromium phone-viewport checks. Human acceptance
of this patch remains pending.

Preceding repair: [generated audio follows current wording](../../docs/howto/community-current-audio.md).
Manny reports the defaults/voices increment works but found outdated TTS still in
normal playback after editing. The repair keeps that audio in labelled history;
67 mocked-provider app tests pass. Manny subsequently confirms that only matching
audio is now shown. He requests check-in and plans AWS deployment/mobile testing
on 29 September. He subsequently reports that the AWS update worked; detailed
physical-device acceptance of the AI features remains unrecorded.

Preceding implementation and human evidence:
[working entry/photo/audio report, followed by defaults and named voices](voices-and-defaults-2026-09-28.md).
Manny reports the previous entry/audio patch is all working. His two further
requests are implemented with 64 passing mocked-provider tests and Chromium
phone-viewport rehearsals. The original voice/defaults patch has since received a broad human success report;
AWS/physical-phone acceptance of the AI additions is unreported.
[Install and try](../../docs/howto/community-voices-and-defaults.md). Local dictionary
lookup remains explicitly deferred until discussion with Sophie.

Earlier human evidence: [first live laptop photo trial](photo-laptop-trial-2026-09-28.md).
Manny reports quick horse recognition, Swedish wording, good device-voice playback
and saved edited text. Entry-level discovery and persistent synthetic audio motivate the later patch above. The [SDK repair](photo-import-fix-2026-09-28.md) brings the backend suite
to 41 tests; automated provider responses remain mocked. AWS/physical-phone
acceptance of this new flow is unreported. The existing human-media phone success
remains a separate earlier result. See the original
[28 September implementation record](photo-learning-2026-09-28.md) for build evidence.

Status: [iteration 1](iteration-001.md) produced the first functional patch,
with initial laptop success reported by Manny. [Iteration 2](iteration-002.md)
repairs microphone feedback and text discoverability. Its 21 backend tests and
controlled Chromium workflow pass. Manny subsequently confirmed that direct
laptop recording works after selecting the correct input: see the
[laptop trial](laptop-trial-2026-09-24.md). The implementation is now on `main`.
On 25 September Manny confirmed AWS laptop use and a first physical-phone
trial: Cathy took and saved a picture, then he added a recording. See the
[AWS/phone trial](aws-phone-trial-2026-09-25.md), including the 26 September
production-settings follow-up. Broader phone/browser coverage, closure of the
remaining deployment warnings and the invited Icelandic pilot remain pending.

On 26 September Manny confirmed that the server Assistant now retrieves this
updated evidence. He then requested optional image generation/TTS and a plan to
reduce his routine technical work. See the [direction review](direction-review-2026-09-26.md)
and [next-stage roadmap](../../docs/roadmap/community-dictionary-ai-and-maintenance.md).
These functions and an operational AI service are proposed, not yet implemented.
A later [situated-learning review](situated-learning-review-2026-09-26.md) adds spoken
sentences grounded in personal photographs and learner-history connections to the
proposal; the stakeholder paper is now a two-page version 3.

- [Specification and acceptance criteria](../../docs/roadmap/community-dictionary.md)
- [Setup and testing](../../docs/howto/community-dictionary.md)
- [Application](../../platform_server/community_dictionary/README.md)
- [Initial stakeholder report](../../docs/publications/community_dictionaries_initial/README.md)

The experiment asks whether the agreed, bounded prototype can be produced in a
few substantial AI implementation iterations with little human technical work.
It starts with community construction and discussion using photographs and
human recordings. Optional AI media is now the next proposed implementation
increment; dedicated practice and video remain later work. The new maintenance
experiment measures required human interventions, service outcomes and total
human effort as well as software development speed.

Specification work, repository setup and this scaffold count as preparation and
must be reported as part of the total effort. A development iteration may
contain many tool calls, test runs and repairs; do not report it as one model call.

As work proceeds, add dated records here identifying:

- base and resulting commits, or patch name and checksum;
- the instruction or consolidated feedback initiating the iteration;
- agent/model identity and settings where actually available;
- reused components and substantive implementation changes;
- exact checks run, outcomes, known failures and untested areas;
- human participation, elapsed time and cost where measured;
- the next bounded step.

Retain completed records and distinguish later corrections from original
observations. Use relative links to committed evidence. Keep uploaded community
media and credentials out of experiment records. This directory does not replace
the existing issue tracker or global workspace.

## Latest user-driven increment

The [1 October picture/word-link record](picture-word-links-2026-10-01.md)
records acceptance of the preceding laptop repairs, main commit `b945623`, and
Manny/Cathy's roughly fifty-entry Swedish dictionary. It implements requested
manual links and complementary browsing with inline listening/translation.
95 dictionary tests and controlled browser checks pass. Manny subsequently
confirms first-time laptop success with the sofa/cat example; a fuller server
and physical-phone trial remains next.

## Bootstrap record

- Base: `82bb185181acf0fa01958a19a3187f6ee8492f4f`.
- Work: add the app scaffold, import the version 0.4 discussion specification,
  and document application/setup and experiment conventions.
- Scope: new files only; no app registration, routes, schema changes or changes
  to running C-LARA-2 behaviour.
- Product result: structure and documentation prepared; prototype not implemented.
- Validation and subsequent environment results: reported with the delivered
  patch and recorded with the next implementation work. No passing functional
  app test is claimed by this bootstrap.

- [Contribution control, 1 October](contribution-control-2026-10-01.md): 118
  tests, migration fixture and Chromium phone/desktop rehearsal; laptop/AWS
  acceptance of this increment remains pending.

- [Contribution display, 1 October](contribution-display-2026-10-01.md): Manny reports
  successful contribution-control installation and entry creation, then requests
  entry context. The display-only follow-up passes 128 app tests and a Chromium
  phone/desktop rehearsal. Manny subsequently confirms the display works as intended on his laptop and
  requests check-in; new AWS/physical-phone acceptance remains pending.

- [Share back, 2 October](share-back-2026-10-02.md): the checked-in contribution
  controls work on the laptop, but the destination selector is hard to discover.
  A shortcut confirms the original entry automatically. 140 app tests and a
  Chromium rehearsal pass at that revision. Manny subsequently finds the shortcut
  an improvement but asks to remove confirmation and repeat review.

- [Immediate restoration, 2 October](immediate-restore-2026-10-02.md): one click
  returns current material to its original entry and retains valid prior approval.
  148 app tests and a Chromium rehearsal pass; human acceptance of this follow-up
  and new AWS/physical-phone validation remain pending.

## Pronunciation follow-up (5 October 2026)

The prepared [homograph guidance and bounded silence retry](../../docs/howto/community-tts-guidance.md) increment
includes review warnings, explicit cost accounting and additive migration 0013.
275 app tests pass. Manny now reports successful chat/lit generation and a successful
small-dictionary laptop test. The local startup notes now retain `--insecure` for
static files with `DEBUG=False`. Manny subsequently reports AWS conversion/review
of 61 French entries, with four initially unsatisfactory recordings; two remain
unresolved after his local remedies. A review-UX follow-up adds next-item navigation,
saved-word labels and private attention flags (migration 0014; 286 passing tests),
still awaiting human acceptance.

See [review workflow and installation notes](../../docs/howto/community-port-review.md).

- [Picture-centred sentence capture, 7 October 2026](picture-capture-2026-10-07.md):
  optional first implementation, 310 passing tests and simulated-provider browser
  rehearsal; live linguistic quality and human deployment/trial remain pending.


7 October follow-up: [picture-description expressions, editable vocabulary and image-only test copies](picture-vocabulary-2026-10-07.md). Manny reports a faster laptop workflow; the correction patch has 324 passing tests and now has reported small-Swedish-dictionary laptop acceptance. AWS deployment is now reported, with the first three examples exposing a redundant source card and a failed sentence TTS request; further MWE refinement remains deferred.

7 October AWS follow-up: [browsing and sentence-audio fixes](picture-capture-aws-fixes-2026-10-07.md), with 334 passing app tests and simulated Chromium progress/playback checks. New live acceptance and the original provider failure diagnosis remain pending.

- [Later AWS acceptance and audio recovery, 7 October](audio-recovery-2026-10-07.md): typed/spoken English/Swedish on laptop Chrome, one reported timeout/recovery issue, 338 tests and a focused return-navigation repair; Cathy trial planned.
