from __future__ import annotations

import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.project_understanding import (
    build_codex_exec_command,
    build_codex_exec_environment,
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
            self.stdout.write(
                self.style.WARNING(
                    "codex login status failed; this may be okay if OPENAI_API_KEY is supplied at runtime, "
                    "but cached CLI authentication is not currently ready."
                )
            )
            detail = (login_status.stderr or login_status.stdout).strip()
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
            raise CommandError(f"codex exec smoke test failed with status {smoke.returncode}: {detail[:2000]}")
        self.stdout.write(self.style.SUCCESS("codex exec smoke test succeeded."))
        output = (smoke.stdout or "").strip()
        if output:
            self.stdout.write(output[:2000])
