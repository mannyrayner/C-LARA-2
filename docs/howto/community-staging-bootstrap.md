# Create and rehearse on-demand Community Dictionaries staging

**Prepared 16 November 2026; not provisioned or activated.** This is the operator
runbook for the [bootstrap specification](../roadmap/community-dictionary-aws-staging-bootstrap.md).
The generator makes code bundles and CloudFormation templates without contacting
AWS. The live workflow is a template, not an installed workflow. Keep the existing
production approval process throughout this pilot.

## Review boundary and proposed resources

The next human step is a read-only AWS/GitHub preflight, followed by review of the
actual account-specific CloudFormation change sets. Execution, DNS changes and
live IAM/workflow activation are separate operator actions. Do not paste keys,
passwords, credential files or secret values into chat or GitHub issues.

| Item | Proposed value |
| --- | --- |
| Region | Sydney, `ap-southeast-2` |
| Host | Ubuntu 24.04 x86_64, `t3.small`, Standard CPU credits, normally stopped |
| Disk | 24 GiB encrypted gp3; retained on termination |
| Network | New VPC `10.77.0.0/24`; public subnet; no production routes, peering, SSH, NAT, load balancer or new RDS |
| Address | One retained Elastic IP; `c-lara-2-staging.c-lara.org` |
| Database | Local PostgreSQL 18, staging-only database/user and generated password |
| Credentials/data | Independent Django secret, HTTP gate and two synthetic users; invented private dictionary/image/tone; no production copy or provider keys |
| Coordinator | One Lambda, reserved concurrency 1; `live` and `watchdog` aliases share its published version |
| Shutdown | Independent minute Scheduler plus root boot/expiry guard; instance-initiated shutdown is stop |
| Limits | Default request 30 minutes; 15–120 allowed; original deadline cannot extend; monthly admission allowance 80 hours |
| Alerts | Confirmed email subscription; watchdog errors/missing invocations; USD 10 monthly tagged-budget alerts |

Only fixed staging resources appear in the generated IAM policies. The routine
GitHub role can invoke the `live` alias and read its own browser-fixture secret
and metadata; it cannot start EC2, send SSM commands, edit state, invoke the
watchdog alias, provision resources or operate production. The host cannot write
the lifecycle state. The coordinator cannot provision resources or reconcile/reset
state. Both aliases reject weighted routing. Live admission checks their actual
version, serialization, recent independent heartbeat, instance tags/shutdown
behaviour, exact guarded HTTPS SHA, source/main ancestry, eligible diff and latest
successful push/main CI for the candidate.

### Cost checkpoint

Recheck regional rates and the account's existing free allowances before execution.
At the AWS Sydney Linux on-demand rate read on 16 November 2026, `t3.small` is
USD 0.0264/hour. Five to ten hours/week is about USD 0.57–1.14/month. Keeping the
IPv4 address costs USD 0.005/hour, approximately USD 3.65 for 730 hours even while
stopped. Allow USD 3/month for the 24 GiB disk pending a regional EBS quote,
USD 0.40 for one secret, and USD 1 for two alarms, small logs, object/API usage
and transfer. The resulting planning allowance is **about USD 8.60–9.20/month**,
before tax/currency conversion; it is an estimate, not a billing cap.

The conservative allowances plus the full 80-hour runtime admission ceiling total
about USD 10.16. The USD 10 budget sends alerts; it does not prevent this or other
overshoot. Bootstrap, manual maintenance, retained resources and failed/unknown
operations can add cost. Do not silently raise the budget or machine size. Confirm
the actual quote and accept this distinction before provisioning. EBS, IPv4,
Secrets Manager and retained state/artifacts continue to cost money while off.
State history expires after seven days, while current replay-protection state is
retained. Evidence expires after 30 days. No always-running Actions inspection job
is used. No provider spend is enabled in this initial fixture.

