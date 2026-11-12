# On-demand Community Dictionaries staging pilot

**Updated:** 12 November 2026. **Owner:** Manny Rayner; implementation: Codex.
**Status:** Detailed plan; offline request rehearsal implemented. No staging
AWS resources, private control repository or live trigger have been created.

This extends the [staging roadmap](community-dictionary-aws-staging.md) and
[bootstrap specification](community-dictionary-aws-staging-bootstrap.md).
Manny requested the on-demand plan and the start of implementation on
12 November. Cost containment is a requirement of this pilot.
The production approval process remains in place during the initial pilot.

## Intended result

From a fresh chat, Codex requests a bounded session, deploys a reviewed
candidate, signs in, tests the user-visible result, retains evidence and stops
staging without needing Manny's laptop. The control path remains available
while staging is off. Neither a lost connection nor a repeated request renews
the deadline or silently submits another deployment. Staging uses synthetic
data, independent credentials and staging-only permissions.

Deployment tooling is installed through the reviewed operator path outside
the application checkout. Changes under `ops/` cannot be delivered through
the existing code-only application release mechanism.

## Resources and cost

| Component | Starting configuration |
| --- | --- |
| App host | Sydney `ap-southeast-2`, Linux x86-64 `t3.small`, Standard CPU credits, encrypted 24 GiB gp3 disk; instance-initiated shutdown behaviour `stop` |
| Address | Retain a staging Elastic IP and `c-lara-2-staging.c-lara.org`, preserving DNS/TLS across stops |
| App data | Local PostgreSQL matching production's major version, synthetic dictionaries/media, captured mail and bounded worker concurrency |
| Control | New private `clara-staging-control`, protected `main`, restricted issue-writing connection, short GitHub-hosted Linux jobs |
| Lifecycle | Small Lambda coordinator with reserved concurrency **one**; private S3 prefix for durable session/budget records |
| Shutdown | EventBridge Scheduler invokes the coordinator every minute; a root-owned host boot/expiry unit independently enforces the lease |
| Evidence | Private bounded receipts/artifacts retained for 30 days; short log retention; no credentials or unrestricted browser traces |

The first pilot adds no RDS instance, load balancer, NAT gateway or
customer-managed KMS key. Use ordinary AWS-managed encryption. The staging
network has no route or resource grants to production private data. Verify
Lambda concurrency quota before provisioning. Run Chromium on the external
trusted runner rather than the 2 GiB app host. Install dependencies during
bootstrap; ordinary releases do not rebuild the environment.

The forecast uses the seven days ending 12 November: 16 successful laptop
candidate installations and 12 successful production deployment jobs. The
production jobs took 23–35 seconds, median 26, excluding functional testing.
Allow 15–20 minutes per candidate plus investigations, retries and inspection:
**300–600 running minutes/week**. This is a forecast, not measured staging
uptime. Measure cold-start CPU throttling, readiness and browser-test duration
during the pilot. CI and development happen while staging is off.

| Monthly item, USD before tax | Planning amount |
| --- | ---: |
| Compute at $0.0264/hour, 5–10 hours/week and 52/12 weeks/month | $0.57–1.14 |
| 24 GiB retained disk, conservative allowance rather than an exact quote | $3.00 |
| Retained public IPv4, 730 hours at $0.005/hour | $3.65 |
| Coordination, bounded logs and small state/evidence storage allowance | $0.50–1.00 |
| Expected total | about $8/month |
| Proposed pilot infrastructure allowance | $10/month |

