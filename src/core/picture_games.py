"""Pure picture-clue puzzle builders shared by C-LARA and Community Dictionaries.

Extracted without behavioural changes from projects.views. No database, media
storage or provider dependencies: callers supply their own approved vocabulary.
"""
from __future__ import annotations

import random
import unicodedata
from typing import Any

WORD_SCRAMBLE_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 0),
    (1, 1),
    (-1, 1),
)
WORD_SCRAMBLE_DISTRACTOR_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _word_scramble_normalize_answer(value: str) -> str:
    return "".join(ch.upper() for ch in unicodedata.normalize("NFC", value or "") if ch.isalpha())


def _word_scramble_random_letters(candidates: list[dict[str, Any]]) -> list[str]:
    letters: list[str] = []
    for candidate in candidates:
        letters.extend(_word_scramble_normalize_answer(str(candidate.get("source_word") or "")))
    return letters or list(WORD_SCRAMBLE_DISTRACTOR_LETTERS)


def _word_scramble_can_place(
    grid: list[list[str | None]],
    word: str,
    row: int,
    col: int,
    dr: int,
    dc: int,
) -> bool:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    end_row = row + dr * (len(word) - 1)
    end_col = col + dc * (len(word) - 1)
    if end_row < 0 or end_row >= rows or end_col < 0 or end_col >= cols:
        return False
    for idx, letter in enumerate(word):
        cell = grid[row + dr * idx][col + dc * idx]
        if cell is not None and cell != letter:
            return False
    return True


def _word_scramble_place_word(
    grid: list[list[str | None]],
    word: str,
    rng: random.Random,
) -> list[dict[str, int]] | None:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    placements: list[tuple[int, int, int, int]] = []
    for row in range(rows):
        for col in range(cols):
            for dr, dc in WORD_SCRAMBLE_DIRECTIONS:
                if _word_scramble_can_place(grid, word, row, col, dr, dc):
                    placements.append((row, col, dr, dc))
    if not placements:
        return None
    row, col, dr, dc = rng.choice(placements)
    path: list[dict[str, int]] = []
    for idx, letter in enumerate(word):
        cell_row = row + dr * idx
        cell_col = col + dc * idx
        grid[cell_row][cell_col] = letter
        path.append({"row": cell_row, "col": cell_col})
    return path


