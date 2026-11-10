# AWS staging and supervised releases for Community Dictionaries

**Status** · Proposal for review, 10 November 2026

## Goal and starting point

Let Codex take a Community Dictionaries change from an agreed request through
installation and functional testing on AWS. Manny initially decides whether the
tested commit goes to production. Later, he can delegate a defined class of
releases if the pilot shows that Codex can detect failures, recover safely and
reduce his workload. Collaborator feedback can supply a real request and its
acceptance criterion. Release authority comes from the project’s deployment
policy.

The existing supervised path installs a specific commit on Manny’s laptop,
then installs the same commit on AWS after he accepts it. The controller already
checks the expected installed commit, refuses ineligible changes, drains
tracked activity, verifies startup and attempts to recover the previous code
if startup fails. A same-version rehearsal and a changed release have passed
with human acceptance. They establish a useful baseline for installation.
Staging adds an independently accessible AWS target and evidence from testing
the feature through the application.

See the [collaboration roadmap](community-dictionary-ai-led-collaboration.md),
[Stage 1a runbook](../howto/community-deployment-stage-a.md) and
[deployment rehearsal](../../experiments/community_dictionary/deployment-and-tools-2026-10-30.md).

## 1. Build a small, isolated AWS installation

Use a separate small EC2 instance and HTTPS hostname in the existing AWS account.
Run the regular C-LARA-2 Django application with Community Dictionaries as the
focus of the tests. Match production’s relevant Linux, Python, PostgreSQL,
Nginx, Gunicorn, and worker configuration. Record differences that could affect
the checks, including dependency versions, upload limits and timeouts. A
staging database on the staging host is a reasonable first option if its
PostgreSQL version and settings are representative. Use separate managed
PostgreSQL if a later test depends on RDS-specific behaviour.

| Component | Proposed staging setup |
| --- | --- |
| Runtime | Separate instance, checkout, services, queue, activity directory, and logs |
| Data | Staging-only database and role, private media storage, resettable synthetic dictionaries with small image and audio fixtures |
| Access | Dedicated staging identities for Codex and Manny, plus a restricted test user to check access boundaries. Verify authenticated browser access from a fresh session |
| Secrets | Staging-only Django key, database and storage credentials, and any external provider credentials. Keep them in host or runner secret storage |
| Side effects | Capture application email in a test mailbox. Use controlled provider responses for routine tests. Enable live providers only for named tests with an agreed call and spending limit |

Before enabling automated deployments, review what the staging host and both
deployment identities can reach. Check that the staging role can invoke the
fixed staging command and that policy evaluation denies the production command
and target. Check that the staging application has access only to staging
database, media, queue and delivery credentials. Seed test accounts and data
from a reproducible setup, with a reset procedure that is scoped to staging.
Record the expected monthly cost and who can stop the instance or disable the
trigger.

## 2. Reuse the controller and separate the release permissions

Use the existing GitHub Actions → AWS OIDC → Systems Manager pattern. Install
the controller and its configuration outside the application checkout. Give
staging its own explicit target in configuration and receipts. The controller
currently recognises `laptop` and `aws`. Add staging as a Linux target using
the same preflight, service management, expected-commit and recovery logic.
Use separate staging paths, service names and a readiness URL. Rehearse the
controller change on disposable checkouts before bootstrapping the host.

The staging trigger takes a release request ID, a full application commit SHA,
and the expected current staging SHA. Keep the source repository, services and
command parameters fixed in trusted configuration. The staging Actions role
should have short-lived credentials, a trust policy restricted to the trusted
control ref, permission to run a fixed version of the staging command on the
staging instance, and the read access needed for its command results. Use a
separate private staging control repository if the available trigger permission
applies to the whole repository. Keep the production workflow and its AWS role
under separate control. Verify the staging trigger from a fresh Codex session,
including retrieving a receipt. Access to read or rerun a previous workflow
does not establish the ability to start a new one.

Keep the controller’s forward ancestry and code eligibility checks for the
pilot. Stage a candidate already reachable from application `main`. If a
preview is ever tested before merge, rerun the checks on the actual merge
commit before offering it for promotion. Review the whole change between the
currently installed production commit and the candidate. A staging host may
already be ahead of production, so its own deployment diff can miss changes
that the production controller would have to install.

Use one staging release at a time through installation and browser verification.
Check the running commit before and after the browser test. If a connection
drops, look up the release request, workflow run and saved SSM command before
retrying. If the result is unknown, reconcile it with the controller’s receipt
and the host’s current state before submitting another command.

