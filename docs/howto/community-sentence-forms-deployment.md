# Deploying sentence forms

Migration 0027 adds `form` to the existing contribution-kind choices. It changes
Django's migration state, emits no database schema SQL, and does not rewrite
dictionary data. The installed deployment controller still rejects migration
files, so this release uses the same explicit preparation / code-only installation
sequence as learning preferences. No controller, IAM, SSM or dependency changes
are required.

The reviewed preparation commit is
`d0e8b043645841046ede4fffa864135dcdb5ff2c`. It contains the model choice, the
hash-pinned migration, the bounded preparation helper and its tests. The helper
checks the exact installed release, clean checkout, migration scope, running
activity, service lifecycle and readiness. It verifies a SQLite backup outside
the checkout. On failure it attempts to restore the preceding code without
reversing migrations; an unverified recovery retains maintenance mode.

Both hosts were last accepted at
`b43a76cff201139f6a9a0975a4f20dab58fa1522`. Stop if the installed version differs;
do not substitute an unverified expected commit.

## Laptop first

In Cygwin, with the existing Actions runner available:

```bash
cd /home/github/c-lara-2
git fetch origin &&
git show d0e8b043645841046ede4fffa864135dcdb5ff2c:ops/community_deploy/prepare_forms_schema.py > ../clara-deploy/prepare_forms_schema.py &&
./.venv/Scripts/python.exe -E ../clara-deploy/prepare_forms_schema.py \
  --controller ../clara-deploy/bin/runner.py \
  --config ../clara-deploy/laptop.json \
  --expected b43a76cff201139f6a9a0975a4f20dab58fa1522 \
  --commit d0e8b043645841046ede4fffa864135dcdb5ff2c
```

Expect `status: prepared`. Then start a **new**
[Install Community Dictionaries on laptop](https://github.com/mannyrayner/clara-deployment-control/actions/workflows/laptop.yml)
run on **main**. Do not rerun an old release workflow or start another development
server. The control request installs the subsequent feature commit and expects
the preparation commit on each host.

Follow the [acceptance checks](community-sentence-forms.md). In a dictionary already
using guided pictures, renew that personal mode in Settings to accept the updated
estimate for the additional audio. Check existing manual and writing flows too.

## AWS after laptop acceptance

In the AWS terminal:

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git fetch origin &&
git show d0e8b043645841046ede4fffa864135dcdb5ff2c:ops/community_deploy/prepare_forms_schema.py > /var/lib/clara-deploy/prepare_forms_schema.py &&
/usr/bin/python3 /var/lib/clara-deploy/prepare_forms_schema.py \
  --controller /opt/clara-deploy/runner.py \
  --config /etc/clara-deploy.json \
  --expected b43a76cff201139f6a9a0975a4f20dab58fa1522 \
  --commit d0e8b043645841046ede4fffa864135dcdb5ff2c
```

After `prepared`, run a **new**
[Accept laptop and deploy AWS](https://github.com/mannyrayner/clara-deployment-control/actions/workflows/aws.yml)
workflow on **main**, using the successful laptop run as usual. It verifies and
deploys that exact accepted feature commit. Check readiness and browse on a phone.

The static collector must continue to run as its configured identity, `ssm-user`,
with write access to `platform_server/staticfiles`. The previous deployment's
ownership correction should already satisfy this; do not change unrelated files
or run a different manual collector as another identity.

Receipts are kept in the configured state directory, including
`forms-schema-receipt.json`. If preparation fails, use its reported recovery status
and private log before retrying. A retry after successful preparation must not
claim that the old feature release is still installed.
