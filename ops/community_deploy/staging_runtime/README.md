# On-demand staging implementation

**Prepared for operator review, 16 November 2026; not provisioned or activated.**
The complete sequence, cost checkpoint, change-set review, bootstrap, recovery,
TLS maintenance and cleanup are in the
[operator runbook](../../../docs/howto/community-staging-bootstrap.md).
No application release installs these tools and the private workflow still uses
the existing no-AWS rehearsal.

| Component | Responsibility |
| --- | --- |
| `../staging_lifecycle.py` | Durable single session, original deadline, budget admission/actual accounting and retained terminal request IDs |
| `../staging_aws.py` | Fixed EC2/SSM resources, conditional S3 state, bounded SDK calls with one attempt |
| `../staging_source.py` | Fixed public main ancestry, complete eligible diff, latest exact push/main CI |
| `../staging_runtime_app.py` | Disabled-by-default handler, original-event validation, independently qualified watchdog, actual guard/readiness probes |
| `../staging_guard.py` | Root boot gate/expiry outside checkout, synchronized and elapsed clock, root-owned lease marker |
| `../staging_install.py` | Fixed SSM entry point rejecting delayed/obsolete commands |
| `../staging_job.py`, `../staging_browser.py` | Short trusted request/deploy/browser/stop job with private synthetic fixture |
| `../staging_bootstrap_host.py`, `../staging_initialize.py` | Operator-only host preparation and create-only state initialization |
| `../staging_fault.py` | Operator-only expiring one-use recovery fault for one candidate |
| `../package_staging.py`, `../staging_templates.py`, `../staging_operator.py` | Deterministic review bundles, disabled CloudFormation templates and private operator inputs; no AWS calls |

This directory contains host/service/nginx/SSM settings and the uninstalled live
workflow. App units bind to the root guard. The two actual services are Gunicorn
and the understanding worker; the initial bounded task queue uses its existing
in-process implementation. Example IAM/binding JSON from the earlier design is
illustrative; generated CloudFormation and the runbook are the integrated setup.

One Lambda function serializes both aliases with reserved concurrency one across
versions. Conditional writes also fence stale state, but do not serialize cloud
effects alone. Intent precedes mutations; unknown start/stop/SSM outcomes are
never retried blindly. They retain ownership and require operator reconciliation.
Duplicates cannot reopen or extend a request. Missing/corrupt state refuses
admission; there is no routine reset action.

The watchdog alone updates its heartbeat. The root guard checks the boot lease,
reconciled checkout, guard digest and synchronized clock, then enforces the earlier
of absolute and elapsed deadlines without subsequent cloud access. Root-owned
readiness metadata binds HTTPS to the original lease/deadline/revisions/hash.
Instance-initiated shutdown must be stop. Real stop/drain behaviour needs rehearsal.

Offline checks:

```bash
python -m unittest discover -s ops/community_deploy/tests -v
python ops/community_deploy/package_staging.py --output ../staging-bundle
cfn-lint --region ap-southeast-2 --template ../staging-bundle/host.cfn.json ../staging-bundle/runtime.cfn.json
```

Tests use fake cloud clients, clocks and disposable checkouts; no test calls AWS
or poweroff. Django tests exercise fixture repeatability and actual private
entry/media authorization. Live IAM isolation, SSM registration, Linux services,
DNS/TLS, browser acceptance and shutdown remain explicitly unproven. The
fresh-session dry run proved the setup connection's reachability, not a narrow
requester identity. Complete the runbook's preflight before activating anything.
