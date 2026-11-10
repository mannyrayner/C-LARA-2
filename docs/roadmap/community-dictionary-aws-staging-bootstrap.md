# Community Dictionaries staging bootstrap

**Status** · Proposed implementation details, 10 November 2026

This specification covers phase A of the [AWS staging plan](community-dictionary-aws-staging.md).
It ends with a staging deployment that Codex can request and test from a fresh
session, and a demonstrated return to the previous release after a controlled
failure. Manny is the proposed AWS and DNS operator for the one-time setup.
The live release process continues to use the [Stage 1a runbook](../howto/community-deployment-stage-a.md)
during this phase.

## 1. Verify the request path before creating AWS resources

Create a private control repository, proposed name `clara-staging-control`.
Use the existing GitHub issue-creation capability to request deployments.
A workflow on the repository’s protected default branch listens for
`issues: opened`. In the first version, its only job is to validate a request
and publish a dry-run receipt. This tests whether the connector can actually
start a workflow without a manual dispatch.

| Setting | Proposed value |
| --- | --- |
| Request identity | Dedicated staging connection with Issues write and Actions read on this repository, plus the minimum read permissions required by the connector |
| Request title | `Deploy Community Dictionaries to staging` |
| Request body | A JSON object with exactly `schema` (integer `1`), `commit` and `expected_staging` (full lowercase Git SHAs) |
| Request identifier | Repository ID and issue number from the event, with run ID and run attempt recorded separately |
| Trusted code | Workflow and validators from the protected default branch. The project’s C-LARA-2 repository is the fixed release source |

Check the repository ID, sender ID and event action before processing the
request. Allowlist the verified connector sender. Validate the original
event snapshot from `GITHUB_EVENT_PATH`; parse the body as data and pass
validated values as arguments. Pin workflow actions to reviewed commit SHAs.
The request identity must be unable to edit the workflow, its allowlist, or
the private production control repository. Verify the permissions of the
actual connection. An issue submitted using a broadly privileged identity
can demonstrate event delivery but cannot demonstrate isolation.

For a same-commit rehearsal the issue body has this shape, with both values
replaced by the recorded baseline SHA:

```json
{
  "schema": 1,
  "commit": "0000000000000000000000000000000000000000",
  "expected_staging": "0000000000000000000000000000000000000000"
}
```

**Pass** · From a fresh session, Codex opens a valid request and retrieves
the receipt. Malformed requests and requests from an unlisted sender stop
before any privileged job. Editing or reopening the issue does not deploy
anything. If a suitable staging-only identity cannot be connected, Manny
can run a staging-only manual dispatch for rehearsal. Fresh-session
deployment remains an open acceptance item until the delegated trigger works.

