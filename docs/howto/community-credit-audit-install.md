# Install the credit display correction and read-only audit

Patch: `community_dictionary_credit_audit.patch`.
Baseline: `9fd3d9d695467c13264e447908d96ff749be5625`
(`Bound workflow guidance queries and collapse redundant picture cards`).

This patch clarifies proposed, held and settled credit. It adds a diagnostic
command without changing balances, reservation amounts or settlement behavior.
No migrations, collectstatic, pip install or environment changes are needed.

## Laptop

Stop the development server. Save the patch beside the repository, and check
that the working tree is clean before applying it. If it is not clean, preserve
the changes and inspect them before continuing.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_credit_audit.patch &&
git apply --index ../community_dictionary_credit_audit.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary.tests.test_credit_audit community_dictionary.tests.test_porting community_dictionary.tests.test_port_vocabulary community_dictionary.tests.test_workflow_guidance
```

The focused suite has 82 tests. Deliberate mocked timeout/failure logs are normal;
the final result must be `OK`. Then optionally inspect the laptop account:

```bash
../.venv/Scripts/python.exe -E manage.py community_credit_audit --username 'YOUR_LOGIN_NAME'
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Replace `YOUR_LOGIN_NAME` with the exact login name. A laptop result does not
reconcile the separate AWS database. In the UI, an offered job should say
**Credit needed to start**; a completed job should show zero credit still held.
There is no need to buy an AI operation just to check the wording.

When satisfied:

```bash
cd /home/github/c-lara-2
git diff --cached --check
git diff --cached --stat
git status --short
git commit -m "Clarify Community Dictionary credit holds and add read-only audit"
git push
git rev-parse HEAD
```

## AWS

Allow any active AI requests to finish before the brief service restart; review
previews may remain pending. Do not cancel jobs just to run this audit.

```bash
sudo -iu ssm-user
umask 022
cd /srv/C-LARA-2
git branch --show-current
git status --short
git fetch origin
git log --oneline HEAD..origin/main
git rev-parse HEAD
```

Expect `main` and a clean tree. Keep the last printed SHA for rollback. Define
the normal helper if this shell does not already have it:

```bash
clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu \
    --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}
```

Then deploy:

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker
git merge --ff-only origin/main
clara_manage check
clara_manage migrate --check
```

If a command fails, stop and retain its output. If both checks pass:

```bash
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
clara_manage community_credit_audit --username 'YOUR_LOGIN_NAME'
```

Send the audit output. It contains credit amounts, job IDs and status counts;
no content or credentials. The app can remain online during the audit. In
particular, do not manually refund or cancel anything based solely on a large
number: we first need to distinguish a proposed allowance, a genuine unfinished
job hold, and a ledger discrepancy. See `community-credit-audit.md` for details.
