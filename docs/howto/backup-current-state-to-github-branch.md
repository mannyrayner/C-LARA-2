# Back up current work to a GitHub branch

This guide shows how to create a **backup branch on GitHub** from your current local state, so you can safely revert later if needed.

## When to use this

Use this before risky changes (large refactors, migrations, prompt overhauls), or whenever you want a restore point.

## Quick version

```bash
# from repo root
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
BACKUP_BRANCH="backup/${CURRENT_BRANCH}-$(date -u +%Y-%m-%d-%H%M)"

git status
git add -A
git commit -m "WIP backup before risky change" || true

git branch "$BACKUP_BRANCH"
git push -u origin "$BACKUP_BRANCH"
```

After this, your snapshot is stored on GitHub under that branch name.

---

## Step-by-step (recommended)

### 1) Confirm you are in the right repo/branch

```bash
pwd
git rev-parse --show-toplevel
git branch --show-current
```

### 2) Check what is uncommitted

```bash
git status
```

If there are changes you want in the backup, commit them first:

```bash
git add -A
git commit -m "Backup snapshot before <short reason>"
```

If there is nothing to commit, `git commit` will just report no changes.

### 3) Create a timestamped backup branch locally

```bash
CURRENT_BRANCH=$(git branch --show-current)
BACKUP_BRANCH="backup/${CURRENT_BRANCH}-$(date -u +%Y-%m-%d-%H%M)"
git branch "$BACKUP_BRANCH"
```

Suggested naming pattern:

- `backup/<source-branch>-YYYY-MM-DD-HHMM` (UTC time)

Example:

- `backup/work-2026-04-16-1430`

### 4) Push that backup branch to GitHub

```bash
git push -u origin "$BACKUP_BRANCH"
```

Now the backup exists remotely and can be used to restore/recover.

### 5) Verify backup exists on remote

```bash
git ls-remote --heads origin "$BACKUP_BRANCH"
```

You should see a line with the commit hash and branch ref.

---

## Restoring from a backup branch later

### Option A: continue work from backup branch

```bash
git fetch origin
git switch -c restore-from-backup origin/<backup-branch-name>
```

### Option B: reset current branch to backup commit (destructive)

```bash
git fetch origin
git reset --hard origin/<backup-branch-name>
```

Only do Option B if you are sure you want to discard current local history/state.

---

## Optional: also create a tag for the same snapshot

```bash
TAG_NAME="backup-$(date -u +%Y-%m-%d-%H%M)"
git tag "$TAG_NAME"
git push origin "$TAG_NAME"
```

Tags are useful for immutable checkpoints, while backup branches are easier for iterative recovery.

---

## Common mistakes

- Forgetting to commit local changes before creating the backup branch.
- Pushing to the wrong remote (check with `git remote -v`).
- Forgetting branch name after push (copy it from terminal output).
- Using local time without noting timezone; prefer UTC in names.

