# Deploying Community Dictionaries co-owners

Migration 0029 adds `co_owner` to the existing membership-role choices. It changes
Django's migration state, emits no database schema SQL and rewrites no dictionary
content. The installed controller still refuses migrations. Use the reviewed
one-time preparation below, then the usual code-only release workflow.

The preparation commit is `6500f47e4f55d064ee809c274f4587406fd5d586`. It adds the role,
a hash-pinned migration, a bounded preparation helper and recovery tests.
Co-owner assignment is disabled at this intermediate commit; the subsequent
feature release enables its guarded invitation and management controls.
No installed controller, IAM, SSM, workflow or dependency change is needed.

Both hosts' latest installation receipts identify
`d0241477e74cb003ba50753d8708b4a56a0ce31b`. Stop if the installed version differs.
The helper checks the exact installed release, a clean checkout, migration scope,
activity drain, service lifecycle and readiness. It verifies a SQLite backup
outside the checkout. Failure restores previous code when possible without
reversing migrations; uncertain recovery retains maintenance mode.

## Laptop first

In Cygwin, with the existing Actions runner available:

```bash
cd /home/github/c-lara-2
git fetch origin &&
git show 6500f47e4f55d064ee809c274f4587406fd5d586:ops/community_deploy/prepare_coowner_schema.py > ../clara-deploy/prepare_coowner_schema.py &&
./.venv/Scripts/python.exe -E ../clara-deploy/prepare_coowner_schema.py \
  --controller ../clara-deploy/bin/runner.py \
  --config ../clara-deploy/laptop.json \
  --expected d0241477e74cb003ba50753d8708b4a56a0ce31b \
  --commit 6500f47e4f55d064ee809c274f4587406fd5d586
```

After `status: prepared`, start a **new**
[Install Community Dictionaries on laptop](https://github.com/mannyrayner/clara-deployment-control/actions/workflows/laptop.yml)
run on **main**. Do not rerun an old release or start a second development server.
The release request expects the preparation commit and installs the following
feature commit.

Check **People → Invite an account → Co-owner**, or change an existing member's
role to **Co-owner**. Accept a new invitation from that account, confirm Settings,
Tools and **Download this dictionary and its media** work, then remove the role
and confirm download access is blocked. The original owner's account retains
control. Existing member/editor/coordinator access and individual contribution
control should still work. See [co-owner permissions](community-coowners.md).

## AWS after laptop acceptance

In the AWS terminal:

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git fetch origin &&
git show 6500f47e4f55d064ee809c274f4587406fd5d586:ops/community_deploy/prepare_coowner_schema.py > /var/lib/clara-deploy/prepare_coowner_schema.py &&
/usr/bin/python3 /var/lib/clara-deploy/prepare_coowner_schema.py \
  --controller /opt/clara-deploy/runner.py \
  --config /etc/clara-deploy.json \
  --expected d0241477e74cb003ba50753d8708b4a56a0ce31b \
  --commit 6500f47e4f55d064ee809c274f4587406fd5d586
```

After `prepared`, run a **new**
[Accept laptop and deploy AWS](https://github.com/mannyrayner/clara-deployment-control/actions/workflows/aws.yml)
workflow on **main**, retaining the successful laptop run and exact release
request. Check browsing and co-owner export there too.

Receipts are stored as `coowner-schema-receipt.json` in the configured controller
state directory. Inspect the reported recovery status and private log before a
retry. After successful preparation, the installed version is the preparation
commit, so do not repeat a command claiming the preceding release is installed.
