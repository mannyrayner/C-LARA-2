# Roadmap: authenticated project-understanding assistant

Tracked by [ISSUE-0034](../issues/issues/ISSUE-0034.json).

## Goal

Create a lightweight authenticated-user feature that lets authorised C-LARA-2 users ask high-level questions about the C-LARA-2 project and receive answers grounded in the repository.

The revised architecture is deliberately simple: the platform should delegate the whole project-understanding task to Codex running against the checked-out C-LARA-2 repository, rather than trying to preselect evidence files or reconstruct Codex-style repository understanding in application code.

The target evidence base is the full repository available to Codex in read-only mode. Codex should decide which files to inspect, including `docs/roadmap/`, `docs/issues/`, `docs/howto/`, project reports, tests, prompts, and relevant source files. The assistant should support questions about architecture, goals, implementation status, issue structure, roadmap plans, prompt design, tests, and module relationships.

This is not intended as a general public chatbot. The current product is an authenticated project-maintenance and evidence-gathering tool that demonstrates how well C-LARA-2 can use Codex and its repository-native documentation/code to explain itself.

## Why this matters

C-LARA-2 is intentionally developed with extensive repository-native documentation so AI tools can understand and help maintain the platform. An authenticated self-knowledge assistant makes this capability inspectable from inside the platform and could:

- help project maintainers, trusted reviewers, and report authors find reliable answers faster;
- create a versioned evidence record of how well Codex can answer project-level questions from the repository;
- support the initial C-LARA-2 report's argument about autonomy and AI-assisted authorship by letting sceptical readers inspect concrete question/answer records;
- reveal gaps, contradictions, or stale areas in the documentation when Codex cannot answer reliably;
- provide a reusable baseline for later user-facing help or broader conversational UX, if the authenticated version proves accurate and safe.

The practical motivation for using Codex directly is that C-LARA-2 has already been maintained successfully for months through Codex sessions connected to the repository. That is the strongest evidence that Codex is the right component to choose and inspect supporting files, rather than a bespoke API wrapper trying to guess the relevant evidence before the model sees the question.

## Revised architecture: delegate repository understanding to `codex exec`

The earlier idea of wrapping a user request, preselecting likely evidence files, and sending that package to a model through a normal API call is now considered brittle. It asks the platform to solve the hardest part of the task — knowing what repo evidence matters — before the system has invoked the tool that is best at repository exploration.

Instead, the platform should:

1. Accept an authenticated user's project-understanding question.
2. Build a concise, versioned instruction prompt that tells Codex to answer from the C-LARA-2 repository, cite files, distinguish implemented from planned work, and identify uncertainty.
3. Invoke `codex exec` in the deployed C-LARA-2 checkout with a read-only sandbox, non-interactive stdin prompt passing, and no unsupported approval flags.
4. Let Codex inspect the repository and choose evidence files itself.
5. Capture Codex's stdout/stderr, exit status, model name, prompt version, repository path, and timestamp.
6. Store the answer and metadata as a versionable project-understanding evidence record.

A representative command shape is:

```bash
codex exec \
  --cd /srv/C-LARA-2 \
  --sandbox read-only \
  --ephemeral \
  --model gpt-5.3-codex - < prompt.txt
```

The exact command should be generated without shell-injection hazards; production code should prefer `subprocess.run([...], input=prompt_text, ...)` or an equivalently safe argument vector over interpolating untrusted text into a shell command. The example above is documentation of the intended Codex invocation semantics, not a prescription to use unsafe shell string construction.

### Current implementation status (2026-06-07)

The first platform implementation is now in place and has been moved out of the Admin tab to the main authenticated navigation as **Assistant**. It includes:

- a core `codex exec` wrapper in `src/core/project_understanding.py` that builds the versioned project-understanding prompt, constructs a read-only/non-interactive argument vector, passes the prompt through stdin, passes a reduced environment that can use either `OPENAI_API_KEY` or cached Codex CLI credentials under `HOME`/`CODEX_HOME`, resolves common Windows npm, Linux service-user, and configured absolute Codex paths, applies a timeout, forces UTF-8 subprocess decoding, extracts the final answer and token count where available from stdout or stderr, and returns structured metadata;
- configurable Django settings for the Codex executable, repository checkout path, model, timeout, and GitHub blob URL: `PROJECT_UNDERSTANDING_CODEX_EXECUTABLE`, `PROJECT_UNDERSTANDING_REPOSITORY_PATH`, `PROJECT_UNDERSTANDING_MODEL`, `PROJECT_UNDERSTANDING_TIMEOUT_SECONDS`, and `PROJECT_UNDERSTANDING_GITHUB_BLOB_BASE_URL`;
- an authenticated platform surface at `/assistant/project-understanding/`, linked as **Assistant** from the top navigation, with legacy redirects from the previous `/admin-tools/project-understanding/` URLs, a textarea for the question, and a result area showing the answer, model, prompt version, elapsed time, token count when extractable, estimated upper-bound cost, exit status, repository path, and stderr when present;
- an asynchronous Django Q execution path: submitting a question queues a background task, immediately redirects to a monitor page, records `TaskUpdate` progress rows, emits periodic heartbeat messages while Codex is running, and polls a JSON status endpoint until the run finishes or fails;
- request/result persistence under `MEDIA_ROOT/admin_project_understanding/` (directory name retained for backward compatibility with existing runs), so the monitor page can keep showing the current question during execution and after completion, and can render the completed answer produced by the worker process;
- usage/cost tracking for completed Codex runs when the CLI reports `tokens used`: because current CLI output exposes only a total token count rather than separate input/cached-input/output counts, the platform records a conservative output-priced upper-bound estimate through the existing OpenAI pricing/credits framework and labels the value as an upper bound in run metadata; local comparisons with the OpenAI Usage page suggest the estimate can be at least three times higher than the eventual API charge, presumably because real billing applies cheaper input/cached-input rates or Codex-specific accounting not visible in the plain CLI transcript;
- tests for prompt construction, command/environment construction, Codex executable resolution, transcript parsing, timeout/error handling, record rendering, authenticated access control, task queueing, monitor rendering, and status/result JSON;
- a `check_project_understanding_codex` management command that reports the configured executable, resolved executable, repository path, model, credential-related environment, `codex --version`, `codex login status`, and optionally runs an end-to-end read-only `codex exec` smoke test.

