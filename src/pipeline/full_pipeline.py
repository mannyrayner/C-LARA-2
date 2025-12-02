"""End-to-end pipeline orchestration from segmentation to HTML output."""
from __future__ import annotations

import asyncio
import json
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


PIPELINE_ORDER = [
    "text_gen",
    "segmentation_phase_1",
    "segmentation_phase_2",
    "translation",
    "mwe",
    "lemma",
    "gloss",
    "pinyin",
    "audio",
    "compile_html",
]


@dataclass(slots=True)
class FullPipelineSpec:
    """Specification for the full annotation pipeline.

    The pipeline can start and end at any stage in :data:`PIPELINE_ORDER`.
    Provide ``text_obj`` if starting after segmentation; otherwise supply a
    ``text`` string or ``description`` for upstream stages to consume.
    """

    text: str | None = None
    text_obj: dict[str, Any] | None = None
    description: str | None = None  # optional text_gen description
    language: str = "en"
    target_language: str = "fr"
    voice: str | None = None
    audio_cache_dir: Path | None = None
    output_dir: Path | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None
    start_stage: str = "segmentation_phase_1"
    end_stage: str = "compile_html"
    require_real_tts: bool = False
    persist_intermediates: bool = False


async def run_full_pipeline(
    spec: FullPipelineSpec, *, client: OpenAIClient | None = None
) -> dict[str, Any]:
    """Run the pipeline from ``start_stage`` through ``end_stage``."""

    if spec.start_stage not in PIPELINE_ORDER:
        raise ValueError(f"Unknown start stage {spec.start_stage!r}")
    if spec.end_stage not in PIPELINE_ORDER:
        raise ValueError(f"Unknown end stage {spec.end_stage!r}")

    start_index = PIPELINE_ORDER.index(spec.start_stage)
    end_index = PIPELINE_ORDER.index(spec.end_stage)
    if start_index > end_index:
        raise ValueError("start_stage must come before end_stage")

    telemetry = spec.telemetry or NullTelemetry()
    op_id = spec.op_id or "full_pipeline"
    ai_client = client or OpenAIClient()

    current: Any = spec.text_obj
    raw_text: str | None = spec.text

    stage_dir: Path | None = None
    if spec.persist_intermediates:
        base_dir = spec.output_dir or Path.cwd() / "artifacts"
        stage_dir = base_dir / "stages"
        stage_dir.mkdir(parents=True, exist_ok=True)

    def _persist(stage: str, payload: Any) -> None:
        if not stage_dir:
            return
        try:
            (stage_dir / f"{stage}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # Allow description-driven generation when no text is provided.
    if raw_text is None and current is None:
        if spec.description:
            telemetry.event(op_id, "info", "Generating text from description")
            generated = await generate_text(
                TextGenSpec(description=spec.description, language=spec.language), client=ai_client
            )
            raw_text = generated.get("surface", "")
            _persist("text_gen", generated)
        else:
            raise ValueError("FullPipelineSpec.text, text_obj, or description must be provided")

    # If starting after segmentation, ensure a segmented object is available.
    if current is None and start_index > PIPELINE_ORDER.index("segmentation_phase_1"):
        raise ValueError("text_obj is required when starting after segmentation_phase_1")

    html_result: dict[str, Any] | None = None

    for stage in PIPELINE_ORDER[start_index : end_index + 1]:
        if stage == "text_gen":
            if current is None:
                telemetry.event(op_id, "info", "Generating text from description")
                generated = await generate_text(
                    TextGenSpec(description=spec.description or "", language=spec.language), client=ai_client
                )
                raw_text = generated.get("surface", "")
                _persist("text_gen", generated)
            continue

        if stage == "segmentation_phase_1":
            if not isinstance(raw_text, str):
                raise ValueError("segmentation_phase_1 requires a raw text string")
            current = await segmentation_phase_1(
                SegmentationSpec(text=raw_text, language=spec.language), client=ai_client
            )
            _persist("segmentation_phase_1", current)
            continue

        if current is None:
            raise ValueError(f"Stage {stage} requires annotated text input")

        if stage == "segmentation_phase_2":
            current = await segmentation_phase_2(
                SegmentationPhase2Spec(text=current, language=spec.language), client=ai_client
            )
            _persist("segmentation_phase_2", current)
        elif stage == "translation":
            current = await translate(
                TranslationSpec(text=current, language=spec.language, target_language=spec.target_language),
                client=ai_client,
            )
            _persist("translation", current)
        elif stage == "mwe":
            current = await annotate_mwes(
                MWESpec(text=current, language=spec.language, telemetry=telemetry, op_id=op_id), client=ai_client
            )
            _persist("mwe", current)
        elif stage == "lemma":
            current = await annotate_lemmas(
                LemmaSpec(text=current, language=spec.language, telemetry=telemetry, op_id=op_id), client=ai_client
            )
            _persist("lemma", current)
        elif stage == "gloss":
            current = await annotate_gloss(
                GlossSpec(
                    text=current,
                    language=spec.language,
                    target_language=spec.target_language,
                    telemetry=telemetry,
                    op_id=op_id,
                ),
                client=ai_client,
            )
            _persist("gloss", current)
        elif stage == "pinyin":
            if spec.language.lower().startswith("zh"):
                current = annotate_pinyin(PinyinSpec(text=current, language=spec.language, telemetry=telemetry))
                _persist("pinyin", current)
        elif stage == "audio":
            current = await annotate_audio(
                AudioSpec(
                    text=current,
                    language=spec.language,
                    voice=spec.voice,
                    cache_dir=spec.audio_cache_dir,
                    telemetry=telemetry,
                    op_id=op_id,
                    require_real_tts=spec.require_real_tts,
                )
            )
            _persist("audio", current)
        elif stage == "compile_html":
            html_result = compile_html(
                CompileHTMLSpec(text=current, output_dir=spec.output_dir, telemetry=telemetry, op_id=op_id)
            )
            _persist("compile_html", html_result or {})

    result: dict[str, Any] = {"text": current}
    if html_result:
        result["html"] = html_result
    return result


__all__ = ["FullPipelineSpec", "PIPELINE_ORDER", "run_full_pipeline"]