def _generate_word_scramble_items(
    candidates: list[dict[str, Any]],
    *,
    item_count: int,
    rows: int,
    cols: int,
    seed: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create a single word-search-style grid and one picture-clue item per word."""

    rng = random.Random(seed)
    normalized_candidates: list[dict[str, Any]] = []
    seen_answers: set[str] = set()
    for candidate in candidates:
        answer = _word_scramble_normalize_answer(str(candidate.get("source_word") or ""))
        if len(answer) < 2 or len(answer) > max(rows, cols):
            continue
        if answer in seen_answers:
            continue
        seen_answers.add(answer)
        normalized_candidates.append({**candidate, "scramble_answer": answer})

    normalized_candidates.sort(
        key=lambda cand: (
            -len(str(cand.get("scramble_answer") or "")),
            str(cand.get("source_word") or "").casefold(),
        )
    )
    grid: list[list[str | None]] = [[None for _ in range(cols)] for _ in range(rows)]
    placed: list[tuple[dict[str, Any], list[dict[str, int]]]] = []
    for candidate in normalized_candidates:
        if len(placed) >= item_count:
            break
        answer = str(candidate["scramble_answer"])
        path = _word_scramble_place_word(grid, answer, rng)
        if path is None:
            continue
        placed.append((candidate, path))

    distractor_letters = _word_scramble_random_letters(normalized_candidates)
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] is None:
                grid[row][col] = rng.choice(distractor_letters)
    grid_rows = ["".join(str(cell) for cell in row) for row in grid]
    grid_payload = {
        "rows": rows,
        "cols": cols,
        "grid": grid_rows,
    }
    items: list[dict[str, Any]] = []
    for order_index, (candidate, path) in enumerate(placed):
        answer = str(candidate["scramble_answer"])
        items.append(
            {
                "order_index": order_index,
                "page_number": candidate["page_number"],
                "segment_index": candidate["segment_index"],
                "segment_text": candidate["segment_text"],
                "prompt": "Select the letters in the grid that match the picture clue.",
                "answer": answer,
                "options": [],
                "rationale": {
                    "exercise_kind": "word_scramble",
                    **grid_payload,
                    "path": path,
                    "display_answer": candidate.get("source_word") or answer,
                    "translation": candidate.get("target_gloss") or "",
                    "image_project_id": candidate.get("dictionary_project_id"),
                    "image_path": candidate.get("image_path"),
                    "dictionary_entry_id": candidate.get("dictionary_entry_id"),
                    "dictionary_surface": candidate.get("dictionary_surface") or "",
                    "dictionary_lemma": candidate.get("dictionary_lemma") or "",
                },
            }
        )
    return items, grid_payload


CROSSWORD_DIRECTIONS = {
    "across": (0, 1),
    "down": (1, 0),
}


def _crossword_can_place(
    grid: dict[tuple[int, int], str],
    word: str,
    row: int,
    col: int,
    direction: str,
    *,
    require_intersection: bool,
    max_grid_size: int,
) -> tuple[bool, int]:
    dr, dc = CROSSWORD_DIRECTIONS[direction]
    intersections = 0
    end_row = row + dr * (len(word) - 1)
    end_col = col + dc * (len(word) - 1)
    if min(row, col, end_row, end_col) < 0 or max(row, col, end_row, end_col) >= max_grid_size:
        return False, 0
    before = (row - dr, col - dc)
    after = (end_row + dr, end_col + dc)
    if before in grid or after in grid:
        return False, 0
    for idx, letter in enumerate(word):
        pos = (row + dr * idx, col + dc * idx)
        existing = grid.get(pos)
        if existing is not None:
            if existing != letter:
                return False, 0
            intersections += 1
            continue
        if direction == "across":
            if (pos[0] - 1, pos[1]) in grid or (pos[0] + 1, pos[1]) in grid:
                return False, 0
        else:
            if (pos[0], pos[1] - 1) in grid or (pos[0], pos[1] + 1) in grid:
                return False, 0
    if require_intersection and intersections == 0:
        return False, 0
    return True, intersections


def _crossword_path(word: str, row: int, col: int, direction: str) -> list[dict[str, int]]:
    dr, dc = CROSSWORD_DIRECTIONS[direction]
    return [{"row": row + dr * idx, "col": col + dc * idx} for idx, _letter in enumerate(word)]


def _crossword_place_word(
    grid: dict[tuple[int, int], str],
    word: str,
    row: int,
    col: int,
    direction: str,
) -> list[dict[str, int]]:
    path = _crossword_path(word, row, col, direction)
    for idx, pos in enumerate(path):
        grid[(pos["row"], pos["col"])] = word[idx]
    return path


def _crossword_find_intersection_placement(
    grid: dict[tuple[int, int], str],
    placed_words: list[dict[str, Any]],
    word: str,
    *,
    max_grid_size: int,
) -> tuple[int, int, str, int] | None:
    options: list[tuple[int, int, str, int]] = []
    for placed in placed_words:
        next_direction = "down" if placed["direction"] == "across" else "across"
        for placed_idx, placed_cell in enumerate(placed["path"]):
            placed_letter = placed["answer"][placed_idx]
            for word_idx, letter in enumerate(word):
                if letter != placed_letter:
                    continue
                dr, dc = CROSSWORD_DIRECTIONS[next_direction]
                row = placed_cell["row"] - dr * word_idx
                col = placed_cell["col"] - dc * word_idx
                can_place, intersections = _crossword_can_place(
                    grid,
                    word,
                    row,
                    col,
                    next_direction,
                    require_intersection=True,
                    max_grid_size=max_grid_size,
                )
                if can_place:
                    options.append((row, col, next_direction, intersections))
    if not options:
        return None
    options.sort(key=lambda item: (-item[3], item[0], item[1], item[2]))
    return options[0]


def _crossword_find_disconnected_placement(
    grid: dict[tuple[int, int], str],
    word: str,
    *,
    max_grid_size: int,
) -> tuple[int, int, str] | None:
    for row in range(max_grid_size):
        for col in range(max_grid_size):
            for direction in ("across", "down"):
                can_place, _intersections = _crossword_can_place(
                    grid,
                    word,
                    row,
                    col,
                    direction,
                    require_intersection=False,
                    max_grid_size=max_grid_size,
                )
                if can_place:
                    return row, col, direction
    return None


def _build_crossword_item(
    candidates: list[dict[str, Any]],
    *,
    item_count: int,
    max_grid_size: int,
) -> dict[str, Any] | None:
    normalized_candidates: list[dict[str, Any]] = []
    seen_answers: set[str] = set()
    for candidate in candidates:
        answer = _word_scramble_normalize_answer(str(candidate.get("source_word") or ""))
        if len(answer) < 2 or len(answer) > max_grid_size:
            continue
        if answer in seen_answers:
            continue
        seen_answers.add(answer)
        normalized_candidates.append({**candidate, "crossword_answer": answer})
    normalized_candidates.sort(
        key=lambda cand: (
            -len(str(cand.get("crossword_answer") or "")),
            str(cand.get("source_word") or "").casefold(),
        )
    )
    selected = normalized_candidates[:item_count]
    if not selected:
        return None

    grid: dict[tuple[int, int], str] = {}
    placed_words: list[dict[str, Any]] = []
    unplaced_words: list[str] = []
    first = selected[0]
    first_answer = str(first["crossword_answer"])
    first_row = max_grid_size // 2
    first_col = max(0, (max_grid_size - len(first_answer)) // 2)
    first_path = _crossword_place_word(grid, first_answer, first_row, first_col, "across")
    placed_words.append({**first, "answer": first_answer, "direction": "across", "path": first_path})

    disconnected_used = False
    for candidate in selected[1:]:
        answer = str(candidate["crossword_answer"])
        placement = _crossword_find_intersection_placement(
            grid,
            placed_words,
            answer,
            max_grid_size=max_grid_size,
        )
        if placement is not None:
            row, col, direction, _intersections = placement
            path = _crossword_place_word(grid, answer, row, col, direction)
            placed_words.append({**candidate, "answer": answer, "direction": direction, "path": path})
            continue
        if not disconnected_used:
            fallback = _crossword_find_disconnected_placement(grid, answer, max_grid_size=max_grid_size)
            if fallback is not None:
                row, col, direction = fallback
                path = _crossword_place_word(grid, answer, row, col, direction)
                placed_words.append({**candidate, "answer": answer, "direction": direction, "path": path, "disconnected": True})
                disconnected_used = True
                continue
        unplaced_words.append(str(candidate.get("source_word") or answer))

    if not placed_words:
        return None
    min_row = min(row for row, _col in grid)
    max_row = max(row for row, _col in grid)
    min_col = min(col for _row, col in grid)
    max_col = max(col for _row, col in grid)
    for placed in placed_words:
        for cell in placed["path"]:
            cell["row"] -= min_row
            cell["col"] -= min_col
    shifted_grid = {(row - min_row, col - min_col): letter for (row, col), letter in grid.items()}
    rows = max_row - min_row + 1
    cols = max_col - min_col + 1

    starts: dict[tuple[int, int], int] = {}
    next_number = 1
    for placed in sorted(placed_words, key=lambda item: (item["path"][0]["row"], item["path"][0]["col"], item["direction"])):
        start = (placed["path"][0]["row"], placed["path"][0]["col"])
        if start not in starts:
            starts[start] = next_number
            next_number += 1
        placed["number"] = starts[start]
        placed["clue_id"] = f"{placed['direction']}-{placed['number']}-{placed['answer'].lower()}"

    grid_rows: list[list[dict[str, Any]]] = []
    for row in range(rows):
        rendered_row: list[dict[str, Any]] = []
        for col in range(cols):
            letter = shifted_grid.get((row, col))
            rendered_row.append(
                {
                    "row": row,
                    "col": col,
                    "letter": letter or "",
                    "is_black": letter is None,
                    "number": starts.get((row, col)),
                }
            )
        grid_rows.append(rendered_row)

    clues_by_direction = {"across": [], "down": []}
    option_images: dict[str, dict[str, Any]] = {}
    for placed in placed_words:
        clue = {
            "clue_id": placed["clue_id"],
            "number": placed["number"],
            "direction": placed["direction"],
            "answer": placed["answer"],
            "display_answer": placed.get("source_word") or placed["answer"],
            "translation": placed.get("target_gloss") or "",
            "path": placed["path"],
            "dictionary_entry_id": placed.get("dictionary_entry_id"),
            "image_project_id": placed.get("dictionary_project_id"),
            "image_path": placed.get("image_path"),
            "page_number": placed.get("page_number"),
            "segment_index": placed.get("segment_index"),
            "disconnected": bool(placed.get("disconnected")),
        }
        clues_by_direction[placed["direction"]].append(clue)
        option_images[placed["clue_id"]] = {
            "source_word": clue["display_answer"],
            "image_project_id": clue["image_project_id"],
            "image_path": clue["image_path"],
        }
    for clues in clues_by_direction.values():
        clues.sort(key=lambda clue: (clue["number"], clue["display_answer"]))

    path_counts: dict[tuple[int, int], int] = {}
    for placed in placed_words:
        for cell in placed["path"]:
            pos = (cell["row"], cell["col"])
            path_counts[pos] = path_counts.get(pos, 0) + 1
    intersections = sum(1 for count in path_counts.values() if count > 1)
    summary = {
        "selected_count": len(selected),
        "placed_count": len(placed_words),
        "unplaced_words": unplaced_words,
        "intersection_count": intersections,
        "has_disconnected_fallback": any(bool(placed.get("disconnected")) for placed in placed_words),
    }
    first_candidate = placed_words[0]
    return {
        "order_index": 0,
        "page_number": first_candidate.get("page_number") or 1,
        "segment_index": first_candidate.get("segment_index") or 0,
        "segment_text": "Picture-clue crossword",
        "prompt": "Review this picture-clue crossword layout.",
        "answer": "",
        "options": [],
        "rationale": {
            "exercise_kind": "crossword",
            "rows": rows,
            "cols": cols,
            "grid": grid_rows,
            "clues": clues_by_direction,
            "option_images": option_images,
            "summary": summary,
        },
    }


def _exercise_base_form(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in decomposed if ch.isalnum())


def _exercise_edit_distance_at_most_one(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if left == right:
        return True
    if len(left) == len(right):
        return sum(1 for a, b in zip(left, right) if a != b) <= 1
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    for idx in range(len(longer)):
        if longer[:idx] + longer[idx + 1 :] == shorter:
            return True
    return False


def _exercise_near_duplicate(left: str, right: str) -> bool:
    left_base = _exercise_base_form(left)
    right_base = _exercise_base_form(right)
    if not left_base or not right_base:
        return False
    if left_base == right_base:
        return True
    shorter, longer = (left_base, right_base) if len(left_base) < len(right_base) else (right_base, left_base)
    if len(shorter) >= 4 and longer.startswith(shorter):
        return True
    return _exercise_edit_distance_at_most_one(left_base, right_base)
