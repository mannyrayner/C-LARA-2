from __future__ import annotations

import json
import logging
import re
import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from django.core.exceptions import PermissionDenied
from django.db import transaction
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


def _page_has_non_null_translation(page: dict) -> bool:
    for segment in page.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        if _non_null_text((segment.get("annotations") or {}).get("translation")):
            return True
        for token in segment.get("tokens") or []:
            if not isinstance(token, dict):
                continue
            if _non_null_text((token.get("annotations") or {}).get("translation")):
                return True
    return False


def _first_translated_token(page: dict) -> dict | None:
    fallback: dict | None = None
    for segment in page.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        for token in segment.get("tokens") or []:
            if not isinstance(token, dict):
                continue
            surface = _normalise_word(token.get("surface") or "")
            if not surface or not _token_surface_is_word(surface):
                continue
            if fallback is None:
                fallback = token
            if _non_null_text((token.get("annotations") or {}).get("translation")):
                return token
    return fallback


def _extract_dictionary_seed_pages(source_project: Project) -> tuple[list[dict], list[str]]:
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
        if not _page_has_non_null_translation(page):
            discarded_without_translation += 1
            continue
        token = _first_translated_token(page)
        surface = _normalise_word((token or {}).get("surface") or page.get("surface") or "")
        if not surface:
            discarded_without_word += 1
            continue
        annotations = (token or {}).get("annotations") or {}
        retained.append(
            {
                "old_page_number": old_page_number,
                "surface": surface,
                "lemma": _normalise_word(annotations.get("lemma") or surface),
                "pos": _normalise_word(annotations.get("pos") or "").upper(),
                "translation": _non_null_text(annotations.get("translation")),
                "image_page": image_pages.get(old_page_number),
            }
        )
    diagnostics.append(f"Retained {len(retained)} page(s) with non-null translations.")
    if discarded_without_translation:
        diagnostics.append(f"Discarded {discarded_without_translation} page(s) without non-null translations.")
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
            "discourage_text_in_images": style.discourage_text_in_images,
            "ai_model": style.ai_model,
            "status": style.status,
        },
    )


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
        image_path = getattr(image_page, "image_path", "") if image_page else ""
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
    _write_dictionary_annotation_stages(dictionary, created_entries)

    summary = {
        "source_project_id": source_project.id,
        "source_project_title": source_project.title,
        "target_project_id": target_project.id,
        "old_dictionary_project_id": old_project_id,
        "entries_created": len(retained_pages),
        "page_map": page_map,
        "diagnostics": diagnostics,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_dir = target_project.artifact_dir() / "picture_dictionary_import"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _sync_project_source_from_registry(dictionary)
    return dictionary, summary


@transaction.atomic
def ensure_picture_dictionary_for_community(*, community: Community, organiser) -> PictureDictionary:
    _require_organiser(community, organiser)
    existing = PictureDictionary.objects.select_related("project").filter(community=community).first()
    if existing:
        _bootstrap_registry_from_project_source(existing)
        _sync_project_source_from_registry(existing)
        return existing
    project = Project.objects.create(
        owner=organiser,
        title=f"{community.name} picture dictionary",
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
            entry.save(update_fields=["is_active", "current_page_number", "updated_at"])
            removed += 1
    if removed:
        _sync_project_source_from_registry(dictionary)
    return removed


def remove_entries_by_ids(*, dictionary: PictureDictionary, entry_ids: Iterable[int]) -> int:
    ids = {int(pk) for pk in entry_ids}
    removed = 0
    for entry in dictionary.entries.filter(id__in=ids, is_active=True):
        entry.is_active = False
        entry.current_page_number = None
        entry.save(update_fields=["is_active", "current_page_number", "updated_at"])
        removed += 1
    if removed:
        _sync_project_source_from_registry(dictionary)
    return removed


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
    for stage_name in ("segmentation_phase_2", "mwe", "lemma", "gloss", "romanization", "pinyin"):
        payload = _dictionary_stage_payload(dictionary, entries, stage_name)
        write_stage_artifact(run_dir.parent, stage_name, payload)


def compile_picture_dictionary(
    *,
    dictionary: PictureDictionary,
    progress_callback: Callable[[str], None] | None = None,
    compile_task_report_id: str | None = None,
    compile_task_user_id: int | None = None,
    compile_task_type: str | None = None,
) -> dict[str, object]:
    def _post_progress(message: str) -> None:
        if progress_callback:
            progress_callback(message)

    _bootstrap_registry_from_project_source(dictionary)
    entries = list(dictionary.entries.filter(is_active=True).order_by("id"))
    _sync_project_source_from_registry(dictionary)
    _post_progress(f"Dictionary text compilation started for {len(entries)} image entr{'y' if len(entries) == 1 else 'ies'}.")
    _post_progress("Text phase 1/3: syncing dictionary entries to image pages.")

    for idx, entry in enumerate(entries, start=1):
        existing = ProjectImagePage.objects.filter(project=dictionary.project, page_number=idx).first()
        if existing:
            changed = False
            if existing.page_text != entry.surface:
                existing.page_text = entry.surface
                changed = True
            if existing.generation_prompt != entry.surface:
                existing.generation_prompt = entry.surface
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
                page_text=entry.surface,
                generation_prompt=entry.surface,
                image_model="gpt-image-1",
                image_path=entry.image_path,
            )
            entry.current_page_number = idx
            if not entry.image_path and page.image_path:
                entry.image_path = page.image_path
            entry.save(update_fields=["image_path", "current_page_number", "updated_at"])

    ProjectImagePage.objects.filter(project=dictionary.project, page_number__gt=len(entries)).delete()
    _post_progress("Text phase 2/3: writing segmentation and annotation stage artifacts.")
    _write_segmentation_phase_1(dictionary, entries)
    _write_dictionary_annotation_stages(dictionary, entries)
    annotation_run = "skipped"
    annotation_error = ""
    generated_images = 0
    image_generation_note = ""
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

    _post_progress(f"Dictionary image compilation started for {len(entries)} image entr{'y' if len(entries) == 1 else 'ies'}.")
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
        if style_usable:
            from .views import _generate_project_page_images

            generated_images = _generate_project_page_images(
                dictionary.project,
                image_model=style.sample_image_model or "gpt-image-1",
                variants_per_page=1,
                discourage_text_in_image=bool(style.discourage_text_in_images),
                include_full_text=False,
                include_elements=False,
                missing_only=True,
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