The local smoke tests have also demonstrated that `codex exec` can answer repository-level questions by inspecting files itself and returning plausible cited answers. Observed answers correctly used repository evidence for questions such as a three-bullet repository summary and the internal annotated-text representation.

Important remaining work before treating the feature as broadly usable:

- add an explicit export/review flow that writes selected answers into `docs/project_understanding/` as committed evidence records;
- add reviewer assessment fields in the UI rather than only in rendered Markdown records;
- add hard budget/rate-limit controls for admin runs now that the UI records total tokens and a clearly labelled upper-bound cost estimate;
- reconcile exact cost accounting if a future Codex CLI/API surface exposes input, cached-input, and output token splits rather than only the total `tokens used`;
- keep local absolute path citations rewritten to GitHub URLs before answers are shown outside trusted-admin contexts;
- run a curated evaluation set and summarize successes, failures, stale-documentation discoveries, and safety observations.

#### Migration-state note from the 2026-06-01 implementation pass

The migration warning seen while starting the platform was separate from the project-understanding assistant work: the assistant added settings, views, forms, templates, and file-backed request/result records, but did not add or alter Django models. Investigation showed a pre-existing `projects` migration graph with two leaves: `0036_profile_byok_fields` and `0038_projectimagestyle_disallow_text_in_images`. This has now been resolved using the usual Django workflow:

- `0039_merge_20260524_1408` and the compatibility alias `0039_merge_0036_profile_byok_fields_0038_projectimagestyle_disallow_text_in_images` are no-op merge migrations depending on both leaves; keeping both names avoids a leaf conflict across checkouts that had already seen one merge name or the other.
- `0040_alter_creditledgerentry_entry_type_and_more` depends on both merge migrations and captures the remaining model-state changes detected after the graph merge (`CreditLedgerEntry.entry_type` choices and the current `ExerciseSet.flashcard_mode` choices).

After these migrations, `manage.py makemigrations --check --dry-run` reports no changes, and the admin-tool Django tests can build a clean fresh test database.

### Installation and runtime prerequisites for `codex exec`

The platform does not need to embed Codex as a Python library. It needs a working, pinned Codex CLI executable available to the process that runs the management command or background worker. The installation checklist should be explicit because local development, staging, and production may use different operating-system images.

Minimum local or server prerequisites:

1. **Supported host environment.** Use a host supported by the Codex CLI distribution used for deployment, for example macOS, Linux, or Windows through WSL2. Prefer the same OS family in staging and production so sandbox behaviour can be tested before release.
2. **Codex CLI executable.** Install the maintained OpenAI Codex CLI through an approved route such as the official install script, `npm install -g @openai/codex`, Homebrew, or a pinned release binary. For production, prefer a pinned binary or container image rather than a floating global install.
3. **Authentication.** Configure Codex authentication for the account or service identity that is allowed to answer project-understanding questions. This is not a separate C-LARA-2 licence key: Codex must be signed in with ChatGPT, an OpenAI API key, or an enterprise Codex access token before `codex exec` can call the OpenAI service. A `401 Unauthorized` response from `https://api.openai.com/v1/responses` means the CLI did not have valid cached credentials or a valid bearer token. The secret must be available to Codex at runtime but must not be written into evidence records, web responses, stderr displays, or committed config.
4. **Repository checkout.** Provide a checked-out C-LARA-2 repository at a fixed configured path, initially something like `/srv/C-LARA-2` in production and the developer's working tree locally. Git should be installed if the system records `git rev-parse HEAD` or uses repository metadata.
5. **Writable Codex state outside the repository.** Even a read-only repository run may need a writable home/cache/session directory for the CLI itself. Configure `HOME` or `CODEX_HOME` to a dedicated service directory that contains no unrelated secrets and is excluded from the evidence record.
6. **Network access to OpenAI services.** The process running `codex exec` needs outbound network access required by the Codex CLI. Other outbound access should be minimized in production.
7. **Version and capability check.** Deployment should verify `codex --version` and `codex exec --help` during setup, record the version used for evidence runs, and fail closed if the required flags are unavailable.

A developer bootstrap note can be included in the feature documentation, for example:

```bash
# Choose one approved install route and pin it where practical.
npm install -g @openai/codex

# Verify the installed CLI and the non-interactive command.
codex --version
codex exec --help

# Authenticate once before the smoke test. Use exactly one route:
#   1. Browser login for a local developer machine.
codex login
#   2. Device-code login for a terminal/headless machine.
# codex login --device-auth
#   3. API-key login for automation or a service account.
# printenv OPENAI_API_KEY | codex login --with-api-key

# Confirm that Codex has usable cached credentials.
codex login status

# Run a local read-only smoke test from a C-LARA-2 checkout.
# On Windows/Cygwin/Git Bash, use a forward-slash path such as
# C:/cygwin64/home/github/c-lara-2 or normalize CLARA2 first.
REPO_ROOT="/path/to/C-LARA-2"
printf '%s\n' 'Summarise the repository in three bullet points; cite files if possible.' | \
  codex exec \
    --cd "$REPO_ROOT" \
    --sandbox read-only \
    --ephemeral \
    --model gpt-5.3-codex -
```

