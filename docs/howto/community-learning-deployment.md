# One-time preparation for persistent learning settings

The guided-photo release needs two new tables: dictionary language level and
personal contribution preference/standing consent. Migration 0026 creates them;
it does not alter existing content. The current Actions/SSM installer remains
code-only and must not be used to cross this migration directly.

The release therefore has two commits. First prepare the schema at exact commit
`8ee6024719b73de9f702ce4dad2848ffee88a4a7` using the manual helper below. Then
run the usual laptop workflow, which installs the subsequent feature commit
recorded in the private control repository's `current_release.json`. Both expected
host commits in that request are the schema-preparation commit.

The helper uses the already installed, trusted controller and host configuration:
clean-checkout and exact-head checks, fetch/ancestry checks, maintenance admission
control, active-job draining, service stop/restart and readiness checks. It accepts
only the reviewed migration's hash and two CreateModel operations; other pending
migrations or infrastructure/dependency changes stop it. It makes and verifies a
SQLite backup outside the checkout. PostgreSQL performs the two-table migration
transactionally. It neither archives media nor modifies existing content.

On a preparation failure after stopping, it attempts to restart the preceding
code with any newly added tables retained. It never reverses this migration. If
recovery cannot be verified, maintenance stays on and the receipt says
`recovery_required`; inspect the private log path printed by the helper.

## Laptop: prepare once

Run in **Cygwin**, using the existing native Windows virtual environment. Do not
start a second manual development server or a second Actions runner. The helper
stops and restarts the server managed by the existing controller.

The expected laptop release here is the writing-practice release that Manny
reported testing, `863e401bf1dec9dfb59f730976f56fb88699ff96`. If the controller
reports a different installed commit, stop and reconcile it rather than replacing
this expectation with a guess.

```bash
cd /home/github/c-lara-2

git fetch origin &&
git show 8ee6024719b73de9f702ce4dad2848ffee88a4a7:ops/community_deploy/prepare_learning_schema.py > ../clara-deploy/prepare_learning_schema.py &&
./.venv/Scripts/python.exe -E ../clara-deploy/prepare_learning_schema.py \
  --controller ../clara-deploy/bin/runner.py \
  --config ../clara-deploy/laptop.json \
  --expected 863e401bf1dec9dfb59f730976f56fb88699ff96 \
  --commit 8ee6024719b73de9f702ce4dad2848ffee88a4a7
```

Expect a JSON receipt with `status: prepared`. The app should still browse
normally; the new guided UI is in the following feature commit. The receipt is
`learning-schema-receipt.json` in the configured deployment state directory, and
the verified laptop backup is in its `backups` subdirectory.

Now start a **new** [Install Community Dictionaries on laptop](https://github.com/mannyrayner/clara-deployment-control/actions/workflows/laptop.yml)
workflow on **main**. Do not rerun an older release workflow. Test the
[guided-picture sequence](community-guided-pictures.md) and writing practice.
The feature-only diff from the preparation commit passes the existing controller
path restrictions; no migration is run by Actions.

## AWS: only after laptop acceptance

AWS was last confirmed at the Tools release
`48ad6c3866ba7e633a3f91da3a44a85c1c3cc50f`. The manual preparation below also
brings in the previously laptop-tested writing code on its way to the schema
commit. Schedule the short restart normally; the helper refuses a dirty checkout
or an unexpected installed release.

In the AWS SSH/SSM terminal:

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022

git fetch origin &&
git show 8ee6024719b73de9f702ce4dad2848ffee88a4a7:ops/community_deploy/prepare_learning_schema.py > /var/lib/clara-deploy/prepare_learning_schema.py &&
/usr/bin/python3 /var/lib/clara-deploy/prepare_learning_schema.py \
  --controller /opt/clara-deploy/runner.py \
  --config /etc/clara-deploy.json \
  --expected 48ad6c3866ba7e633a3f91da3a44a85c1c3cc50f \
  --commit 8ee6024719b73de9f702ce4dad2848ffee88a4a7
```

Expect `status: prepared` and normal browsing. Then use **Accept laptop and deploy
AWS** on main to install exactly the feature release accepted on the laptop.
The usual laptop receipt check remains required. Confirm the public health
release matches the feature commit and perform the main flow on a phone.

No IAM, SSM document, Actions permission, installed controller or dependency
changes are part of this preparation. Keep the preparation receipt and laptop
backup. Later code-only updates continue through the existing workflows.
