# Deployment stage (1a): preparation evidence, 21 October 2026

Base: `45a907f47477894075bd48d2731823ff27715cb2` (main, Slovak localisation).
Prepared in an isolated worktree; no changes were made to the older carrier-language
worktree. No remote commit, workflow dispatch, cloud resource creation, live install,
message or paid provider request was performed.

## Scope

Standard-library controller; exact-commit requests; private control-repository
workflow templates; optional application activity leases and content-free readiness;
manual acceptance before AWS; code/static-only releases; recovery of preceding code.
No database migration, dependency update, new interface localisation or autonomous
functional acceptance. The initial patch and connection bootstrap need manual setup.

## Checks performed here

- 24 controller/protocol tests passed on Linux. They exercise real disposable Git
  repositories, temporary HTTP servers and the detached server supervisor. Cases
  include successful exact release, restart, bad health, failed static collection,
  interruption during restart, recovery, uncertain recovery retaining maintenance,
  dirty checkout preservation, wrong base/origin/ancestry, protected file changes,
  deployment locking and an active lease preventing progress.
- Cloud tests use mocked GitHub/AWS calls. They verify receipt/run matching, named
  acceptance identity, single submission, saved command ID on polling failure and
  rejection of a successful command that returns the wrong release identity.
- Bootstrap preparation/refusal to overwrite is tested. No runner is registered.
- Django regression run: 758 tests passed (`community_dictionary` plus
  `projects.tests.test_admin_tools`, including the initial 12 deployment tests).
  Runtime was approximately 186 seconds. Provider failure messages in that run
  come from intentional mocked failure tests, not real API traffic.
- After adding three further deployment cases and the per-command Git ownership
  allowance needed for AWS's different service user, all 15 focused deployment
  tests passed. These include maintenance admission for both apps, streaming-close
  cleanup, queued and running background leases, paused assistant-worker admission,
  frozen release identity, pending-migration refusal and opt-in behaviour.
- Django system checks and `makemigrations --check --dry-run` pass with no changes.
- Linux and Windows GitHub-hosted controller jobs were added to CI. They have not
  been run on GitHub in this preparation session.

## Remaining acceptance

Native Windows/Cygwin execution, runner environment inheritance and detached-server
survival across real GitHub Actions cleanup require the laptop rehearsal. AWS
requires verification of service environment, directory ownership, non-interactive
sudo, readiness, OIDC subject/role and the fixed SSM document. None is claimed tested
here. The readiness endpoint checks process release identity and SELECT 1; it does
not establish that a feature works or that every worker is healthy.

Manual or external jobs outside the instrumented request/queue/worker paths must not
run concurrently with deployment. Old processes must all be restarted during the
one-time bootstrap so they participate in activity tracking. The absence of schema
changes is not proof that arbitrary application changes are data-compatible; release
review remains responsible for that claim.

A first rehearsal should install the already-installed commit, then a small visible
change, preserving human acceptance. No destructive production failure drill is
proposed. Future evidence belongs in a subsequent record, not retrospectively here.
