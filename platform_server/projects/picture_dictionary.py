from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import Community, CommunityMembership, PictureDictionary, Project
from .views import _ensure_project_page_rows


def _normalise_word(word: str) -> str:
    return re.sub(r"\s+", " ", str(word or "").strip())


def _entry_pages(project: Project) -> list[str]:
    pages = [chunk.strip() for chunk in re.split(r"(?i)<\s*page\s*/?\s*>", project.source_text or "") if chunk.strip()]
    return pages


def _set_entry_pages(project: Project, pages: Iterable[str]) -> None:
    normalized = [_normalise_word(page) for page in pages]
    normalized = [page for page in normalized if page]
    project.source_text = "<page>".join(normalized)
    project.input_mode = Project.INPUT_SOURCE
    project.save(update_fields=["source_text", "input_mode", "updated_at"])


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
    return PictureDictionary.objects.create(
        community=community,
        project=project,
        organiser=organiser,
        language=community.language or project.language,
    )


def add_words(*, dictionary: PictureDictionary, words: Iterable[str]) -> int:
    pages = _entry_pages(dictionary.project)
    existing_keys = {page.casefold() for page in pages}
    added = 0
    for word in words:
        normalized = _normalise_word(word)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in existing_keys:
            continue
        pages.append(normalized)
        existing_keys.add(key)
        added += 1
    _set_entry_pages(dictionary.project, pages)
    return added


def remove_words(*, dictionary: PictureDictionary, words: Iterable[str]) -> int:
    pages = _entry_pages(dictionary.project)
    removal_keys = {_normalise_word(word).casefold() for word in words if _normalise_word(word)}
    if not removal_keys:
        return 0
    kept = [page for page in pages if page.casefold() not in removal_keys]
    removed = len(pages) - len(kept)
    if removed:
        _set_entry_pages(dictionary.project, kept)
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


def compile_picture_dictionary(*, dictionary: PictureDictionary) -> dict[str, int]:
    pages_synced = _ensure_project_page_rows(dictionary.project)
    return {
        "pages": len(_entry_pages(dictionary.project)),
        "page_rows_synced": pages_synced,
    }


def load_text_argument(*, text: str | None, text_file: str | None) -> str:
    if text:
        return text
    if text_file:
        return Path(text_file).read_text(encoding="utf-8")
    return ""
