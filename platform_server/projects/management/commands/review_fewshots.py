from __future__ import annotations

import asyncio
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.ai_api import OpenAIClient
from core.config import OpenAIConfig
from pipeline.fewshot_curation import FewshotReviewSpec, review_candidate_batch


class Command(BaseCommand):
    help = "Review generated few-shot candidates with AI using a language-specific prompt template."

    def add_arguments(self, parser):
        parser.add_argument("--operation", default="segmentation_phase_2")
        parser.add_argument("--language", required=True)
        parser.add_argument("--mechanism", default="boundary_first")
        parser.add_argument("--target-set", required=True)
        parser.add_argument("--request-id", required=True)
        parser.add_argument("--model", default="gpt-5")
        parser.add_argument("--template-model", default="")
        parser.add_argument("--template-versions", type=int, default=3)
        parser.add_argument("--max-concurrency", type=int, default=4)
        parser.add_argument("--refresh-template", action="store_true")
        parser.add_argument("--timeout-s", type=float, default=180.0)
        parser.add_argument("--heartbeat-s", type=float, default=10.0)
        parser.add_argument("--repo-root", default="")
        parser.add_argument(
            "--curation-root",
            default="",
            help="Optional base directory for curation artifacts; defaults to <repo-root>/docs/few_shot_curation",
        )

    def handle(self, *args, **options):
        spec = FewshotReviewSpec(
            operation=options["operation"],
            language=options["language"],
            mechanism=options["mechanism"],
            target_set=options["target_set"],
            request_id=options["request_id"],
            model=options["model"],
            template_model=options["template_model"] or None,
            template_versions=options["template_versions"],
            max_concurrency=options["max_concurrency"],
            refresh_template=options["refresh_template"],
        )
        repo_root = Path(options["repo_root"] or getattr(settings, "ROOT_DIR", Path.cwd())).resolve()
        curation_root_base = Path(options["curation_root"]).resolve() if options.get("curation_root") else None

        def trace(message: str) -> None:
            self.stdout.write(f"[review_fewshots] {message}")
            self.stdout.flush()

        trace(
            f"request operation={spec.operation} language={spec.language} mechanism={spec.mechanism} "
            f"target_set={spec.target_set} request_id={spec.request_id} "
            f"template_versions={spec.template_versions} max_concurrency={spec.max_concurrency} "
            f"model={spec.model} timeout_s={options['timeout_s']}"
        )
        client = OpenAIClient(config=OpenAIConfig(timeout_s=options["timeout_s"], heartbeat_s=options["heartbeat_s"]))
        try:
            result = asyncio.run(
                review_candidate_batch(
                    spec,
                    repo_root=repo_root,
                    client=client,
                    trace=trace,
                    curation_root_base=curation_root_base,
                )
            )
        except Exception as exc:  # pragma: no cover - surfaced by command output/tests through CommandError
            raise CommandError(str(exc)) from exc

        summary = result["summary"]
        self.stdout.write(self.style.SUCCESS(f"Stored few-shot reviews under {result['root']}"))
        self.stdout.write(f"Reviews: {summary['review_count']}; severity_counts: {summary['severity_counts']}")
