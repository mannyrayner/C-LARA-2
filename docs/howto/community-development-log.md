# Development study journal — first version

## Purpose and scope

Record a consecutive series of Community Dictionaries changes, from request
through specification, implementation, installation and human acceptance. Keep
revisions, unsuccessful attempts and unfinished features in the dataset.

The reusable recorder is `scripts/development_log.py`, using only Python's
standard library. The operational journal belongs in the **private deployment
control repository**, under `development_log/`. Do not put conversation copies,
private test material, receipts or operational notes in the public application
repository. No application migration, service restart, API key or paid model
request is required to use this recorder.

## Timing definitions

The primary AI timing is **instrumented assistant response elapsed time**. Start
the clock at the first available tool operation after a substantive request;
stop at the final recording checkpoint. This includes reasoning, composing,
tools and waits inside that interval. It is not a measurement of internal
reasoning-only time, compute consumption, token generation or active CPU time.
We cannot infer those quantities by subtracting tool durations.

If instrumentation starts after work has begun, mark coverage `partial` and say
what is missing. Missing initial/final time is never silently estimated. Record
an externally supplied UI timing separately as a reported observation, with its
source and definition. The elapsed time of an open session is not counted as
completed work. Interruptions and overnight waits between responses must not
be turned into thinking time. Optional tool and human work intervals are separate
categories, not added to the enclosing response interval. Overlapping intervals
are merged before totals are calculated.

Every event has both `recorded_at` (when this journal received it) and optional
`occurred_at` (when the event happened). Timing precision is `observed`,
`reported_exact`, `approximate` or `unknown`. Approximate/unknown event times do
not produce exact turnaround metrics. UTC timestamps include a timezone offset.
Retrospective imports are labelled, and remain distinguishable from prospective
recording. An AI-authored note does not become independent external evidence.

## Milestones and evidence

| Event | Evidence to retain |
| --- | --- |
| `request` | Concise request, category, request reference; receipt time if known |
| `specification` | Versioned scope and acceptance criteria; distinguish written from human agreed |
| `implementation_ready` | Exact commit, tests and installable artifact |
| `installation_finished` | Controller receipt, target, requested/previous commit and outcome |
| `acceptance` | Explicit human report, target, tested commit and checks performed |
| `revision_requested` | Explicit requested change, target and relevant commit |
| `note` | Additional observation, scope change, uncertainty or waiting reason |
| `feature_closed` | Explicit outcome: accepted, abandoned or superseded; record inapplicable milestones in a note |

Work sessions use `work_started` and `work_stopped`, with a stable session ID.
An interrupted session can be closed with unknown end time; it is then reported
as unmeasured rather than credited with the entire overnight gap.

Controller receipts can be imported without copying raw command output. They
prove controller outcomes, not that a human tested the feature. GitHub workflow
JSON can also be imported: success is recorded as workflow success, never silently
promoted to installation or functional acceptance. Use job completion timestamps
only when available; GitHub `updated_at` is not assumed to be completion time.
Imports are idempotent. Re-running a workflow is a separate attempt.

## Assistant workflow

1. At the first available tool call, record the clock and feature/request ID.
   Reuse the feature ID across its revisions. Record request-received time only
   if exposed by the interface; otherwise use `unknown` and retain the first
   observed clock separately. Do not fabricate a timestamp from message order.
2. Start a response interval, record the proposed specification and its evidence,
   and work normally. Record an agreed specification only after explicit agreement.
3. Add implementation evidence after tests and publication. Record failures and
   changed scope as well as successes. Add a concise note at each material change.
4. Import available deployment receipts/workflow metadata. When the user reports
   testing, attribute it as a human report and preserve timing uncertainty.
5. Stop the response interval at the final recording checkpoint; export summaries
   and sync new event files to the private repository with a checked branch lease.
   Verify publication. Do not overwrite event files, replay deployments or modify
   deployment permission gates to collect evidence.

If the private journal is unavailable, preserve a local checkpoint and disclose
the unsynced state. Do not block necessary product work or replace missing data
with invented timings. Future requests may reuse the recorder without a new
installation. Human work intervals are optional and must be human reported or
directly instrumented, never inferred from a gap between messages.

## Commands

Run `python scripts/development_log.py --help` for the complete interface. Examples
use a private checkout outside the public application repository:

```bash
python scripts/development_log.py --store ../private-control/development_log new \
  --feature DEV-001 --title 'Example feature' --category feature \
  --summary 'Requested behaviour and request reference.'
python scripts/development_log.py --store ../private-control/development_log start \
  --feature DEV-001 --phase assistant_response --coverage partial \
  --summary 'First instrumented checkpoint; earlier response time unavailable.'
```

Save the returned session ID. `event` records milestones; `stop` closes a session;
`void` adds an explained correction without deleting the original record.
`import-receipt` and `import-workflow` read local JSON evidence without contacting
either provider. `export --output PATH` writes a JSON dataset, event CSV and
Markdown report. Export files are derived views; only the event files are the
canonical journal. A generated report must not be used as the source for new
events.

For example, close the recorded session and generate the three reports with:

```bash
python scripts/development_log.py --store ../private-control/development_log stop \
  --feature DEV-001 --session RETURNED_SESSION_ID \
  --summary 'Final recording checkpoint; publication of the log and delivery of the reply follow.'
python scripts/development_log.py --store ../private-control/development_log export \
  --output ../private-control/development_log/reports
```

If a session was interrupted and its real end is unavailable, use `stop
--unknown-end` instead. For a timed human report, use `--at` with the actual
reported timestamp. To repair a timed session, void its stop before voiding
its start, then append the corrected records. A `.write-lock` directory prevents
simultaneous local writers; remove a stale lock only after confirming that no
writer is running. Git branch leases protect synchronization across machines.

Run the isolated tests with `python -m unittest discover -s scripts/tests -v`.

## First-cut acceptance criteria

- Create a feature and multiple response intervals; keep incomplete/unknown and
  partial timing distinguishable from complete measured intervals.
- Record the seven agreed request/specification/implementation/install/acceptance
  milestones, preserving separate laptop and AWS results and revision requests.
- Import successful and failed controller receipts and workflow attempts without
  confusing deployment, testing and human acceptance; repeated imports add nothing.
- Correct a record without rewriting it, reject malformed timestamps/references,
  and export all features including unfinished and abandoned ones.
- Report observed turnaround where endpoints exist, interval unions, rework and
  failures. Protect CSV text from formula execution.
- Maintain this first feature in the private journal, including its incomplete
  initial timing coverage. Keep the recorder independent of application services.

## Interpreting results

The report describes this project's observed response, delivery, effort and
revision process. It does not establish a causal speedup over a different model
or a human-only team. Categories and scope should be recorded before results are
known. Report completed-feature turnaround alongside open/abandoned counts;
never quietly drop difficult work. A fast first version and a reliable accepted
version are distinct outcomes.

The journal is append-only through this tool and reviewable through Git history;
it is not cryptographically independent evidence. Qualitative judgments remain
attributed. A small prospective series can supplement clearly labelled historical
reconstruction, without assigning retrospective timestamps to new observations.
