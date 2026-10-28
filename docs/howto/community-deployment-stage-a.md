# Community Dictionaries: deployment stage (1a)

Prepared 21 October 2026 against main `45a907f47477894075bd48d2731823ff27715cb2`.
Initial implementation, not yet accepted on Manny's Windows laptop or AWS.

## What this adds

For an eligible release: install a specified commit on the laptop, restart the local server,
check startup/database access, ask Manny to try the feature, and deploy the **same commit** to
AWS after his acceptance. The source remains in C-LARA-2. A separate **private** GitHub
repository holds the release request and deployment controls.

This first version handles code/static-file releases only. It refuses changed migrations,
dependency manifests and deployment/workflow/instrumentation files, pending migrations, model changes needing
migrations, unexpected installed commits and dirty checkouts. It installs no packages and
performs no migrations or data restores. The author must additionally confirm that the change
is compatible with existing data and job formats and with a return to the previous code.

The gate applies to both Community Dictionaries and ordinary C-LARA-2 on this server.
Optional activity tracking covers HTTP requests, the bounded local Django-Q adapter (including
waiting tasks), and the project-understanding worker. Do not run manual management jobs or
another deployment concurrently. Other schedulers or external workers need their own drain
integration before using this procedure. The controller waits up to 120 seconds for activity;
it refuses a busy installation instead of killing paid work.

**Not included:** automated feature acceptance, AWS staging, schema/dependency releases,
continuous monitoring, or autonomous permission changes. No provider requests are made by
the controller or its tests. Existing user jobs may of course continue using providers while
the controller waits for them.

## A. Apply and test on the laptop

Stop your manually started development server with Ctrl-C. Keep this patch separate from any
uncommitted localisation work in the other thread. From Cygwin:

```bash
cd /home/github/c-lara-2
git status --short
git rev-parse HEAD
```

If there are local changes, preserve and finish them first. Do not reset them. The commands
below assume the patch is saved beside the repository and `git apply --check` succeeds.

```bash
git apply --check ../community_deployment_stage_a.patch &&
git apply --index ../community_deployment_stage_a.patch
git diff --cached --check
./.venv/Scripts/python.exe -E -m unittest discover -s ops/community_deploy/tests -v
```

Then:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py makemigrations --check --dry-run &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_admin_tools
```

No database migration is introduced. With `CLARA_DEPLOY_ACTIVITY_DIR` unset, the installed app
continues to behave normally, and the new readiness URL returns 404. Start it using your
usual command and check it before enabling deployment mode.

If the checks pass, review the staged diff, commit and push using the usual process. There
must be no other staged work in this commit unless deliberately included:

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git commit -m "Add supervised deployment controller and AI collaboration draft"
git push
git rev-parse HEAD
```

Record that full commit. The initial infrastructure patch itself is a **manual installation**;
the new controller deliberately cannot replace its own policy automatically.

## B. Prepare the laptop controller once

After committing, stop the manually started server. Prepare a NEW external directory:

```bash
cd /home/github/c-lara-2
./.venv/Scripts/python.exe -E ops/community_deploy/bootstrap.py \
  --destination "$(cygpath -w /home/github/clara-deploy)"
```

This creates only local files. It does not register a runner or contact AWS. The result is:

- `clara-deploy/bin/runner.py`: installed controller;
- `clara-deploy/laptop.json`: host configuration, including the existing native Python;
- `clara-deploy/state` and `activity`: private logs, server state and activity leases;
- `clara-deploy/control`: files for the private GitHub control repository.

Inspect `laptop.json`. The repository, native Python and Git paths must be correct. Port 8000
must be free. The controller supplies the activity environment variable to its managed server;
there is no need to change tracked Django settings or store API keys in this file.

For the first local rehearsal, set both SHA arguments below to the full installed commit
printed above. Using the same SHA rehearses startup without changing the code:

```bash
./.venv/Scripts/python.exe -E ../clara-deploy/bin/runner.py install \
  --config ../clara-deploy/laptop.json \
  --commit YOUR_FULL_INSTALLED_COMMIT \
  --expected YOUR_FULL_INSTALLED_COMMIT \
  --receipt ../clara-deploy/state/first-receipt.json
```

Expected: `status: installed`. Open `http://127.0.0.1:8000/community-dictionaries/` and try the
normal workflow. Readiness should also show the installed commit at
`http://127.0.0.1:8000/community-dictionaries/deployment-health/`.

Do not also launch a second `runserver`. The supervisor retains the managed server after the
installation command ends. To stop it deliberately, create an empty file named `stop` in the
session directory identified by `state/server.json`, then wait for that directory's `exited`
file. Logs are in that directory's `server.log`. Never kill a guessed PID.

## C. Connect the private control repository

Create a private repository, for example `mannyrayner/clara-deployment-control`, and place the
contents of `clara-deploy/control` at its root on branch `main`. Include the `.github` directory.
Do not put host configs, logs, credentials or activity files there. Restrict write access to
trusted deployment operators. Do not enable pull-request workflows or register the laptop
runner against the public C-LARA-2 repository.

