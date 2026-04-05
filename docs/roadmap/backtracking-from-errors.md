# Backtracking from errors

This document records major project backtracking decisions, why they were made, and what baseline we reset to. The goal is to keep recovery actions explicit and auditable.

## Incident log

### 2026-04-05: Roll back `main` to pre-report baseline

**Summary**
- We observed that `main` contained inconsistent state after report-related changes.
- The affected changes were intentionally abandoned rather than repaired in place.

**Actions taken**
- `git switch main`
- `git branch backup/broken-main-after-report`
- `git reset --hard pre-report-state`
- `git push --force-with-lease origin main`

**Decision**
1. `main` is reset to the known-good pre-report state.
2. Report-related changes are abandoned.
3. We do not recover, merge, or reintroduce those abandoned changes.
4. New work starts from current `main` (or fresh branches created from it).

**Operational rule going forward**
- Before starting work: `git fetch origin && git switch main && git pull --ff-only origin main`.
- Create fresh task branches from that tip.
- If another rollback is needed, log it here using the same format.

---

## Template for future incidents

### YYYY-MM-DD: <short incident title>

**Summary**
- <what went wrong and symptoms>

**Actions taken**
- `<command 1>`
- `<command 2>`

**Decision**
1. <decision point 1>
2. <decision point 2>

**Operational rule going forward**
- <short prevention/recovery rule>
