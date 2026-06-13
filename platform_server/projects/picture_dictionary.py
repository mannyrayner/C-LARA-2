from __future__ import annotations

import json
import logging
import re
import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.urls import reverse
from pipeline.stage_artifacts import read_stage_artifact, stage_artifact_path, write_stage_artifact

from .models import (
    Community,
    CommunityMembership,
    PictureDictionary,
    PictureDictionaryEntry,
    Project,
    ProjectImagePage,
    ProjectImagePageVariant,
    ProjectImageStyle,
)

NON_AI_ENABLED_LANGUAGES = {"xkk", "iai", "dre"}

logger = logging.getLogger(__name__)


def _normalise_word(word: str) -> str:
    return re.sub(r"\s+", " ", str(word or "").strip())


def _extract_entries_from_plain_text(source_text: str) -> list[str]:
    if re.search(r"(?i)<\s*page\s*/?\s*>", source_text or ""):
        return [chunk.strip() for chunk in re.split(r"(?i)<\s*page\s*/?\s*>", source_text or "") if chunk.strip()]
    return [line.strip() for line in (source_text or "").splitlines() if line.strip()]


def _sync_project_source_from_registry(dictionary: PictureDictionary) -> None:
    entries = list(dictionary.entries.filter(is_active=True).order_by("id"))
    dictionary.project.source_text = "\n".join(entry.surface for entry in entries)
    dictionary.project.input_mode = Project.INPUT_SOURCE
    dictionary.project.save(update_fields=["source_text", "input_mode", "updated_at"])


def _bootstrap_registry_from_project_source(dictionary: PictureDictionary) -> None:
    if dictionary.entries.exists():
        return
    for surface in _extract_entries_from_plain_text(dictionary.project.source_text or ""):
        PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface=surface,
            lemma=surface,
            pos="",
            is_active=True,
        )


def _require_organiser(community: Community, user) -> None:
    is_organiser = CommunityMembership.objects.filter(
        community=community,
        user=user,
        role=CommunityMembership.ROLE_ORGANISER,
    ).exists()
    if not is_organiser:
        raise PermissionDenied("User must be a community organiser to manage picture dictionaries.")


def _unique_project_title(owner, base_title: str) -> str:
    candidate = (base_title or "Picture dictionary").strip() or "Picture dictionary"
    if len(candidate) > 200:
        candidate = candidate[:200].rstrip()
    if not Project.objects.filter(owner=owner, title=candidate).exists():
        return candidate
    root = candidate[:190].rstrip()
    for idx in range(2, 200):
        titled = f"{root} ({idx})"
        if not Project.objects.filter(owner=owner, title=titled).exists():
            return titled
    return f"{root} ({datetime.now(timezone.utc).strftime('%H%M%S')})"[:200]


def _latest_stage_payload(project: Project, stage_name: str) -> dict | None:
    runs_root = project.artifact_dir() / "runs"
    if not runs_root.exists():
        return None
    newest_run: Path | None = None
    newest_mtime = float("-inf")
    for run_dir in runs_root.iterdir():
        if not run_dir.is_dir():
            continue
        candidate = stage_artifact_path(run_dir, stage_name)
        if not candidate.exists():
            continue
        mtime = candidate.stat().st_mtime
        if mtime > newest_mtime:
            newest_run = run_dir
            newest_mtime = mtime
    if newest_run is None:
        return None
    try:
        payload = read_stage_artifact(newest_run, stage_name)
    except Exception:
        logger.exception("Could not read %s stage for project %s", stage_name, project.pk)
        return None
    return payload if isinstance(payload, dict) else None