See the [controller](../../ops/community_deploy/runner.py),
[AWS workflow helper](../../ops/community_deploy/cloud.py),
[GitHub OIDC guidance](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
and [AWS command-scoping examples](https://docs.aws.amazon.com/systems-manager/latest/userguide/security_iam_id-based-policy-examples.html).

## 3. Test the installed application

Use a maintained browser smoke suite, supplemented by Codex’s interactive
inspection of the feature. Keep the baseline suite and its pass criteria under
reviewed control. For each release, write the feature-specific acceptance
criterion before deploying. A change to a test or its expected result needs
its own review when that test supplies evidence for release approval.

- **Baseline on every run.** Check the reported SHA and service readiness. Sign
  in with a staging test account, open a private fixture dictionary, load
  static assets and media, and verify the restricted user cannot access that
  dictionary. Check a read-only page outside Community Dictionaries because
  the application services also serve the wider C-LARA-2 platform.
- **Feature checks.** Use the normal UI and an appropriate role. For the first
  pilot, choose a small visible change and a check that fails on the baseline
  and passes on the candidate. Add image upload, audio playback, evaluation
  submission and worker completion checks as those workflows enter the pilot.
  Use a disposable fixture or reset fixture state between runs.
- **Provider and human checks.** A controlled provider response can verify
  that extraction runs and the UI displays the result. A bounded live run
  can check the deployed provider integration. Keep linguistic judgments,
  live-provider evidence and physical-phone microphone checks separate so
  the release review can see which claims each test supports.

Store the controller receipt and a short functional report privately. Record
the candidate and previous SHAs, run and attempt IDs, timestamps, staging
readiness result, fixture and test revisions, checks and outcomes, known
coverage gaps, and any provider usage. A controlled automated check should
record its own outcome. Label exploratory observations and human judgments
with their source. Keep credentials, test media and full browser traces out
of routine reports.

## 4. Promote with explicit approval and rehearse recovery

During the pilot, Codex deploys to staging, tests and prepares the release
summary. Manny independently reviews selected checks and initiates production
deployment through the established laptop acceptance workflow. Compare the
staging report with his findings. The laptop step can be retired for this
release class after a separate decision and after the production workflow can
verify staging evidence itself.

For the next supervised phase, change the production gate to require a
successful install receipt and passing functional report from the trusted
staging workflow, both for the exact requested SHA and run attempt. Also
require green source CI, an eligible diff from the expected production SHA,
and Manny’s approval bound to that release request. As a starting point, expire
evidence after 24 hours, matching the current laptop gate. A newer failure for
the release, a different candidate, or a changed production starting point
requires new evidence and approval. Fetch the recorded artifacts from the
trusted workflow, with the release summary serving as the human-readable view.
Verify the production SHA and run read-only smoke checks after deployment.

| Failure | Expected response |
| --- | --- |
| Ineligible diff, stale request, unexpected checkout or busy workers | Controller refuses the release. Inspect the specific cause and reconcile the installed SHA before preparing another request |
| Candidate fails to start | Controller attempts to restore the preceding code and verify readiness. Rehearse this on staging with a controlled fault and check that the failed candidate cannot be promoted |
| Staging starts but a functional check fails | Mark the release ineligible. Retain the failed report and repair the candidate or restore the staging baseline before continuing |
| Production starts but the smoke check fails | Pause further releases and use the operator recovery procedure. Before delegating production, rehearse a bounded rollback to the recorded prior commit, with its own expected-current check and post-rollback smoke test |
| Recovery fails or deployment state is uncertain | Halt automation and notify Manny or the named operator. Preserve receipts, keep maintenance in effect where the controller requires it, and resume after the operator verifies state |

Start with narrowly scoped, backward-compatible code and static-file changes.
Review compatibility with existing data and queued jobs. Schema changes,
dependencies, access policy, billing, deployment controls and infrastructure
need separate operator review. Code recovery uses the live database and media.
Rehearse backup restoration separately in a disposable environment before
delegating production, including checking that the restored database and
media agree.

## 5. Increase authority in stages

| Phase | Codex responsibility | Manny’s responsibility and evidence to advance |
| --- | --- | --- |
| A · Bootstrap and rehearse | Prepare infrastructure and control changes for review. Run the same-commit rehearsal, a changed release, and a controlled startup failure on staging | Authorise the one-time AWS setup and review the verified isolation, a fresh-session staging deployment, successful feature checks, and recovery |
| B · Run the pilot alongside the existing gate | Handle staging end to end and supply a release report. Investigate failures and record what needed human help | Retain laptop acceptance and initiate production. Compare a sample of the staging checks independently and record any missed defects |
| C · Supervised promotion from staging | Prepare promotion of the tested SHA and verify production after deployment | Approve the exact release in the production control path. Review evidence that routine releases and recovery work with staging as the acceptance environment |
| D · Delegate a limited class of production releases | Execute releases within a separately approved policy, monitor results, and stop or escalate on a failed or ambiguous check | Set and review the release policy, keep an independent way to pause deployment, and review exceptions and a sample of outcomes |

For the pilot, aim for three consecutive eligible releases after the first
rehearsal, with different user-visible checks. Include the controlled recovery
drill, evidence that failed or stale attempts are rejected by the proposed
promotion gate, and successful post-release checks. Three releases are an
initial review point. Advancing phases requires a separate decision and
resolved discrepancies between Codex’s and Manny’s findings. Scope the first
delegated class to presentation-only changes such as wording or styling.
Treat a production incident, unexpected privilege, or unexplained mismatch
between staging and production as a reason to pause and review the delegation.

Record all attempts in the private [development study
journal](../howto/community-development-log.md). Track manual interventions
and their reported minutes, turnaround, missed defects, failed installations,
recovery outcomes and provider cost. Compare these with comparable releases
through the existing laptop workflow. Count time spent by other collaborators
when a task moves to them.

## First implementation slice

1. Agree on the staging hostname, hosting cost, operator and staging-only
   trigger identity. Confirm the browser can reach the chosen access boundary.
2. Prepare the isolated host and fixtures, parameterise the reviewed
   controller for staging, and test the policy and receipt boundaries.
3. From a fresh session, request a same-commit staging install, retrieve the
   receipt, log in, and run the baseline browser checks.
4. Run a small visible release and the recovery drill on staging. Hand Manny
   the evidence for the visible release to review alongside the existing
   production process.

The proposal separates the initial infrastructure decision, the production
approval decision for each pilot release, and any later decision to delegate
production authority.
