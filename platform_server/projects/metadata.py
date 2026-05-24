from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from core.ai_api import OpenAIClient
from core.config import DEFAULT_MODEL, OpenAIConfig
from pipeline.stage_artifacts import read_stage_artifact, stage_artifact_path

from .billing import record_openai_usage_and_charge
from .models import Profile, Project

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}
_CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _tokenize_words(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", text or "", flags=re.UNICODE)


def _estimate_level_from_text(text: str) -> str:
    words = _tokenize_words(text)
    if not words:
        return "unknown"
    sentence_chunks = [chunk.strip() for chunk in re.split(r"[.!?]+", text or "") if chunk.strip()]
    avg_sentence_len = len(words) / max(1, len(sentence_chunks))
    if len(words) < 120 and avg_sentence_len < 10:
        return "A1/A2"
    if len(words) < 500 and avg_sentence_len < 18:
        return "B1/B2"
    return "C1/C2"


def _normalize_cefr_level(raw: str, *, max_levels: int = 2) -> str:
    value = (raw or "").strip().upper()
    if not value:
        return ""
    aliases = {
        "BEGINNER": "A1/A2",
        "ELEMENTARY": "A1/A2",
        "INTERMEDIATE": "B1/B2",
        "UPPER INTERMEDIATE": "B2/C1",
        "ADVANCED": "C1/C2",
    }
    if value in aliases:
        value = aliases[value]
    tokens = re.findall(r"[ABC][12]", value.replace("-", "/"))
    if not tokens:
        return ""
    deduped: list[str] = []
    for token in tokens:
        if token in _CEFR_LEVELS and token not in deduped:
            deduped.append(token)
    if not deduped:
        return ""
    deduped = deduped[:max_levels]
    indices = sorted(_CEFR_LEVELS.index(token) for token in deduped)
    normalized = [_CEFR_LEVELS[idx] for idx in indices]
    return "/".join(normalized)


def _extract_keywords(text: str, *, max_keywords: int = 8) -> list[str]:
    tokens = [tok.lower() for tok in _tokenize_words(text) if len(tok) >= 4]
    filtered = [tok for tok in tokens if tok not in _STOPWORDS and not tok.isdigit()]
    counts = Counter(filtered)
    return [word for word, _count in counts.most_common(max_keywords)]


def _fallback_summary(text: str, title: str) -> str:
    sentences = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", text or "") if chunk.strip()]
    if not sentences:
        return title
    summary = " ".join(sentences[:2]).strip()
    return summary[:400]


def _run_billed_chat_text(
    *,
    project: Project,
    prompt: str,
    request_type: str,
    temperature: float | None,
) -> str:
    usage_events: list[dict[str, Any]] = []

    def _collect(event: dict[str, Any]) -> None:
        usage_events.append(dict(event or {}))

    profile_obj = Profile.objects.filter(user=project.owner).first()
    byok_key = ""
    if profile_obj and profile_obj.use_personal_openai_key:
        byok_key = (profile_obj.openai_api_key or "").strip()
    client = OpenAIClient(
        config=OpenAIConfig(
            api_key=byok_key or None,
            model=DEFAULT_MODEL,
            usage_reporter=_collect,
        )
    )
    response = asyncio.run(client.chat_text(prompt, model=DEFAULT_MODEL, temperature=temperature))
    for event in usage_events:
        payload = dict(event or {})
        if not byok_key:
            record_openai_usage_and_charge(
                user_id=project.owner_id,
                project_id=project.id,
                model=str(payload.get("model") or DEFAULT_MODEL),
                operation=str(payload.get("operation") or "chat_text"),
                prompt_tokens=max(0, int(payload.get("prompt_tokens") or 0)),
                completion_tokens=max(0, int(payload.get("completion_tokens") or 0)),
                total_tokens=max(0, int(payload.get("total_tokens") or 0)),
                request_type=request_type,
            )
    return response or ""


def _generate_summary_with_ai(project: Project, text: str, title: str) -> str:
    if not (getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY")):
        return ""
    prompt = (
        "Write a short discovery summary (max 45 words) for this learner text. "
        "Keep punctuation and proper names. Return plain text only.\n\n"
        f"Title: {title}\n\nText:\n{text[:6000]}"
    )
    try:
        response = _run_billed_chat_text(
            project=project,
            prompt=prompt,
            request_type="discovery_summary_generate",
            temperature=0.2,
        )
        return (response or "").strip()[:400]
    except Exception:
        logger.exception("AI summary generation failed; falling back to heuristic summary")
        return ""


def _generate_keywords_with_ai(project: Project, text: str, title: str) -> list[str]:
    if not (getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY")):
        return []
    prompt = (
        "Return 6 to 10 concise discovery keywords for this learner text. "
        "Avoid prepositions, determiners and pronouns. Prefer topic-bearing nouns and short noun phrases. "
        "Return JSON as an array of strings only.\n\n"
        f"Title: {title}\n\nText:\n{text[:6000]}"
    )
    try:
        response = _run_billed_chat_text(
            project=project,
            prompt=prompt,
            request_type="discovery_keywords_generate",
            temperature=0.1,
        )
        response = (response or "").strip()
        parsed = _parse_keywords_response(response)
        if parsed:
            return parsed[:10]
    except Exception:
        logger.exception("AI keyword generation failed; falling back to heuristic keywords")
    return []


def _translate_keywords_to_english_with_ai(project: Project, keywords: list[str]) -> list[str]:
    if not keywords:
        return []
    if not (getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY")):
        return []
    prompt = (
        "Translate the following discovery keywords into concise English equivalents. "
        "Return JSON as an array of strings only, preserving keyword order.\n\n"
        f"Keywords: {keywords}"
    )
    try:
        response = _run_billed_chat_text(
            project=project,
            prompt=prompt,
            request_type="discovery_keywords_translate_en",
            temperature=0.0,
        )
        parsed = _parse_keywords_response((response or "").strip())
        if parsed:
            return parsed[: len(keywords)]
    except Exception:
        logger.exception("AI keyword translation failed; falling back to source keywords")
    return []


def _parse_keywords_response(response: str) -> list[str]:
    text = (response or "").strip()
    if not text:
        return []
    # 1) Try strict JSON array first.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            cleaned = [str(item).strip() for item in parsed if str(item).strip()]
            if cleaned:
                return cleaned
    except Exception:
        pass
    # 2) Try to recover array embedded in markdown/text.
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, list):
                cleaned = [str(item).strip() for item in parsed if str(item).strip()]
                if cleaned:
                    return cleaned
        except Exception:
            pass
    # 3) Fall back to comma/newline separated text.
    stripped = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    parts = [part.strip(" -•\t\r\n\"'") for part in re.split(r"[,;\n]+", stripped)]
    return [part for part in parts if part]


def _latest_text_gen_surface(project: Project) -> str:
    runs_root = project.artifact_dir() / "runs"
    if not runs_root.exists():
        return ""
    candidates: list[Path] = []
    for run_dir in runs_root.iterdir():
        if not run_dir.is_dir():
            continue
        path = stage_artifact_path(run_dir, "text_gen")
        if path.exists():
            candidates.append(path)
    if not candidates:
        return ""
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        payload = read_stage_artifact(latest.parent.parent, "text_gen")
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("surface") or "").strip()


def build_project_discovery_metadata(project: Project) -> dict[str, Any]:
    generated_surface = _latest_text_gen_surface(project)
    source = generated_surface or (project.source_text or "").strip()
    description = (project.description or "").strip()
    text_for_analysis = source or description
    words = _tokenize_words(text_for_analysis)
    summary = _generate_summary_with_ai(project, text_for_analysis, project.title) or _fallback_summary(text_for_analysis, project.title)
    keywords = _generate_keywords_with_ai(project, text_for_analysis, project.title) or _extract_keywords(text_for_analysis or project.title)
    if (project.language or "").lower().startswith("en"):
        keywords_en = list(keywords)
    else:
        keywords_en = _translate_keywords_to_english_with_ai(project, keywords) or list(keywords)
    return {
        "discovery_summary": summary,
        "discovery_keywords": keywords,
        "discovery_keywords_en": keywords_en,
        "discovery_level": _normalize_cefr_level(_estimate_level_from_text(text_for_analysis), max_levels=2),
        "discovery_word_count": len(words),
    }


def update_project_discovery_metadata(project: Project, *, force: bool = False) -> bool:
    if (
        not force
        and project.discovery_summary
        and project.discovery_keywords
        and project.discovery_keywords_en
        and project.discovery_word_count > 0
    ):
        return False
    payload = build_project_discovery_metadata(project)
    project.discovery_summary = payload["discovery_summary"]
    project.discovery_keywords = payload["discovery_keywords"]
    project.discovery_keywords_en = payload.get("discovery_keywords_en") or []
    project.discovery_level = payload["discovery_level"]
    project.discovery_word_count = payload["discovery_word_count"]
    project.discovery_metadata_updated_at = timezone.now()
    project.save(
        update_fields=[
            "discovery_summary",
            "discovery_keywords",
            "discovery_keywords_en",
            "discovery_level",
            "discovery_word_count",
            "discovery_metadata_updated_at",
            "updated_at",
        ]
    )
    return True