See [GitHub issue events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#issues)
and [GitHub’s guidance on treating event input as data](https://docs.github.com/en/actions/concepts/security/script-injections).

## 2. Provision one small host

| Item | Proposed starting value |
| --- | --- |
| Region and host | Sydney (`ap-southeast-2`), Linux x86-64 on-demand `t3.small`, Standard CPU credits, encrypted 24 GiB gp3 root disk |
| DNS and TLS | `c-lara-2-staging.c-lara.org` on a staging Elastic IP, with its own certificate and HTTPS virtual host |
| Network | Staging-only VPC and security group with no route to production private networks. Public ingress on TCP 443 and TCP 80 for redirect and certificate validation. Operator access via Systems Manager |
| Database | Local PostgreSQL bound to loopback, with a separate database and non-superuser application role. Match production’s PostgreSQL major version after an operator verifies it |
| App and services | `/srv/C-LARA-2-staging` and its own virtualenv. Nginx, Gunicorn, bounded local Django queue, and project-understanding worker, each with staging configuration and state |
| Data and mail | Synthetic fixture data and private media. Django file-based mail capture in a restricted staging directory. Start with password-reset email disabled and provider credentials absent |

Budget about **US$25/month** for compute, disk and one public IPv4 address
at 730 hours, before taxes, transfer, or snapshots. Ask Manny to verify
the AWS quote and approve a **US$35/month pilot budget** before launching.
Tag the resources for cost tracking and set a budget alert. An alert is
a notification, so the operator should also be able to stop the instance
and disable the staging trigger. Resize only after measuring memory
and CPU during bootstrapping and the smoke suite, and agreeing the
revised estimate.

Compare the [Sydney instance rate](https://www.doit.com/compute/compute/aws/ap-southeast-2/t3.small),
[Sydney gp3 rate](https://aws-pricing.com/ap-southeast-2.html) and
[AWS public IPv4 pricing](https://aws.amazon.com/vpc/pricing/).

The operator records the current production SHA and the relevant platform
versions, then selects a verified baseline SHA **B** on application
`main`. Install matching runtime dependencies, migrate the empty staging
database at B, load the fixtures, collect static files, and start the staging
services. Use local PostgreSQL, staged media paths and independent Django
credentials in the staging settings. Keep the hostname allowlist explicit,
set secure session and CSRF cookies, and use a trusted proxy header for the
external HTTPS scheme. The instance role needs Systems Manager registration
and the staging resources explicitly configured for the pilot.

Protect the staging vhost with an HTTPS access gate, initially Nginx HTTP
authentication, then use the ordinary Django sign-in. Put the staging-only
credentials in the runner’s secret storage and use the approved private
credential path for the interactive browser. Disable public registration and
keep the gate in front of static assets and media. Check the access gate
from a fresh browser early, including whether it can accept credentials
without exposing them. Headless CI must pass the same gate. Strip the gate’s
Authorization header at the proxy before forwarding requests to Django.
Serve the existing readiness route through a loopback-only Nginx listener
for the controller. The browser suite can read that route through the gated
HTTPS vhost. Both routes must reach the same Gunicorn service.

**Pass** · The host answers with B over both readiness routes. An unauthenticated
browser is challenged, and the signed-in browser and runner reach the app.
Verify that staging database, media, queue and mail paths resolve only to
staging resources. Check that the host has no route to production’s private
database and has no production secrets or resource grants.

## 3. Connect the existing release controller

Prepare the staging support and tests in the application repository. Install
the reviewed controller, wrapper and config separately on the host. Give
the controller an explicit `staging` target using the existing AWS service
lifecycle and PostgreSQL checks, including the initial readiness check before
it drains activity. Keep the clean checkout, ancestry and changed-path
checks, maintenance gate, activity leases, lock and code recovery. The public
templates can use placeholders for instance and role IDs.

Configure OIDC for the staging control repository and protected ref. Grant
the Actions role permission to run only the staging document on the staging
instance. The workflow pins a version of that document, proposed name
`CLARA-DeployStaging`. The document passes two validated SHAs to the
installed controller using fixed paths.
Permit the read operations needed to retrieve command results. Test the IAM
policy against both the staging and production targets and documents. Restrict
the workflow’s AWS credentials to the deploy job. The browser job receives
staging browser credentials and the validated receipt.

Use one workflow concurrency group across install and browser tests. Submit
the SSM command once, with the issue and run IDs in its comment and receipt.
Record the command ID as soon as it is returned. Preserve the host’s terminal
receipt even on a nonzero command exit, including `recovered_previous_release`
and `recovery_required`. Verify its target, requested and previous SHA,
and terminal status before classifying the attempt. On a polling timeout or
interruption, reconcile the issue with SSM command history and the host state.
A rerun must check that history before it can submit a command.

**Pass** · Local controller tests cover staging success, a wrong expected SHA,
and recovery. Policy evaluation allows only the intended document and target.
From the same request path proved in step 1, request B with expected B.
The receipt reports `target: staging` and `status: installed`, the services
return, and the HTTPS readiness route still reports B.

## 4. Prove the browser checks and recovery

Seed one private dictionary with an invented entry, a small generated test
image and a short synthetic audio clip. Seed a dictionary owner and an
unrelated signed-in account. Provide the fixture identifier and credentials
to the test runner through staging configuration, with a repeatable seed
and reset procedure.

Use a small Chromium browser suite on the trusted runner. It checks the
running SHA at the start and end, signs in normally, opens the fixture,
loads the image, exercises the audio response, and checks the unrelated
account is denied the dictionary and its media. It also loads a read-only
C-LARA-2 page outside Community Dictionaries. Verify the fixture once
interactively from Codex. Keep the pass/fail results and browser version
in the report. Redact credentials and keep full traces off by default.

Choose a reviewed wording change **C** on application `main`, descended
from B and eligible for the code-only controller. A small copy edit on
the Community Dictionaries About page is a candidate. Agree on the old
and new text before deployment. Check the old text is visible and the
new text assertion fails on B.

| Attempt | Expected observation |
| --- | --- |
| Install B with expected B | Install passes, and the baseline browser suite and old-text assertion pass |
| Install C with expected B, with a controlled fault | A staging-only operator hook fails the service start once after the checkout moves to C. The controller restores B, and the old-text check and baseline suite pass again |
| Install the same C with expected B, after confirming the hook is disarmed | Install passes, the running SHA is C, and both the baseline suite and new-text assertion pass |

Implement the fault in a trusted staging service wrapper using a one-use,
expiring marker for the exact candidate SHA. Manny arms it through the
staging operator path. The request interface accepts only the two SHAs and
the schema version. The restored B must bypass the hook, and a recovered
attempt is recorded as a failed deployment even when B is healthy.

**Pass** · Codex supplies the three receipts and browser reports, identifies
the restored baseline after the fault, and shows that the successful
rehearsal installed the same C that failed under injection. Record every
intervention and its owner in the private development journal. Manny can
then decide whether to begin the parallel staging pilot.

## Operator handoff

Manny’s first decision is whether to set up the dedicated private GitHub
repository and verify a staging-only identity for the dry run. Once that
works, the next handoff is an AWS estimate, hostname, and exact provisioning
change set for review. Codex prepares the controller patch, fixture and
browser tests, and reads the resulting evidence. Manny retains the staging
operator access needed to suspend the workflow, stop the instance, or
resolve an uncertain recovery.

Prepare three reviewable changes in this order:

1. Private staging control repository. Add the issue validator and dry-run
   workflow with tests for rejected input and sender identity.
2. Application repository. Add the staging target and host templates under
   [`ops/community_deploy/`](../../ops/community_deploy/README.md), with controller
   tests for both staging and existing targets. Prepare the host configuration
   and fixture setup alongside those templates.
3. Private staging control repository. Wire the live command and browser
   suite to the validated request. Record baseline, failure and changed-release
   results in the private journal.
