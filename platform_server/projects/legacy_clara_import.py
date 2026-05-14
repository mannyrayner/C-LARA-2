"""Import support for legacy C-LARA JSON export bundles.

Legacy C-LARA exports are ZIP files, either flat or rooted at one directory,
containing ``annotated_text.json`` plus optional ``audio/`` and ``images/`` folders.  This
module converts that hierarchical representation into C-LARA-2 project records
and stage artifacts so the imported project can be inspected and rerun using the
normal C-LARA-2 tooling.
"""
from __future__ import annotations

import copy
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
import zipfile

from core.config import DEFAULT_MODEL
from pipeline.stage_artifacts import write_stage_artifact

from .models import Project, ProjectImageElement, ProjectImagePage, ProjectImageStyle

LEGACY_CLARA_ANNOTATED_TEXT = "annotated_text.json"
LEGACY_CLARA_METADATA = "metadata.json"
LEGACY_CLARA_ROOT = "legacy_clara"
LEGACY_CLARA_COHERENT_IMAGES_DIR = "coherent_images_v2_project_dir"

LEGACY_CLARA_STAGE_NAMES = [
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

_LANGUAGE_MAP = {
    "arabic": "ar",
    "chinese": "zh",
    "mandarin": "zh",
    "mandarin chinese": "zh",
    "中文": "zh",
    "english": "en",
    "french": "fr",
    "german": "de",
    "hindi": "hi",
    "italian": "it",
    "japanese": "ja",
    "kok kaper": "xkk",
    "kok-kaper": "xkk",
    "kokkaper": "xkk",
    "korean": "ko",
    "portuguese": "pt",
    "spanish": "es",
}


@dataclass(slots=True)
class LegacyClaraImportResult:
    """Result returned after importing a legacy C-LARA bundle."""

    project: Project
    diagnostics: list[str] = field(default_factory=list)


class LegacyClaraImportError(ValueError):
    """Raised when a ZIP file is not a valid legacy C-LARA JSON bundle."""


def find_legacy_clara_bundle_root(names: list[str]) -> str | None:
    """Return the legacy bundle root, supporting both flat and rooted ZIPs."""

    if is_legacy_clara_bundle(names, ""):
        return ""

    candidate_roots = []
    for name in names:
        parts = PurePosixPath(name).parts
        if parts:
            candidate_roots.append(parts[0])
    for root in dict.fromkeys(candidate_roots):
        if root and is_legacy_clara_bundle(names, root):
            return root
    return None


def is_legacy_clara_bundle(names: list[str], root: str) -> bool:
    """Return ``True`` if ``names`` look like a legacy C-LARA JSON export."""

    name_set = set(names)
    required = {_bundle_member(root, LEGACY_CLARA_ANNOTATED_TEXT), _bundle_member(root, LEGACY_CLARA_METADATA)}
    return required.issubset(name_set)


def is_legacy_clara_project_dir_bundle(names: list[str]) -> bool:
    """Return True for legacy source.zip exports containing project_dir/ artifacts."""

    name_set = set(names)
    return "metadata.json" in name_set and "project_dir/metadata.json" in name_set


def legacy_clara_project_dir_bundle_title(zf: zipfile.ZipFile) -> str:
    """Return a best-effort title for a legacy project_dir export."""

    metadata = _read_optional_json(zf, "metadata.json")
    if isinstance(metadata, dict):
        for key in ("title", "name", "project_title"):
            if metadata.get(key):
                return str(metadata[key])
    project_metadata = _read_optional_json(zf, "project_dir/metadata.json")
    if isinstance(project_metadata, dict):
        for key in ("title", "name", "project_title"):
            if project_metadata.get(key):
                return str(project_metadata[key])
    return "Imported legacy C-LARA project"


def legacy_clara_bundle_title(zf: zipfile.ZipFile, root: str) -> str:
    """Return a best-effort title for a legacy C-LARA JSON export."""

    annotated = _read_json(zf, _bundle_member(root, LEGACY_CLARA_ANNOTATED_TEXT))
    if isinstance(annotated, dict):
        return _title_from_annotated_text(annotated)
    return "Imported legacy C-LARA project"


def import_legacy_clara_bundle(
    *,
    zf: zipfile.ZipFile,
    names: list[str],
    root: str,
    user: Any,
    unique_title: str,
) -> LegacyClaraImportResult:
    """Import a legacy C-LARA JSON export as a new C-LARA-2 project."""

    annotated = _read_json(zf, _bundle_member(root, LEGACY_CLARA_ANNOTATED_TEXT))
    legacy_metadata = _read_json(zf, _bundle_member(root, LEGACY_CLARA_METADATA))
    if not isinstance(annotated, dict):
        raise LegacyClaraImportError("Legacy C-LARA bundle has unreadable annotated_text.json.")
    if not isinstance(legacy_metadata, dict):
        raise LegacyClaraImportError("Legacy C-LARA bundle has unreadable metadata.json.")
    if not isinstance(annotated.get("pages"), list):
        raise LegacyClaraImportError("Legacy C-LARA annotated_text.json is missing a pages list.")

    diagnostics: list[str] = []
    title = unique_title or _title_from_annotated_text(annotated)
    language = _normalize_language(annotated.get("l2_language"), fallback="en")
    target_language = _normalize_language(annotated.get("l1_language"), fallback="fr")

    project = Project.objects.create(
        owner=user,
        title=title[:200] or "Imported legacy C-LARA project",
        description="Imported from a legacy C-LARA JSON export bundle.",
        source_text=_build_source_text(annotated)[:1000000],
        input_mode=Project.INPUT_SOURCE,
        language=language[:16],
        target_language=target_language[:16],
        ai_model=DEFAULT_MODEL[:64],
        page_image_placement=_image_placement_from_metadata(zf, root)[:16],
        page_image_text_source=Project.PAGE_IMAGE_TEXT_SOURCE_SEGMENTATION,
        # Keep project-level processing settings valid so users can rerun later
        # stages (for example compile_html -> compile_html) from the imported
        # artifacts without tripping the normal form validation. The stage
        # artifacts and import summary below retain legacy provenance.
        segmentation_method="auto",
        romanization_method="auto",
    )

    artifact_root = project.artifact_dir().resolve()
    # Test databases and restored deployments can reuse project identifiers while
    # leaving old artifact directories behind.  Start legacy imports from a clean
    # project artifact root so stale stage files cannot be mistaken for the new
    # imported run.
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    legacy_root = artifact_root / LEGACY_CLARA_ROOT
    legacy_root.mkdir(parents=True, exist_ok=True)

    _copy_legacy_tree(zf, names, root, legacy_root)
    stages_text, conversion_diagnostics = _convert_annotated_text(annotated, artifact_root=artifact_root)
    diagnostics.extend(conversion_diagnostics)
    stage_payloads = _legacy_stage_payloads(stages_text)

    run_dir = artifact_root / "runs" / f"run_legacy_clara_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    for stage_name in LEGACY_CLARA_STAGE_NAMES:
        write_stage_artifact(run_dir, stage_name, stage_payloads.get(stage_name, stages_text))
    (run_dir / "legacy_import_summary.json").write_text(
        json.dumps(
            {
                "source_format": "legacy_clara_json_export",
                "source_root": root,
                "stage_names": LEGACY_CLARA_STAGE_NAMES,
                "diagnostics": diagnostics,
                "metadata": legacy_metadata,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _restore_legacy_image_records(project=project, zf=zf, root=root, artifact_root=artifact_root, text=stages_text)
    _restore_legacy_coherent_image_records(
        project=project,
        zf=zf,
        names=names,
        root=root,
        artifact_root=artifact_root,
        text=stages_text,
    )
    return LegacyClaraImportResult(project=project, diagnostics=diagnostics)


def import_legacy_clara_project_dir_bundle(
    *,
    zf: zipfile.ZipFile,
    names: list[str],
    user: Any,
    unique_title: str,
) -> LegacyClaraImportResult:
    """Import a legacy C-LARA source.zip with project_dir/ artifacts."""

    legacy_metadata = _read_optional_json(zf, "metadata.json")
    project_metadata = _read_optional_json(zf, "project_dir/metadata.json")
    if not isinstance(legacy_metadata, dict):
        raise LegacyClaraImportError("Legacy C-LARA project_dir bundle has unreadable metadata.json.")
    if not isinstance(project_metadata, dict):
        raise LegacyClaraImportError("Legacy C-LARA project_dir bundle has unreadable project_dir/metadata.json.")

    diagnostics: list[str] = [
        "Imported from legacy C-LARA project_dir/source.zip layout; detailed annotations may need regeneration."
    ]
    source_text = _legacy_project_dir_source_text(zf, names)
    if not source_text.strip():
        diagnostics.append("Could not find readable source text under project_dir/plain or related text folders.")
        source_text = legacy_clara_project_dir_bundle_title(zf)
    annotated = _annotated_text_from_plain_text(
        source_text,
        title=legacy_clara_project_dir_bundle_title(zf),
        l2=legacy_metadata.get("l2") or legacy_metadata.get("language") or project_metadata.get("l2_language"),
        l1=legacy_metadata.get("l1") or legacy_metadata.get("target_language") or project_metadata.get("l1_language"),
    )

    title = unique_title or legacy_clara_project_dir_bundle_title(zf)
    language = _normalize_language(legacy_metadata.get("l2") or project_metadata.get("l2_language"), fallback="en")
    target_language = _normalize_language(legacy_metadata.get("l1") or project_metadata.get("l1_language"), fallback="fr")

    project = Project.objects.create(
        owner=user,
        title=title[:200] or "Imported legacy C-LARA project",
        description="Imported from a legacy C-LARA project_dir/source.zip export bundle.",
        source_text=source_text[:1000000],
        input_mode=Project.INPUT_SOURCE,
        language=language[:16],
        target_language=target_language[:16],
        ai_model=DEFAULT_MODEL[:64],
        page_image_placement=_image_placement_from_metadata(zf, "")[:16],
        page_image_text_source=Project.PAGE_IMAGE_TEXT_SOURCE_SEGMENTATION,
        segmentation_method="auto",
        romanization_method="auto",
    )

    artifact_root = project.artifact_dir().resolve()
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    legacy_root = artifact_root / LEGACY_CLARA_ROOT
    legacy_root.mkdir(parents=True, exist_ok=True)
    _copy_legacy_tree(zf, names, "", legacy_root)

    stages_text, conversion_diagnostics = _convert_annotated_text(annotated, artifact_root=artifact_root)
    diagnostics.extend(conversion_diagnostics)
    stage_payloads = _legacy_stage_payloads(stages_text)

    run_dir = artifact_root / "runs" / f"run_legacy_clara_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    for stage_name in LEGACY_CLARA_STAGE_NAMES:
        write_stage_artifact(run_dir, stage_name, stage_payloads.get(stage_name, stages_text))
    (run_dir / "legacy_import_summary.json").write_text(
        json.dumps(
            {
                "source_format": "legacy_clara_project_dir_export",
                "stage_names": LEGACY_CLARA_STAGE_NAMES,
                "diagnostics": diagnostics,
                "metadata": legacy_metadata,
                "project_dir_metadata": project_metadata,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _restore_legacy_image_records(project=project, zf=zf, root="", artifact_root=artifact_root, text=stages_text)
    _restore_legacy_coherent_image_records(
        project=project,
        zf=zf,
        names=names,
        root="",
        artifact_root=artifact_root,
        text=stages_text,
    )
    return LegacyClaraImportResult(project=project, diagnostics=diagnostics)


def _bundle_member(root: str, relpath: str) -> str:
    """Return a POSIX ZIP member path under ``root`` or at archive top level."""

    rel = relpath.strip("/")
    return f"{root}/{rel}" if root else rel


def _read_json(zf: zipfile.ZipFile, member: str) -> Any:
    try:
        with zf.open(member, "r") as fp:
            return json.loads(fp.read().decode("utf-8"))
    except Exception as exc:
        raise LegacyClaraImportError(f"Could not read {member} from legacy C-LARA bundle.") from exc


def _read_optional_json(zf: zipfile.ZipFile, member: str) -> Any:
    try:
        with zf.open(member, "r") as fp:
            return json.loads(fp.read().decode("utf-8"))
    except Exception:
        return None


def _read_text_member(zf: zipfile.ZipFile, member: str) -> str:
    with zf.open(member, "r") as fp:
        data = fp.read()
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _legacy_project_dir_source_text(zf: zipfile.ZipFile, names: list[str]) -> str:
    prefixes = (
        "project_dir/plain/",
        "project_dir/segmented/",
        "project_dir/segmented_with_images/",
        "project_dir/summary/",
    )
    candidates = [
        name
        for name in names
        if not name.endswith("/")
        and any(name.startswith(prefix) for prefix in prefixes)
        and PurePosixPath(name).name not in {"metadata.json", ".DS_Store"}
    ]
    for name in sorted(candidates, key=lambda item: (not item.startswith("project_dir/plain/"), item)):
        try:
            text = _read_text_member(zf, name).strip()
        except Exception:
            continue
        if text:
            return text
    return ""


def _annotated_text_from_plain_text(source_text: str, *, title: str, l2: Any, l1: Any) -> dict[str, Any]:
    return {
        "l2_language": l2 or "english",
        "l1_language": l1 or "english",
        "pages": [
            {
                "annotations": {"title": title},
                "segments": [
                    {
                        "annotations": {"translated": "", "mwes": [], "page_number": 1},
                        "content_elements": [
                            {"type": "NonWordText", "content": source_text, "annotations": {}},
                        ],
                    }
                ],
            }
        ],
    }


def _normalize_language(value: Any, *, fallback: str) -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return fallback
    if raw in _LANGUAGE_MAP:
        return _LANGUAGE_MAP[raw]
    if len(raw) <= 16 and raw.replace("-", "").isalnum():
        return raw
    return fallback


def _title_from_annotated_text(text: dict[str, Any]) -> str:
    for page in text.get("pages", []):
        if isinstance(page, dict):
            annotations = page.get("annotations") or {}
            title = annotations.get("title") if isinstance(annotations, dict) else None
            if title:
                return str(title)
    return "Imported legacy C-LARA project"


def _build_source_text(text: dict[str, Any]) -> str:
    page_surfaces = []
    for page in text.get("pages", []):
        if not isinstance(page, dict):
            continue
        segment_surfaces = []
        for segment in page.get("segments", []):
            if isinstance(segment, dict):
                segment_surfaces.append(_segment_surface(segment))
        page_surface = "".join(segment_surfaces).strip()
        if page_surface:
            page_surfaces.append(page_surface)
    return "\n\n".join(page_surfaces)


def _segment_surface(segment: dict[str, Any]) -> str:
    parts: list[str] = []
    for element in segment.get("content_elements", []):
        if not isinstance(element, dict):
            continue
        if element.get("type") in {"Word", "NonWordText"}:
            parts.append(str(element.get("content") or ""))
    return "".join(parts)


def _image_placement_from_metadata(zf: zipfile.ZipFile, root: str) -> str:
    try:
        image_metadata = _read_json(zf, _bundle_member(root, "images/metadata.json"))
    except LegacyClaraImportError:
        return "none"
    if isinstance(image_metadata, list):
        for row in image_metadata:
            if not isinstance(row, dict):
                continue
            if row.get("image_type") == "page" and row.get("position") in {"top", "bottom"}:
                return str(row["position"])
    return "none"


def _copy_legacy_tree(zf: zipfile.ZipFile, names: list[str], root: str, target_root: Path) -> None:
    prefix = f"{root}/" if root else ""
    for member_name in names:
        if member_name.endswith("/"):
            continue
        if prefix and not member_name.startswith(prefix):
            continue
        rel_posix = member_name[len(prefix) :] if prefix else member_name
        rel = PurePosixPath(rel_posix)
        if rel.is_absolute() or ".." in rel.parts:
            continue
        target = (target_root / Path(*rel.parts)).resolve()
        try:
            target.relative_to(target_root.resolve())
        except ValueError:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member_name, "r") as fp:
            target.write_bytes(fp.read())


def _convert_annotated_text(text: dict[str, Any], *, artifact_root: Path) -> tuple[dict[str, Any], list[str]]:
    diagnostics: list[str] = []
    pages_out: list[dict[str, Any]] = []
    for page_index, page in enumerate(text.get("pages", []), start=1):
        if not isinstance(page, dict):
            diagnostics.append(f"Skipped non-object page at index {page_index}.")
            continue
        page_annotations = _convert_annotations(page.get("annotations") or {}, artifact_root=artifact_root, level="page")
        segments_out: list[dict[str, Any]] = []
        page_images: list[dict[str, Any]] = []
        for segment_index, segment in enumerate(page.get("segments", []), start=1):
            if not isinstance(segment, dict):
                diagnostics.append(f"Skipped non-object segment at page {page_index}, index {segment_index}.")
                continue
            tokens: list[dict[str, Any]] = []
            legacy_elements: list[dict[str, Any]] = []
            for element in segment.get("content_elements", []):
                if not isinstance(element, dict):
                    continue
                element_type = element.get("type")
                if element_type in {"Word", "NonWordText"}:
                    annotations = _convert_annotations(element.get("annotations") or {}, artifact_root=artifact_root, level="token")
                    token = {"surface": str(element.get("content") or ""), "annotations": annotations}
                    if element_type == "NonWordText":
                        token["kind"] = "non_word_text"
                    tokens.append(token)
                elif element_type == "Image" and isinstance(element.get("content"), dict):
                    image = dict(element["content"])
                    image["path"] = _legacy_asset_path(image.get("src"), "images", artifact_root)
                    image["thumbnail_path"] = _legacy_asset_path(image.get("thumbnail_src"), "images", artifact_root)
                    page_images.append(image)
                    legacy_elements.append({"type": "Image", "content": image})
                elif element_type == "Markup":
                    legacy_elements.append({"type": "Markup", "content": element.get("content")})
                else:
                    diagnostics.append(
                        f"Preserved unsupported content element type {element_type!r} "
                        f"at page {page_index}, segment {segment_index}."
                    )
                    legacy_elements.append(dict(element))
            segment_annotations = _convert_annotations(segment.get("annotations") or {}, artifact_root=artifact_root, level="segment")
            if legacy_elements:
                segment_annotations["legacy_clara_content_elements"] = legacy_elements
            segment_out = {
                "surface": "".join(token.get("surface", "") for token in tokens),
                "tokens": tokens,
                "annotations": segment_annotations,
            }
            segments_out.append(segment_out)
        if page_images:
            page_annotations["legacy_clara_images"] = page_images
            first_image = page_images[0]
            if first_image.get("path"):
                page_annotations["generated_image"] = {
                    "path": first_image["path"],
                    "placement": "bottom",
                    "source": "legacy_clara_import",
                }
        pages_out.append(
            {
                "surface": "".join(segment.get("surface", "") for segment in segments_out),
                "segments": segments_out,
                "annotations": page_annotations,
            }
        )

    converted = {
        "l2": _normalize_language(text.get("l2_language"), fallback="en"),
        "l1": _normalize_language(text.get("l1_language"), fallback="fr"),
        "title": _title_from_annotated_text(text),
        "surface": "\n\n".join(page.get("surface", "") for page in pages_out if page.get("surface")),
        "pages": pages_out,
        "annotations": {
            "legacy_clara_annotations": text.get("annotations", {}),
            "legacy_clara_import": True,
        },
    }
    return converted, diagnostics


def _legacy_stage_payloads(converted: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return stage-specific payloads for converted legacy annotations.

    Later legacy-derived stages keep the rich annotation payload, but the two
    segmentation stages should look like normal C-LARA-2 segmentation outputs:
    phase 1 has only page/segment surfaces, while phase 2 adds token surfaces
    without token-level linguistic/audio annotations.
    """

    return {
        "segmentation_phase_1": _legacy_segmentation_phase_1_payload(converted),
        "segmentation_phase_2": _legacy_segmentation_phase_2_payload(converted),
    }


def _legacy_segmentation_phase_1_payload(converted: dict[str, Any]) -> dict[str, Any]:
    payload = _legacy_stage_payload_base(converted)
    pages: list[dict[str, Any]] = []
    for page in converted.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        segments: list[dict[str, Any]] = []
        for segment in page.get("segments", []) or []:
            if not isinstance(segment, dict):
                continue
            segments.append({"surface": str(segment.get("surface") or ""), "annotations": {}})
        pages.append(
            {
                "surface": str(page.get("surface") or ""),
                "segments": segments,
                "annotations": {},
            }
        )
    payload["pages"] = pages
    return payload


def _legacy_segmentation_phase_2_payload(converted: dict[str, Any]) -> dict[str, Any]:
    payload = _legacy_stage_payload_base(converted)
    pages: list[dict[str, Any]] = []
    for page in converted.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        segments: list[dict[str, Any]] = []
        for segment in page.get("segments", []) or []:
            if not isinstance(segment, dict):
                continue
            tokens: list[dict[str, Any]] = []
            for token in segment.get("tokens", []) or []:
                if not isinstance(token, dict):
                    continue
                token_out = {"surface": str(token.get("surface") or "")}
                if token.get("kind"):
                    token_out["kind"] = token.get("kind")
                tokens.append(token_out)
            segments.append(
                {
                    "surface": str(segment.get("surface") or ""),
                    "tokens": tokens,
                    "annotations": {},
                }
            )
        pages.append(
            {
                "surface": str(page.get("surface") or ""),
                "segments": segments,
                "annotations": {},
            }
        )
    payload["pages"] = pages
    return payload


def _legacy_stage_payload_base(converted: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in ("l2", "l1", "title", "surface"):
        if key in converted:
            payload[key] = copy.deepcopy(converted[key])
    payload["annotations"] = {"legacy_clara_import": True}
    return payload


def _convert_annotations(annotations: dict[str, Any], *, artifact_root: Path, level: str) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    for key, value in annotations.items():
        if key == "translated":
            converted["translation"] = value
        elif key == "tts" and isinstance(value, dict):
            converted["tts"] = value
            audio = _audio_annotation_from_tts(value, artifact_root=artifact_root, level=level)
            if audio:
                converted["audio"] = audio
        else:
            converted[key] = value
    return converted


def _audio_annotation_from_tts(tts: dict[str, Any], *, artifact_root: Path, level: str) -> dict[str, Any] | None:
    file_path = str(tts.get("file_path") or "").strip()
    if not file_path:
        return None
    normalized = PurePosixPath(file_path.replace("\\", "/"))
    filename = normalized.name
    if not filename:
        return None
    imported_path = artifact_root / LEGACY_CLARA_ROOT / "audio" / filename
    return {
        "path": str(imported_path),
        "engine": tts.get("engine_id") or "legacy_clara_tts",
        "voice": tts.get("voice_id") or "default",
        "language": tts.get("language_id"),
        "level": level,
        "source": "legacy_clara_import",
    }


def _legacy_asset_path(value: Any, subdir: str, artifact_root: Path) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = PurePosixPath(raw.replace("\\", "/"))
    filename = normalized.name
    if not filename:
        return ""
    return str(artifact_root / LEGACY_CLARA_ROOT / subdir / filename)


def _restore_legacy_image_records(
    *, project: Project, zf: zipfile.ZipFile, root: str, artifact_root: Path, text: dict[str, Any]
) -> None:
    try:
        image_metadata = _read_json(zf, _bundle_member(root, "images/metadata.json"))
    except LegacyClaraImportError:
        return
    if not isinstance(image_metadata, list):
        return

    for row in image_metadata:
        if not isinstance(row, dict):
            continue
        image_type = row.get("image_type")
        image_rel_path = _legacy_asset_path(row.get("image_file_path"), "images", artifact_root)
        if image_type == "style":
            ProjectImageStyle.objects.update_or_create(
                project=project,
                defaults={
                    "style_brief": row.get("advice") or row.get("style_description") or "Legacy C-LARA imported style",
                    "expanded_style_description": row.get("style_description") or "",
                    "sample_image_prompt": row.get("user_prompt") or row.get("advice") or "",
                    "sample_image_path": _relative_to_artifact_root(image_rel_path, artifact_root),
                    "status": ProjectImageStyle.STATUS_APPROVED,
                    "ai_model": DEFAULT_MODEL,
                },
            )
        elif image_type == "page":
            page_number = row.get("page")
            if not isinstance(page_number, int):
                continue
            ProjectImagePage.objects.update_or_create(
                project=project,
                page_number=page_number,
                defaults={
                    "page_text": _page_text(text, page_number),
                    "generation_prompt": row.get("user_prompt") or row.get("content_description") or "",
                    "image_path": _relative_to_artifact_root(image_rel_path, artifact_root),
                    "status": ProjectImagePage.STATUS_APPROVED,
                },
            )



def _restore_legacy_coherent_image_records(
    *, project: Project, zf: zipfile.ZipFile, names: list[str], root: str, artifact_root: Path, text: dict[str, Any]
) -> None:
    """Restore C-LARA coherent-images-v2 intermediates into C-LARA-2 image records.

    Newer legacy JSON exports may include ``coherent_images_v2_project_dir``.
    The directory has the same conceptual artifacts as the C-LARA-2 image
    pipeline (style, recurring elements, and page images), so import the useful
    editable records while still preserving the original directory under
    ``legacy_clara/`` via ``_copy_legacy_tree``.
    """

    coherent_prefix = _bundle_member(root, LEGACY_CLARA_COHERENT_IMAGES_DIR)
    prefix_with_slash = f"{coherent_prefix}/"
    if not any(name.startswith(prefix_with_slash) for name in names):
        return

    _restore_legacy_coherent_style(project=project, zf=zf, root=root, artifact_root=artifact_root)
    _restore_legacy_coherent_elements(project=project, zf=zf, names=names, root=root, artifact_root=artifact_root)
    _restore_legacy_coherent_pages(project=project, zf=zf, names=names, root=root, artifact_root=artifact_root, text=text)


def _restore_legacy_coherent_style(*, project: Project, zf: zipfile.ZipFile, root: str, artifact_root: Path) -> None:
    style_prefix = _bundle_member(root, f"{LEGACY_CLARA_COHERENT_IMAGES_DIR}/style")
    expanded_description = _read_optional_text(zf, f"{style_prefix}/expanded_description.txt")
    image_member = _first_existing_member(
        zf,
        [
            f"{style_prefix}/image.jpg",
            f"{style_prefix}/image.jpeg",
            f"{style_prefix}/image.png",
        ],
    )
    if not expanded_description and not image_member:
        return

    style, _created = ProjectImageStyle.objects.get_or_create(
        project=project,
        defaults={
            "style_brief": "Legacy C-LARA imported coherent image style",
            "ai_model": DEFAULT_MODEL,
            "status": ProjectImageStyle.STATUS_APPROVED,
        },
    )
    if expanded_description:
        style.expanded_style_description = expanded_description
        if not style.style_brief:
            style.style_brief = expanded_description[:500]
    if image_member:
        style.sample_image_path = _relative_member_path(image_member, root)
    if not style.status or style.status == ProjectImageStyle.STATUS_DRAFT:
        style.status = ProjectImageStyle.STATUS_APPROVED
    style.save(
        update_fields=[
            "style_brief",
            "expanded_style_description",
            "sample_image_path",
            "status",
            "updated_at",
        ]
    )


def _restore_legacy_coherent_elements(
    *, project: Project, zf: zipfile.ZipFile, names: list[str], root: str, artifact_root: Path
) -> None:
    elements_prefix = _bundle_member(root, f"{LEGACY_CLARA_COHERENT_IMAGES_DIR}/elements")
    element_dirs = _direct_child_dirs(names, elements_prefix)
    element_rows = _legacy_coherent_element_rows(_read_optional_json(zf, f"{elements_prefix}/elements.json"))

    rows_by_dir: dict[str, dict[str, Any]] = {}
    rows_without_dir: list[dict[str, Any]] = []
    for row in element_rows:
        explicit_dir = _coherent_row_dir(row)
        if explicit_dir:
            rows_by_dir[_normalise_lookup_key(explicit_dir)] = row
        else:
            rows_without_dir.append(row)

    used_dirs: set[str] = set()
    for child_dir in sorted(element_dirs):
        row = rows_by_dir.get(_normalise_lookup_key(child_dir)) or _best_row_for_dir(child_dir, rows_without_dir)
        if row is not None:
            used_dirs.add(_normalise_lookup_key(child_dir))
        _upsert_legacy_coherent_element(
            project=project,
            zf=zf,
            root=root,
            elements_prefix=elements_prefix,
            child_dir=child_dir,
            row=row or {},
        )

    # If elements.json lists entries whose directories were not present or whose
    # names do not match directory names, still create editable C-LARA-2 element
    # rows from the metadata.
    for row in element_rows:
        explicit_dir = _coherent_row_dir(row)
        lookup = _normalise_lookup_key(explicit_dir or _coherent_row_name(row))
        if lookup and lookup in used_dirs:
            continue
        _upsert_legacy_coherent_element(
            project=project,
            zf=zf,
            root=root,
            elements_prefix=elements_prefix,
            child_dir=explicit_dir or "",
            row=row,
        )


def _upsert_legacy_coherent_element(
    *,
    project: Project,
    zf: zipfile.ZipFile,
    root: str,
    elements_prefix: str,
    child_dir: str,
    row: dict[str, Any],
) -> None:
    name = _coherent_row_name(row) or child_dir or "Element"
    expanded_description = ""
    image_member = ""
    if child_dir:
        element_prefix = f"{elements_prefix}/{child_dir}"
        expanded_description = _read_optional_text(zf, f"{element_prefix}/expanded_description.txt")
        image_member = _first_existing_member(
            zf,
            [
                f"{element_prefix}/image.jpg",
                f"{element_prefix}/image.jpeg",
                f"{element_prefix}/image.png",
            ],
        )
    expanded_description = expanded_description or str(
        row.get("expanded_description") or row.get("description") or row.get("prompt") or ""
    )
    image_path = _relative_member_path(image_member, root) if image_member else str(row.get("image_path") or "")
    page_refs = _coherent_page_refs(row)
    element_type = str(row.get("element_type") or row.get("type") or "character")[:64]
    ProjectImageElement.objects.update_or_create(
        project=project,
        name=str(name)[:255],
        defaults={
            "element_type": element_type,
            "page_refs": page_refs[:255],
            "expanded_description": expanded_description,
            "expanded_prompt": expanded_description,
            "image_path": image_path[:512],
            "is_confirmed": bool(image_path or expanded_description),
            "ai_model": DEFAULT_MODEL,
            "status": ProjectImageElement.STATUS_CONFIRMED if image_path else ProjectImageElement.STATUS_EXPANDED,
        },
    )


def _restore_legacy_coherent_pages(
    *, project: Project, zf: zipfile.ZipFile, names: list[str], root: str, artifact_root: Path, text: dict[str, Any]
) -> None:
    pages_prefix = _bundle_member(root, f"{LEGACY_CLARA_COHERENT_IMAGES_DIR}/pages")
    for child_dir in sorted(_direct_child_dirs(names, pages_prefix)):
        page_number = _page_number_from_name(child_dir)
        if page_number is None:
            continue
        page_prefix = f"{pages_prefix}/{child_dir}"
        expanded_description = _read_optional_text(zf, f"{page_prefix}/expanded_description.txt")
        image_member = _first_existing_member(
            zf,
            [
                f"{page_prefix}/image.jpg",
                f"{page_prefix}/image.jpeg",
                f"{page_prefix}/image.png",
            ],
        )
        if not expanded_description and not image_member:
            continue
        defaults = {
            "page_text": _page_text(text, page_number),
            "generation_prompt": expanded_description,
            "status": ProjectImagePage.STATUS_APPROVED if image_member else ProjectImagePage.STATUS_GENERATED,
        }
        if image_member:
            defaults["image_path"] = _relative_member_path(image_member, root)
        ProjectImagePage.objects.update_or_create(
            project=project,
            page_number=page_number,
            defaults=defaults,
        )


def _legacy_coherent_element_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("elements", "items", "characters"):
            if isinstance(payload.get(key), list):
                return _legacy_coherent_element_rows(payload[key])
        return [dict(payload)] if payload else []
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            rows.append(dict(item))
        elif item:
            rows.append({"name": str(item)})
    return rows


def _coherent_row_name(row: dict[str, Any]) -> str:
    for key in ("name", "element_name", "id", "label"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _coherent_row_dir(row: dict[str, Any]) -> str:
    for key in ("directory", "dir", "folder", "folder_name", "relative_path"):
        value = str(row.get(key) or "").strip().replace("\\", "/").strip("/")
        if value:
            return PurePosixPath(value).parts[-1]
    return ""


def _coherent_page_refs(row: dict[str, Any]) -> str:
    for key in ("page_refs", "pages", "page_numbers", "appears_on_pages"):
        value = row.get(key)
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        if value:
            return str(value)
    return ""


def _direct_child_dirs(names: list[str], prefix: str) -> set[str]:
    prefix_with_slash = f"{prefix}/"
    children: set[str] = set()
    for name in names:
        if not name.startswith(prefix_with_slash):
            continue
        rel = name[len(prefix_with_slash) :]
        parts = PurePosixPath(rel).parts
        if len(parts) >= 2:
            children.add(parts[0])
    children.discard("elements.json")
    return children


def _best_row_for_dir(child_dir: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    child_key = _normalise_lookup_key(child_dir)
    for row in rows:
        if _normalise_lookup_key(_coherent_row_name(row)) == child_key:
            return row
    return None


def _normalise_lookup_key(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _page_number_from_name(value: str) -> int | None:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _read_optional_text(zf: zipfile.ZipFile, member: str) -> str:
    try:
        with zf.open(member, "r") as fp:
            return fp.read().decode("utf-8").strip()
    except Exception:
        return ""


def _first_existing_member(zf: zipfile.ZipFile, candidates: list[str]) -> str:
    names = set(zf.namelist())
    for candidate in candidates:
        if candidate in names:
            return candidate
    return ""


def _relative_member_path(member: str, root: str) -> str:
    if not member:
        return ""
    prefix = f"{root}/" if root else ""
    rel = member[len(prefix) :] if prefix and member.startswith(prefix) else member
    return (PurePosixPath(LEGACY_CLARA_ROOT) / PurePosixPath(rel)).as_posix()


def _relative_to_artifact_root(path_str: str, artifact_root: Path) -> str:
    if not path_str:
        return ""
    try:
        return Path(path_str).resolve().relative_to(artifact_root.resolve()).as_posix()
    except Exception:
        return path_str


def _page_text(text: dict[str, Any], page_number: int) -> str:
    try:
        return str(text.get("pages", [])[page_number - 1].get("surface", ""))
    except Exception:
        return ""