In the private repository's Settings → Actions → Runners, add a Windows x64 self-hosted runner
with the extra label `clara-laptop`, following GitHub's generated instructions. Register it
under Manny's existing user account, outside either checkout. Initially run it interactively
from an environment with the same application variables as the normal local server. Do not
run it as LocalSystem. If launching its `run.cmd` from Cygwin, use `cmd.exe /c run.cmd` from its
directory. Verify that Git, native Python and the necessary app variables are available to
that process. Keep this terminal and laptop available during deployments. A Windows service
can be considered after the interactive rehearsal works.

Set these non-secret repository variables (Settings → Secrets and variables → Actions → Variables):

| Variable | Value |
|---|---|
| `CLARA_PYTHON` | Full Windows path to `c-lara-2\.venv\Scripts\python.exe` |
| `CLARA_CONTROLLER` | Full Windows path to `clara-deploy\bin\runner.py` |
| `CLARA_CONFIG` | Full Windows path to `clara-deploy\laptop.json` |
| `HUMAN_APPROVER` | `mannyrayner`, or the exact agreed GitHub login |

Use native Windows paths as printed by the bootstrap. No app secret goes in these variables.
A self-hosted runner gives its trusted workflows the privileges of its user; this is a
powerful connection, not a sandbox. Ordinary collaborators should not get control-repository
write access merely to contribute to a dictionary.

Edit `current_release.json` in the private repository. Supply full 40-character SHAs for
`commit`, `expected_laptop` and `expected_aws`; describe the change and leave
`rollback_compatible: true` only after checking compatibility. Empty example fields are
intentionally invalid. Commit the request on private `main`.

The **Install Community Dictionaries on laptop** workflow is a manual action. It runs the
installed controller and uploads a content-free receipt. Once an authorised connection to
this private repository is available to the assistant, the assistant can initiate this
workflow and read its result. This patch does not itself establish that connector permission.
For the initial rehearsal, Manny can click Actions → workflow → Run workflow → `main`.

## D. Bootstrap AWS once, after laptop acceptance

This section is a one-time operator setup, not the routine release procedure. Use the existing
SSM login and `clara_manage` wrapper. Check that AWS's checkout is clean, then deploy the
committed infrastructure patch through the established manual code-update procedure. There
are no new migrations or dependencies in this patch. Allow current jobs to finish before
restarting all three services: older processes do not yet provide activity leases.

As an administrator on AWS, install the controller and non-secret policy files:

```bash
sudo install -d -m 755 /opt/clara-deploy
sudo install -m 644 /srv/C-LARA-2/ops/community_deploy/runner.py /opt/clara-deploy/runner.py
sudo install -m 755 /srv/C-LARA-2/ops/community_deploy/services.sh /opt/clara-deploy/services.sh
sudo install -m 644 /srv/C-LARA-2/ops/community_deploy/aws.example.json /etc/clara-deploy.json
sudo install -d -o ssm-user -g ssm-user -m 700 /var/lib/clara-deploy
sudo install -d -o ssm-user -g www-data -m 2770 /var/lib/clara-deploy-activity
```

Keep `/opt/clara-deploy` and `/etc/clara-deploy.json` root-owned. Inspect the JSON: its settings
match the previously reported server, but verify before use. The application checks run as
`ubuntu:www-data`; `collectstatic` runs as `ssm-user`, matching the reported ownership of
`staticfiles`. The installed `ssm-user` already used sudo in the existing runbook. Confirm its
non-interactive sudo access for the fixed commands; do not add a new blanket sudo grant.

Using `sudoedit /etc/clara2.env`, add this non-secret line once, preserving everything else:

```text
CLARA_DEPLOY_ACTIVITY_DIR=/var/lib/clara-deploy-activity
```

All three units must load this same environment file. Verify their `EnvironmentFile` settings
without displaying the contents of the file. Then, during the agreed quiet period:

```bash
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
clara_manage community_deployment_check \
  --activity-dir /var/lib/clara-deploy-activity --backend postgresql
clara_manage community_queue_check --tasks 20
```

Keep the bounded local queue: `USE_REAL_DJANGO_Q=False` is intentional here. This patch does
not require switching to real Django Q. Open the HTTPS readiness URL and confirm its release
matches `git rev-parse HEAD`; check the normal app too. Do not continue if preflight fails.

The controller's `systemd-run` commands use `/etc/clara2.env` without printing it. Transient
checks have their own time limits. Nginx is not restarted by routine code deployment.

### Connect AWS without a stored AWS access key

Use an existing AWS administrator account to configure this once:

1. Confirm the EC2 instance is an online managed node in Systems Manager; record its region,
   account ID and instance ID. Use the existing instance role/agent if already configured.
2. In the private repository, run **Show AWS trust identity (setup only)** on `main`. It prints
   only the token's audience, subject, repository and branch, never the token. Check repository
   and branch. Use the exact printed subject in the trust template; do not guess its format.
3. Configure GitHub's OIDC provider in IAM if absent, with audience `sts.amazonaws.com`. Create
   a dedicated role using `aws-trust.example.json`, replacing the account and exact subject.
