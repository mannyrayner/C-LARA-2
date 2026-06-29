"""End-to-end pipeline orchestration from segmentation to HTML output."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.ai_api import OpenAIClient, normalize_json_text
from core.telemetry import NullTelemetry, Telemetry

from .audio import AudioSpec, annotate_audio
from .compile_html import CompileHTMLSpec, compile_html
from .gloss import GlossSpec, annotate_gloss
from .lemma import LemmaSpec, annotate_lemmas
from .mwe import MWESpec, annotate_mwes
from .pinyin import PinyinSpec, annotate_pinyin
from .segmentation import SegmentationPhase2Spec, SegmentationSpec, segmentation_phase_1, segmentation_phase_2
from .stage_artifacts import write_stage_artifact
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
    description: dict[str, Any] | str | None = None  # optional text_gen description
    language: str = "en"
    target_language: str = "fr"
    voice: str | None = None
    audio_cache_dir: Path | None = None
    output_dir: Path | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None
    start_stage: str = "segmentation_phase_1"
    end_stage: str = "compile_html"
    page_images: dict[int, dict[str, str]] | None = None
    picture_glosses: dict[str, dict[str, str]] | None = None
    segmentation_method: str = "auto"
    romanization_method: str = "auto"
    require_real_tts: bool = False
    audio_mode: str = "tts"
    persist_intermediates: bool = False
    progress_callback: Callable[[str, str, str], None] | None = None
    stage_parameters: dict[str, dict[str, Any]] | None = None


def _strip_audio_annotations(payload: Any) -> Any:
    """Return a deep copy of annotated text with all audio annotations removed."""

    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if key == "audio":
                continue
            cleaned[key] = _strip_audio_annotations(value)
        return cleaned
    if isinstance(payload, list):
        return [_strip_audio_annotations(item) for item in payload]
    return payload


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
    progress_cb = spec.progress_callback
    if spec.persist_intermediates:
        base_dir = spec.output_dir or Path.cwd() / "artifacts"
        stage_dir = base_dir / "stages"
        stage_dir.mkdir(parents=True, exist_ok=True)

    def _persist(stage: str, payload: Any) -> None:
        if not stage_dir:
            return
        try:
            write_stage_artifact(stage_dir.parent, stage, payload, normalize=normalize_json_text)
        except Exception:
            pass

    def _stage_parameters(stage: str) -> dict[str, Any]:
        params = (spec.stage_parameters or {}).get(stage, {})
        return params if isinstance(params, dict) else {}

    if spec.persist_intermediates and spec.stage_parameters:
        _persist("processing_parameters", spec.stage_parameters)

    def _progress(stage: str, status: str) -> None:
        if progress_cb is None:
            return
        timestamp = datetime.utcnow().isoformat()
        try:
            progress_cb(stage, status, timestamp)
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
        stage_op_id = f"{op_id}:{stage}"
        telemetry.event(stage_op_id, "info", "stage start")

        if stage == "text_gen":
            try:
                if current is None:
                    telemetry.event(stage_op_id, "info", "Generating text from description")
                    _progress("text_gen", "start")
                    generated = await generate_text(
                        TextGenSpec(
                            description=spec.description or "",
                            language=spec.language,
                            telemetry=telemetry,
                            op_id=stage_op_id,
                        ),
                        client=ai_client,
                    )
                    raw_text = generated.get("surface", "")
                    _persist("text_gen", generated)
                    _progress("text_gen", "done")
                telemetry.event(stage_op_id, "info", "stage done")
            except Exception as exc:
                _progress("text_gen", "error")
                telemetry.event(stage_op_id, "error", "stage failed", {"error": str(exc)})
                raise
            continue

        if stage == "segmentation_phase_1":
            if not isinstance(raw_text, str):
                raise ValueError("segmentation_phase_1 requires a raw text string")
            try:
                _progress("segmentation_phase_1", "start")
                seg1_params = _stage_parameters("segmentation_phase_1")
                current = await segmentation_phase_1(
                    SegmentationSpec(
                        text=raw_text,
                        language=spec.language,
                        telemetry=telemetry,
                        op_id=stage_op_id,
                        prioritise_sentences=bool(seg1_params.get("prioritise_sentences")),
                    ),
                    client=ai_client,
                )
                _persist("segmentation_phase_1", current)
                _progress("segmentation_phase_1", "done")
                telemetry.event(stage_op_id, "info", "stage done")
            except Exception as exc:
                _progress("segmentation_phase_1", "error")
                telemetry.event(stage_op_id, "error", "stage failed", {"error": str(exc)})
                raise
            continue

        if current is None:
            raise ValueError(f"Stage {stage} requires annotated text input")

        if stage == "segmentation_phase_2":
            try:
                _progress("segmentation_phase_2", "start")
                seg2_params = _stage_parameters("segmentation_phase_2")
                seg2_variant = str(seg2_params.get("variant") or "")
                current = await segmentation_phase_2(
                    SegmentationPhase2Spec(
                        text=current,
                        language=spec.language,
                        telemetry=telemetry,
                        op_id=stage_op_id,
                        method=spec.segmentation_method,
                        mechanism=str(seg2_params.get("mechanism") or "json_direct"),
                        prompt_variant=str(
                            seg2_params.get("prompt_variant")
                            or seg2_params.get("template_variant")
                            or seg2_variant
                        ),
                        fewshot_variant=str(seg2_params.get("fewshot_variant") or seg2_variant),
                        fewshot_count=str(
                            seg2_params.get("fewshot_count")
                            or seg2_params.get("fewshot_limit")
                            or seg2_params.get("fewshot_tranche")
                            or "all"
                        ),
                        chunk_prompt_variant=str(
                            seg2_params.get("chunk_prompt_variant")
                            or "chunk_decomposition_multilingual_v1"
                        ),
                        chunk_prompt_split=str(seg2_params.get("chunk_prompt_split") or "development"),
                        chunk_prompt_cycle=(
                            int(seg2_params["chunk_prompt_cycle"])
                            if seg2_params.get("chunk_prompt_cycle") is not None
                            else None
                        ),
                        max_concurrency=int(seg2_params.get("max_concurrency") or 20),
                    ),
                    client=ai_client,
                )
                _persist("segmentation_phase_2", current)
                _progress("segmentation_phase_2", "done")
                telemetry.event(stage_op_id, "info", "stage done")
            except Exception as exc:
                _progress("segmentation_phase_2", "error")
                telemetry.event(stage_op_id, "error", "stage failed", {"error": str(exc)})
                raise
        elif stage == "translation":
            try:
                _progress("translation", "start")
                current = await translate(
                    TranslationSpec(
                        text=current,
                        language=spec.language,
                        target_language=spec.target_language,
                        telemetry=telemetry,
                        op_id=stage_op_id,
                    ),
                    client=ai_client,
                )
                _persist("translation", current)
                _progress("translation", "done")
                telemetry.event(stage_op_id, "info", "stage done")
            except Exception as exc:
                _progress("translation", "error")
                telemetry.event(stage_op_id, "error", "stage failed", {"error": str(exc)})
                raise
        elif stage == "mwe":
            _progress("mwe", "start")
            current = await annotate_mwes(
                MWESpec(text=current, language=spec.language, telemetry=telemetry, op_id=stage_op_id), client=ai_client
            )
            _persist("mwe", current)
            _progress("mwe", "done")
            telemetry.event(stage_op_id, "info", "stage done")
        elif stage == "lemma":
            _progress("lemma", "start")
            current = await annotate_lemmas(
                LemmaSpec(text=current, language=spec.language, telemetry=telemetry, op_id=stage_op_id), client=ai_client
            )
            _persist("lemma", current)
            _progress("lemma", "done")
            telemetry.event(stage_op_id, "info", "stage done")
        elif stage == "gloss":
            _progress("gloss", "start")
            current = await annotate_gloss(
                GlossSpec(
                    text=current,
                    language=spec.language,
                    target_language=spec.target_language,
                    telemetry=telemetry,
                    op_id=stage_op_id,
                ),
                client=ai_client,
            )
            _persist("gloss", current)
            _progress("gloss", "done")
            telemetry.event(stage_op_id, "info", "stage done")
        elif stage == "pinyin":
            _progress("pinyin", "start")
            current = await annotate_pinyin(
                PinyinSpec(
                    text=current,
                    language=spec.language,
                    telemetry=telemetry,
                    op_id=stage_op_id,
                    method=spec.romanization_method,
                ),
                client=ai_client,
            )
            _persist("pinyin", current)
            _progress("pinyin", "done")
            telemetry.event(stage_op_id, "info", "stage done")
        elif stage == "audio":
            _progress("audio", "start")
            if spec.audio_mode == "none":
                current = _strip_audio_annotations(current)
                telemetry.event(stage_op_id, "info", "audio disabled; skipping TTS")
            else:
                current = await annotate_audio(
                    AudioSpec(
                        text=current,
                        language=spec.language,
                        voice=spec.voice,
                        cache_dir=spec.audio_cache_dir,
                        telemetry=telemetry,
                        op_id=stage_op_id,
                        require_real_tts=spec.require_real_tts,
                    )
                )
            _persist("audio", current)
            _progress("audio", "done")
            telemetry.event(stage_op_id, "info", "stage done")
        elif stage == "compile_html":
            if spec.audio_mode == "none":
                current = _strip_audio_annotations(current)
            if spec.page_images and isinstance(current, dict):
                pages = current.get("pages") or []
                if isinstance(pages, list):
                    for page_number, image_meta in spec.page_images.items():
                        if not isinstance(page_number, int):
                            continue
                        idx = page_number - 1
                        if idx < 0 or idx >= len(pages):
                            continue
                        page_obj = pages[idx]
                        if not isinstance(page_obj, dict):
                            continue
                        annotations = page_obj.setdefault("annotations", {})
                        if isinstance(annotations, dict):
                            annotations["generated_image"] = image_meta
            _progress("compile_html", "start")
            html_result = compile_html(
                CompileHTMLSpec(
                    text=current,
                    output_dir=spec.output_dir,
                    telemetry=telemetry,
                    op_id=stage_op_id,
                    picture_glosses=spec.picture_glosses,
                )
            )
            _persist("compile_html", html_result or {})
            _progress("compile_html", "done")
            telemetry.event(stage_op_id, "info", "stage done")

    result: dict[str, Any] = {"text": current}
    if html_result:
        result["html"] = html_result
    return result


__all__ = ["FullPipelineSpec", "PIPELINE_ORDER", "run_full_pipeline"]
