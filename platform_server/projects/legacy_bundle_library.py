"""Safe filesystem and ZIP helpers for a configured legacy bundle library."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .legacy_clara_import import find_legacy_clara_bundle_root


def safe_import_path(root: Path, row: dict[str, Any]) -> Path | None:
    """Resolve a metadata row's payload path, rejecting escapes from ``root``."""

    raw = (
        row.get("import_relative_path")
        or row.get("zip_relative_path")
        or row.get("relative_path")
        or row.get("directory_name")
        or ""
    )
    if not raw:
        return None
    candidate = Path(str(raw))
    if candidate.is_absolute():
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def legacy_zip_trace(names: list[str], *, limit: int = 20) -> dict[str, Any]:
    """Return concise diagnostics describing a candidate legacy ZIP."""

    annotated = [name for name in names if PurePosixPath(name).name == "annotated_text.json"]
    metadata = [name for name in names if PurePosixPath(name).name == "metadata.json"]
    return {
        "entry_count": len(names),
        "first_entries": names[:limit],
        "annotated_text_entries": annotated[:limit],
        "metadata_entries": metadata[:limit],
        "legacy_root_detected": find_legacy_clara_bundle_root(names),
    }


def open_server_bundle_for_import(import_path: Path):
    """Return a spooled ZIP and trace for a server-side bundle path."""

    base_trace = {
        "selected_import_path": str(import_path),
        "selected_import_path_type": "directory" if import_path.is_dir() else "file",
    }
    if import_path.is_dir():
        zip_candidates = sorted(import_path.glob("*.zip"), key=lambda path: (path.name != "source.zip", path.name))
        metadata_path = import_path / "metadata.json"
        if zip_candidates and metadata_path.exists():
            spool, trace = _zip_with_sidecar_metadata(zip_candidates[0], metadata_path)
            trace.update(base_trace)
            return spool, trace
        spool = _zip_directory(import_path)
        with zipfile.ZipFile(spool) as archive:
            trace = {**base_trace, **legacy_zip_trace(archive.namelist())}
        spool.seek(0)
        return spool, trace

    metadata_path = import_path.with_name("metadata.json")
    if import_path.suffix.lower() == ".zip" and metadata_path.exists():
        spool, trace = _zip_with_sidecar_metadata(import_path, metadata_path)
        trace.update(base_trace)
        return spool, trace

    spool = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    spool.write(import_path.read_bytes())
    spool.seek(0)
    with zipfile.ZipFile(spool) as archive:
        trace = {**base_trace, **legacy_zip_trace(archive.namelist())}
    spool.seek(0)
    return spool, trace


def _zip_directory(directory: Path):
    spool = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(directory).as_posix())
    spool.seek(0)
    return spool


def _metadata_arcnames(names: list[str]) -> list[str]:
    if any(PurePosixPath(name).name == "metadata.json" for name in names):
        return []
    arcnames = []
    for name in names:
        path = PurePosixPath(name)
        if path.name == "annotated_text.json":
            parent = path.parent.as_posix()
            arcnames.append("metadata.json" if parent == "." else f"{parent}/metadata.json")
    return list(dict.fromkeys(arcnames))


def _zip_with_sidecar_metadata(zip_path: Path, metadata_path: Path):
    spool = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    with zipfile.ZipFile(zip_path) as source:
        names = source.namelist()
        arcnames = _metadata_arcnames(names)
        trace = {
            **legacy_zip_trace(names),
            "source_zip_path": str(zip_path),
            "sidecar_metadata_path": str(metadata_path),
            "sidecar_metadata_exists": metadata_path.exists(),
            "injected_metadata_entries": arcnames if metadata_path.exists() else [],
        }
        if not arcnames or not metadata_path.exists():
            spool.write(zip_path.read_bytes())
        else:
            metadata_text = metadata_path.read_text(encoding="utf-8")
            with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as target:
                for info in source.infolist():
                    target.writestr(info, source.read(info.filename))
                for arcname in arcnames:
                    target.writestr(arcname, metadata_text)
            trace.update(legacy_zip_trace(names + arcnames))
    spool.seek(0)
    return spool, trace
