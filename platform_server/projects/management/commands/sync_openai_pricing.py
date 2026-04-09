from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from projects.models import OpenAIModelPricing
from projects.views import _extract_openai_pricing_with_ai


class Command(BaseCommand):
    help = "Sync OpenAI model pricing using AI-assisted extraction from a source page."

    def add_arguments(self, parser):
        parser.add_argument("--source-url", default="https://openai.com/api/pricing/")
        parser.add_argument("--ai-model", default=getattr(settings, "OPENAI_PRICING_AI_MODEL", "gpt-5"))

    def handle(self, *args, **options):
        source_url = options["source_url"]
        models_to_extract = list(getattr(settings, "OPENAI_PRICING_TRACKED_MODELS", []))
        extracted = _extract_openai_pricing_with_ai(
            source_url=source_url,
            models_to_extract=models_to_extract,
            ai_model=options["ai_model"],
        )
        now = timezone.now()
        changed = 0
        for model_name, prices in extracted.items():
            input_price = prices.get("input")
            output_price = prices.get("output")
            if not input_price or not output_price:
                continue
            notes = f"AI-parsed evidence: {prices.get('evidence', '')}".strip()
            obj, _ = OpenAIModelPricing.objects.get_or_create(
                model_name=model_name,
                defaults={
                    "input_usd_per_1m": input_price,
                    "output_usd_per_1m": output_price,
                    "source_url": source_url,
                    "status": OpenAIModelPricing.STATUS_AI_PARSED,
                    "last_synced_at": now,
                    "notes": notes,
                },
            )
            obj.input_usd_per_1m = input_price
            obj.output_usd_per_1m = output_price
            obj.source_url = source_url
            obj.status = OpenAIModelPricing.STATUS_AI_PARSED
            obj.last_synced_at = now
            if notes:
                obj.notes = notes
            obj.save(
                update_fields=[
                    "input_usd_per_1m",
                    "output_usd_per_1m",
                    "source_url",
                    "status",
                    "last_synced_at",
                    "notes",
                    "updated_at",
                ]
            )
            changed += 1
        self.stdout.write(self.style.SUCCESS(f"Updated {changed} pricing row(s) from {source_url}"))
