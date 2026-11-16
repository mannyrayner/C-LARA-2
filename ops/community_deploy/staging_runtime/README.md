# Staging lifecycle and expiry components

**Status: offline implementation, 16 November 2026.** These are reviewable
components and installation examples. They are not an activated AWS service or
a complete provisioning bundle. No application release installs these tools.

The private GitHub request/receipt path has passed a fresh-session no-AWS
rehearsal using the existing operator connection. Restricted requester access,
protected-main enforcement and an independent unlisted-sender live test remain
open. The private control workflow continues to run its original dry run only.

## Implemented components

| Component | Responsibility |
| --- | --- |
| `../staging_lifecycle.py` | One durable session, original deadline, monthly reservation/charges, command identity and retained terminal request IDs |
| `../staging_aws.py` | Conditional S3 state writes and fixed-instance EC2/SSM operations; no AWS client at import |
| `../staging_guard.py` | Root-owned boot gate and independent local expiry; matching lease, synchronized boot clock and reconciled checkout required |
| `../staging_install.py` | Fixed SSM entry point; rejects delayed commands for obsolete/expired leases |
| `../runner.py` | Explicit PostgreSQL/service-managed `staging` target with existing release/recovery safeguards |

The coordinator requires an independently supplied trusted release verifier.
A dry-run receipt never authorizes admission. Source verification and readiness
are mandatory integration interfaces, with no permissive default.

All lifecycle mutations must use **one Lambda function with reserved concurrency
one across all versions**. Conditional S3 writes are an additional stale-writer
fence, not a replacement for serialization of EC2/SSM effects. Configure SDK
clients with bounded connect/read timeouts and **one total attempt** for
mutations and state writes. An uncertain result must not be retried blindly.

Reservation and operation intent are persisted before a cloud mutation. Unknown
starts/stops retain ownership even when one later observation says stopped;
the original API might complete late. Operator reconciliation is required.
The routine path has no state-reset or reconciliation operation. Missing or
corrupt state blocks admission; initialise it only through reviewed bootstrap.

Duplicates never reopen a closed request or extend its deadline. Retention is
bounded and refuses admission when full, without deleting replay protection.
Reservations span both UTC months at a boundary. Actual charges conservatively
cover admission through confirmed stop, including startup and overshoot;
unused reservation is released only then. Runtime accounting is not a bill cap.
A stopped host with an unfinished installation blocks the next session until
the checkout is reconciled. Confirmed code recovery keeps the previous baseline
and records that candidate as a failed deployment.

The guard enforces the earlier of absolute time and elapsed time, without
further cloud reads. Linux uses `CLOCK_BOOTTIME` to include suspended time.
Reboot during installation is refused. Root systemd `ExecStopPost` requests
shutdown on guard exit, and each app/worker unit binds its lifetime to the
guard. Verify instance-initiated shutdown is **stop**, not terminate. Service
stop/drain limits and actual poweroff still need live rehearsal.

## Installation examples

All examples contain placeholders; actual identifiers/credentials belong in the
private operator setup. None is automatically installed or applied.

| File | Intended use |
| --- | --- |
| `lease.example.json` | Root-owned `/etc/clara-staging-lease.json`, protected from app writes |
| `clara-staging-lease.service` | Root boot gate; isolated trusted Python/SDK environment outside checkout |
| `app-lease.conf` | Drop-in on each of the three staging app/worker units only |
| `services.sh` | Fixed staging service set under `/opt/clara-staging-deploy/` |
| `ssm-document.json` | Reviewed version of `CLARA-DeployStaging` with internal generated `LeaseId` |
| `coordinator-policy.example.json` | Fixed instance/document/state object/log group permissions |
| `requester-policy.example.json` | GitHub role may invoke only the coordinator alias |
| `requester-trust.example.json` | OIDC trust bound to the private staging repo and `main` ref |
| `host-policy.example.json` | Own-lease read and minimal SSM registration/channel permissions |
| `bindings.example.json` | Review checklist, deliberately `live_enabled: false` |

The host policy omits parameter-store access. Verify actual SSM registration
and commands with this restricted role before changing it. Use a reviewed SDK
supporting conditional S3 `PutObject`.

## Remaining integration before provisioning

This slice supplies no externally callable Lambda handler. Complete and test:

1. Trusted original-event admission: verified repo/sender IDs and protected ref,
   source/main ancestry, green CI, eligible diff and actual baseline. Bind this
   verifier in trusted code, never to a boolean from an issue.
2. Guard probe: actual function-wide concurrency, enabled Scheduler target/alias,
   installed guard revision and shutdown setting. Check quota permits reserved
   concurrency one; AWS requires at least 100 units left unreserved.
3. Readiness probe: guarded host identity and SHA through the gated staging
   endpoint. Connect short jobs/browser evidence without holding Actions idle
   during human inspection.
4. Exact infrastructure change set, host/network/local PostgreSQL/DNS/TLS config,
   current itemised quote and reviewed initial-state bootstrap. The examples
   above are components of that bundle, not a complete stack.
5. Private fixture/browser suite and operator reconciliation procedure. Inspect
   API/SSM history and actual checkout after unknown operations; a single stopped
   observation does not resolve an uncertain start/stop request.

Then run the baseline, controlled recovery and expiry rehearsals in the
[bootstrap specification](../../../docs/roadmap/community-dictionary-aws-staging-bootstrap.md).
Offline tests establish no live IAM isolation, SSM registration, Linux service
installation, host poweroff or browser acceptance.

## Offline verification

```bash
python -m unittest discover -s ops/community_deploy/tests -v
```

Tests use fake clocks/cloud clients and disposable local Git checkouts. They
cover interruption/unknown operations, duplicate/stale requests, month-boundary
budgets, code recovery, missing guards/state, restarts, clock changes, shutdown
without later cloud access and stale internal SSM commands. No test calls AWS
or an operating-system poweroff command.

Primary AWS references checked during implementation:
[S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html),
[function-wide reserved concurrency](https://docs.aws.amazon.com/lambda/latest/api/API_PutFunctionConcurrency.html),
[instance-initiated shutdown](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_ChangingInstanceInitiatedShutdownBehavior.html).
