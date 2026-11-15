# Supervised deployment, stage (1a)

Start with [the runbook](../../docs/howto/community-deployment-stage-a.md).
The broader discussion draft is
[AI-led collaboration](../../docs/roadmap/community-dictionary-ai-led-collaboration.md).

`bootstrap.py` prepares laptop files only. `runner.py` is installed outside the
application checkout. `control/` is a template for a **separate private** repository;
its workflows do not belong in the public source repository's `.github/workflows`.
AWS examples contain placeholders and require administrator setup and verification.

No credentials, app data, live deployment, paid calls or external messages are
included in this patch. Application activity tracking is disabled unless
`CLARA_DEPLOY_ACTIVITY_DIR` is explicitly configured.

Run disposable controller/recovery tests from the repository root:

```bash
python -m unittest discover -s ops/community_deploy/tests -v
```

[Repeated-request verification](../../docs/howto/community-repeat-installs.md)
recognizes an already installed and healthy target without restarting it. Its
controller/cloud-helper upgrade is separate from ordinary application releases.

These tests use local temporary repositories and HTTP servers. AWS/GitHub APIs are
mocked. Native Windows CI is configured but must actually run before its result
can be claimed. No test submits a real cloud deployment.

The [on-demand staging plan](../../docs/roadmap/community-dictionary-on-demand-staging.md)
and [dry-run control template](staging_control/README.md) describe the next
pilot. `staging_request.py` validates issue requests locally and produces a
truthfully labelled no-AWS receipt. Its workflow belongs only in a separate
private staging control repository. No production workflow or installed
controller is changed by that rehearsal.
