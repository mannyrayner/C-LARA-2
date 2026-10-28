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

These tests use local temporary repositories and HTTP servers. AWS/GitHub APIs are
mocked. Native Windows CI is configured but must actually run before its result
can be claimed. No test submits a real cloud deployment.
