# Community dictionary development experiment

Status: preparation. No functional implementation iteration has been completed.

- [Specification and acceptance criteria](../../docs/roadmap/community-dictionary.md)
- [Setup and testing](../../docs/howto/community-dictionary.md)
- [Application](../../platform_server/community_dictionary/README.md)

The experiment asks whether the agreed, bounded prototype can be produced in a
few substantial AI implementation iterations with little human technical work.
It starts with community construction and discussion using photographs and
human recordings. AI media generation and practice are later work.

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
