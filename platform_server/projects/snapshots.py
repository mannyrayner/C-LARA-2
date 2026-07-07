"""File-backed project snapshot helpers.

The functions in this module are deliberately callable from both Django views and
management commands/experiments.  Snapshots live under the project artifact tree
so they travel with the same storage root as pipeline outputs while being
excluded from the snapshotted artifact payload to avoid recursive copies.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import shutil
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from django.utils.text import slugify

from .models import Project, ProjectImageElement, ProjectImagePage, ProjectImagePageVariant, ProjectImageStyle

SNAPSHOTS_DIRNAME = "snapshots"
ARTIFACTS_DIRNAME = "artifacts"
MANIFEST_FILENAME = "manifest.json"

PROJECT_FIELD_NAMES = [
    field.name
    for field in Project._meta.fields
    if field.name not in {"id", "owner", "created_at", "updated_at"}
]
STYLE_FIELD_NAMES = [
    field.name
    for field in ProjectImageStyle._meta.fields
    if field.name not in {"id", "project", "created_at", "updated_at"}
]
ELEMENT_FIELD_NAMES = [
    field.name
    for field in ProjectImageElement._meta.fields
    if field.name not in {"id", "project", "created_at", "updated_at"}
]
PAGE_FIELD_NAMES = [
    field.name
    for field in ProjectImagePage._meta.fields
    if field.name not in {"id", "project", "preferred_variant", "created_at", "updated_at"}
]
VARIANT_FIELD_NAMES = [
    field.name
    for field in ProjectImagePageVariant._meta.fields
    if field.name not in {"id", "page", "created_at", "updated_at"}
]


@dataclass(frozen=True)
class ProjectSnapshot:
    """Summary of a saved project snapshot."""

    snapshot_id: str
    name: str
    created_at: str
    path: Path
    created_by: str = ""
    contains_gold_standard: bool = False
    gold_standard_components: tuple[str, ...] = ()


def snapshots_dir(project: Project) -> Path:
    return project.artifact_dir() / SNAPSHOTS_DIRNAME


def _safe_snapshot_id(name: str, created_at: str | None = None) -> str:
    base = slugify(name)[:60] or "snapshot"
    stamp = (created_at or timezone.now().strftime("%Y%m%d-%H%M%SZ")).replace(":", "").replace("-", "")
    return f"{stamp}-{base}"


def _manifest_path(project: Project, snapshot_id: str) -> Path:
    return snapshots_dir(project) / snapshot_id / MANIFEST_FILENAME


def _copy_project_artifacts(source_root: Path, target_root: Path) -> None:
    if not source_root.exists():
        _mkdir(target_root)
        return

    _mkdir(target_root)
    for source_path in _iter_artifact_paths(source_root):
        rel_path = source_path.relative_to(source_root)
        target_path = target_root / rel_path
        if source_path.is_dir():
            _mkdir(target_path)
            continue
        if not source_path.exists():
            continue
        _mkdir(target_path.parent)
        shutil.copy2(_windows_long_path(source_path), _windows_long_path(target_path))


def _iter_artifact_paths(source_root: Path):
    """Yield artifact paths while pruning nested snapshot directories.

    ``Path.rglob`` cannot prune after it has yielded a directory.  Because new
    snapshots live under the artifact root, using rglob can accidentally descend
    into the snapshot currently being written.  This explicit stack walk skips
    any directory named ``snapshots`` before recursing.
    """

    stack = [source_root]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(_windows_long_path(directory)))
        except FileNotFoundError:
            continue
        for entry in entries:
            source_path = directory / entry.name
            if entry.is_dir(follow_symlinks=False):
                if entry.name == SNAPSHOTS_DIRNAME:
                    continue
                stack.append(source_path)
            yield source_path


def _mkdir(path: Path) -> None:
    """Create a directory, using extended-length paths on Windows."""

    Path(_windows_long_path(path)).mkdir(parents=True, exist_ok=True)


def _remove_tree(path: Path) -> None:
    """Remove a directory tree, using extended-length paths on Windows."""

    shutil.rmtree(_windows_long_path(path), ignore_errors=True)


def _windows_long_path(path: Path) -> Path:
    """Return an extended-length Windows path for robust deep artifact copies."""

    if os.name != "nt":
        return path
    raw = str(path.resolve())
    extended_prefix = "\\\\?\\"
    if raw.startswith(extended_prefix):
        return Path(raw)
    if raw.startswith("\\\\"):
        return Path(f"{extended_prefix}UNC\\{raw[2:]}")
    return Path(f"{extended_prefix}{raw}")


def _replace_project_artifacts(project: Project, snapshot_artifacts: Path) -> None:
    artifact_root = project.artifact_dir()
    preserved_snapshots = artifact_root / SNAPSHOTS_DIRNAME
    artifact_root.mkdir(parents=True, exist_ok=True)
    for child in artifact_root.iterdir():
        if child == preserved_snapshots:
            continue
        if child.is_dir():
            _remove_tree(child)
        else:
            child.unlink()
    _copy_project_artifacts(snapshot_artifacts, artifact_root)


def _project_db_payload(project: Project) -> dict[str, Any]:
    preferred_by_page = {}
    pages = []
    variants = []
    for page in project.image_pages.prefetch_related("variants").order_by("page_number", "id"):
        page_payload = model_to_dict(page, fields=PAGE_FIELD_NAMES)
        pages.append(page_payload)
        if page.preferred_variant_id:
            preferred_by_page[str(page.page_number)] = page.preferred_variant.variant_index
        for variant in page.variants.order_by("variant_index", "id"):
            variant_payload = model_to_dict(variant, fields=VARIANT_FIELD_NAMES)
            variant_payload["page_number"] = page.page_number
            variants.append(variant_payload)

    style = getattr(project, "image_style", None)
    return {
        "project": model_to_dict(project, fields=PROJECT_FIELD_NAMES),
        "image_style": model_to_dict(style, fields=STYLE_FIELD_NAMES) if style else None,
        "image_elements": [
            model_to_dict(element, fields=ELEMENT_FIELD_NAMES)
            for element in project.image_elements.order_by("name", "id")
        ],
        "image_pages": pages,
        "image_page_variants": variants,
        "preferred_variants": preferred_by_page,
    }


def _restore_project_db_payload(project: Project, payload: dict[str, Any]) -> None:
    for field_name, value in (payload.get("project") or {}).items():
        setattr(project, field_name, value)
    project.save()

    ProjectImageStyle.objects.filter(project=project).delete()
    style_payload = payload.get("image_style")
    if style_payload:
        ProjectImageStyle.objects.create(project=project, **style_payload)

    project.image_elements.all().delete()
    for element_payload in payload.get("image_elements") or []:
        ProjectImageElement.objects.create(project=project, **element_payload)

    project.image_pages.all().delete()
    page_by_number: dict[int, ProjectImagePage] = {}
    for page_payload in payload.get("image_pages") or []:
        page = ProjectImagePage.objects.create(project=project, **page_payload)
        page_by_number[page.page_number] = page

    variant_by_page_and_index: dict[tuple[int, int], ProjectImagePageVariant] = {}
    for variant_payload in payload.get("image_page_variants") or []:
        page_number = variant_payload.pop("page_number")
        page = page_by_number.get(page_number)
        if not page:
            continue
        variant = ProjectImagePageVariant.objects.create(page=page, **variant_payload)
        variant_by_page_and_index[(page_number, variant.variant_index)] = variant

    for page_number_text, variant_index in (payload.get("preferred_variants") or {}).items():
        try:
            page_number = int(page_number_text)
        except (TypeError, ValueError):
            continue
        page = page_by_number.get(page_number)
        variant = variant_by_page_and_index.get((page_number, variant_index))
        if page and variant:
            page.preferred_variant = variant
            page.save(update_fields=["preferred_variant", "updated_at"])


def save_project_snapshot(
    project: Project,
    *,
    name: str,
    created_by: str = "",
    contains_gold_standard: bool = False,
    gold_standard_components: list[str] | tuple[str, ...] | None = None,
) -> ProjectSnapshot:
    """Save a named full-project snapshot and return its summary.

    The first version captures project DB fields, image prompt/selection rows, and
    the current artifact directory.  Snapshots themselves are excluded from the
    artifact copy so repeated saves do not recursively duplicate older snapshots.
    """

    clean_name = (name or "").strip()
    if not clean_name:
        raise ValidationError("Snapshot name is required.")
    components = tuple(component.strip() for component in (gold_standard_components or []) if component.strip())
    created_at = timezone.now().replace(microsecond=0).isoformat().replace("+00:00", "Z")
    snapshot_id = _safe_snapshot_id(clean_name)
    snapshot_root = snapshots_dir(project) / snapshot_id
    if snapshot_root.exists():
        raise ValidationError(f"Snapshot {snapshot_id!r} already exists.")
    snapshot_root.mkdir(parents=True)
    try:
        _copy_project_artifacts(project.artifact_dir(), snapshot_root / ARTIFACTS_DIRNAME)
    except Exception:
        _remove_tree(snapshot_root)
        raise
    manifest = {
        "schema_version": 1,
        "snapshot_id": snapshot_id,
        "name": clean_name,
        "created_at": created_at,
        "created_by": created_by,
        "contains_gold_standard": bool(contains_gold_standard),
        "gold_standard_components": list(components),
        "project_id": project.id,
        "project_title": project.title,
        "payload": _project_db_payload(project),
    }
    (snapshot_root / MANIFEST_FILENAME).write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
    return ProjectSnapshot(snapshot_id, clean_name, created_at, snapshot_root, created_by, bool(contains_gold_standard), components)


def load_project_snapshot(project: Project, snapshot_id: str) -> dict[str, Any]:
    path = _manifest_path(project, snapshot_id)
    if not path.exists():
        raise FileNotFoundError(f"Snapshot {snapshot_id!r} not found for project {project.id}.")
    return json.loads(path.read_text(encoding="utf-8"))


def list_project_snapshots(project: Project) -> list[ProjectSnapshot]:
    root = snapshots_dir(project)
    if not root.exists():
        return []
    snapshots: list[ProjectSnapshot] = []
    for manifest_path in sorted(root.glob(f"*/{MANIFEST_FILENAME}")):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        snapshots.append(
            ProjectSnapshot(
                snapshot_id=data.get("snapshot_id") or manifest_path.parent.name,
                name=data.get("name") or manifest_path.parent.name,
                created_at=data.get("created_at") or "",
                path=manifest_path.parent,
                created_by=data.get("created_by") or "",
                contains_gold_standard=bool(data.get("contains_gold_standard")),
                gold_standard_components=tuple(data.get("gold_standard_components") or ()),
            )
        )
    return sorted(snapshots, key=lambda item: item.created_at, reverse=True)


@transaction.atomic
def restore_project_snapshot(project: Project, *, snapshot_id: str) -> ProjectSnapshot:
    """Restore project DB state and artifacts from a snapshot."""

    manifest = load_project_snapshot(project, snapshot_id)
    snapshot_root = snapshots_dir(project) / snapshot_id
    _restore_project_db_payload(project, manifest.get("payload") or {})
    _replace_project_artifacts(project, snapshot_root / ARTIFACTS_DIRNAME)
    return ProjectSnapshot(
        snapshot_id=manifest.get("snapshot_id") or snapshot_id,
        name=manifest.get("name") or snapshot_id,
        created_at=manifest.get("created_at") or "",
        path=snapshot_root,
        created_by=manifest.get("created_by") or "",
        contains_gold_standard=bool(manifest.get("contains_gold_standard")),
        gold_standard_components=tuple(manifest.get("gold_standard_components") or ()),
    )