4. Attach `aws-policy.example.json` after replacing region, account and instance placeholders.
   It permits sending this fixed document to this one instance and reading command results.
   It grants no permission to create documents, alter IAM, or run arbitrary SSM documents.
5. Create the Systems Manager **Command** document named `CLARA-DeployCode` from
   `aws-ssm-document.json`, as version **1**. Inspect its fixed controller path and command.
   Updating the document or controller later is a separate operator task; the workflow pins
   version 1.
6. Set private repository variables `CLARA_AWS_ROLE` (role ARN), `CLARA_AWS_REGION`, and
   `CLARA_INSTANCE_ID`.

These templates do not provision resources themselves. No credentials should be pasted into
a conversation, committed, or included in receipts. An administrator should inspect the
concrete identifiers before applying the templates. The existing EC2 role still needs its
usual Systems Manager permissions. This is not a request to rotate existing app secrets.

## E. The steady-state procedure

The AI prepares and tests the release, arranges the reviewed source commit on public `main`,
and prepares the private release request with exact installed SHAs. Existing GitHub CI should
be green; controller startup checks do not replace software tests. The controller enforces
commit ancestry and local checks but does not query CI conclusions.

1. **Install on laptop:** dispatch the private laptop workflow. It fetches the source, verifies
   the request, pauses new activity, drains work, installs, collects static files, restarts
   and checks release identity. The workflow reports the result.
2. **Human checks:** Manny tries the requested change. If unsatisfactory, do not deploy AWS.
   Prepare a correction or deliberately return to an earlier version through an operator
   procedure; a successful startup receipt is not an acceptance verdict.
3. **Accept and deploy AWS:** Manny runs **Accept laptop and deploy AWS**, on private `main`.
   This explicit action is his acceptance. The workflow requires the configured human login,
   the latest successful laptop run for the same private-control commit, its matching receipt
   and an age under 24 hours. It sends the fixed SSM command and reports the outcome.

Do not edit the private request between the laptop run and AWS acceptance. If a second laptop
run fails, the AWS workflow will not fall back to an older successful run. Requests older than
24 hours need a newly prepared request and laptop run; set expected SHAs to what is actually
installed. After any successful laptop installation, `expected_laptop` for the *next* request
must be the newly installed SHA, not its predecessor.

The first complete rehearsal can deploy the already installed infrastructure commit to both
machines with matching expected SHAs. Then rehearse a small visible code-only change and
acceptance. Rehearse recovery using a disposable local test installation, not a deliberately
broken public deployment. Only after those checks should routine changes use this route.

GitHub identity checks assume trusted control-repository writers. They cannot distinguish a
human click from software using that person's credentials. The assistant must not initiate
the acceptance workflow without Manny's explicit acceptance of that release. Required-reviewer
features are not assumed: their availability for private repositories depends on GitHub plan.

## F. Failures and recovery

The receipt reports `installed`, `refused`, `recovered_previous_release`, or `recovery_required`.

- **Refused:** inspect the reason. Dirty files, wrong installed versions and busy/stale leases
  are not corrected by deleting or resetting material automatically.
- **Recovered:** the old code was restarted and passed readiness. The requested release was
  not installed; diagnose before trying another release.
- **Recovery required:** maintenance remains active. Inspect host receipt/log and services,
  resolve the specific failure, restart and verify the intended version before removing the
  maintenance file. Never erase the gate simply to obtain a green workflow result.

On AWS, inspect `/var/lib/clara-deploy/result.json` and `install-*.log` as `ssm-user`. On the
laptop, inspect the corresponding `state` files. Raw logs are not uploaded to GitHub and may
contain sensitive diagnostics; share only the relevant redacted portion.

A controller crash may leave `install.lock` or leases. Check the recorded process and running
services/tasks before removing anything. A lease is not safe to remove merely because it is
old. The controller never deletes stale leases or terminates an unknown process automatically.
If the connection fails after SSM submission, `aws-receipt.json` records the command ID when
available. Inspect that invocation in Systems Manager before retrying. A failure during the
submission itself can have an uncertain outcome too: inspect recent commands on the instance.
Do not assume a network timeout means nothing ran. The workflow does not retry submissions.

Code recovery does not erase new user content. Normal database/media backups remain necessary,
but this code-only procedure does not create a multi-gigabyte media archive during every update.
There is a short maintenance window and failed startup can lengthen it; this is not zero-downtime
deployment. Supervision and staging are later stages.

## Evidence and references

See `experiments/community_dictionary/deployment-stage-a-2026-10-21.md` for the actual checks
performed. Linux simulations are not evidence of an AWS deployment or native Windows success.
GitHub-hosted Windows/Linux controller tests are added to CI; no public workflow uses the
private laptop runner.

Relevant official documentation, consulted during preparation:

- [GitHub self-hosted runners](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)
- [GitHub deployment protection availability](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
- [GitHub OpenID Connect](https://docs.github.com/en/actions/concepts/security/openid-connect)
- [AWS Systems Manager Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html)
