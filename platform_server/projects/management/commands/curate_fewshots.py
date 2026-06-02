from __future__ import annotations

import asyncio
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pipeline.fewshot_curation import FewshotCurationSpec, generate_candidate_batch, store_candidate_batch


class Command(BaseCommand):
    help = "Generate and store candidate few-shot examples for linguistic annotation."

    def add_arguments(self, parser):
        parser.add_argument("--operation", default="segmentation_phase_2")
        parser.add_argument("--language", required=True)
        parser.add_argument("--mechanism", default="boundary_first")
        parser.add_argument("--target-set", required=True)
        parser.add_argument("--phenomena", default="")
        parser.add_argument("--count", type=int, default=10)
        parser.add_argument("--model", default="gpt-5")
        parser.add_argument("--request-id", default="")
        parser.add_argument("--notes", default="")
        parser.add_argument("--accept-valid", action="store_true")
        parser.add_argument("--write-prompt-variant", action="store_true")
        parser.add_argument("--repo-root", default="")

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
        )
        repo_root = Path(options["repo_root"] or getattr(settings, "ROOT_DIR", Path.cwd())).resolve()
        try:
            batch = asyncio.run(generate_candidate_batch(spec))
            result = store_candidate_batch(
                batch,
                repo_root=repo_root,
                accept_valid=options["accept_valid"],
                write_prompt_variant=options["write_prompt_variant"],
            )
        except Exception as exc:  # pragma: no cover - surfaced by command output/tests through CommandError
            raise CommandError(str(exc)) from exc

        manifest = result["manifest"]
        self.stdout.write(self.style.SUCCESS(f"Stored few-shot curation batch under {result['root']}"))
        self.stdout.write(
            f"Candidates: {manifest['candidate_count']}; accepted: {manifest['accepted_count']}; "
            f"prompt files: {len(manifest['prompt_files'])}"
        )