References: [AWS Sydney Linux price feed](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/Asia%20Pacific%20%28Sydney%29/Linux/index.json),
[EBS billing](https://aws.amazon.com/ebs/pricing/) and
[IPv4 pricing](https://aws.amazon.com/vpc/pricing/).
Before provisioning, retain an itemised current quote privately. The estimate
excludes tax, paid AI calls and billable GitHub Actions overages. Do not hold
an Actions runner idle during human inspection. No paid provider calls by default.

Propose **120-minute maximum sessions**, normally requesting 30 minutes, with
no in-place extension. Propose an **80-hour monthly admission budget**. Reserve
the full lease before start, release unused time only after confirmed stop,
and refuse requests exceeding the available allowance. Reserve against both
UTC months if a session spans month-end. Include startup, shutdown, failures
and ambiguous intervals in accounting. Tagged AWS cost reporting and budget
alerts provide another check; neither admission accounting nor alerts guarantee
an absolute bill cap if shutdown enforcement fails. Resizing or higher recurring
spending needs a revised estimate and Manny's decision.

## Request path and permissions

The first protocol accepts an original `issues: opened` event on the private
control repo. The exact title is `Deploy Community Dictionaries to staging`.
The JSON body has only `schema: 1`, `commit`, `expected_staging` and
`lease_minutes`. SHAs are full, lowercase and nonzero; minutes are an integer
from 15 to the trusted policy limit, at most 120. No issue field selects an
instance, AWS role, executable, network or service name.

Verify the numeric repository/sender IDs, private status, protected default
ref and runner context. Read the immutable original event snapshot, not a
subsequent edited issue. Reject unknown/duplicate JSON fields, malformed
input and reruns. A later live coordinator also deduplicates request IDs.

The GitHub request identity needs Issues write and Actions read only on the
staging control repository. It cannot change the workflow, validator or
policy, or modify production control. The present GitHub tools can create
issues and read results, but cannot create a private repository or configure
the connection's scope. Those are one-time operator steps. A broad operator
connection proves event delivery only, not delegated isolation.

For live operation, GitHub OIDC trust is bound to the staging repo/ref. Its
role can invoke a fixed coordinator alias and the fixed, versioned staging
SSM document, and read scoped results. **Only the coordinator's role** may
start/stop the configured instance and mutate its state prefix. No role in
this path may create instances, change IAM/network policy or affect production.
The host reads only its own boot lease and cannot grant or extend one.

All lifecycle mutations, including expiry and explicit stop, go through the
**same coordinator with reserved concurrency one across versions**. Persist
state externally. An operator retains an independent AWS emergency-stop path,
after which automation reconciles state before further work.

AWS documents [function-wide concurrency limits](https://docs.aws.amazon.com/lambda/latest/api/API_PutFunctionConcurrency.html)
and [independent Scheduler invocations](https://docs.aws.amazon.com/lambda/latest/dg/with-eventbridge-scheduler.html).
Use reserved concurrency, not paid provisioned concurrency. Configure bounded
event age/retries and treat delayed or duplicate invocations as normal inputs.

## Lifecycle and interruption handling

The durable session records issue/request ID, unique lease ID, configured
instance, candidate/expected SHAs, policy/control revisions, run/attempt IDs,
created/deadline times, budget reservation, phase, SSM command IDs and receipt
locations. Retain terminal request records so a duplicate event cannot open
another lease after its original session closes.

| Phase | Required action/evidence |
| --- | --- |
| Admit | Validate source CI, candidate ancestry/eligible diff and expected installed SHA; refuse active/uncertain ownership; reserve budget |
| Arm | Persist lease/deadline and reservation before starting; verify watchdog and host enforcement configuration; failure permits no start |
| Start | Start the configured host once, retain the API result and poll through the coordinator for running state, SSM and app readiness |
| Boot guard | Before app/workers start, a root-owned unit reads the matching lease and arms local expiry; missing, expired or unavailable lease stops the host |
| Deploy | Submit the fixed staging SSM command once; save its ID immediately; verify the controller's terminal receipt and actual running SHA |
| Test | Run baseline and feature checks, verify SHA before/after, retain evidence externally; interactive inspection can use the remaining lease |
| Stop | Close, failure, cancellation or expiry requests bounded drain/shutdown; persist `stopping` before the API call; retain ownership until confirmed stopped |
| Close | Record actual stop, account for runtime, release unused reservation and ownership; unknown outcomes require reconciliation |

The periodic watchdog reads the **current** lease rather than replaying a raw
old per-session stop instruction. A delayed explicit stop must match the
active lease ID. Closed requests never reopen. Coordinator serialization
prevents an old stop from racing a newer start. API timeouts/unknown results
enter `recovery_required` and block new starts; an unreachable URL or green
GitHub run is not proof that EC2 stopped.

Normal close allows a short bounded drain. At expiry the independent
root-owned host timer enforces shutdown even if chat, GitHub or the coordinator
is unavailable. App users/processes cannot alter that timer. An interrupted
deployment is uncertain: next boot reconciles checkout, controller receipts
and maintenance state before serving or accepting a new deployment. Ordinary
stop preserves disk/database; fixture reset is a separate staging-only action.

Use explicit coordinator/API/poll timeouts. Watchdog delivery is not instant;
record deadline, stop request and actual stopped timestamps separately. Alert
the operator if watchdog heartbeats or stop confirmation are missing. Rehearse
loss of chat, GitHub, network, watchdog invocation and boot-lease access. The
host timer supplies the independent second enforcement path.

## Using the pilot for a change

1. Agree the user-visible acceptance criterion; implement, run CI and prepare
   an eligible code-only release descended from the baseline and reachable
   from application `main`. Install trusted-tool changes separately.
2. Codex opens the staging issue with candidate, expected staging SHA and
   bounded lease, then retrieves the receipt from the short control job.
   After setup acceptance, routine start/stop needs no repeated human click.
3. Sign in normally through the external HTTPS access gate. Baseline checks
   cover a private fixture dictionary, static/media delivery and denial to
   an unrelated account. The feature check distinguishes baseline from
   candidate. Keep mocked-provider, paid integration, linguistic and physical
   phone/microphone evidence separate.
4. Save the report externally and close the lease. For Manny's inspection,
   display the original deadline and keep within it. A later visit requests
   another bounded session, not an extension of the old one.
5. Prepare the report for the exact candidate and expected production SHA.
   During the pilot Manny retains laptop acceptance and the existing AWS
   production gate. Staging success alone never promotes a release.

## Implementation order and pass criteria

| Slice | Deliverable and acceptance | Current state |
| --- | --- | --- |
| 1 · Offline requests | Validator, private-workflow template, bounded examples, portable tests, truthful no-AWS receipt | Implemented; no live round trip claimed |
| 2 · GitHub rehearsal | Operator creates/connects private repo; Codex creates an issue from a fresh session and retrieves its new receipt; wrong identities/malformed requests fail | Needs one-time repository and restricted connection setup; no AWS resources |
| 3 · Lifecycle code | Coordinator, durable leases/budgets, boot timer, IAM/infrastructure templates and fake-clock/AWS tests | Next code slice |
| 4 · Infrastructure | Reviewed exact resources/permissions and quote; deploy coordinator/watchdog and stopped EC2; verify isolation and expiry | After slice 3 tests and operator resource review |
| 5 · Baseline/recovery | Same-commit install/login, controlled failed candidate restores baseline, then identical candidate succeeds; expiry works with chat absent | Requires live infrastructure and staging controller/browser support |
| 6 · Parallel pilot | Three consecutive eligible visible releases, independent sample checks by Manny, reliable shutdown and measured runtime/cost | Compare with laptop path before changing production policy |

Slice 1: [validator](../../ops/community_deploy/staging_request.py),
[control template/setup](../../ops/community_deploy/staging_control/README.md),
[tests](../../ops/community_deploy/tests/test_staging_request.py).
Its receipt explicitly disclaims AWS contact, deployment, source verification
and runtime reservation. Validation success cannot authorize a later live job.

Slice 3 must prove: no start before durable admission; old stop cannot affect
a newer lease; no double reservation for one issue; unavailable state/budget/
guard refuses a start; unknown stop blocks a new start; and expiry works without
GitHub/Codex. Cover duplicate delivery, same-commit requests, failed deploys,
deadline/month boundaries, restarts and recovery. Add staging support to the
existing controller with regression tests for laptop/AWS targets. Check the
whole candidate-to-production diff, not just staging's incremental diff.

Before provisioning, prepare the exact instance, subnet, role, state prefix,
coordinator alias, scheduler and SSM-document changes and itemised quote.
Verify policy denial against production resources, network isolation and the
hostname/TLS/browser access boundary. One-time setup also includes DNS,
browser credentials and AWS trust. Codex prepares the reviewable materials
before the operator creates resources or changes permissions.

## Evidence and later decisions

Record requests/failures, manual interventions, source/control/test revisions,
boot/test/stop durations, actual/reserved minutes, provider usage and tagged
monthly cost privately. Attribute laptop and real-phone acceptance separately
from automated results. Keep account IDs, credentials and community data out
of public source. Review the first invoice and three eligible releases against
the current path: missed defects, recovery, manual effort and turnaround.

Removing the laptop gate, delegating production, enabling paid providers or
raising recurring spending requires a separate concrete decision. Preparation,
local tests and the no-AWS rehearsal can proceed under Manny's instruction to
plan and begin implementation.
