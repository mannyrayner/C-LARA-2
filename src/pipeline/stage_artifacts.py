"""Format-independent helpers for pipeline stage artifacts.

Phase A keeps the on-disk representation as the existing pretty JSON files while
centralising stage artifact reads/writes behind a small API. Later phases can add
format adapters without changing pipeline callers.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

DEFAULT_STAGE_ARTIFACT_FORMAT = "json_pretty"
JSON_STAGE_ARTIFACT_FORMATS = {"json", "json_pretty"}
SUPPORTED_STAGE_ARTIFACT_FORMATS = JSON_STAGE_ARTIFACT_FORMATS

_MISSING = object()


@dataclass(frozen=True, slots=True)
class StageArtifactMetadata:
    """Basic information about a stage artifact on disk."""

    stage_name: str
    path: Path
    format: str
    payload_bytes: int
    elapsed_ms: float | None = None


def stage_artifacts_dir(run_dir: Path) -> Path:
    """Return the stage-artifacts directory for ``run_dir``."""

    return Path(run_dir) / "stages"


def stage_artifact_path(run_dir: Path, stage_name: str, *, format: str = DEFAULT_STAGE_ARTIFACT_FORMAT) -> Path:
    """Return the canonical path for ``stage_name`` in ``run_dir``.

    The first implementation deliberately maps all supported formats to the
    historical ``<stage>.json`` file name. That preserves all existing run
    layouts while giving callers a stable abstraction to use.
    """

    normalized_format = _normalize_format(format)
    if normalized_format in JSON_STAGE_ARTIFACT_FORMATS:
        return stage_artifacts_dir(run_dir) / f"{stage_name}.json"
    raise ValueError(f"Unsupported stage artifact format {format!r}")


def write_stage_artifact(
    run_dir: Path,
    stage_name: str,
    payload: Any,
    *,
    format: str = DEFAULT_STAGE_ARTIFACT_FORMAT,
    normalize: Callable[[Any], Any] | None = None,
) -> StageArtifactMetadata:
    """Write a stage artifact and return basic metadata.

    Writes are atomic within the target directory where the platform supports
    ``os.replace``. The default encoding/indentation matches the pre-existing
    JSON artifact format for downward compatibility.
    """

    normalized_format = _normalize_format(format)
    if normalized_format not in JSON_STAGE_ARTIFACT_FORMATS:
        raise ValueError(f"Unsupported stage artifact format {format!r}")

    target = stage_artifact_path(run_dir, stage_name, format=normalized_format)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload_to_write = normalize(payload) if normalize else payload
    started = time.perf_counter()
    text = json.dumps(payload_to_write, ensure_ascii=False, indent=2)
    _atomic_write_text(target, text, encoding="utf-8")
    elapsed_ms = (time.perf_counter() - started) * 1000
    return StageArtifactMetadata(
        stage_name=stage_name,
        path=target,
        format=normalized_format,
        payload_bytes=target.stat().st_size,
        elapsed_ms=elapsed_ms,
    )


def read_stage_artifact(
    run_dir: Path,
    stage_name: str,
    *,
    format: str | None = None,
    default: Any = _MISSING,
) -> Any:
    """Read a stage artifact payload.

    Existing JSON artifacts remain the compatibility baseline: when no explicit
    format is supplied, the helper reads ``<stage>.json`` exactly as previous
    code did.
    """

    candidate_format = _normalize_format(format or DEFAULT_STAGE_ARTIFACT_FORMAT)
    path = stage_artifact_path(run_dir, stage_name, format=candidate_format)
    if not path.exists():
        if default is _MISSING:
            raise FileNotFoundError(path)
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        if default is _MISSING:
            raise
        return default


def artifact_exists(run_dir: Path, stage_name: str, *, format: str | None = None) -> bool:
    """Return whether the stage artifact exists."""

    candidate_format = _normalize_format(format or DEFAULT_STAGE_ARTIFACT_FORMAT)
    return stage_artifact_path(run_dir, stage_name, format=candidate_format).exists()


def artifact_metadata(run_dir: Path, stage_name: str, *, format: str | None = None) -> StageArtifactMetadata | None:
    """Return basic metadata for an existing artifact, if present."""

    candidate_format = _normalize_format(format or DEFAULT_STAGE_ARTIFACT_FORMAT)
    path = stage_artifact_path(run_dir, stage_name, format=candidate_format)
    if not path.exists():
        return None
    return StageArtifactMetadata(
        stage_name=stage_name,
        path=path,
        format=candidate_format,
        payload_bytes=path.stat().st_size,
    )


def _normalize_format(format: str) -> str:
    normalized = (format or DEFAULT_STAGE_ARTIFACT_FORMAT).strip().lower()
    if normalized == "json":
        return "json_pretty"
    return normalized


def _atomic_write_text(path: Path, text: str, *, encoding: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fp:
            fp.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


__all__ = [
    "DEFAULT_STAGE_ARTIFACT_FORMAT",
    "JSON_STAGE_ARTIFACT_FORMATS",
    "SUPPORTED_STAGE_ARTIFACT_FORMATS",
    "StageArtifactMetadata",
    "artifact_exists",
    "artifact_metadata",
    "read_stage_artifact",
    "stage_artifact_path",
    "stage_artifacts_dir",
    "write_stage_artifact",
]
