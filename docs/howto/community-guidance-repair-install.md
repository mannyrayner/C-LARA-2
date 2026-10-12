# Install the workflow-guidance performance and picture-card repair

Patch: `community_dictionary_guidance_repair.patch`.
Baseline: `dbeb9173d696a0f8574e95047dab61d3ef9a111e`
(`Guide incremental updates to dictionary language versions`).

**No database migration, collectstatic, dependency installation or environment
change is needed.** Existing content is preserved; no cleanup command is needed.
Normal backup arrangements should continue. There is no need to repeat the
large media backup or pay to regenerate existing French content.

For temporary relief before installation, turn off **Settings → Workflow
suggestions** in the dictionaries whose notices are expensive. Turn them on again
after the repair to check the new performance.

## Laptop

Stop the development server and save the patch beside the repository:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
```

Expect a clean tree containing the baseline above. Keep unrelated changes; do
not reset files merely to make the patch apply.

```bash
git apply --check ../community_dictionary_guidance_repair.patch &&
git apply --index ../community_dictionary_guidance_repair.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary projects.tests.test_email_reset projects.tests.test_admin_tools projects.tests.test_profile &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expected at this revision: **614 tests, OK**. The scaled regression deliberately
compares slow and repaired paths and prints query/timing measurements. Simulated
provider and mail failures also log messages; stop if the final result is not OK.

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Check normal navigation with guidance enabled, the existing cost/review prompts,
and the French dictionary's default Accepted picture view. All entries should
still expose the retained originals. The small laptop dictionary cannot establish
production performance, so the AWS check below is important.

## Check in

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat
git status --short
git commit -m "Bound workflow guidance queries and collapse redundant picture cards"
git push
git rev-parse HEAD
```

## AWS

Let any active AI jobs finish first. Use one shell for these blocks:

```bash
sudo -iu ssm-user
umask 022
cd /srv/C-LARA-2
git branch --show-current
git status --short
git fetch origin
git log --oneline HEAD..origin/main
git rev-parse origin/main
```

Expect main, a clean tree and the intended repair commit. Stop on unexpected
changes. Define the usual command that runs with the service's protected environment:

```bash
clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu \
    --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}
clara_manage check &&
clara_manage migrate --check
git rev-parse HEAD
```

Retain the pre-update SHA. Both apps share these services and will be briefly
unavailable during the next block:

```bash
sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git merge --ff-only origin/main &&
clara_manage check &&
clara_manage migrate --check &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker

sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD
```

Stop and retain the output if a command fails. No nginx restart or daemon-reload
is needed, and this patch has no static changes to collect.

## Production check

1. Enable workflow suggestions if temporarily disabled. Visit My dictionaries
   several times, then open Swedish and French. Compare ordinary navigation
   latency with the reported tens-of-seconds delay.
2. Open French → Pictures → Accepted. The previously converted sentences should
   still have their text, audio and word links. Redundant image-only cards with
   matching copy ancestry should now be absent.
3. All entries intentionally retains original records. If a blank card remains
   in Accepted, send its URL and the corresponding sentence URL; do not delete it.
4. Check that a real outstanding review/update still appears, and that refreshes
   start no job or charge. Existing completed translations need no regeneration.

If rollback is needed, stop services and revert only this code commit through
the usual repository workflow, then redeploy. No database restore/schema reversal
is appropriate for this repair. Disable guidance for temporary latency relief
and retain any error output for diagnosis.