The smoke-test syntax above matches `codex-cli 0.135.0`, where `codex exec [OPTIONS] [PROMPT]` reads the prompt from stdin when `-` is used or when no prompt argument is provided. That version does **not** support the older `--ask-for-approval never` flag, so the wrapper should not include it. For a machine where `CLARA2` is set to a Windows-style path such as `C:\cygwin64\home\github\c-lara-2`, use `REPO_ROOT="${CLARA2//\\//}"` in Bash to pass `C:/cygwin64/home/github/c-lara-2` to `--cd`. A `401 Unauthorized` during the smoke test is an authentication problem, not a sandbox or repository-path problem: run `codex login status`, then sign in with ChatGPT, use device-code login, or pipe an OpenAI API key into `codex login --with-api-key`. If a later version reintroduces an approval-control option, the wrapper can fail closed unless the option is explicitly configured to refuse interactive/privileged escalation. In all versions, preserve the same safety properties: no shell interpolation of user text, fixed repository path, read-only sandbox, non-interactive operation, and bounded runtime.

#### Laptop/AWS configuration contract

The important rule is that Django must not depend on a developer's interactive shell startup files. The same settings should exist in the laptop shell, the Django development process, the AWS Gunicorn process, and the Django Q worker process:

| Setting / environment variable | Laptop example | AWS example | Notes |
| --- | --- | --- | --- |
| `C_LARA_CODEX_EXECUTABLE` | `codex` or `/Users/alice/.local/bin/codex` | `/opt/codex/bin/codex`, `/usr/local/bin/codex`, or `/home/clara/.local/bin/codex` | Prefer an absolute path on AWS because systemd/Gunicorn often has a shorter `PATH` than an SSH shell. |
| `C_LARA_PROJECT_UNDERSTANDING_REPO` | `$CLARA2` or the current checkout | `/srv/C-LARA-2` | Must be the checked-out repo Codex should inspect; mount/read it read-only where possible. |
| `C_LARA_PROJECT_UNDERSTANDING_MODEL` | `gpt-5.3-codex` | `gpt-5.3-codex` | Keep laptop and AWS aligned unless testing a model change. |
| `C_LARA_PROJECT_UNDERSTANDING_TIMEOUT_SECONDS` | `300` | `300` or a deployment-specific cap | Bound spend and request lifetime. |
| `CODEX_HOME` | optional, or a local Codex config dir | `/var/lib/c-lara/codex` | Recommended on AWS so cached Codex credentials do not live in the app checkout or a human home directory. |
| `OPENAI_API_KEY` | optional if `codex login` has cached credentials | optional if `CODEX_HOME` has cached credentials; otherwise set through the secret manager/service environment | The wrapper now passes it if present but no longer requires it, so cached `codex login` credentials work. |

On AWS, install Codex as the same Unix service identity that will run the Q worker, or install it in a root-owned path readable/executable by that identity. The install command suggested by GPT-5.5, `curl -fsSL https://chatgpt.com/codex/install.sh | sh`, should be used only after checking that it is still the current official installer; deployment should record the resulting absolute binary path and version. If the script installs into `~/.local/bin`, either add that directory to the service `PATH` or set `C_LARA_CODEX_EXECUTABLE=/home/<service-user>/.local/bin/codex`. Avoid relying on `~/.bashrc`, because Gunicorn/systemd services typically do not read it.

A minimal systemd-style service environment for both `gunicorn` and `qcluster` should look like this (adapt paths/usernames to the actual server):

```ini
Environment=PATH=/opt/codex/bin:/usr/local/bin:/usr/bin:/bin
Environment=C_LARA_CODEX_EXECUTABLE=/opt/codex/bin/codex
Environment=C_LARA_PROJECT_UNDERSTANDING_REPO=/srv/C-LARA-2
Environment=C_LARA_PROJECT_UNDERSTANDING_MODEL=gpt-5.3-codex
Environment=C_LARA_PROJECT_UNDERSTANDING_TIMEOUT_SECONDS=300
Environment=CODEX_HOME=/var/lib/c-lara/codex
# Use either cached `codex login` credentials in CODEX_HOME or a secret-managed key:
# Environment=OPENAI_API_KEY=...
```

Recommended AWS deployment sequence:

1. Create/choose a non-root service user, for example `clara`, and create a locked-down Codex home: `sudo install -d -o clara -g clara -m 700 /var/lib/c-lara/codex`.
2. Install Codex using the approved route. If using the install script, run it as the service user or copy the resulting binary into an explicit deployment path such as `/opt/codex/bin/codex`; then record `codex --version`.
3. Authenticate the service identity: either run `sudo -u clara CODEX_HOME=/var/lib/c-lara/codex /opt/codex/bin/codex login --device-auth` and complete the device flow, or pipe a secret-managed API key into `codex login --with-api-key` without writing the key to shell history.
4. Add the environment variables above to both Gunicorn and Django Q worker service definitions, then restart both services. The web process and worker must agree on the same executable, repo, model, and `CODEX_HOME`.
5. Run `python platform_server/manage.py check_project_understanding_codex` in the exact deployment virtualenv and service-like environment. It should print the resolved executable, version, and login status.
6. Run `python platform_server/manage.py check_project_understanding_codex --smoke` once before enabling general use. A 401 at this stage means authentication is not available to the service environment; a `FileNotFoundError` means the service cannot see the configured executable; a repository-path error means `C_LARA_PROJECT_UNDERSTANDING_REPO` is wrong or inaccessible.

