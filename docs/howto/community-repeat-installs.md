# Repeated deployment requests

A laptop release can succeed and then be launched again by mistake. Previously
the second run refused the now-outdated starting SHA. The AWS acceptance helper
correctly refused to skip that newer failed run in favour of an older success.

The controller now recognizes a completed transition when HEAD is already the
requested target, rather than its different expected predecessor. It verifies
the checkout, origin, published-main ancestry, the original transition's
code-only paths, Django preflight and the running server's frozen release
identity. Laptop verification also requires its managed-server record. An
operator maintenance gate, dirty files, stopped/unmanaged server or mismatched
health still cause refusal. An unexpected HEAD is reported as `observed_before`.

A successful repeat returns `already_installed`, without draining work, changing
code, collecting static files or restarting services. It records:

| Field | Meaning |
| --- | --- |
| `commit` | Requested and verified running release |
| `previous` | Actual unchanged HEAD |
| `observed_before` | HEAD observed before verification |
| `expected_previous` | Starting SHA specified in the original request |
| `operation` | `verify_existing` |

The CLI exits successfully and prints **Already installed and verified** for
the laptop. Same-SHA bootstrap requests keep their existing install/restart
behaviour; they are not inferred to be successful without a running server.

The cloud helper accepts either the existing exact installed receipt or the
new exact verification receipt. It continues to require the latest successful
laptop run for the current private-control commit, the configured human's AWS
acceptance, and the existing freshness limit. It does not reuse an older green
run after a newer failure. Repeated AWS requests recognize the new receipt too.
The development journal records verification separately from a new installation
and does not count it as a failed install or infer a new installation time.

## One-time activation, separate from application installation

This changes infrastructure installed outside the app checkout. An ordinary
code-only application release must not copy these files or weaken its blocked
path checks. Finish the current laptop/AWS application release first: changing
the private-control commit between laptop proof and AWS acceptance invalidates
that proof.

After reviewing the source revision and its Linux/Windows controller tests:

1. With deployment workflows idle, update `cloud.py` and its matching `runner.py`
   in the private control repository from the reviewed source revision. The new
   helper accepts old installed receipts, so upgrade it before the host
   controllers can emit the new status. Keep host settings, release requests and
   human-acceptance checks intact.
2. Back up the installed laptop controller and export the reviewed `runner.py`
   to a candidate file **outside** the app checkout. Fetch/show the pinned
   revision; do not move the application's HEAD to obtain infrastructure files:

   ```text
   git -C APP_CHECKOUT fetch origin main
   git -C APP_CHECKOUT show REVIEWED_FULL_SHA:ops/community_deploy/runner.py > EXTERNAL_CANDIDATE_FILE
   ```

   Use the existing Windows Command Prompt or a byte-preserving download/export;
   older PowerShell output redirection can change file encoding. Verify that
   the export succeeded, compare it with the pinned source, and compile it with
   the host Python before replacing the existing controller. Preserve a backup
   and the existing path/configuration. No app server restart is required merely
   to replace this CLI controller while workflows are idle.
3. Apply the same reviewed controller-only replacement on AWS, retaining the
   existing root ownership and permissions of `/opt/clara-deploy/runner.py`.
   Use the existing administrator channel; do not recreate federation, download
   credentials or alter the instance role.
4. During the next normal laptop release, run the same request a second time.
   Require `already_installed`, unchanged server-session identity and healthy
   release identity. Check the app, then use the normal AWS acceptance workflow.

To roll back, restore the backed-up host controllers first. The new cloud helper
also accepts their existing installed receipts. Restore the previous private
helper only as a separate idle tooling change, then prepare a fresh request
with the actual installed baselines and run the laptop workflow again before
AWS acceptance. Changing the control commit invalidates the previous proof.
The app checkout, database, host configuration and stored media are unaffected by
the controller-file upgrade.

## Validation

Disposable real-Git/HTTP tests cover first install and bootstrap, repeat
verification without restart/drain, dirty/maintenance/stopped-server refusals,
a moved HEAD with an older server still running, blocked original transitions,
CLI success and exact laptop/AWS receipt binding. Cloud APIs remain mocked.

```bash
python -m unittest discover -s ops/community_deploy/tests -v
python -m unittest discover -s scripts/tests -v
```

These checks are not evidence that the installed laptop/AWS controller copies
have already been upgraded. Live activation remains an operator step.