Rate sources: [EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/),
[AWS Sydney Linux price feed](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/Asia%20Pacific%20%28Sydney%29/Linux/index.json),
[EBS](https://aws.amazon.com/ebs/pricing/), [IPv4](https://aws.amazon.com/vpc/pricing/),
[Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/).

## 1. Read-only preflight and source baseline

Use an operator's AWS CloudShell/session in the intended account. Record account,
region and outputs privately. No long-lived AWS key needs to be given to Codex.

```bash
aws sts get-caller-identity
aws lambda get-account-settings --region ap-southeast-2
aws ec2 describe-instance-types --region ap-southeast-2 --instance-types t3.small
aws iam list-open-id-connect-providers
aws ec2 describe-images --region ap-southeast-2 --owners 099720109477 \
  --filters Name=name,Values='ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*' \
            Name=state,Values=available Name=architecture,Values=x86_64 \
  --query 'sort_by(Images,&CreationDate)[-3:].[ImageId,Name,CreationDate]'
```

Verify the chosen AMI is Canonical Ubuntu 24.04, its root-device mapping, and SSM
Agent installation. Confirm quota permits concurrency 1 while leaving AWS's
required unreserved capacity. Verify the GitHub OIDC provider and thumbprint
through the account's normal process; do not create a second provider blindly.
Check current production PostgreSQL/Python versions read-only. PostgreSQL 18 is
the proposed matching major; resolve a mismatch before creating the host. Confirm
the new VPC range does not conflict with intended future networks. Confirm domain
control and use the existing DNS zone; do not create a paid extra hosted zone.

The source PR must be reviewed and merged, with green **push/main CI**, before
selecting baseline B. B must contain `staging_settings`, the seed/health code and
all reviewed bootstrap tools. The old pre-bootstrap baseline does not contain
them. The existing code-only production controller deliberately rejects ops,
dependency and schema changes: this PR is not an ordinary app install request.
Any trusted controller/baseline advancement is an explicit operator operation;
this runbook does not advance production or weaken its filter.

Verify `mannyrayner/clara-staging-control` is private (numeric repo ID
1459683099), and that main protection is actually enforced for the request
workflow. Verify a restricted requester connection and an independent refused
unlisted-sender test. The successful fresh-session dry run proved reachability
with the setup/operator connection, not permission isolation. Do not activate
the live template until these checks are resolved. Never give the routine
requester a broad AWS token as a workaround.

## 2. Build and inspect the exact bundle

From a clean checkout of the reviewed source revision:

```bash
python ops/community_deploy/package_staging.py --output ../clara-staging-bundle
python -m unittest discover -s ops/community_deploy/tests -v
cfn-lint --region ap-southeast-2 --template \
  ../clara-staging-bundle/host.cfn.json ../clara-staging-bundle/runtime.cfn.json
```

The bundle has `manifest.json`, deterministic `runtime.zip` and `host-tools.zip`,
CloudFormation JSON, private-control files under `control/`, and operator tools
under `operator/`. `--allow-dirty-for-validation` produces a visibly unreviewed
validation bundle; **never provision from it**. Store the reviewed source SHA,
manifest and ZIP hashes alongside the change-set evidence. Check no credential
or real learner content appears in the bundle. Install `cfn-lint` in a separate
tooling environment if needed; validation used version 1.60.1.

Create one new staging-only artifact bucket using the AWS console's private,
AES256-encrypted, versioned settings and `ClaraEnvironment=staging` tag, or a
separately reviewed equivalent. This is an operator action. Retain only the
reviewed code bundles under the manifest's content-addressed keys. Use those
exact keys for uploads; do not overwrite an existing key with different bytes.
Upload both ZIPs, and retain the manifest/templates privately.

## 3. Host change set: inspect, then execute separately

Set shell variables to the reviewed values (no passwords): `STAGING_AMI`,
`STAGING_ARTIFACT_BUCKET`, and `STAGING_BUNDLE` (bundle directory). Then:

```bash
aws cloudformation validate-template --region ap-southeast-2 \
  --template-body "file://$STAGING_BUNDLE/host.cfn.json"
aws cloudformation create-change-set --region ap-southeast-2 \
  --stack-name clara-community-staging-host --change-set-name initial-host \
  --change-set-type CREATE --template-body "file://$STAGING_BUNDLE/host.cfn.json" \
  --capabilities CAPABILITY_IAM \
  --parameters "ParameterKey=AmiId,ParameterValue=$STAGING_AMI" \
               "ParameterKey=ArtifactBucket,ParameterValue=$STAGING_ARTIFACT_BUCKET" \
  --tags Key=ClaraEnvironment,Value=staging
aws cloudformation describe-change-set --region ap-southeast-2 \
  --stack-name clara-community-staging-host --change-set-name initial-host
```

Review additions, IAM, disk retention, EIP and network boundaries before a
separate `execute-change-set` operation. No production resource may appear.
After execution, the initial boot installs OS packages/PostgreSQL/SSM and stops.
Its temporary 30-minute timer also bounds subsequent manual setup boots.
Confirm **stopped** in EC2, inspect cloud-init/SSM OS-preparation evidence, and
confirm the `os-ready` flag before application bootstrap. Failure to prepare
means fix the setup; it is not permission to disable the timer.

Save `describe-stacks --stack-name clara-community-staging-host` as
`host-outputs.json`. Create the staging DNS A record pointing at its `PublicIp`;
verify public resolution before issuing the certificate. No SSH port is opened.

## 4. Runtime change set, still disabled

Prepare `runtime-parameters.json` in the private operator workspace, using the
manifest for these values:

| Parameter | Value |
| --- | --- |
| ArtifactBucket | New staging artifact bucket |
| RuntimeCodeKey | `runtime_code_key` from manifest |
| RuntimeZipSha256 | `runtime_zip_sha256_base64` |
| GuardRevision, PolicyRevision | Full reviewed bundle source SHA |
| GuardSha256 | `guard_sha256` |
| ControlRepositoryId | `1459683099` after identity verification |
| AllowedSenderIds | Verified numeric GitHub IDs, comma separated; setup identity is not proof of a restricted requester |
| AdminEmail | Operator's confirmed alert address |
| EnableLive | `false` |

Use AWS CLI's usual array of `ParameterKey`/`ParameterValue` objects. Other
parameters have staging-only defaults; review them, especially the hostname and
imported host stack name. Validate `runtime.cfn.json`, then create and inspect a
CREATE change set for `clara-community-staging-runtime`, with `CAPABILITY_IAM`,
`--parameters file://runtime-parameters.json`, and the staging tag. Execute only
after review. Save its `describe-stacks` output as `runtime-outputs.json`.

The function and minute schedule remain disabled. Confirm the SNS subscription
email and activate the `ClaraEnvironment` cost-allocation tag if needed; budget
filtering does not work retroactively. Inspect policies/CloudTrail and the
fixed `CLARA-DeployStaging` document/version. Register the instance with its
restricted role; if registration fails, diagnose actual missing actions before
expanding it. Do not attach a broad managed instance/admin policy by default.

## 5. Bounded application bootstrap and create-only state

Run the bundle's operator generator locally/in CloudShell:

```bash
python "$STAGING_BUNDLE/operator/staging_operator.py" \
  --manifest "$STAGING_BUNDLE/manifest.json" --host-outputs host-outputs.json \
  --runtime-outputs runtime-outputs.json --baseline "$STAGING_BASELINE" \
  --admin-email "$STAGING_ADMIN_EMAIL" --artifact-bucket "$STAGING_ARTIFACT_BUCKET" \
  --output ./staging-operator-private
```

It makes `bootstrap-config.json` and `bootstrap-ssm-parameters.json` without AWS
calls or secret values. Inspect both. Set `STAGING_INSTANCE` to the host output's
exact instance ID, verify its staging tags, manually start **that instance**,
wait for SSM Online, then send one operator bootstrap command:

```bash
aws ssm send-command --region ap-southeast-2 --document-name AWS-RunShellScript \
  --instance-ids "$STAGING_INSTANCE" \
  --parameters file://staging-operator-private/bootstrap-ssm-parameters.json \
  --comment 'One-time reviewed staging bootstrap'
```

Retain the command ID before polling. Do not replay an uncertain command. The
script downloads/verifies the host ZIP, installs root-owned tools outside the
checkout and a dedicated SDK venv, clones B, creates the empty local database,
migrates, seeds the private synthetic fixture, captures email locally, collects
static assets, sets up HTTP authentication and ACME TLS, and installs the boot
guard and two actual app/worker units. It writes a sanitized bootstrap receipt
to its own bucket and powers off on success or failure. Provider credentials,
real dictionaries, production settings and database backups are not copied.

Once confirmed stopped, inspect the receipt, local config/permissions, TLS and
package/service versions through the operator path. Apply **only to this host**
the verified `ClaraGuardRevision` and `ClaraGuardSha256` EC2 tags from the manifest.
Then initialize state once:

```bash
python "$STAGING_BUNDLE/operator/staging_initialize.py" \
  --config staging-operator-private/bootstrap-config.json
```

This checks source CI, stopped host, tags and bootstrap receipt. S3 creation uses
`IfNoneMatch=*`: existing/missing/corrupt state is never reset by a routine job.
An initialization refusal needs diagnosis, not an overwrite. The host role cannot
perform this initialization. Keep the original receipt/state version privately.

## 6. Enable only after the isolation checks, then rehearse

Install the reviewed `control/` contents on protected private main without
replacing its existing no-AWS evidence. Set repository variables:
`STAGING_REQUESTER_ROLE`, `STAGING_LIVE_ALIAS`, `STAGING_HOSTNAME`,
`STAGING_CREDENTIAL_SECRET`, `STAGING_STATE_BUCKET`, from verified outputs.
The workflow assumes a short OIDC session, uses pinned actions, and takes no
resource ID/command/credential from the issue. Review its installation separately;
this source PR does not install it.

After all preflight checks, make/review an UPDATE change set with `EnableLive=true`
and the same reviewed code/hash/configuration. It publishes a new function
version for the enabled configuration, moves both aliases together and enables
the minute schedule. Changing any runtime configuration later requires a new
reviewed policy/source revision and corresponding version publication. Confirm
actual recent watchdog heartbeat, alias versions, alarms and concurrency before
opening a session. A missing heartbeat refuses admission.

Submit B with expected B through the original validated issue format, initially
for 30 minutes. Read the receipt and browser report. The normal job stops the
host immediately after tests; the operator may temporarily set the private
repository variable `STAGING_KEEP_OPEN=true` (or use CLI `--keep-open`) to retain a
successful inspection session until the **original** deadline, with no idle
Actions job. Prove owner login, private entry/image/audio, static assets, outside
page, unrelated-account denial and exact SHA. Also inspect once interactively.
An automated browser report alone is not human acceptance or audible speech
quality assessment. The fixture audio is a labeled synthetic tone.

Then execute the [controlled B/C recovery and expiry checks](../roadmap/community-dictionary-aws-staging-bootstrap.md#4-prove-the-browser-checks-and-recovery).
Choose C as an eligible wording change on green main. The root-only fault helper
is installed outside the checkout. During a successful B inspection lease, arm
it via the operator's SSM path for **that C only**:

```bash
/opt/clara-staging-guard/bin/python /opt/clara-staging-deploy/staging_fault.py --arm FULL_C_SHA
```

The marker expires in ten minutes and is atomically consumed on C's next service
start. B's recovery start bypasses it. The routine request interface cannot arm
it. Restore `STAGING_KEEP_OPEN` to false, close B using the coordinator's `close`
action and B's exact lease ID through the operator path, confirm stopped, and
submit C within ten minutes of arming. If setup takes longer, re-arm through a
new bounded B inspection session after the expired marker is removed by the
operator. Preserve failed-candidate/recovered-B evidence; then request the same C
normally and prove the wording change. Do not add a fault flag to issues.

Rehearse deadline expiry, Scheduler failure, root guard failure/exit, stopped-host
restart without a valid lease, stale/duplicate requests and uncertain SSM/EC2
outcomes. Observe actual EC2 stopped, not merely API acceptance. Offline tests
cannot establish IAM, poweroff latency, DNS/TLS, SSM or browser acceptance.

## Operation, certificate renewal and recovery

The routine job's finally path requests close and confirms stop. Cancellation or
network loss is covered by the independent Scheduler and local original deadline.
Budget reservation/actual accounting includes startup through observed stop; an
unknown mutation retains ownership and blocks another session. Inspect the
**original issue/lease**, SSM command ID/history, CloudTrail, state versions,
checkout, maintenance marker and receipt. A single stopped observation does not
resolve a potentially late start/stop. There is no automated reset/reconcile API.
An operator must record the evidence and a reviewed state repair if required.

Certificates age while the host is off. Check expiry before the first rehearsal
and periodically thereafter. Renew through the operator path within a bounded
valid lease, using `certbot renew --non-interactive` and `nginx -t`/reload; if HTTPS
readiness fails due to expiry, an operator can renew via SSM while the already
bounded starting lease is active. No routine admission bypass is needed. Prove
this maintenance path before relying on the server long term. A scheduled
certificate-maintenance automation is not activated by this runbook.

For an emergency, suspend new requests/disable the schedule through operator
access and **stop only the tagged staging instance**, then verify stopped and
preserve state/history. Do not terminate it, delete the database, alter production
or reopen a lease to make an error disappear. A previously accepted unknown call
may still complete; continue reconciliation. Alerting is an additional signal,
not a replacement for the host shutdown guard.

For teardown, first disable the workflow/schedule and confirm stopped, then
review backups/evidence and the exact retained resources. CloudFormation retains
the host/disk, EIP, state bucket and secret; deleting stacks alone does not stop
their costs and can fail while retained resources still reference network/IAM
objects. Inventory and remove retained resources deliberately, with a separate
operator cleanup decision. Release the EIP and delete unwanted volumes/secret/
objects only after that decision. Do not perform destructive cleanup implicitly.

Record change sets, verified identities, costs, receipts, browser results,
interventions and acceptance in the private development journal. Begin the
parallel staging pilot only after the baseline, recovery, expiry and restricted
requester tests pass. Moving production approval from laptop/human to staging
requires the later pilot decision.