The laptop setup is the same contract with less ceremony: install Codex, authenticate with `codex login`, set `C_LARA_CODEX_EXECUTABLE` only if `codex` is not on the Django process `PATH`, set `C_LARA_PROJECT_UNDERSTANDING_REPO` if the Django checkout is not the intended evidence checkout, then run the same management command.

#### Concrete AWS example: Codex copied from `ubuntu` to `/opt/codex`

A common AWS path is now:

```bash
sudo install -d -o root -g root -m 755 /opt/codex/bin
sudo install -o root -g root -m 755 /home/ubuntu/.local/bin/codex /opt/codex/bin/codex
```

This is a good setup. It deliberately separates the **Codex executable** from the **Codex configuration/credential directory**:

- `C_LARA_CODEX_EXECUTABLE=/opt/codex/bin/codex` points Django/Q at a root-owned executable that every service user can run.
- `CODEX_HOME=...` points Codex at a writable configuration directory for the Unix user that is actually running `manage.py`, Gunicorn, and Q.

Do not set `CODEX_HOME=/home/ubuntu/.codex` unless those processes really run as `ubuntu`. A successful `ubuntu` login stored under `/home/ubuntu/.codex` is not automatically usable by a process running as `ssm-user`, `www-data`, or another service account. If `check_project_understanding_codex` prints `HOME: /home/ssm-user` and `CODEX_HOME: /home/ubuntu/.codex`, the executable problem has been solved but `CODEX_HOME` is still wrong for that process.

For the current `/opt/codex/bin/codex` setup, the recommended `/etc/clara2.env` shape is:

```env
C_LARA_CODEX_EXECUTABLE=/opt/codex/bin/codex
C_LARA_PROJECT_UNDERSTANDING_REPO=/srv/C-LARA-2
C_LARA_PROJECT_UNDERSTANDING_MODEL=gpt-5.3-codex
C_LARA_PROJECT_UNDERSTANDING_TIMEOUT_SECONDS=300
CODEX_HOME=/var/lib/c-lara/codex
# OPENAI_API_KEY=...  # if supplied by the existing secret/env mechanism
```

Create `CODEX_HOME` for the Unix user that actually runs Gunicorn and Q. If the current check is being run as `ssm-user` and the services also run as `ssm-user`, use:

```bash
sudo install -d -o ssm-user -g ssm-user -m 700 /var/lib/c-lara/codex
```

If Gunicorn/Q run as a different user, replace `ssm-user` with that service user. The key rule is that the same user that starts Codex must be able to read and write `CODEX_HOME`.

If the shell smoke test says `Process user: ssm-user (uid 1001)` but the Assistant worker message says `worker user=ubuntu uid=1000`, then the shell test and Assistant are using different Unix users. In that case, either run the smoke test as `ubuntu`, or make `/var/lib/c-lara/codex` owned by `ubuntu` and authenticate Codex under that same directory, for example:

```bash
sudo chown -R ubuntu:ubuntu /var/lib/c-lara/codex
sudo chmod 700 /var/lib/c-lara/codex
sudo -u ubuntu CODEX_HOME=/var/lib/c-lara/codex /opt/codex/bin/codex login status
# If needed, authenticate as ubuntu with the same CODEX_HOME:
# sudo -u ubuntu CODEX_HOME=/var/lib/c-lara/codex /opt/codex/bin/codex login --device-auth
# or pipe the service API key into: sudo -u ubuntu CODEX_HOME=/var/lib/c-lara/codex /opt/codex/bin/codex login --with-api-key
```

After changing `/etc/clara2.env`, changing ownership, or authenticating Codex, restart both Gunicorn and Q/qcluster so they receive the new environment. Then run the check from the deployment virtualenv with the same user/environment the service uses:

```bash
python platform_server/manage.py check_project_understanding_codex
python platform_server/manage.py check_project_understanding_codex --smoke
```

If that shell check passes as `ssm-user` but the Assistant worker later reports `worker user=ubuntu`, the successful check has not proved the exact worker environment. Run the smoke path as the worker user before looking at repository permissions:

```bash
sudo -u ubuntu env CODEX_HOME=/var/lib/c-lara/codex \
  /opt/codex/bin/codex login status
printf 'Summarise the repository in one sentence; cite one file if possible.\n' | \
  sudo -u ubuntu env CODEX_HOME=/var/lib/c-lara/codex \
  /opt/codex/bin/codex exec --cd /srv/C-LARA-2 --sandbox read-only --ephemeral --model gpt-5.3-codex -
```

A response such as `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`, especially when the normal shell smoke test succeeds, means the package is installed and the repository path is probably fine, but the worker's process context cannot create the bubblewrap/user-namespace sandbox Codex expects. `sudo -u ubuntu ... codex exec ...` is a useful Unix-user check, but it does not prove the systemd service context if the Q worker is started by a unit with extra sandboxing. Inspect the Gunicorn and Django Q service units (`systemctl cat ...`) for hardening options that block namespaces or sandbox helper processes, such as `PrivateUsers=`, `RestrictNamespaces=`, `NoNewPrivileges=`, or a restrictive `SystemCallFilter=`. Either relax those options for the Q worker that launches Codex, or run the Codex Assistant worker under a service unit/user that permits Codex's read-only sandbox. After changing a unit, run `sudo systemctl daemon-reload`, restart Gunicorn and Q, and repeat the Assistant request.

To advise on the exact edit, collect the service names and the non-secret systemd properties for the web and worker units. The useful commands are:

