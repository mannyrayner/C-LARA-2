# Evaluation presentation follow-up

Apply `community_dictionary_evaluation_display_fix.patch` **after** the initial
`community_dictionary_evaluation.patch` already installed on the laptop. Do not
reapply the original patch. The follow-up preserves existing evaluation sets,
ratings and saved competences. It adds no migrations or dependencies.

## Laptop

Stop the local server. Download the follow-up patch to `/home/github/`, beside
the checkout. The original patch may still be staged, or already committed.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_evaluation_display_fix.patch &&
git apply --index ../community_dictionary_evaluation_display_fix.patch &&
git diff --cached --check
```

If the apply check fails, stop and send the output; do not discard local changes.

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary.tests.test_evaluation
```

Expect **37 tests** and final `OK`. Then:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Check these points:

1. On an open evaluation set, each question has its relevant material immediately
   above the prompt/rating. In particular, the full list of lemmas and expressions
   appears with the **Extracted vocabulary** question, and audio controls appear
   alongside both sentence- and word-audio questions.
2. Before starting a new evaluation, both languages show **Reading** and
   **Listening** with the full labels, such as **Fluent / highly proficient**.
3. Existing sessions show the declarations saved when they started, on the
   evaluation overview and **Your session** pages. Updating Profile affects new
   sessions, not an earlier session's record. No re-entry of existing competences
   is necessary.
4. If your original two-page set is already closed, use a fresh small test set to
   inspect the question pages. A closed set stays closed.

## Check in and deploy after acceptance

Both the original evaluation implementation and this follow-up must be committed
and pushed before deployment. Inspect the complete staged diff; keep databases
and backups out of Git.

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat
git status --short
git commit -m "Add dictionary evaluation and refine question context and competence summaries" &&
git push origin main &&
git rev-parse HEAD
```

For AWS, follow **sections 4 and 5** of the original evaluation runbook:
`docs/howto/community-evaluation-install.md`. That sequence backs up the database,
checks static-directory permissions, stops services, updates code, runs migrations
(including the original **0024_evaluation**), collects static files and restarts.
The initial evaluation feature has not yet been deployed there, so its migration
and static file are still needed. This follow-up adds neither. Keep the tested
queue configuration and `DEBUG=False`.
