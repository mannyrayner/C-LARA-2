# Community dictionary: setup and testing

Status: bootstrap only. The app is not registered, there is no new route, and
there are no database migrations or functional tests to run yet.

- [Specification](../roadmap/community-dictionary.md)
- [App scaffold](../../platform_server/community_dictionary/README.md)
- [Experiment records](../../experiments/community_dictionary/README.md)
- [Existing platform setup](run-django-platform.md)
- [Existing server administration](server-admin-tasks.md)

## Apply the bootstrap patch

The patch was prepared against C-LARA-2 commit
`82bb185181acf0fa01958a19a3187f6ee8492f4f`. It only adds files, so it can also
apply to later revisions if none of those paths already exist.

Save `community_dictionary_bootstrap.patch` one directory above your checkout.
From the repository root, first check `git status --short` and preserve any
unrelated work before switching branches. Start from your intended up-to-date
base branch, then run:

```bash
git switch -c feature/community-dictionary-prototype
git apply --check ../community_dictionary_bootstrap.patch
git apply ../community_dictionary_bootstrap.patch
git status --short
```

Run the application command only if the check succeeds. If the feature branch
already exists, switch to it instead of creating it again. If Git says one of
the new files already exists, inspect that state instead of forcing the patch.

Stage only the bootstrap files, inspect the staged summary, then commit:

```bash
git add platform_server/community_dictionary docs/roadmap/community-dictionary.md docs/howto/community-dictionary.md experiments/community_dictionary
git diff --cached --check
git diff --cached --stat
git commit -m "Bootstrap community dictionary app and specification"
git push -u origin feature/community-dictionary-prototype
```

This does not require a database migration, server restart or deployment. The
feature branch can remain separate from `main` during prototype development.

## Preparation for implementation

Establish a dedicated Python environment and install the repository's
`requirements.txt` and `requirements-dev.txt`. Follow the existing platform
instructions and use a local SQLite test database and temporary media storage.
Do not point automated tests at the production database or media directory.

Record the base commit, environment, exact commands and results in the
[experiment records](../../experiments/community_dictionary/README.md).
Check the relevant existing account/community/dictionary behaviour before
changing it; distinguish pre-existing failures from regressions.

The root pytest configuration only collects `tests/`. Existing platform tests
are Django tests under `platform_server/projects/tests/`. The first functional
patch must therefore add an explicit CI step for the new app's Django tests;
an empty successful discovery in this scaffold would establish nothing.

## First functional patch

Replace this section with verified commands and concrete deployment instructions
when the implementation exists. That patch should include app registration,
routes, models and migrations, protected media handling, mobile pages, tests,
and a short phone-test checklist. The proposed URL is
`/community-dictionaries/`; it does not exist in this bootstrap.

The first phone trial should exercise picture contribution, a partnership request
for audio, a partner's recording, discussion and acceptance. Repeat in the
opposite direction, requesting a picture for an audio contribution. No AI keys
or services should be needed for either workflow.

Report the installed commit, device/browser, reproduction steps and relevant
output or screenshots. Real-device testing is still needed for recording,
camera permissions and interrupted uploads even when automated checks pass.