```bash
systemctl list-units --type=service | egrep -i 'clara|gunicorn|django|qcluster|q|celery'
sudo systemctl cat <gunicorn-service-name>
sudo systemctl cat <django-q-service-name>
sudo systemctl show <gunicorn-service-name> \
  -p User -p Group -p EnvironmentFiles -p WorkingDirectory \
  -p NoNewPrivileges -p PrivateUsers -p RestrictNamespaces -p SystemCallFilter \
  -p ProtectHome -p ProtectSystem -p PrivateTmp -p AppArmorProfile
sudo systemctl show <django-q-service-name> \
  -p User -p Group -p EnvironmentFiles -p WorkingDirectory \
  -p NoNewPrivileges -p PrivateUsers -p RestrictNamespaces -p SystemCallFilter \
  -p ProtectHome -p ProtectSystem -p PrivateTmp -p AppArmorProfile
```

Do not paste secret values such as `OPENAI_API_KEY`; if an `Environment=` line contains secrets, redact the values and leave the variable names.

If those service properties show no explicit namespace hardening (`NoNewPrivileges=no`, `PrivateUsers=no`, `RestrictNamespaces=no`, and no restrictive syscall filter), the next most likely difference is `PATH`: an interactive `sudo -u ubuntu` shell may find the OS package `/usr/bin/bwrap`, while the Gunicorn/Q service may not. The management command and Assistant runtime summary print `PATH` and `bwrap on PATH`/`bwrap=...` for this reason. On Ubuntu, prefer an explicit service path in `/etc/clara2.env` or the systemd unit, for example:

```env
PATH=/opt/codex/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

After adding or changing `PATH`, run `sudo systemctl daemon-reload`, restart Gunicorn and Q, then confirm that the Assistant worker message shows `bwrap=/usr/bin/bwrap` rather than `bwrap=(not found)`.

Interpret the next result as follows:

- If the Assistant UI shows `Background worker picked up request; launching Codex (...)`, compare the `worker user=...`, `HOME=...`, `CODEX_HOME=...`, and `codex=...` values in that message with the successful shell smoke test. They must refer to the same service-owned `CODEX_HOME` and executable.
- If the Assistant UI only shows `Django Q accepted project-understanding task <Thread(...)>. Waiting for a worker to start Codex.` and never shows `Background worker picked up request; launching Codex.`, the request reached the async-task layer but the local Django-Q compatibility thread did not actually enter `_run_project_understanding_task`. Check the Gunicorn/Django logs for thread exceptions and verify the deployed code includes the dotted-task-path resolution used by the local `django_q` shim.
- `Resolved executable: /opt/codex/bin/codex` and `codex --version: ...` mean the executable path is correct.
- `failed to read CODEX_HOME` or `Failed to read config file /var/lib/c-lara/codex/config.toml: Permission denied` means `CODEX_HOME` or files inside it are still owned by the wrong Unix user. Fix ownership recursively for the actual Gunicorn/Q user, for example `sudo chown -R <service-user>:<service-user> /var/lib/c-lara/codex && sudo chmod 700 /var/lib/c-lara/codex`.
- `codex login status failed` without a `CODEX_HOME` permission error may be acceptable if `OPENAI_API_KEY available to child: yes`; the `--smoke` check is the decisive end-to-end test.
- `Process user: root (uid 1001)` is misleading: older diagnostics used environment variables for the name. The effective uid is authoritative; current diagnostics resolve the uid through the OS user database. Use the uid/name shown by the updated command and Assistant worker message when fixing ownership.
- A `bubblewrap` warning is not always fatal, but if the smoke answer says it cannot inspect `/srv/C-LARA-2` because command access is failing or bubblewrap is missing, install bubblewrap for the service environment (on Ubuntu, typically `sudo apt-get install bubblewrap`) and rerun `--smoke`. If bubblewrap is installed and the exact error is `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`, treat it as a service sandbox/namespace problem for the worker user rather than a checked-out-repository file-permission problem.
- A 401 during `--smoke` means the executable and `CODEX_HOME` are accessible, but authentication is not available to Codex. In practice, `OPENAI_API_KEY available to child: yes` is not enough if Codex still reports `Not logged in` and the websocket call returns `401 Unauthorized`. Keep the service-owned `CODEX_HOME` and authenticate Codex as the actual service user, for example:

```bash
# Run this as the same Unix user that runs Gunicorn/Q, or use sudo -u <service-user>.
export CODEX_HOME=/var/lib/c-lara/codex
printenv OPENAI_API_KEY | /opt/codex/bin/codex login --with-api-key
/opt/codex/bin/codex login status
```

If the service does not expose `OPENAI_API_KEY` to an interactive shell, use the server's secret-loading mechanism to run the same command with that variable present, or use `codex login --device-auth` as the service user with `CODEX_HOME=/var/lib/c-lara/codex`.


#### Authentication setup and 401 diagnostics

A successful installation only proves that the `codex` binary is present. It does not prove that the CLI has a valid credential. The project should document the credential setup separately from the smoke test:

- **Local developer machine:** run `codex login` and complete the ChatGPT browser login, then verify with `codex login status`. This uses the developer's ChatGPT/Codex entitlement and cached local credentials.
- **Headless local or staging machine:** run `codex login --device-auth` if browser login cannot complete on the same machine.
- **Automation or service account:** prefer an OpenAI API key or enterprise Codex access token provisioned specifically for this feature. Pipe it into `codex login --with-api-key` or the corresponding access-token login flow; do not put the key directly on the command line, in a prompt, in a committed config file, or in an evidence record.
- **Production worker:** set `CODEX_HOME` to a locked-down service directory, authenticate the worker identity once during deployment or startup, and run `codex login status` plus `python platform_server/manage.py check_project_understanding_codex` as readiness checks before accepting web jobs. If the checks fail, the feature should be disabled or return an administrator-facing configuration error.

For the first local retry after a `401`, the recommended sequence is:

```bash
codex login status
# If not authenticated, choose one:
codex login
# or: codex login --device-auth
# or: printenv OPENAI_API_KEY | codex login --with-api-key

