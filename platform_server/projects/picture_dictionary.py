from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import (
    Community,
    CommunityMembership,
    PictureDictionary,
    PictureDictionaryEntry,
    Project,
    ProjectImagePage,
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
    (run_dir / "segmentation_phase_1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
        (run_dir / f"{stage_name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


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
