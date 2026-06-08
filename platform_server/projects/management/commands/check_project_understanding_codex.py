from __future__ import annotations

import getpass
import os
import pwd
import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.project_understanding import (
    build_codex_exec_command,
    build_codex_exec_environment,
    detect_codex_sandbox_access_failure,
    resolve_codex_executable,
)


class Command(BaseCommand):
    help = "Check that the Codex CLI configured for project-understanding is visible to Django/Q workers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--smoke",
            action="store_true",
            help="Run a short read-only codex exec smoke test against the configured repository.",
        )
        parser.add_argument(
            "--question",
            default="Summarise the repository in one sentence; cite one file if possible.",
            help="Question to use with --smoke.",
        )

    def handle(self, *args, **options):
        configured_executable = getattr(settings, "PROJECT_UNDERSTANDING_CODEX_EXECUTABLE", "codex")
        repository_path = getattr(settings, "PROJECT_UNDERSTANDING_REPOSITORY_PATH", settings.ROOT_DIR)
        model = getattr(settings, "PROJECT_UNDERSTANDING_MODEL", "gpt-5.3-codex")
        timeout = float(getattr(settings, "PROJECT_UNDERSTANDING_TIMEOUT_SECONDS", 300))
        env = build_codex_exec_environment(openai_api_key=getattr(settings, "OPENAI_API_KEY", ""))
        resolved_executable = resolve_codex_executable(configured_executable, environment=env)

        self.stdout.write(f"Configured executable: {configured_executable}")
        self.stdout.write(f"Resolved executable: {resolved_executable}")
        self.stdout.write(f"Repository path: {repository_path}")
        self.stdout.write(f"Model: {model}")
        try:
            effective_uid = os.geteuid() if hasattr(os, "geteuid") else None
        except Exception:
            effective_uid = None
        try:
            process_user = pwd.getpwuid(effective_uid).pw_name if effective_uid is not None else getpass.getuser()
        except Exception:
            try:
                process_user = getpass.getuser()
            except Exception:
                process_user = "unknown"
        self.stdout.write(f"Process user: {process_user}{f' (uid {effective_uid})' if effective_uid is not None else ''}")
        self.stdout.write(f"CODEX_HOME: {env.get('CODEX_HOME') or '(not set)'}")
        self.stdout.write(f"HOME: {env.get('HOME') or env.get('USERPROFILE') or '(not set)'}")
        self.stdout.write(f"OPENAI_API_KEY available to child: {'yes' if env.get('OPENAI_API_KEY') else 'no'}")

        try:
            version = subprocess.run(
                [resolved_executable, "--version"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=20,
                check=False,
                env=env,
            )
        except FileNotFoundError as exc:
            raise CommandError(
                "Codex CLI was not found. Set C_LARA_CODEX_EXECUTABLE to an absolute codex path "
                "or put the Codex install directory on PATH for the Django/Q service."
            ) from exc
        except PermissionError as exc:
            raise CommandError(
                f"Could not run Codex CLI because the Django/Q service user cannot access `{resolved_executable}`: {exc}. "
                "Either run Gunicorn and Q as the user that owns that Codex install, or move/copy Codex to a "
                "shared executable path such as /opt/codex/bin/codex and point C_LARA_CODEX_EXECUTABLE there."
            ) from exc
        except OSError as exc:
            raise CommandError(f"Could not run Codex CLI: {exc}") from exc

        if version.returncode != 0:
            raise CommandError(f"`codex --version` failed: {(version.stderr or version.stdout).strip()}")
        self.stdout.write(self.style.SUCCESS(f"codex --version: {(version.stdout or version.stderr).strip()}"))

        login_status = subprocess.run(
            [resolved_executable, "login", "status"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=20,
            check=False,
            env=env,
        )
        if login_status.returncode == 0:
            self.stdout.write(self.style.SUCCESS("codex login status succeeded."))
        else:
            detail = (login_status.stderr or login_status.stdout).strip()
            if "CODEX_HOME" in detail and "Permission denied" in detail:
                raise CommandError(
                    "Codex CLI is installed, but the configured CODEX_HOME is not readable/writable "
                    "by this Django/Q service user. Set CODEX_HOME to a private directory owned by "
                    "the same Unix user that runs Gunicorn and Q (for example /var/lib/c-lara/codex), "
                    "or run the services as the user that owns the existing CODEX_HOME. Detail: "
                    f"{detail[:1000]}"
                )
            self.stdout.write(
                self.style.WARNING(
                    "codex login status failed; this may be okay if OPENAI_API_KEY is supplied at runtime, "
                    "but cached CLI authentication is not currently ready."
                )
            )
            if detail:
                self.stdout.write(detail[:1000])

        if not options["smoke"]:
            self.stdout.write(self.style.SUCCESS("Codex CLI visibility check complete. Use --smoke for an end-to-end exec test."))
            return

        command = build_codex_exec_command(
            repository_path=repository_path,
            codex_executable=resolved_executable,
            model=model,
        )
        smoke = subprocess.run(
            command,
            input=options["question"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        if smoke.returncode != 0:
            detail = (smoke.stderr or smoke.stdout).strip()
            if "401 Unauthorized" in detail or "Not logged in" in detail:
                raise CommandError(
                    "codex exec reached the OpenAI service but was not authenticated. "
                    "The executable and CODEX_HOME are visible, so fix Codex authentication for this service user: "
                    "run `codex login`/`codex login --with-api-key` with the same CODEX_HOME, or verify that the "
                    "OPENAI_API_KEY supplied to the service is valid for Codex. Detail: "
                    f"{detail[:2000]}"
                )
            raise CommandError(f"codex exec smoke test failed with status {smoke.returncode}: {detail[:2000]}")
        output = (smoke.stdout or "").strip()
        sandbox_failure_detail = detect_codex_sandbox_access_failure("\n".join([smoke.stdout or "", smoke.stderr or ""]))
        if sandbox_failure_detail:
            raise CommandError(
                "codex exec exited successfully, but Codex reported that repository inspection was blocked by "
                "the Linux sandbox/bubblewrap layer. This is usually a service-user or systemd namespace "
                "configuration issue rather than a repository-file permission problem. Detail: "
                f"{sandbox_failure_detail[:2000]}"
            )
        self.stdout.write(self.style.SUCCESS("codex exec smoke test succeeded."))
        if output:
            self.stdout.write(output[:2000])
