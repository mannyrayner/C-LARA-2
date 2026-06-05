from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pipeline.fewshot_curation import FewshotCurationSpec, generate_candidate_batch, store_candidate_batch


def _resolve_cli_path(value: str | Path | None, default: str | Path) -> Path:
    """Resolve a CLI path, translating Cygwin POSIX paths for Windows Python when possible."""

    raw = str(value or default)
    if os.name == "nt" and raw.startswith("/"):
        try:
            raw = subprocess.check_output(["cygpath", "-w", raw], text=True, stderr=subprocess.DEVNULL).strip() or raw
        except (OSError, subprocess.SubprocessError):
            pass
    return Path(raw).resolve()


class Command(BaseCommand):
    help = "Generate and store candidate few-shot examples for linguistic annotation."

    def add_arguments(self, parser):
        parser.add_argument("--operation", default="segmentation_phase_2")
        parser.add_argument("--language", required=True)
        parser.add_argument("--mechanism", default="boundary_first")
        parser.add_argument("--target-set", required=True)
        parser.add_argument("--phenomena", default="")
        parser.add_argument("--count", type=int, default=10)
        parser.add_argument("--batch-size", type=int, default=5)
        parser.add_argument("--max-concurrency", type=int, default=4)
        parser.add_argument("--model", default="gpt-5")
        parser.add_argument("--request-id", default="")
        parser.add_argument("--notes", default="")
        parser.add_argument("--accept-valid", action="store_true")
        parser.add_argument("--write-prompt-variant", action="store_true")
        parser.add_argument("--repo-root", default="")
        parser.add_argument(
            "--curation-root",
            default="",
            help="Optional base directory for curation artifacts; defaults to <repo-root>/docs/few_shot_curation",
        )

    def handle(self, *args, **options):
        phenomena = tuple(part.strip() for part in (options["phenomena"] or "").split(",") if part.strip())
        spec = FewshotCurationSpec(
            operation=options["operation"],
            language=options["language"],
            mechanism=options["mechanism"],
            target_set=options["target_set"],
            phenomena=phenomena,
            count=options["count"],
            model=options["model"],
            request_id=options["request_id"] or None,
            notes=options["notes"],
            batch_size=options["batch_size"],
            max_concurrency=options["max_concurrency"],
        )
        repo_root = _resolve_cli_path(options["repo_root"], getattr(settings, "ROOT_DIR", Path.cwd()))
        curation_root_base = _resolve_cli_path(options["curation_root"], "") if options.get("curation_root") else None

        def trace(message: str) -> None:
            self.stdout.write(f"[curate_fewshots] {message}")
            self.stdout.flush()

        trace(
            f"request operation={spec.operation} language={spec.language} mechanism={spec.mechanism} "
            f"target_set={spec.target_set} count={spec.count} batch_size={spec.batch_size} "
            f"max_concurrency={spec.max_concurrency} model={spec.model}"
        )
        try:
            batch = asyncio.run(generate_candidate_batch(spec, trace=trace))
            trace("generation and validation complete; storing records")
            result = store_candidate_batch(
                batch,
                repo_root=repo_root,
                accept_valid=options["accept_valid"],
                write_prompt_variant=options["write_prompt_variant"],
                curation_root_base=curation_root_base,
            )
        except Exception as exc:  # pragma: no cover - surfaced by command output/tests through CommandError
            raise CommandError(str(exc)) from exc

        manifest = result["manifest"]
        self.stdout.write(self.style.SUCCESS(f"Stored few-shot curation batch under {result['root']}"))
        self.stdout.write(
            f"Candidates: {manifest['candidate_count']}; accepted: {manifest['accepted_count']}; "
            f"prompt files: {len(manifest['prompt_files'])}"
        )
