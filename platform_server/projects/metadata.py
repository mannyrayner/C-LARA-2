from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from django.utils import timezone

from .models import Project


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


def _tokenize_words(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", text or "", flags=re.UNICODE)


def _estimate_level_from_text(text: str) -> str:
    words = _tokenize_words(text)
    if not words:
        return "unknown"
    sentence_chunks = [chunk.strip() for chunk in re.split(r"[.!?]+", text or "") if chunk.strip()]
    avg_sentence_len = len(words) / max(1, len(sentence_chunks))
    if len(words) < 120 and avg_sentence_len < 10:
        return "A1-A2"
    if len(words) < 500 and avg_sentence_len < 18:
        return "B1-B2"
    return "C1+"


def _extract_keywords(text: str, *, max_keywords: int = 8) -> list[str]:
    tokens = [tok.lower() for tok in _tokenize_words(text) if len(tok) >= 4]
    filtered = [tok for tok in tokens if tok not in _STOPWORDS and not tok.isdigit()]
    counts = Counter(filtered)
    return [word for word, _count in counts.most_common(max_keywords)]


def _latest_text_gen_surface(project: Project) -> str:
    runs_root = project.artifact_dir() / "runs"
    if not runs_root.exists():
        return ""
    candidates: list[Path] = []
    for run_dir in runs_root.iterdir():
        if not run_dir.is_dir():
            continue
        path = run_dir / "stages" / "text_gen.json"
        if path.exists():
            candidates.append(path)
    if not candidates:
        return ""
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
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
    summary_source_words = words or _tokenize_words(project.title)
    summary = " ".join(summary_source_words[:48]).strip()
    if len(summary_source_words) > 48:
        summary += "…"
    if not summary:
        summary = project.title
    return {
        "discovery_summary": summary,
        "discovery_keywords": _extract_keywords(text_for_analysis or project.title),
        "discovery_level": _estimate_level_from_text(text_for_analysis),
        "discovery_word_count": len(words),
    }


def update_project_discovery_metadata(project: Project, *, force: bool = False) -> bool:
    if not force and project.discovery_summary and project.discovery_keywords and project.discovery_word_count > 0:
        return False
    payload = build_project_discovery_metadata(project)
    project.discovery_summary = payload["discovery_summary"]
    project.discovery_keywords = payload["discovery_keywords"]
    project.discovery_level = payload["discovery_level"]
    project.discovery_word_count = payload["discovery_word_count"]
    project.discovery_metadata_updated_at = timezone.now()
    project.save(
        update_fields=[
            "discovery_summary",
            "discovery_keywords",
            "discovery_level",
            "discovery_word_count",
            "discovery_metadata_updated_at",
            "updated_at",
        ]
    )
    return True
