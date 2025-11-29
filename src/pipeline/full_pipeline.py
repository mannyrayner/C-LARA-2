"""End-to-end pipeline orchestration from segmentation to HTML output."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.ai_api import OpenAIClient
from core.telemetry import NullTelemetry, Telemetry

from .audio import AudioSpec, annotate_audio
from .compile_html import CompileHTMLSpec, compile_html
from .gloss import GlossSpec, annotate_gloss
from .lemma import LemmaSpec, annotate_lemmas
from .mwe import MWESpec, annotate_mwes
from .pinyin import PinyinSpec, annotate_pinyin
from .segmentation import SegmentationPhase2Spec, SegmentationSpec, segmentation_phase_1, segmentation_phase_2
from .text_gen import TextGenSpec, generate_text
from .translation import TranslationSpec, translate


@dataclass(slots=True)
class FullPipelineSpec:
    """Specification for the full annotation pipeline."""

    text: str | None = None
    description: str | None = None  # optional text_gen description
    language: str = "en"
    target_language: str = "fr"
    voice: str | None = None
    audio_cache_dir: Path | None = None
    output_dir: Path | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None


async def run_full_pipeline(
    spec: FullPipelineSpec, *, client: OpenAIClient | None = None
) -> dict[str, Any]:
    """Run the full pipeline from segmentation through HTML compilation."""

    telemetry = spec.telemetry or NullTelemetry()
    op_id = spec.op_id or "full_pipeline"
    ai_client = client or OpenAIClient()

    # 1) Generate text if description provided, otherwise use the supplied raw text.
    raw_text: str
    if spec.description and not spec.text:
        telemetry.event(op_id, "info", "Generating text from description")
        generated = await generate_text(
            TextGenSpec(description=spec.description, language=spec.language), client=ai_client
        )
        raw_text = generated.get("surface", "")
    elif spec.text:
        raw_text = spec.text
    else:
        raise ValueError("FullPipelineSpec.text or description must be provided")

    text_obj = await segmentation_phase_1(SegmentationSpec(text=raw_text, language=spec.language), client=ai_client)

    # 2) Segmentation phase 2 (tokenization)
    text_obj = await segmentation_phase_2(
        SegmentationPhase2Spec(text=text_obj, language=spec.language), client=ai_client
    )

    # 3) Translation
    text_obj = await translate(
        TranslationSpec(text=text_obj, language=spec.language, target_language=spec.target_language), client=ai_client
    )

    # 4) MWE detection
    text_obj = await annotate_mwes(MWESpec(text=text_obj, language=spec.language), client=ai_client)

    # 5) Lemma tagging
    text_obj = await annotate_lemmas(LemmaSpec(text=text_obj, language=spec.language), client=ai_client)

    # 6) Glossing
    text_obj = await annotate_gloss(
        GlossSpec(text=text_obj, language=spec.language, target_language=spec.target_language), client=ai_client
    )

    # 7) Optional pinyin for Chinese
    if spec.language.lower().startswith("zh"):
        text_obj = annotate_pinyin(PinyinSpec(text=text_obj, language=spec.language, telemetry=telemetry))

    # 8) Audio (token, segment, page)
    text_obj = await annotate_audio(
        AudioSpec(
            text=text_obj,
            language=spec.language,
            voice=spec.voice,
            cache_dir=spec.audio_cache_dir,
            telemetry=telemetry,
            op_id=op_id,
        )
    )

    # 9) HTML rendering
    html_result = compile_html(
        CompileHTMLSpec(text=text_obj, output_dir=spec.output_dir, telemetry=telemetry, op_id=op_id)
    )

    return {"text": text_obj, "html": html_result}


__all__ = ["FullPipelineSpec", "run_full_pipeline"]