def _non_null_text(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.casefold() in {"none", "null"}:
        return ""
    return text


def _token_surface_is_word(surface: str) -> bool:
    return bool(re.search(r"\w", surface or "", flags=re.UNICODE))


def _token_gloss_or_translation(token: dict) -> str:
    annotations = token.get("annotations") or {}
    return _non_null_text(annotations.get("gloss")) or _non_null_text(annotations.get("translation"))


def _first_glossed_or_translated_token(page: dict) -> dict | None:
    for segment in page.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        for token in segment.get("tokens") or []:
            if not isinstance(token, dict):
                continue
            surface = _normalise_word(token.get("surface") or "")
            if not surface or not _token_surface_is_word(surface):
                continue
            if _token_gloss_or_translation(token):
                return token
    return None


def _page_import_image_path(page: dict) -> str:
    annotations = page.get("annotations") or {}
    generated_image = annotations.get("generated_image") or {}
    if isinstance(generated_image, dict):
        path = str(generated_image.get("path") or "").strip()
        if path:
            return path
    legacy_images = annotations.get("legacy_clara_images") or []
    if isinstance(legacy_images, list):
        for image in legacy_images:
            if not isinstance(image, dict):
                continue
            path = str(image.get("path") or image.get("image_path") or "").strip()
            if path:
                return path
    return ""


def _extract_dictionary_seed_pages(source_project: Project) -> tuple[list[dict], list[str]]:
    lemma_payload = _latest_stage_payload(source_project, "lemma") or {}
    lemma_pos_by_page_surface: dict[tuple[int, str], tuple[str, str]] = {}
    for page_number, lemma_page in enumerate(lemma_payload.get("pages") or [], start=1):
        if not isinstance(lemma_page, dict):
            continue
        for segment in lemma_page.get("segments") or []:
            if not isinstance(segment, dict):
                continue
            for token in segment.get("tokens") or []:
                if not isinstance(token, dict):
                    continue
                surface = _normalise_word(token.get("surface") or "")
                if not surface or not _token_surface_is_word(surface):
                    continue
                ann = token.get("annotations") or {}
                lemma_value = _normalise_word(ann.get("lemma") or surface)
                pos_value = _normalise_word(ann.get("pos") or "").upper()
                lemma_pos_by_page_surface[(page_number, surface.casefold())] = (lemma_value, pos_value)

    seg1_payload = _latest_stage_payload(source_project, "segmentation_phase_1") or {}
    seg1_surface_by_page: dict[int, str] = {}
    for page_number, seg1_page in enumerate(seg1_payload.get("pages") or [], start=1):
        if not isinstance(seg1_page, dict):
            continue
        seg1_surface = _normalise_word(seg1_page.get("surface") or "")
        if seg1_surface and _token_surface_is_word(seg1_surface):
            seg1_surface_by_page[page_number] = seg1_surface

    payload = None
    for stage_name in ("gloss", "lemma", "translation", "segmentation_phase_2", "segmentation_phase_1"):
        payload = _latest_stage_payload(source_project, stage_name)
        if payload and payload.get("pages"):
            break
    diagnostics: list[str] = []
    if not payload:
        diagnostics.append("No stage payload with pages was found on the source project.")
        return [], diagnostics

    source_pages = list(payload.get("pages") or [])
    image_pages = {
        row.page_number: row
        for row in source_project.image_pages.select_related("preferred_variant").order_by("page_number", "id")
    }
    retained: list[dict] = []
    discarded_without_translation = 0
    discarded_without_word = 0
    for old_page_number, page in enumerate(source_pages, start=1):
        if not isinstance(page, dict):
            continue
        token = _first_glossed_or_translated_token(page)
        if token is None:
            discarded_without_translation += 1
            continue
        fallback_surface = _normalise_word(token.get("surface") or page.get("surface") or "")
        preferred_surface = seg1_surface_by_page.get(old_page_number, "")
        surface = preferred_surface or fallback_surface
        if not surface:
            discarded_without_word += 1
            continue
        annotations = (token or {}).get("annotations") or {}
        fallback_lemma, fallback_pos = lemma_pos_by_page_surface.get(
            (old_page_number, surface.casefold()),
            ("", ""),
        )
        retained.append(
            {
                "old_page_number": old_page_number,
                "surface": surface,
                "lemma": _normalise_word(annotations.get("lemma") or fallback_lemma or surface),
                "pos": _normalise_word(annotations.get("pos") or fallback_pos or "").upper(),
                "gloss": _non_null_text(annotations.get("gloss")),
                "translation": _non_null_text(annotations.get("translation")),
                "image_path": _page_import_image_path(page),
                "image_page": image_pages.get(old_page_number),
            }
        )
    diagnostics.append(f"Retained {len(retained)} page(s) with token-level glosses/translations.")
    if discarded_without_translation:
        diagnostics.append(f"Discarded {discarded_without_translation} page(s) without token-level glosses/translations.")
    if discarded_without_word:
        diagnostics.append(f"Discarded {discarded_without_word} translated page(s) without a usable word surface.")
    return retained, diagnostics


def _copy_project_artifacts(source_project: Project, target_project: Project) -> None:
    source_root = source_project.artifact_dir()
    target_root = target_project.artifact_dir()
    if target_root.exists():
        shutil.rmtree(target_root)
    if source_root.exists():
        shutil.copytree(source_root, target_root, dirs_exist_ok=True)
    else:
        target_root.mkdir(parents=True, exist_ok=True)


def _copy_project_image_style(source_project: Project, target_project: Project) -> None:
    style = getattr(source_project, "image_style", None)
    if not style:
        return
    ProjectImageStyle.objects.update_or_create(
        project=target_project,
        defaults={
            "style_brief": style.style_brief,
            "expanded_style_description": style.expanded_style_description,
            "representative_excerpt": style.representative_excerpt,
            "sample_image_prompt": style.sample_image_prompt,
            "sample_image_path": style.sample_image_path,
            "sample_image_revised_prompt": style.sample_image_revised_prompt,
            "sample_image_model": style.sample_image_model,
            "discourage_text_in_images": False,
            "disallow_text_in_images": True,
            "ai_model": style.ai_model,
            "status": style.status,
        },
    )


def _apply_picture_dictionary_image_defaults(project: Project) -> None:
    language = (project.language or "").strip().lower()
    project.page_image_text_source = (
        Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION
        if language in NON_AI_ENABLED_LANGUAGES
        else Project.PAGE_IMAGE_TEXT_SOURCE_SEGMENTATION
    )
    project.save(update_fields=["page_image_text_source", "updated_at"])
    style, _ = ProjectImageStyle.objects.get_or_create(
        project=project,
        defaults={"ai_model": project.ai_model or "gpt-4o"},
    )
    update_fields: list[str] = []
    if style.discourage_text_in_images:
        style.discourage_text_in_images = False
        update_fields.append("discourage_text_in_images")
    if not bool(getattr(style, "disallow_text_in_images", False)):
        style.disallow_text_in_images = True
        update_fields.append("disallow_text_in_images")
    if update_fields:
        update_fields.append("updated_at")
        style.save(update_fields=update_fields)


@transaction.atomic
def import_project_as_picture_dictionary(
    *,
    community: Community,
    organiser,
    source_project: Project,
) -> tuple[PictureDictionary, dict[str, object]]:
    """Create/update a community picture dictionary from a dictionary-like project copy.

    The initial importer is intentionally conservative: it keeps only pages that
    contain at least one non-null translation annotation, which discards title or
    cover pages in projects such as ``50 words in Kok Kaper`` while preserving
    approved word/image pages as dictionary entries.
    """

    _require_organiser(community, organiser)
    if source_project.community_id != community.id:
        raise PermissionDenied("Source project must belong to the organiser's community.")

    retained_pages, diagnostics = _extract_dictionary_seed_pages(source_project)
    if not retained_pages:
        raise ValueError("No dictionary entries found. The source project needs pages with non-null translations.")

    title = _unique_project_title(organiser, f"{source_project.title} picture dictionary")
    target_project = Project.objects.create(
        owner=organiser,
        title=title,
        description=(
            f"Picture dictionary for {community.name}, copied from project “{source_project.title}”. "
            "Pages without non-null translations were discarded during import."
        ),
        source_text="\n".join(row["surface"] for row in retained_pages)[:1000000],
        input_mode=Project.INPUT_SOURCE,
        language=(community.language or source_project.language or "en")[:16],
        target_language=(source_project.target_language or community.language or source_project.language or "en")[:16],
        ai_model=source_project.ai_model,
        page_image_placement=source_project.page_image_placement,
        image_generation_pivot_language=source_project.image_generation_pivot_language,
        page_image_text_source=source_project.page_image_text_source,
        segmentation_method=source_project.segmentation_method or "auto",
        romanization_method=source_project.romanization_method or "auto",
        access_scope=Project.ACCESS_COMMUNITY,
        community=community,
    )
    _copy_project_artifacts(source_project, target_project)
    _copy_project_image_style(source_project, target_project)
    _apply_picture_dictionary_image_defaults(target_project)

    dictionary = PictureDictionary.objects.select_related("project").filter(community=community).first()
    old_project_id = dictionary.project_id if dictionary else None
    if dictionary:
        dictionary.entries.all().delete()
        dictionary.project = target_project
        dictionary.organiser = organiser
        dictionary.language = community.language or target_project.language
        dictionary.is_active = True
        dictionary.save(update_fields=["project", "organiser", "language", "is_active", "updated_at"])
    else:
        dictionary = PictureDictionary.objects.create(
            community=community,
            project=target_project,
            organiser=organiser,
            language=community.language or target_project.language,
        )

    page_map: dict[int, int] = {}
    created_entries: list[PictureDictionaryEntry] = []
    for new_page_number, row in enumerate(retained_pages, start=1):
        image_page = row.get("image_page")
        image_path = (getattr(image_page, "image_path", "") if image_page else "") or str(row.get("image_path") or "")
        entry = PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface=str(row["surface"]),
            lemma=str(row.get("lemma") or row["surface"]),
            pos=str(row.get("pos") or ""),
            image_path=image_path or "",
            current_page_number=new_page_number,
            is_active=True,
        )
        page = ProjectImagePage.objects.create(
            project=target_project,
            page_number=new_page_number,
            page_text=str(row["surface"]),
            generation_prompt=(
                (getattr(image_page, "generation_prompt", "") or str(row["surface"]))
                if image_page
                else str(row["surface"])
            ),
            image_model=getattr(image_page, "image_model", "gpt-image-1") if image_page else "gpt-image-1",
            image_path=image_path or "",
            image_revised_prompt=getattr(image_page, "image_revised_prompt", "") if image_page else "",
            status=(
                getattr(image_page, "status", ProjectImagePage.STATUS_APPROVED)
                if image_page
                else ProjectImagePage.STATUS_APPROVED
            ),
        )
        page_map[int(row["old_page_number"])] = new_page_number
        if image_page:
            preferred_variant = None
            for variant in image_page.variants.order_by("variant_index", "id"):
                copied_variant = ProjectImagePageVariant.objects.create(
                    page=page,
                    variant_index=variant.variant_index,
                    image_model=variant.image_model,
                    image_path=variant.image_path,
                    generation_prompt=variant.generation_prompt,
                    image_revised_prompt=variant.image_revised_prompt,
                    status=variant.status,
                )
                if image_page.preferred_variant_id == variant.id:
                    preferred_variant = copied_variant
            if preferred_variant:
                page.preferred_variant = preferred_variant
                page.save(update_fields=["preferred_variant", "updated_at"])
        if not entry.image_path and page.image_path:
            entry.image_path = page.image_path
            entry.save(update_fields=["image_path", "updated_at"])
        created_entries.append(entry)

    _write_segmentation_phase_1(dictionary, created_entries)
    _write_imported_dictionary_annotation_stages(dictionary, retained_pages)

    summary = {
        "source_project_id": source_project.id,
        "source_project_title": source_project.title,
        "target_project_id": target_project.id,
        "old_dictionary_project_id": old_project_id,
        "entries_created": len(retained_pages),
        "filter": "token_level_gloss_or_translation",
        "page_map": page_map,
        "diagnostics": diagnostics,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Keep the JSON dependency local to the summary-write path. This makes the
    # organiser import robust if a deployment accidentally has an older module
    # body loaded without the module-level import after a hot reload.
    import json as summary_json

    summary_dir = target_project.artifact_dir() / "picture_dictionary_import"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "summary.json").write_text(
        summary_json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _sync_project_source_from_registry(dictionary)
    return dictionary, summary


@transaction.atomic
def ensure_picture_dictionary_for_community(*, community: Community, organiser) -> PictureDictionary:
    _require_organiser(community, organiser)
    existing = (
        PictureDictionary.objects.select_related("project")
        .filter(community=community)
        .order_by("-is_active", "-id")
        .first()
    )
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.organiser = organiser
            existing.language = community.language or existing.project.language
            existing.save(update_fields=["is_active", "organiser", "language", "updated_at"])
        _bootstrap_registry_from_project_source(existing)
        _sync_project_source_from_registry(existing)
        return existing
    project = Project.objects.create(
        owner=organiser,
        title=_unique_project_title(organiser, f"{community.name} picture dictionary"),
        description=f"Picture dictionary for {community.name} ({community.language or 'language unspecified'}).",
        input_mode=Project.INPUT_SOURCE,
        source_text="",
        language=community.language or "en",
        target_language=community.language or "en",
        access_scope=Project.ACCESS_COMMUNITY,
        community=community,
    )
    dictionary = PictureDictionary.objects.create(
        community=community,
        project=project,
        organiser=organiser,
        language=community.language or project.language,
    )
    _apply_picture_dictionary_image_defaults(project)
    return dictionary


def add_words(*, dictionary: PictureDictionary, words: Iterable[str]) -> int:
    _bootstrap_registry_from_project_source(dictionary)
    existing = {entry.surface.casefold(): entry for entry in dictionary.entries.order_by("id")}
    added = 0
    for word in words:
        normalized = _normalise_word(word)
        if not normalized:
            continue
        key = normalized.casefold()
        row = existing.get(key)
        if row and row.is_active:
            continue
        if row and not row.is_active:
            row.is_active = True
            row.save(update_fields=["is_active", "updated_at"])
        else:
            created = PictureDictionaryEntry.objects.create(
                dictionary=dictionary,
                surface=normalized,
                lemma=normalized,
                pos="",
                is_active=True,
            )
            existing[key] = created
        added += 1
    _sync_project_source_from_registry(dictionary)
    _refresh_dictionary_placeholder_stages(dictionary)
    return added


def remove_words(*, dictionary: PictureDictionary, words: Iterable[str]) -> int:
    _bootstrap_registry_from_project_source(dictionary)
    removal_keys = {_normalise_word(word).casefold() for word in words if _normalise_word(word)}
    if not removal_keys:
        return 0
    removed = 0
    for entry in dictionary.entries.filter(is_active=True):
        if entry.surface.casefold() in removal_keys:
            entry.is_active = False
            entry.current_page_number = None
            entry.image_path = ""
            entry.save(update_fields=["is_active", "current_page_number", "image_path", "updated_at"])
            removed += 1
    if removed:
        _sync_project_source_from_registry(dictionary)
        _refresh_dictionary_placeholder_stages(dictionary)
    return removed


def remove_entries_by_ids(*, dictionary: PictureDictionary, entry_ids: Iterable[int]) -> int:
    ids = {int(pk) for pk in entry_ids}
    removed = 0
    for entry in dictionary.entries.filter(id__in=ids, is_active=True):
        entry.is_active = False
        entry.current_page_number = None
        entry.image_path = ""
        entry.save(update_fields=["is_active", "current_page_number", "image_path", "updated_at"])
        removed += 1
    if removed:
        _sync_project_source_from_registry(dictionary)
        _refresh_dictionary_placeholder_stages(dictionary)
    return removed


def clear_entries(*, dictionary: PictureDictionary) -> int:
    removed = 0
    for entry in dictionary.entries.filter(is_active=True):
        entry.is_active = False
        entry.current_page_number = None
        entry.image_path = ""
        entry.save(update_fields=["is_active", "current_page_number", "image_path", "updated_at"])
        removed += 1
    if removed:
        _sync_project_source_from_registry(dictionary)
        _refresh_dictionary_placeholder_stages(dictionary)
    return removed


def add_manual_rows(*, dictionary: PictureDictionary, rows: Iterable[dict[str, str]]) -> dict[str, int]:
    """Add/update fully annotated picture-dictionary rows from organiser input.

    Low-resource community organisers use this path to enter the metadata that
    would otherwise have to be added later in the page-oriented annotation
    editor.  The submitted gloss is always reused as the page translation for
    this picture-dictionary workflow.
    """

    _bootstrap_registry_from_project_source(dictionary)
    existing_by_surface = {
        _normalise_word(entry.surface).casefold(): entry
        for entry in dictionary.entries.order_by("id")
        if _normalise_word(entry.surface)
    }
    submitted_by_surface: dict[str, dict[str, str]] = {}
    added = 0
    updated = 0
    skipped = 0

    for raw_row in rows:
        surface = _normalise_word(raw_row.get("surface") or "")
        if not surface:
            skipped += 1
            continue
        lemma = _normalise_word(raw_row.get("lemma") or surface)
        pos = _normalise_word(raw_row.get("pos") or "").upper()
        gloss = _non_null_text(raw_row.get("gloss"))
        translation = gloss
        key = surface.casefold()
        entry = existing_by_surface.get(key)
        if entry is None:
            entry = PictureDictionaryEntry.objects.create(
                dictionary=dictionary,
                surface=surface,
                lemma=lemma,
                pos=pos,
                is_active=True,
            )
            existing_by_surface[key] = entry
            added += 1
        else:
            changed_fields: list[str] = []
            if not entry.is_active:
                entry.is_active = True
                changed_fields.append("is_active")
            if entry.surface != surface:
                entry.surface = surface
                changed_fields.append("surface")
            if entry.lemma != lemma:
                entry.lemma = lemma
                changed_fields.append("lemma")
            if entry.pos != pos:
                entry.pos = pos
                changed_fields.append("pos")
            if changed_fields:
                changed_fields.append("updated_at")
                entry.save(update_fields=changed_fields)
            # Gloss/translation live in stage artifacts rather than the registry
            # row, so a submitted metadata row still counts as an update even
            # when the database fields already matched.
            updated += 1
        submitted_by_surface[key] = {
            "surface": surface,
            "lemma": lemma,
            "pos": pos,
            "gloss": gloss,
            "translation": translation,
        }

    active_entries = list(dictionary.entries.filter(is_active=True).order_by("id"))
    _sync_project_source_from_registry(dictionary)
    _sync_dictionary_project_pages(dictionary, active_entries)
    _write_segmentation_phase_1(dictionary, active_entries)
    manual_rows = _manual_rows_from_entries(dictionary, active_entries)
    for row in manual_rows:
        submitted = submitted_by_surface.get(_normalise_word(row.get("surface") or "").casefold())
        if not submitted:
            continue
        row["lemma"] = submitted["lemma"] or row.get("lemma") or row.get("surface")
        row["pos"] = submitted["pos"]
        row["gloss"] = submitted["gloss"]
        row["translation"] = submitted["translation"]
    _write_imported_dictionary_annotation_stages(dictionary, manual_rows, source="picture_dictionary_manual_entry")
    return {"added": added, "updated": updated, "skipped": skipped, "submitted": len(submitted_by_surface)}


def extract_pictureable_words(text: str) -> list[str]:
    raw = re.findall(r"[\w'-]+", text or "", flags=re.UNICODE)
    candidates: list[str] = []
    seen: set[str] = set()
    for token in raw:
        normalized = _normalise_word(token)
        if len(normalized) <= 2:
            continue
        if normalized.isdigit():
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(normalized)
    return candidates


def add_words_from_text(*, dictionary: PictureDictionary, text: str) -> int:
    return add_words(dictionary=dictionary, words=extract_pictureable_words(text))


def add_lemma_pos_entries(*, dictionary: PictureDictionary, lemma_pos_pairs: Iterable[tuple[str, str]]) -> int:
    _bootstrap_registry_from_project_source(dictionary)
    existing: dict[tuple[str, str], PictureDictionaryEntry] = {}
    for entry in dictionary.entries.order_by("id"):
        lemma_key = _normalise_word(entry.lemma or entry.surface).casefold()
        pos_key = _normalise_word(entry.pos).upper()
        existing[(lemma_key, pos_key)] = entry

    added = 0
    for lemma_raw, pos_raw in lemma_pos_pairs:
        lemma = _normalise_word(lemma_raw)
        pos = _normalise_word(pos_raw).upper()
        if not lemma:
            continue
        key = (lemma.casefold(), pos)
        row = existing.get(key)
        if row and row.is_active:
            continue
        if row and not row.is_active:
            row.is_active = True
            row.surface = lemma
            row.lemma = lemma
            row.pos = pos
            row.save(update_fields=["is_active", "surface", "lemma", "pos", "updated_at"])
        else:
            created = PictureDictionaryEntry.objects.create(
                dictionary=dictionary,
                surface=lemma,
                lemma=lemma,
                pos=pos,
                is_active=True,
            )
            existing[key] = created
        added += 1
    _sync_project_source_from_registry(dictionary)
    _refresh_dictionary_placeholder_stages(dictionary)
    return added


def _write_segmentation_phase_1(dictionary: PictureDictionary, entries: list[PictureDictionaryEntry]) -> None:
    run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages"
    run_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    for entry in entries:
        pages.append({"surface": entry.surface, "segments": [{"surface": entry.surface}], "annotations": {}})
    payload = {
        "l2": dictionary.project.language,
        "surface": "<page>".join(entry.surface for entry in entries),
        "pages": pages,
        "annotations": {},
        "metadata": {
            "source": "picture_dictionary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(entries),
        },
    }
    write_stage_artifact(run_dir.parent, "segmentation_phase_1", payload)


def _dictionary_stage_payload(dictionary: PictureDictionary, entries: list[PictureDictionaryEntry], stage_name: str) -> dict:
    pages = []
    for entry in entries:
        pages.append(
            {
                "surface": entry.surface,
                "segments": [
                    {
                        "surface": entry.surface,
                        "tokens": [{"surface": entry.surface}],
                        "annotations": {},
                    }
                ],
                "annotations": {},
            }
        )
    return {
        "l2": dictionary.project.language,
        "surface": "<page>".join(entry.surface for entry in entries),
        "pages": pages,
        "annotations": {},
        "metadata": {
            "source": "picture_dictionary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(entries),
            "stage": stage_name,
        },
    }


def _write_dictionary_annotation_stages(dictionary: PictureDictionary, entries: list[PictureDictionaryEntry]) -> None:
    run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages"
    run_dir.mkdir(parents=True, exist_ok=True)
    for stage_name in ("segmentation_phase_2", "translation", "mwe", "lemma", "gloss", "romanization", "pinyin"):
        payload = _dictionary_stage_payload(dictionary, entries, stage_name)
        write_stage_artifact(run_dir.parent, stage_name, payload)


def _merge_stage_placeholders_with_existing(
    dictionary: PictureDictionary,
    entries: list[PictureDictionaryEntry],
    *,
    stage_name: str,
) -> None:
    run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary"
    try:
        existing_payload = read_stage_artifact(run_dir, stage_name)
    except Exception:
        existing_payload = {}
    existing_tokens_by_surface: dict[str, dict] = {}
    existing_segment_annotations_by_page: dict[int, list[dict[str, Any]]] = {}
    for page in existing_payload.get("pages") or []:
        if not isinstance(page, dict):
            continue
        page_number = len(existing_segment_annotations_by_page) + 1
        seg_ann_rows: list[dict[str, Any]] = []
        for seg in page.get("segments") or []:
            if not isinstance(seg, dict):
                continue
            seg_ann = seg.get("annotations") if isinstance(seg.get("annotations"), dict) else {}
            seg_ann_rows.append(dict(seg_ann or {}))
            for tok in seg.get("tokens") or []:
                if not isinstance(tok, dict):
                    continue
                key = _normalise_word(tok.get("surface") or "").casefold()
                if key:
                    existing_tokens_by_surface[key] = tok
        if seg_ann_rows:
            existing_segment_annotations_by_page[page_number] = seg_ann_rows

    payload = _dictionary_stage_payload(dictionary, entries, stage_name)
    for page_idx, page in enumerate(payload.get("pages") or [], start=1):
        prior_seg_ann_rows = existing_segment_annotations_by_page.get(page_idx, [])
        for seg_idx, seg in enumerate(page.get("segments") or []):
            if seg_idx < len(prior_seg_ann_rows):
                prior_seg_ann = prior_seg_ann_rows[seg_idx]
                if prior_seg_ann:
                    seg["annotations"] = dict(prior_seg_ann)
            for tok in seg.get("tokens") or []:
                key = _normalise_word(tok.get("surface") or "").casefold()
                prior = existing_tokens_by_surface.get(key)
                if not prior:
                    continue
                prior_ann = prior.get("annotations") if isinstance(prior.get("annotations"), dict) else {}
                if prior_ann:
                    tok["annotations"] = dict(prior_ann)
    write_stage_artifact(run_dir, stage_name, payload)


def _sync_entry_image_paths_from_pages(dictionary: PictureDictionary, entries: list[PictureDictionaryEntry]) -> int:
    """Copy current page image paths back to dictionary entries.

    Page-image generation updates ``ProjectImagePage.image_path``.  The organiser
    dashboard counts missing images from dictionary entries, so keep the registry
    in step immediately after generation instead of waiting for a later compile
    pass to discover the page image paths.
    """

    pages_by_number = {
        page.page_number: page
        for page in ProjectImagePage.objects.filter(project=dictionary.project).order_by("page_number", "id")
    }
    updated = 0
    for idx, entry in enumerate(entries, start=1):
        page_number = entry.current_page_number or idx
        page = pages_by_number.get(page_number)
        if not page:
            continue
        changed_fields: list[str] = []
        page_image_path = (page.image_path or "").strip()
        if page_image_path and entry.image_path != page_image_path:
            entry.image_path = page_image_path
            changed_fields.append("image_path")
        if entry.current_page_number != page.page_number:
            entry.current_page_number = page.page_number
            changed_fields.append("current_page_number")
        if changed_fields:
            changed_fields.append("updated_at")
            entry.save(update_fields=changed_fields)
            updated += 1
    return updated


def _refresh_dictionary_placeholder_stages(dictionary: PictureDictionary) -> None:
    entries = list(dictionary.entries.filter(is_active=True).order_by("id"))
    _sync_project_source_from_registry(dictionary)
    _sync_dictionary_project_pages(dictionary, entries)
    _write_segmentation_phase_1(dictionary, entries)
    for stage_name in ("segmentation_phase_2", "translation", "mwe", "lemma", "gloss", "romanization", "pinyin"):
        _merge_stage_placeholders_with_existing(dictionary, entries, stage_name=stage_name)


def _prune_unreferenced_dictionary_image_artifacts(project: Project, active_image_paths: set[str]) -> None:
    """Remove page-image files/directories no active dictionary entry references."""

    pages_dir = project.artifact_dir() / "images" / "pages"
    if not pages_dir.exists():
        return
    active_parts: set[Path] = set()
    for raw_path in active_image_paths:
        path = Path(str(raw_path or "").strip())
        if not path.parts:
            continue
        if len(path.parts) >= 3 and path.parts[0] == "images" and path.parts[1] == "pages":
            path = Path(*path.parts[2:])
        active_parts.add(path)
    active_page_dirs = {part.parts[0] for part in active_parts if part.parts}
    for child in list(pages_dir.iterdir()):
        if child.is_dir():
            if child.name not in active_page_dirs:
                shutil.rmtree(child, ignore_errors=True)
            continue
        try:
            rel = child.relative_to(pages_dir)
        except ValueError:
            continue
        if rel not in active_parts:
            child.unlink(missing_ok=True)
    try:
        if not any(pages_dir.iterdir()):
            pages_dir.rmdir()
    except OSError:
        pass


def _sync_dictionary_project_pages(dictionary: PictureDictionary, entries: list[PictureDictionaryEntry]) -> None:
    project = dictionary.project
    existing_pages = {page.page_number: page for page in ProjectImagePage.objects.filter(project=project).order_by("id")}
    retained_page_ids: set[int] = set()
    active_image_paths = {(entry.image_path or "").strip() for entry in entries if (entry.image_path or "").strip()}
    for idx, entry in enumerate(entries, start=1):
        page = existing_pages.get(idx)
        if page is None:
            page = ProjectImagePage.objects.create(
                project=project,
                page_number=idx,
                page_text=entry.surface,
                generation_prompt=entry.surface,
                image_model="gpt-image-1",
                image_path=entry.image_path or "",
            )
        else:
            changed = False
            if page.page_text != entry.surface:
                page.page_text = entry.surface
                changed = True
            if page.generation_prompt != entry.surface:
                page.generation_prompt = entry.surface
                changed = True
            if (entry.image_path or "") != (page.image_path or ""):
                page.image_path = entry.image_path or ""
                changed = True
            if changed:
                page.save(update_fields=["page_text", "generation_prompt", "image_path", "updated_at"])
        # Keep variants/preferred variant aligned with canonical page image_path.
        # Without this, judge/images views can show stale variants after dictionary deletions/reindexing.
        canonical_path = (entry.image_path or "").strip()
        if canonical_path:
            variant, _ = ProjectImagePageVariant.objects.update_or_create(
                page=page,
                variant_index=1,
                defaults={
                    "image_model": page.image_model or "gpt-image-1",
                    "image_path": canonical_path,
                    "generation_prompt": page.generation_prompt or "",
                    "image_revised_prompt": "",
                    "status": ProjectImagePageVariant.STATUS_GENERATED,
                },
            )
            stale_variants = page.variants.exclude(id=variant.id)
            if stale_variants.exists():
                stale_variants.delete()
            if page.preferred_variant_id != variant.id:
                page.preferred_variant = variant
                page.status = ProjectImagePage.STATUS_GENERATED
                page.save(update_fields=["preferred_variant", "status", "updated_at"])
        else:
            if page.variants.exists():
                page.variants.all().delete()
            if page.preferred_variant_id is not None:
                page.preferred_variant = None
                page.status = ProjectImagePage.STATUS_DRAFT
                page.save(update_fields=["preferred_variant", "status", "updated_at"])
        if entry.current_page_number != idx:
            entry.current_page_number = idx
            entry.save(update_fields=["current_page_number", "updated_at"])
        retained_page_ids.add(page.id)

    # Remove orphaned pages (and cascading variants/votes) after dictionary deletions.
    # Filtering only by page_number can leave stale duplicate/legacy rows behind;
    # delete anything that was not explicitly retained for the active entries.
    stale_pages = ProjectImagePage.objects.filter(project=project)
    if retained_page_ids:
        stale_pages = stale_pages.exclude(id__in=retained_page_ids)
    stale_pages.delete()
    _prune_unreferenced_dictionary_image_artifacts(project, active_image_paths)


def _imported_dictionary_stage_payload(
    dictionary: PictureDictionary,
    rows: list[dict],
    stage_name: str,
    *,
    source: str = "picture_dictionary_import",
) -> dict:
    pages = []
    for row in rows:
        token_annotations: dict[str, str] = {}
        segment_annotations: dict[str, str] = {}
        if stage_name in {"lemma", "gloss", "romanization", "pinyin"}:
            if row.get("lemma"):
                token_annotations["lemma"] = str(row["lemma"])
            if row.get("pos"):
                token_annotations["pos"] = str(row["pos"])
        if stage_name == "translation":
            translation = row.get("translation") or row.get("gloss") or ""
            if translation:
                token_annotations["translation"] = str(translation)
                segment_annotations["translation"] = str(translation)
        if stage_name in {"gloss", "romanization", "pinyin"}:
            gloss = row.get("gloss") or row.get("translation") or ""
            if gloss:
                token_annotations["gloss"] = str(gloss)
        pages.append(
            {
                "surface": str(row["surface"]),
                "segments": [
                    {
                        "surface": str(row["surface"]),
                        "tokens": [{"surface": str(row["surface"]), "annotations": token_annotations}],
                        "annotations": segment_annotations,
                    }
                ],
                "annotations": {},
            }
        )
    return {
        "l2": dictionary.project.language,
        "surface": "<page>".join(str(row["surface"]) for row in rows),
        "pages": pages,
        "annotations": {},
        "metadata": {
            "source": source,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(rows),
            "stage": stage_name,
        },
    }


def _write_imported_dictionary_annotation_stages(
    dictionary: PictureDictionary,
    rows: list[dict],
    *,
    source: str = "picture_dictionary_import",
) -> None:
    run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages"
    run_dir.mkdir(parents=True, exist_ok=True)
    for stage_name in ("segmentation_phase_2", "translation", "mwe", "lemma", "gloss", "romanization", "pinyin"):
        payload = _imported_dictionary_stage_payload(dictionary, rows, stage_name, source=source)
        write_stage_artifact(run_dir.parent, stage_name, payload)



PICTURE_DICTIONARY_SUBSET_DIR = "picture_dictionary_subsets"


def _picture_dictionary_subset_root(dictionary: PictureDictionary) -> Path:
    return dictionary.project.artifact_dir() / PICTURE_DICTIONARY_SUBSET_DIR


def _picture_dictionary_subset_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", (value or "").strip()).strip("-").lower()
    return slug[:64] or "subset"


def _read_picture_dictionary_subset_config(path: Path) -> dict[str, Any] | None:
    try:
        with (path / "config.json").open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except Exception:
        return None
    return config if isinstance(config, dict) else None


def list_picture_dictionary_subsets(dictionary: PictureDictionary) -> list[dict[str, Any]]:
    """Return stored subset-project metadata for the community dictionary.

    Subsets are tracked as lightweight artifacts under the canonical dictionary
    project so they can point back to parent entries/pages without adding a
    migration for this first cut.
    """

    root = _picture_dictionary_subset_root(dictionary)
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for child in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        config = _read_picture_dictionary_subset_config(child)
        if not config:
            continue
        try:
            with (child / "pages.json").open("r", encoding="utf-8") as handle:
                pages_payload = json.load(handle)
        except Exception:
            pages_payload = {}
        pages = pages_payload.get("pages") if isinstance(pages_payload, dict) else []
        if not isinstance(pages, list):
            pages = []
        project_id = int(config.get("project_id") or 0)
        project = Project.objects.filter(id=project_id).first() if project_id else None
        entry_ids = [int(page.get("entry_id")) for page in pages if isinstance(page, dict) and str(page.get("entry_id") or "").isdigit()]
        rows.append(
            {
                "subset_id": str(config.get("subset_id") or child.name),
                "title": str(config.get("title") or (project.title if project else child.name)),
                "description": str(config.get("description") or ""),
                "selection_note": str(config.get("selection_note") or ""),
                "project_id": project_id or None,
                "project": project,
                "entry_ids": entry_ids,
                "entry_count": len(entry_ids),
                "updated_at": str(config.get("updated_at") or ""),
                "created_at": str(config.get("created_at") or ""),
            }
        )
    rows.sort(key=lambda row: (str(row.get("title") or "").casefold(), str(row.get("subset_id") or "")))
    return rows


def picture_dictionary_subset_project_ids(dictionary: PictureDictionary) -> set[int]:
    return {int(row["project_id"]) for row in list_picture_dictionary_subsets(dictionary) if row.get("project_id")}


def get_picture_dictionary_subset(dictionary: PictureDictionary, subset_id: str) -> dict[str, Any] | None:
    subset_id = str(subset_id or "").strip()
    if not subset_id:
        return None
    for row in list_picture_dictionary_subsets(dictionary):
        if str(row.get("subset_id") or "") == subset_id:
            return row
    return None


def _picture_dictionary_subset_rows(
    dictionary: PictureDictionary,
    selected_entries: list[PictureDictionaryEntry],
) -> list[dict[str, Any]]:
    rows_by_entry_id = {
        int(entry.id): row
        for entry, row in zip(selected_entries, _manual_rows_from_entries(dictionary, selected_entries), strict=False)
    }
    pages_by_number = {
        page.page_number: page
        for page in ProjectImagePage.objects.filter(project=dictionary.project).prefetch_related("variants").order_by("page_number", "id")
    }
    output: list[dict[str, Any]] = []
    for idx, entry in enumerate(selected_entries, start=1):
        row = rows_by_entry_id.get(int(entry.id), {})
        parent_page_number = entry.current_page_number or int(row.get("old_page_number") or idx)
        parent_page = pages_by_number.get(parent_page_number)
        output.append(
            {
                "entry": entry,
                "row": row,
                "parent_page": parent_page,
                "parent_page_number": parent_page_number,
                "page_number": idx,
                "surface": str(row.get("surface") or entry.surface or ""),
                "lemma": str(row.get("lemma") or entry.lemma or entry.surface or ""),
                "pos": str(row.get("pos") or entry.pos or ""),
                "gloss": str(row.get("gloss") or row.get("translation") or ""),
                "translation": str(row.get("translation") or row.get("gloss") or ""),
                "image_path": str(row.get("image_path") or entry.image_path or ""),
            }
        )
    return output


def _write_subset_segmentation_phase_1(
    subset_project: Project,
    dictionary: PictureDictionary,
    subset_rows: list[dict[str, Any]],
) -> None:
    run_dir = subset_project.artifact_dir() / "runs" / "run_picture_dictionary_subset"
    pages = [
        {"surface": row["surface"], "segments": [{"surface": row["surface"]}], "annotations": {}}
        for row in subset_rows
    ]
    payload = {
        "l2": subset_project.language,
        "surface": "<page>".join(row["surface"] for row in subset_rows),
        "pages": pages,
        "annotations": {},
        "metadata": {
            "source": "picture_dictionary_subset",
            "parent_dictionary_id": dictionary.id,
            "parent_dictionary_project_id": dictionary.project_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(subset_rows),
        },
    }
    write_stage_artifact(run_dir, "segmentation_phase_1", payload)


def _write_subset_annotation_stages(
    subset_project: Project,
    dictionary: PictureDictionary,
    subset_rows: list[dict[str, Any]],
) -> None:
    run_dir = subset_project.artifact_dir() / "runs" / "run_picture_dictionary_subset"
    rows = [
        {
            "surface": row["surface"],
            "lemma": row["lemma"],
            "pos": row["pos"],
            "gloss": row["gloss"],
            "translation": row["translation"],
        }
        for row in subset_rows
    ]
    for stage_name in ("segmentation_phase_2", "translation", "mwe", "lemma", "gloss", "romanization", "pinyin"):
        payload = _imported_dictionary_stage_payload(
            dictionary,
            rows,
            stage_name,
            source="picture_dictionary_subset",
        )
        payload["l2"] = subset_project.language
        payload.setdefault("metadata", {}).update(
            {
                "source": "picture_dictionary_subset",
                "parent_dictionary_id": dictionary.id,
                "parent_dictionary_project_id": dictionary.project_id,
                "subset_project_id": subset_project.id,
            }
        )
        write_stage_artifact(run_dir, stage_name, payload)


def _safe_copy_dictionary_image(dictionary: PictureDictionary, subset_project: Project, image_path: str) -> None:
    relative = Path(str(image_path or "").strip())
    if not relative.parts or relative.is_absolute():
        return
    try:
        source = (dictionary.project.artifact_dir() / relative).resolve()
        source.relative_to(dictionary.project.artifact_dir().resolve())
        target = (subset_project.artifact_dir() / relative).resolve()
        target.relative_to(subset_project.artifact_dir().resolve())
    except ValueError:
        return
    if not source.exists() or source.is_dir():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _sync_subset_project_image_pages(
    subset_project: Project,
    dictionary: PictureDictionary,
    subset_rows: list[dict[str, Any]],
) -> None:
    existing_pages = {page.page_number: page for page in ProjectImagePage.objects.filter(project=subset_project).order_by("id")}
    retained_page_ids: set[int] = set()
    for row in subset_rows:
        parent_page = row.get("parent_page")
        page_number = int(row["page_number"])
        image_path = str(row.get("image_path") or "").strip()
        if image_path:
            _safe_copy_dictionary_image(dictionary, subset_project, image_path)
        page = existing_pages.get(page_number)
        defaults = {
            "page_text": row["surface"],
            "generation_prompt": getattr(parent_page, "generation_prompt", "") or row["surface"],
            "image_model": getattr(parent_page, "image_model", "gpt-image-1") or "gpt-image-1",
            "image_path": image_path,
            "image_revised_prompt": getattr(parent_page, "image_revised_prompt", "") or "",
            "status": getattr(parent_page, "status", ProjectImagePage.STATUS_APPROVED) if parent_page else ProjectImagePage.STATUS_APPROVED,
        }
        if page is None:
            page = ProjectImagePage.objects.create(project=subset_project, page_number=page_number, **defaults)
        else:
            for key, value in defaults.items():
                setattr(page, key, value)
            page.save(update_fields=[*defaults.keys(), "updated_at"])
        retained_page_ids.add(page.id)
        ProjectImagePageVariant.objects.filter(page=page).delete()
        preferred_variant = None
        if parent_page is not None:
            for variant in parent_page.variants.order_by("variant_index", "id"):
                variant_image_path = str(variant.image_path or "").strip()
                if variant_image_path:
                    _safe_copy_dictionary_image(dictionary, subset_project, variant_image_path)
                copied = ProjectImagePageVariant.objects.create(
                    page=page,
                    variant_index=variant.variant_index,
                    image_model=variant.image_model,
                    image_path=variant_image_path,
                    generation_prompt=variant.generation_prompt,
                    image_revised_prompt=variant.image_revised_prompt,
                    status=variant.status,
                )
                if parent_page.preferred_variant_id == variant.id:
                    preferred_variant = copied
        elif image_path:
            preferred_variant = ProjectImagePageVariant.objects.create(
                page=page,
                variant_index=1,
                image_model=page.image_model or "gpt-image-1",
                image_path=image_path,
                generation_prompt=page.generation_prompt or row["surface"],
                image_revised_prompt=page.image_revised_prompt or "",
                status=ProjectImagePageVariant.STATUS_GENERATED,
            )
        if preferred_variant and page.preferred_variant_id != preferred_variant.id:
            page.preferred_variant = preferred_variant
            page.save(update_fields=["preferred_variant", "updated_at"])
    stale_pages = ProjectImagePage.objects.filter(project=subset_project)
    if retained_page_ids:
        stale_pages = stale_pages.exclude(id__in=retained_page_ids)
    stale_pages.delete()


@transaction.atomic
def create_or_update_picture_dictionary_subset(
    *,
    dictionary: PictureDictionary,
    organiser,
    title: str,
    entry_ids: Iterable[int],
    subset_id: str = "",
    description: str = "",
    selection_note: str = "",
) -> dict[str, Any]:
    """Create or update a lightweight subset project derived from a picture dictionary."""

    _require_organiser(dictionary.community, organiser)
    cleaned_title = _normalise_word(title) or "Picture dictionary subset"
    cleaned_description = str(description or "").strip()
    cleaned_note = str(selection_note or "").strip()
    ordered_ids: list[int] = []
    seen: set[int] = set()
    for raw_id in entry_ids:
        try:
            entry_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if entry_id in seen:
            continue
        seen.add(entry_id)
        ordered_ids.append(entry_id)
    if not ordered_ids:
        raise ValueError("Select at least one dictionary entry for the subset project.")
    entries_by_id = {
        entry.id: entry
        for entry in dictionary.entries.filter(id__in=ordered_ids, is_active=True).order_by("id")
    }
    selected_entries = [entries_by_id[entry_id] for entry_id in ordered_ids if entry_id in entries_by_id]
    if not selected_entries:
        raise ValueError("The selected dictionary entries are no longer available.")

    existing_subset = get_picture_dictionary_subset(dictionary, subset_id) if subset_id else None
    if existing_subset and existing_subset.get("project_id"):
        subset_project = Project.objects.filter(
            id=int(existing_subset["project_id"]),
            community=dictionary.community,
        ).first()
        if subset_project is None:
            existing_subset = None
    else:
        subset_project = None

    if subset_project is None:
        subset_project = Project.objects.create(
            owner=organiser,
            title=_unique_project_title(organiser, cleaned_title),
            description="",
            source_text="",
            input_mode=Project.INPUT_SOURCE,
            language=dictionary.project.language or dictionary.language,
            target_language=dictionary.project.target_language or "",
            ai_model=dictionary.project.ai_model or "gpt-4o",
            page_image_placement=dictionary.project.page_image_placement,
            image_generation_pivot_language=dictionary.project.image_generation_pivot_language,
            page_image_text_source=dictionary.project.page_image_text_source,
            segmentation_method=dictionary.project.segmentation_method,
            romanization_method=dictionary.project.romanization_method,
            audio_mode=dictionary.project.audio_mode,
            access_scope=Project.ACCESS_COMMUNITY,
            community=dictionary.community,
        )
        subset_id = f"project_{subset_project.id}"
        created = True
    else:
        subset_project.title = cleaned_title[:200]
        subset_project.language = dictionary.project.language or dictionary.language
        subset_project.target_language = dictionary.project.target_language or ""
        subset_project.input_mode = Project.INPUT_SOURCE
        subset_project.access_scope = Project.ACCESS_COMMUNITY
        subset_project.community = dictionary.community
        created = False
        if not subset_id:
            subset_id = f"project_{subset_project.id}"
    subset_project.description = (
        f"Derived subset of picture dictionary “{dictionary.project.title}”.\n\n"
        f"{cleaned_description}".strip()
    )
    subset_project.source_text = "\n".join(entry.surface for entry in selected_entries)
    subset_project.save()

    subset_rows = _picture_dictionary_subset_rows(dictionary, selected_entries)
    _write_subset_segmentation_phase_1(subset_project, dictionary, subset_rows)
    _write_subset_annotation_stages(subset_project, dictionary, subset_rows)
    _sync_subset_project_image_pages(subset_project, dictionary, subset_rows)

    root = _picture_dictionary_subset_root(dictionary)
    root.mkdir(parents=True, exist_ok=True)
    subset_id = _picture_dictionary_subset_slug(subset_id or f"project_{subset_project.id}")
    subset_dir = root / subset_id
    subset_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    existing_config = _read_picture_dictionary_subset_config(subset_dir) or {}
    created_at = str(existing_config.get("created_at") or now)
    config = {
        "schema_version": 1,
        "subset_id": subset_id,
        "title": subset_project.title,
        "description": cleaned_description,
        "selection_note": cleaned_note,
        "project_id": subset_project.id,
        "parent_dictionary_id": dictionary.id,
        "parent_dictionary_project_id": dictionary.project_id,
        "community_id": dictionary.community_id,
        "created_by_user_id": organiser.id,
        "created_at": created_at,
        "updated_at": now,
    }
    pages_payload = {
        "schema_version": 1,
        "subset_id": subset_id,
        "pages": [
            {
                "order": row["page_number"],
                "entry_id": row["entry"].id,
                "parent_page_number": row["parent_page_number"],
                "surface": row["surface"],
                "lemma": row["lemma"],
                "pos": row["pos"],
                "gloss": row["gloss"],
                "translation": row["translation"],
                "image_path": row["image_path"],
            }
            for row in subset_rows
        ],
    }
    provenance = {
        "schema_version": 1,
        "subset_id": subset_id,
        "parent_dictionary_id": dictionary.id,
        "parent_dictionary_project_id": dictionary.project_id,
        "updated_at": now,
        "selection_method": "manual",
        "selection_note": cleaned_note,
        "entry_ids": [entry.id for entry in selected_entries],
    }
    for filename, payload in (
        ("config.json", config),
        ("pages.json", pages_payload),
        ("provenance.json", provenance),
    ):
        with (subset_dir / filename).open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    return {
        "created": created,
        "subset_id": subset_id,
        "project": subset_project,
        "entry_count": len(selected_entries),
        "artifact_dir": subset_dir,
    }


def _index_existing_dictionary_annotations(dictionary: PictureDictionary) -> dict[tuple[str, str], dict]:
    runs_root = dictionary.project.artifact_dir() / "runs"

    def _latest_run_with_stage(stage_name: str) -> Path | None:
        if not runs_root.exists():
            return None
        candidates: list[Path] = []
        for run_dir in runs_root.iterdir():
            if not run_dir.is_dir():
                continue
            stage_path = run_dir / "stages" / f"{stage_name}.json"
            if stage_path.exists():
                candidates.append(run_dir)
        if not candidates:
            return None
        candidates.sort(key=lambda path: (path / "stages" / f"{stage_name}.json").stat().st_mtime, reverse=True)
        return candidates[0]

    translation_run = _latest_run_with_stage("translation")
    translation_by_page: dict[int, str] = {}
    try:
        tr_payload = read_stage_artifact(translation_run, "translation") if translation_run else {}
    except Exception:
        tr_payload = {}
    for page_number, page in enumerate((tr_payload.get("pages") or []), start=1):
        if not isinstance(page, dict):
            continue
        segments = page.get("segments") or []
        parts: list[str] = []
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            translation_text = str(((segment.get("annotations") or {}).get("translation") or "")).strip()
            if translation_text:
                parts.append(translation_text)
        if parts:
            translation_by_page[page_number] = " ".join(parts).strip()

    gloss_run = _latest_run_with_stage("gloss")
    try:
        payload = read_stage_artifact(gloss_run, "gloss") if gloss_run else {}
    except Exception:
        return {}
    indexed: dict[tuple[str, str], dict] = {}
    for page_number, page in enumerate(payload.get("pages") or [], start=1):
        if not isinstance(page, dict):
            continue
        for segment in page.get("segments") or []:
            if not isinstance(segment, dict):
                continue
            for token in segment.get("tokens") or []:
                if not isinstance(token, dict):
                    continue
                surface = _normalise_word(token.get("surface") or "")
                if not surface:
                    continue
                annotations = token.get("annotations") or {}
                row = {
                    "surface": surface,
                    "lemma": _normalise_word(annotations.get("lemma") or surface),
                    "pos": _normalise_word(annotations.get("pos") or "").upper(),
                    "gloss": _non_null_text(annotations.get("gloss")),
                    "translation": _non_null_text(annotations.get("translation")) or translation_by_page.get(page_number, ""),
                }
                indexed[("page", str(page_number))] = row
                indexed[("surface", surface.casefold())] = row
                lemma = _normalise_word(annotations.get("lemma") or "")
                if lemma:
                    indexed[("lemma", lemma.casefold())] = row
    return indexed


def _manual_rows_from_entries(dictionary: PictureDictionary, entries: list[PictureDictionaryEntry]) -> list[dict]:
    existing = _index_existing_dictionary_annotations(dictionary)
    rows: list[dict] = []
    for entry in entries:
        prior = None
        if entry.current_page_number:
            prior = existing.get(("page", str(entry.current_page_number)))
        if prior is None:
            prior = existing.get(("surface", (entry.surface or "").casefold()))
        if prior is None and entry.lemma:
            prior = existing.get(("lemma", entry.lemma.casefold()))
        prior = prior or {}
        prior_gloss = str(prior.get("gloss") or "").strip()
        prior_translation = str(prior.get("translation") or "").strip()
        if prior_gloss and not prior_translation:
            prior_translation = prior_gloss
        elif prior_translation and not prior_gloss:
            prior_gloss = prior_translation
        rows.append(
            {
                "old_page_number": entry.current_page_number or len(rows) + 1,
                "surface": entry.surface,
                "lemma": entry.lemma or prior.get("lemma") or entry.surface,
                "pos": entry.pos or prior.get("pos") or "",
                "gloss": prior_gloss,
                "translation": prior_translation,
                "image_path": entry.image_path or "",
            }
        )
    return rows


def _rows_have_manual_glosses(rows: list[dict]) -> bool:
    return bool(rows) and all(
        (row.get("lemma") or row.get("surface")) and (row.get("gloss") or row.get("translation"))
        for row in rows
    )


def compile_picture_dictionary(
    *,
    dictionary: PictureDictionary,
    progress_callback: Callable[[str], None] | None = None,
    compile_task_report_id: str | None = None,
    compile_task_user_id: int | None = None,
    compile_task_type: str | None = None,
    low_resource_mode: bool = False,
) -> dict[str, object]:
    def _post_progress(message: str) -> None:
        if progress_callback:
            progress_callback(message)

    _bootstrap_registry_from_project_source(dictionary)
    entries = list(dictionary.entries.filter(is_active=True).order_by("id"))
    _sync_project_source_from_registry(dictionary)
    manual_rows = _manual_rows_from_entries(dictionary, entries)
    _post_progress(f"Dictionary text compilation started for {len(entries)} image entr{'y' if len(entries) == 1 else 'ies'}.")
    _post_progress("Text phase 1/3: syncing dictionary entries to image pages.")

    for idx, entry in enumerate(entries, start=1):
        page_prompt_text = entry.surface
        if dictionary.project.page_image_text_source == Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION and idx <= len(manual_rows):
            row = manual_rows[idx - 1]
            candidate = str(row.get("translation") or row.get("gloss") or "").strip()
            if candidate:
                page_prompt_text = candidate
        existing = ProjectImagePage.objects.filter(project=dictionary.project, page_number=idx).first()
        if existing:
            changed = False
            if existing.page_text != page_prompt_text:
                existing.page_text = page_prompt_text
                changed = True
            if existing.generation_prompt != page_prompt_text:
                existing.generation_prompt = page_prompt_text
                changed = True
            if entry.image_path and existing.image_path != entry.image_path:
                existing.image_path = entry.image_path
                changed = True
            if changed:
                existing.save(update_fields=["page_text", "generation_prompt", "image_path", "updated_at"])
            if not entry.image_path and existing.image_path:
                entry.image_path = existing.image_path
            entry.current_page_number = idx
            entry.save(update_fields=["image_path", "current_page_number", "updated_at"])
        else:
            page = ProjectImagePage.objects.create(
                project=dictionary.project,
                page_number=idx,
                page_text=page_prompt_text,
                generation_prompt=page_prompt_text,
                image_model="gpt-image-1",
                image_path=entry.image_path,
            )
            entry.current_page_number = idx
            if not entry.image_path and page.image_path:
                entry.image_path = page.image_path
            entry.save(update_fields=["image_path", "current_page_number", "updated_at"])

    ProjectImagePage.objects.filter(project=dictionary.project, page_number__gt=len(entries)).delete()
    _post_progress("Text phase 2/3: writing segmentation and annotation stage artifacts.")
    manual_annotations_complete = _rows_have_manual_glosses(manual_rows)
    _write_segmentation_phase_1(dictionary, entries)
    if manual_annotations_complete:
        _write_imported_dictionary_annotation_stages(dictionary, manual_rows, source="picture_dictionary_manual_entry")
    elif low_resource_mode:
        _write_dictionary_annotation_stages(dictionary, entries)
    else:
        _write_dictionary_annotation_stages(dictionary, entries)
    annotation_run = "manual" if manual_annotations_complete else ("placeholder" if low_resource_mode else "skipped")
    annotation_error = ""
    generated_images = 0
    image_generation_note = ""
    if manual_annotations_complete:
        _post_progress("Text phase 3/3: using existing manual lemma/gloss annotations; AI annotation skipped.")
    elif low_resource_mode:
        _post_progress(
            "Text phase 3/3: low-resource mode selected. Wrote placeholder artifacts for translation/MWE/lemma/gloss/pinyin."
        )
        _post_progress(
            "Please open page-by-page manual annotation to complete missing values: "
            f"{reverse('manual-page-annotation', args=[dictionary.project.id])}"
        )
    else:
        try:
            from .views import _run_compile_task

            _post_progress("Text phase 3/3: running annotation pipeline (segmentation phase 2 to compile HTML).")
            run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary"
            run_dir.mkdir(parents=True, exist_ok=True)
            seg1_payload = _dictionary_stage_payload(dictionary, entries, "segmentation_phase_1")
            _run_compile_task(
                project_id=dictionary.project.id,
                user_id=compile_task_user_id or dictionary.organiser_id,
                output_dir_str=str(run_dir),
                project_root_str=str(dictionary.project.artifact_dir()),
                start_stage="segmentation_phase_2",
                timezone_name="UTC",
                description=None,
                text=dictionary.project.source_text,
                text_obj=seg1_payload,
                report_id=compile_task_report_id,
                task_type=compile_task_type or f"picture_dictionary_compile_{dictionary.project.id}",
                ai_model=dictionary.project.ai_model,
                end_stage="compile_html",
                page_image_placement=dictionary.project.page_image_placement or "none",
                segmentation_method=dictionary.project.segmentation_method or "auto",
                romanization_method=dictionary.project.romanization_method or "auto",
                detailed_api_trace=False,
            )
            annotation_run = "ok"
        except Exception as exc:
            annotation_run = "error"
            annotation_error = str(exc)
            logger.exception(
                "Picture dictionary annotation compile failed for dictionary project %s",
                dictionary.project_id,
            )

    missing_image_entries = sum(1 for entry in entries if not (entry.image_path or "").strip())
    _post_progress(
        "Dictionary image compilation started: "
        f"{missing_image_entries}/{len(entries)} entr{'y' if len(entries) == 1 else 'ies'} currently missing image files."
    )
    try:
        style = getattr(dictionary.project, "image_style", None)
        style_usable = bool(
            style
            and (
                (style.style_brief or "").strip()
                or (style.expanded_style_description or "").strip()
            )
            and style.status in {"generated", "approved"}
        )
        if low_resource_mode and not manual_annotations_complete:
            image_generation_note = (
                "Image generation skipped: low-resource mode is enabled and manual annotations are incomplete."
            )
        elif style_usable:
            from .views import _generate_project_page_images

            _post_progress(
                "Image phase: generating missing dictionary images from current style. "
                f"Target entries with missing images: {missing_image_entries}."
            )
            generated_images = _generate_project_page_images(
                dictionary.project,
                image_model=style.sample_image_model or "gpt-image-1",
                variants_per_page=1,
                discourage_text_in_image=bool(style.discourage_text_in_images),
                include_full_text=False,
                include_elements=False,
                missing_only=True,
            )
            _post_progress(
                "Image phase complete: "
                f"generated {generated_images} image variant{'s' if generated_images != 1 else ''} "
                f"for dictionary project \"{dictionary.project.title}\"."
            )
            if generated_images:
                refreshed_entries = list(dictionary.entries.filter(is_active=True).order_by("id"))
                synced_entries = _sync_entry_image_paths_from_pages(dictionary, refreshed_entries)
                if synced_entries:
                    _post_progress(
                        "Image phase registry sync: "
                        f"updated {synced_entries} dictionary entr{'y' if synced_entries == 1 else 'ies'} with generated image paths."
                    )
        else:
            image_generation_note = "Image generation skipped (style missing or not approved)."
    except Exception:
        image_generation_note = "Image generation failed."

    return {
        "pages": len(entries),
        "page_rows_synced": len(entries),
        "annotation_run": annotation_run,
        "annotation_error": annotation_error,
        "generated_images": generated_images,
        "image_generation_note": image_generation_note,
    }


def load_text_argument(*, text: str | None, text_file: str | None) -> str:
    if text:
        return text
    if text_file:
        return Path(text_file).read_text(encoding="utf-8")
    return ""
