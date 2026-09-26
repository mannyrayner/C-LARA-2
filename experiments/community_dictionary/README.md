# Community dictionary development experiment

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