codex login status
REPO_ROOT="${CLARA2//\\//}"
printf '%s\n' 'Summarise the repository in three bullet points; cite files if possible.' | \
  codex exec --cd "$REPO_ROOT" --sandbox read-only --ephemeral --model gpt-5.3-codex -
```

A `401 Unauthorized` with text such as `Missing bearer or basic authentication in header` or a websocket `401 Unauthorized` means Codex reached the OpenAI endpoint but did not send a usable credential. The immediate remediation is to authenticate or refresh the cached credential for the same `CODEX_HOME` and Unix user, not to change the repository path, sandbox mode, model prompt, or read-only safety settings.

#### Expected successful smoke-test output

A successful smoke test should look like a normal Codex non-interactive session rather than a silent API call. The transcript will typically include:

- a Codex session header showing the CLI version, working directory, model, provider, approval policy, sandbox mode, reasoning settings, and session ID;
- one or more `exec` events where Codex inspects repository files, commonly using read-only commands such as `rg`, `sed`, or equivalent platform-native shell commands;
- command-result blocks showing matching file lines or short snippets that Codex used as evidence;
- a final answer in the requested format, ideally with concise bullets and citations to repository files and line numbers;
- a token-usage summary.

For the first `Summarise the repository in three bullet points; cite files if possible.` smoke question, plausible behaviour is that Codex searches `README.md`, `docs/README.md`, pipeline code such as `src/pipeline/full_pipeline.py`, Django models such as `platform_server/projects/models.py`, and representative tests such as `tests/test_12_full_pipeline.py`. A good answer should summarize that C-LARA-2 is an AI-assisted language-learning content platform, that the implementation combines a staged Python pipeline with a Django application, and that the repository has tests/CI and operational documentation.

Some transcript details are useful operational metadata but should not be treated as part of the polished user answer. In particular, the platform should separate or redact:

- absolute local/server paths such as `C:\cygwin64\home\github\c-lara-2` or `/srv/C-LARA-2` before displaying answers beyond trusted administrators;
- raw `exec` traces unless the UI is intentionally showing a detailed run log;
- session IDs and token counts if they are not needed for the evidence record;
- duplicated transcript blocks if stdout/stderr capture or terminal copy/paste includes the same run twice.

The important success signal is not the exact wording of the smoke-test answer. It is that Codex authenticates successfully, stays in `read-only` sandbox mode, chooses evidence files itself, cites concrete repository locations, and produces a bounded answer without mutating the checkout.

### Safe invocation model

The first safety goal is to make a project-understanding run answer-only. It should be unable to mutate the repository, trigger platform actions, leak secrets, or turn a user's prompt into a shell command. Safety should be layered, starting with local development and then tightened for web deployment.

#### Local-machine safety baseline

For local management-command development and report-oriented batch runs:

- run from a disposable or clean checkout when possible, or verify that `--sandbox read-only` prevents writes to the working tree before trusting it;
- use a non-privileged OS user and avoid running Codex as `root`;
- invoke Codex with an argument vector, not `shell=True`, for example `subprocess.run([codex_path, "exec", "--cd", repo_path, "--sandbox", "read-only", "--ephemeral", "--model", model, "-"], input=prompt_text, text=True, timeout=timeout_seconds, ...)`;
- keep the repository path, model, timeout, and Codex executable path in trusted configuration rather than user-controllable form fields;
- pass the user's question only inside the versioned prompt text, and impose prompt/question length limits before invoking Codex;
- use `--sandbox read-only` on every run and do not pass unsupported approval flags; treat any interactive prompt, non-zero exit status, timeout, or unexpected stderr as a failed or review-required run;
- set a minimal environment for the subprocess, preserving only variables needed for Codex authentication and ordinary execution;
- store CLI cache/session data in a dedicated directory separate from the repository and inspect whether it contains sensitive material before deciding what, if anything, can be logged;
- capture stdout, stderr, exit status, timeout state, model, prompt version, repository commit, and Codex version, but redact secrets and local-only paths before showing output in a UI or committing evidence records;
- HTML-escape rendered answers in any local preview because repository text and model output are untrusted content.

This baseline is appropriate for an administrator manually running a management command. It is not sufficient by itself for a public or semi-public web surface because a web request can create concurrency, cost, abuse, and data-exposure risks.

#### Web-environment safety baseline

For an authenticated web feature, the web process should not simply run a shell command synchronously inside the request handler. A safer architecture is:

1. The Django view authenticates and authorizes the staff user, validates the question length/type, creates a pending run record, and enqueues a background job.
2. A dedicated worker process runs Codex under a locked-down service account with a fixed configuration.
3. The worker executes Codex in a container, VM, or OS sandbox with the repository mounted read-only and no write access to the application database except through the narrow result-recording path.
4. The worker applies strict timeout, output-size, concurrency, and rate limits; marks timed-out or failed runs as review-required; and never retries unboundedly.
5. The UI displays completed answers with escaping, reviewer status, command metadata, and warnings for stderr/non-zero exits, but hides secrets, raw environment, and unnecessary server paths.

Additional web hardening should include:

- authenticated access controls, audit logging, CSRF protection, and per-user/project rate limits;
- egress controls that allow OpenAI API traffic but block arbitrary internal-network access where possible;
- no access to Docker sockets, cloud instance metadata, deployment credentials, user-upload stores, production databases, or private project data outside the intended repository checkout;
- a read-only bind mount for the repository and a small writable scratch/cache directory that can be deleted after each run or rotated regularly;
- a queue-level budget guard so repeated questions cannot create uncontrolled model spend;
- output-size limits and safe truncation rules for stdout/stderr;
- human review before any evidence record is committed back into the repository;
- regular smoke tests that prove the configured worker cannot write to the repository, cannot access disallowed paths, handles prompt-injection attempts as data, and records failures transparently.

These controls do not make Codex a trusted actor. They make Codex an untrusted subprocess that is useful for repository reading and explanation while the platform retains control over identity, inputs, execution boundaries, output handling, and evidence publication.

### Why `codex exec` rather than a normal API call

- Codex is already designed to operate inside a repository and inspect files as needed.
- The platform does not need to build or maintain a retrieval/indexing layer for the first version.
- Evidence selection remains part of the model/tool task, where project-development experience shows it works well.
- The implementation started as an admin/restricted action that shells out to Codex; the current version is an authenticated UI backed by the same safe command wrapper.
- Running with `--sandbox read-only` makes the intended first version answer-only: Codex can read repository files but cannot mutate the repo. With current `codex-cli 0.135.0` syntax, the platform should rely on non-interactive `codex exec` plus timeout/error handling rather than passing the unsupported `--ask-for-approval never` option.

## Relationship to existing dialogue work

This roadmap is related to, but narrower and more evidence-oriented than, [the freeform dialogue-based top-level roadmap](dialogue-top-level.md).

- The dialogue top level is about helping users operate C-LARA-2 workflows through conversation.
- The project-understanding assistant is about answering questions concerning the project itself, using Codex connected to the repository as the evidence-gathering and reasoning engine.
- The first implementation should be read-only: it must not trigger project mutations, expensive pipeline runs, admin actions, or repository changes from user prompts.
- A later phase can decide whether project-understanding answers become one intent within a broader dialogue/orchestration layer.

## Initial requirements

1. Access began with admins and is now exposed to authenticated users through the Assistant navigation item, with privacy controls on stored turns.
2. The user enters a question through a simple platform form or management command.
3. The system wraps the question in a prompt instructing Codex to answer from the C-LARA-2 repository.
4. The system invokes `codex exec` against the server checkout, initially `/srv/C-LARA-2`, with `--sandbox read-only`, non-interactive stdin prompt passing, and a pinned/default Codex model such as `gpt-5.3-codex`.
5. Codex, not the platform, is responsible for deciding which repository files to inspect.
6. The answer distinguishes implemented functionality from planned or speculative functionality.
7. The answer cites supporting files wherever possible.
8. The answer explicitly says when available project materials do not support a claim.
9. Each run stores the question, answer, timestamp, model name, prompt version, Codex command metadata, repository path/commit where available, and cited/supporting files where extractable.
10. Records are stored in the C-LARA-2 file tree, preferably under `docs/project_understanding/` or a similar folder, so they are versionable and inspectable.
11. Each record includes fields for later human assessment: `accurate`, `partially accurate`, `inaccurate`, or `unclear`, plus reviewer notes.
12. Tests and user/developer documentation are added before broad use.
13. A development log explains design choices and why the feature is relevant to the broader C-LARA-2 authorship/autonomy evidence case.

## Evidence scope

The evidence scope is the repository visible to Codex in the configured checkout. The platform should not attempt to collect evidence files before invoking Codex. It may include high-level guidance in the prompt about likely useful areas, but Codex should choose what to inspect.

Useful evidence areas to mention in the prompt include:

1. `docs/roadmap/` for goals, plans, status notes, and feature relationships.
2. `docs/issues/overview.md`, `docs/issues/index.json`, and `docs/issues/issues/*.json` for current issue state, priorities, dependencies, and human-suggestion provenance.
3. `docs/howto/` and other user/developer guidance when available.
4. Project reports and report drafts, especially material tied to autonomy, authorship, and project history.
5. Tests, prompts, and fixtures for evidence about expected behaviour and model-facing task design.
6. Relevant implementation files for architecture and status questions that documentation alone cannot answer.

This is guidance, not a precomputed retrieval corpus. If the question requires other files, Codex should inspect them. If it cannot find support, it should say so.

## Codex prompt baseline

A first prompt version can be based on the following template:

```text
You are answering questions about the C-LARA-2 project.

You are running as Codex inside a read-only checkout of the C-LARA-2 repository. Use repository files as evidence. You may inspect whatever files are needed, especially docs/roadmap/, docs/issues/, docs/howto/, project reports, tests, prompts, and implementation files.

Answer at the level of a project collaborator who understands the current architecture, goals, status, and development plans.

When relevant:
- distinguish implemented functionality from planned functionality;
- cite supporting repository files and, where practical, line ranges;
- explain relationships between modules or documents;
- identify uncertainty rather than guessing;
- say when the available project materials do not support an answer;
- do not propose or perform repository/platform mutations;
- do not expose secrets, private user/project data, credentials, raw logs, or environment variables.

The question is:
...
```

The production prompt should be versioned and stored with the generated question/answer records so later reviewers can interpret changes in behaviour over time.

## Record format and storage

Use a repository-visible evidence log, for example under `docs/project_understanding/`. The exact schema can evolve, but each run should include at least:

- stable record ID or filename;
- timestamp;
- submitter or authenticated-user identifier, subject to privacy policy;
- question;
- answer;
- model name and Codex invocation route;
- prompt version;
- repository path and repository commit where available;
- command metadata, including sandbox mode, interaction/approval policy for the installed CLI version, exit status, timeout, and whether stderr was non-empty;
- cited/supporting files as reported by Codex or extracted from the answer;
- whether the answer says evidence is missing or uncertain;
- human assessment field: `unreviewed`, `accurate`, `partially accurate`, `inaccurate`, or `unclear`;
- human reviewer notes.

Records should be plain Markdown or JSON/Markdown pairs so they can be committed, diffed, cited in reports, and inspected by human reviewers. If platform code writes records on the server, there should also be an explicit export/review step before committing them to the repository.

## User interface and operating modes

Current/MVP surfaces:

- authenticated Django view linked from the top-level Assistant navigation item;
- `check_project_understanding_codex` management command for laptop/AWS readiness checks and optional smoke tests;
- future optional export command that writes selected records into `docs/project_understanding/` for version control.

The current web path already uses a background worker rather than running Codex synchronously in the request handler. The management-command path remains useful for deployment readiness, batch/report-oriented question runs, and debugging the exact service environment that Gunicorn and Django Q see.

The UI can be minimal: a question box, answer pane, supporting-file list or extracted citations, command/run metadata, and reviewer assessment controls. A management-command path may be especially useful for generating repeatable evidence for the initial report.

## Safety and governance

The assistant should reason over publicly available repository content, but the production platform still needs strict boundaries:

- keep access authenticated and revisit role/credit/quota controls after broader testing;
- run Codex with `--sandbox read-only`, non-interactive prompt passing, and no unsupported approval flags;
- use a fixed repository checkout path controlled by configuration, not arbitrary user-supplied paths;
- pass user questions to Codex without unsafe shell interpolation;
- apply request length limits and execution timeouts;
- capture and review stderr/exit status rather than silently returning partial answers;
- do not expose private user/project data, credentials, server paths beyond the configured repository root, raw logs, or environment variables;
- do not allow user prompts to execute code, mutate repository/platform state, or trigger costly workflows;
- treat repository text and user questions as prompt-injection surfaces;
- rate-limit usage and record costs through the credits/billing framework; for Codex CLI runs, record the reported total token count and use a clearly labelled upper-bound estimate until the CLI exposes input/cached-input/output token splits or another exact billing signal;
- make stale documentation and unsupported answers visible rather than hiding uncertainty;
- preserve human review fields so the evidence log does not imply all model answers are correct.

## Implementation considerations

- Keep settings for the Codex executable path, repository checkout path, model, timeout, prompt version, and output directory aligned across laptop, Gunicorn, and Django Q worker environments.
- Use `check_project_understanding_codex` as the first diagnostic when the assistant works locally but fails on AWS.
- Use `subprocess.run` or `asyncio.create_subprocess_exec` with an argument list and bounded timeout.
- Capture stdout as the candidate answer; capture stderr and non-zero exit status in the record and user-visible error path.
- Record the current repository commit with `git rev-parse HEAD` when available.
- Ensure the process environment does not leak unnecessary secrets. If Codex needs credentials configured on the server, keep them outside the evidence record.
- Add tests around prompt construction, argument-vector construction, timeout/error handling, record serialization, and access control for any UI surface.
- Consider whether a second offline parser should extract file citations from Codex's answer into structured metadata, while still preserving the raw answer.

## Phased plan

### Phase A: revised planning and command design — largely complete

- Treat the normal API/retrieval-wrapper approach as superseded for the main architecture.
- Define the first `codex exec` command contract: executable, repository path, sandbox mode, non-interactive mode, model, timeout, prompt passing, and output capture.
- Version the Codex prompt and decide how prompt versions are stored.
- Define the record schema and create `docs/project_understanding/` conventions.
- Choose the first set of report-relevant evaluation questions.

### Phase B: command/wrapper prototype — complete for first deployment

- Build a callable wrapper that accepts a question, constructs the versioned Codex prompt, invokes `codex exec` in read-only/non-interactive mode, and returns a structured result.
- Capture elapsed time, stdout/stderr, exit status, model, prompt version, token count when extractable, repository path, and the command vector.
- Add tests for prompt construction, safe subprocess argument construction, timeout/error paths, record serialization, and missing-evidence behaviour.
- Still needed: an export command/path for committing selected reviewed records.

### Phase C: authenticated UI and review workflow — first UI implemented

- Add a minimal Django view linked from the authenticated Assistant navigation item.
- Display answer text, command/run metadata, stderr/exit status warnings, and live background-task progress.
- Add access-control, queueing, monitor, and status-endpoint tests.
- Still needed: citation extraction, reviewer assessment controls, exact-cost reconciliation if Codex exposes richer usage data, hard budget/rate-limit controls, and export/review paths for committing selected records.

### Phase D: report/evidence workflow

- Run a curated question set relevant to the initial C-LARA-2 report's autonomy/authorship argument.
- Human-review the answers and fill in assessment fields.
- Add a development log summarizing design choices, limitations, representative successes/failures, and implications for the report.
- Use reviewed records as inspectable evidence rather than unverified promotional claims.

### Phase E: possible productization

- Evaluate whether the authenticated assistant needs tighter role controls, quotas, or review workflows after broader testing.
- Consider a carefully narrowed user-facing help assistant only after accuracy, privacy, safety, and cost controls are demonstrated.
- Consider convergence with the broader dialogue top level, while preserving the evidence-log workflow.

## Open questions

- After the first AWS deployment, should the project standardize on the install script, `npm install -g @openai/codex`, a pinned binary, or a small container image for the Codex CLI?
- How should the platform pass prompts to `codex exec` so long questions are safe and robust without relying on shell interpolation?
- What timeout should be used for project-understanding questions, and how should partial/no-output cases be presented to users?
- Should records be written directly by the platform, exported for later commit, or both?
- What is the minimum curated question set needed for the first report?
- How should human assessments be summarized without overstating model reliability?
- How should answers cite files consistently enough for downstream parsing while still letting Codex decide what to inspect?
