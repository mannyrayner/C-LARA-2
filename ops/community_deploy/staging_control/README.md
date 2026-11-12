# First staging request rehearsal

This template belongs in a **new private control repository**. Nothing in this
directory is an active application workflow. The validator has no AWS client,
network access code, deployment subprocess or spending permission.

1. Create `mannyrayner/clara-staging-control` with default branch `main` and
   Issues enabled. Restrict changes to its default branch and workflow files.
2. Copy `../staging_request.py` to the new repository root, this `.github/`
   directory to its root, and `policy.example.json` to `policy.json`.
3. Replace the policy's repository name and numeric repository ID with the
   actual values. Add only verified numeric sender IDs. Zero/empty placeholders
   deliberately fail. Do not add any AWS secrets, OIDC trust or production
   credentials for this dry run.
4. Connect an identity with Issues write and Actions read on this repository.
   Check its actual permissions: it must not edit the validator, policy or
   workflow, or modify the production control repository. A broader operator
   identity may demonstrate event delivery, but does not prove that isolation.
5. Review and install the files on `main`. Open a new issue with the exact title
   `Deploy Community Dictionaries to staging`. Use `request.example.json` for
   the body, replacing the two placeholders with real full lowercase Git SHAs.
   `lease_minutes` is an integer from 15 to the policy maximum, at most 120.
6. From a fresh assistant session, create the issue through the GitHub connector,
   locate the new workflow run, and read the JSON receipt from its validation
   job log or retained artifact. Record issue, run and attempt IDs privately.
7. Submit a separate malformed request and, through an independently available
   test identity, a request from an unlisted sender. Both must produce a refusal
   receipt. Edit/reopen must not trigger this workflow. Rerun attempts are refused;
   submit a new issue for another rehearsal.

`outcome: validated` proves only request format and event identity. The receipt
explicitly records that no AWS call, source-commit verification, deployment or
runtime reservation occurred. No field authorizes a later live job: that job
must independently verify the source, installed commit, eligible diff and lease.
No untrusted issue content is interpolated into shell commands or logs.

Run the local tests from the application repository root:

```bash
python -m unittest ops.community_deploy.tests.test_staging_request -v
```

The [on-demand plan](../../../docs/roadmap/community-dictionary-on-demand-staging.md)
describes the later coordinator, independent shutdown enforcement, runtime
accounting, infrastructure setup and pilot acceptance. Live deployment remains
unimplemented until those steps and the fresh-session request rehearsal pass.
