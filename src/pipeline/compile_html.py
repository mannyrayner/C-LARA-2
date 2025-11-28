"""Compile annotated text JSON into interactive HTML outputs.

This module builds a lemma-based concordance, renders two-pane HTML with
interactive audio/gloss/MWE behaviors, and writes assets to disk so humans can
open the results directly for review.
"""
from __future__ import annotations

import html
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.telemetry import NullTelemetry, Telemetry


@dataclass(slots=True)
class CompileHTMLSpec:
    """Specification for compiling annotated text into HTML."""

    text: dict[str, Any]
    output_dir: Path | None = None
    run_id: str | None = None
    telemetry: Telemetry | None = None
    op_id: str | None = None
    title: str | None = None


def _is_lexical(surface: str) -> bool:
    if not surface or surface.isspace():
        return False
    # Treat alphanumerics and CJK as lexical; skip pure punctuation/whitespace.
    return any(ch.isalnum() for ch in surface) or any("\u4e00" <= ch <= "\u9fff" for ch in surface)


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _audio_path(path_str: str | None, root: Path) -> str | None:
    if not path_str:
        return None
    try:
        path = Path(path_str)
        return path.as_posix() if path.is_absolute() else (root / path).as_posix()
    except Exception:
        return path_str


def _token_display(token: dict[str, Any]) -> str:
    surface = token.get("surface", "")
    annotations = token.get("annotations", {}) or {}
    pinyin = annotations.get("pinyin")
    if pinyin:
        return f"<ruby><rb>{_escape(surface)}</rb><rt>{_escape(str(pinyin))}</rt></ruby>"
    return _escape(surface)


def _render_tokens(
    tokens: list[dict[str, Any]],
    *,
    page_index: int,
    segment_index: int,
    token_ids: dict[tuple[int, int, int], str],
    run_root: Path,
    token_info: list[dict[str, Any]],
) -> str:
    rendered: list[str] = []
    for idx, token in enumerate(tokens):
        annotations = token.get("annotations", {}) or {}
        surface = token.get("surface", "")
        token_id = token_ids.get((page_index, segment_index, idx))
        lexical = _is_lexical(surface) or bool(annotations)

        if not lexical:
            rendered.append(_escape(surface))
            continue

        data_attrs: list[str] = []
        if token_id:
            data_attrs.append(f'data-token-id="{token_id}"')
        lemma = annotations.get("lemma")
        gloss = annotations.get("gloss")
        mwe_id = annotations.get("mwe_id")
        pos = annotations.get("pos")
        audio_meta = annotations.get("audio")
        audio_path = None
        if isinstance(audio_meta, dict):
            audio_path = _audio_path(audio_meta.get("path"), run_root)

        if lemma:
            data_attrs.append(f'data-lemma="{_escape(str(lemma))}"')
        if gloss:
            data_attrs.append(f'data-gloss="{_escape(str(gloss))}"')
        if pos:
            data_attrs.append(f'data-pos="{_escape(str(pos))}"')
        if mwe_id:
            data_attrs.append(f'data-mwe-id="{_escape(str(mwe_id))}"')
        if audio_path:
            data_attrs.append(f'data-audio="{_escape(audio_path)}"')

        token_info.append(
            {
                "token_id": token_id,
                "lemma": lemma,
                "gloss": gloss,
                "mwe_id": mwe_id,
                "pos": pos,
                "surface": surface,
                "page_index": page_index,
                "segment_index": segment_index,
                "audio": audio_path,
            }
        )

        content = _token_display(token)
        rendered.append(
            f'<span class="token" {" ".join(data_attrs)}>{content}</span>'
        )
    return "".join(rendered)


def _build_concordance(
    text: dict[str, Any], token_info: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    concordance: dict[str, dict[str, Any]] = {}
    for meta in token_info:
        lemma = meta.get("lemma")
        if not lemma:
            continue
        lemma_key = str(lemma)
        entry = concordance.setdefault(
            lemma_key,
            {"lemma": lemma_key, "pos": meta.get("pos"), "gloss": meta.get("gloss"), "occurrences": []},
        )
        if entry.get("pos") is None and meta.get("pos"):
            entry["pos"] = meta.get("pos")
        if entry.get("gloss") is None and meta.get("gloss"):
            entry["gloss"] = meta.get("gloss")
        entry["occurrences"].append(
            {
                "token_id": meta.get("token_id"),
                "page_index": meta.get("page_index"),
                "segment_index": meta.get("segment_index"),
                "surface": meta.get("surface"),
                "mwe_id": meta.get("mwe_id"),
            }
        )
    return sorted(concordance.values(), key=lambda e: e["lemma"].lower())


def _render_concordance(
    concordance: list[dict[str, Any]], *, run_root: Path
) -> str:
    parts: list[str] = []
    for entry in concordance:
        lemma = _escape(entry["lemma"])
        header = [f"<div class=\"lemma-entry\" data-lemma=\"{lemma}\">"]
        header.append(f"<div class=\"lemma-head\"><strong>{lemma}</strong>")
        if entry.get("pos"):
            header.append(f" <span class=\"pos\">{_escape(str(entry['pos']))}</span>")
        if entry.get("gloss"):
            header.append(f" <span class=\"gloss\">{_escape(str(entry['gloss']))}</span>")
        header.append("</div>")

        body: list[str] = ["<ul class=\"occurrences\">"]
        for occ in entry.get("occurrences", []):
            attrs = [f'data-lemma="{lemma}"']
            if occ.get("mwe_id"):
                attrs.append(f'data-mwe-id="{_escape(str(occ["mwe_id"]))}"')
            if occ.get("token_id"):
                attrs.append(f'data-token-id="{_escape(str(occ["token_id"]))}"')
            body.append(
                f"<li class=\"occurrence\" {' '.join(attrs)}>{_escape(str(occ.get('surface', '')))}</li>"
            )
        body.append("</ul>")

        header.extend(body)
        header.append("</div>")
        parts.append("".join(header))
    return "\n".join(parts)


def _render_text_pane(text: dict[str, Any], *, run_root: Path) -> tuple[str, list[dict[str, Any]]]:
    token_ids: dict[tuple[int, int, int], str] = {}
    token_info: list[dict[str, Any]] = []
    counter = 0
    for p_idx, page in enumerate(text.get("pages", [])):
        for s_idx, segment in enumerate(page.get("segments", [])):
            for t_idx, _token in enumerate(segment.get("tokens", [])):
                token_ids[(p_idx, s_idx, t_idx)] = f"t{counter}"
                counter += 1

    pages_html: list[str] = []
    for p_idx, page in enumerate(text.get("pages", [])):
        page_audio = (page.get("annotations", {}) or {}).get("audio")
        page_audio_path = None
        if isinstance(page_audio, dict):
            page_audio_path = _audio_path(page_audio.get("path"), run_root)

        page_header_parts = [f"<div class=\"page\" data-page=\"{p_idx}\">"]
        page_header_parts.append(f"<div class=\"page-header\"><strong>Page {p_idx + 1}</strong>")
        if page_audio_path:
            page_header_parts.append(
                f" <button class=\"play\" data-audio=\"{_escape(page_audio_path)}\">Play page audio</button>"
            )
        page_header_parts.append("</div>")

        segments_html: list[str] = []
        for s_idx, segment in enumerate(page.get("segments", [])):
            translation = (segment.get("annotations", {}) or {}).get("translation")
            seg_audio = (segment.get("annotations", {}) or {}).get("audio")
            seg_audio_path = None
            if isinstance(seg_audio, dict):
                seg_audio_path = _audio_path(seg_audio.get("path"), run_root)

            tokens = segment.get("tokens") or []
            token_markup = _render_tokens(
                tokens,
                page_index=p_idx,
                segment_index=s_idx,
                token_ids=token_ids,
                run_root=run_root,
                token_info=token_info,
            )

            seg_parts = [f"<div class=\"segment\" data-segment=\"{s_idx}\">"]
            controls: list[str] = []
            if translation:
                controls.append(
                    "<button class=\"toggle-translation\" data-target='translation'>Show translation</button>"
                )
            if seg_audio_path:
                controls.append(f"<button class=\"play\" data-audio=\"{_escape(seg_audio_path)}\">Play audio</button>")
            if controls:
                seg_parts.append(f"<div class=\"segment-controls\">{' '.join(controls)}</div>")

            seg_parts.append(f"<div class=\"segment-surface\">{token_markup or _escape(segment.get('surface', ''))}</div>")
            if translation:
                seg_parts.append(
                    f"<div class=\"segment-translation hidden\">{_escape(str(translation))}</div>"
                )
            seg_parts.append("</div>")
            segments_html.append("".join(seg_parts))

        page_header_parts.append("".join(segments_html))
        page_header_parts.append("</div>")
        pages_html.append("".join(page_header_parts))

    return "\n".join(pages_html), token_info


def compile_html(spec: CompileHTMLSpec) -> dict[str, Any]:
    """Render annotated text into an HTML bundle and return artifact metadata."""

    telemetry = spec.telemetry or NullTelemetry()
    op_id = spec.op_id or "compile_html"

    out_root = spec.output_dir or Path("artifacts/html")
    run_id = spec.run_id or f"run_{uuid.uuid4().hex[:8]}"
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    text = spec.text
    title = spec.title or text.get("title") or "Annotated text"

    telemetry.event(op_id, "info", "Rendering HTML", {"output_dir": str(run_dir)})

    text_html, token_info = _render_text_pane(text, run_root=run_dir)
    concordance = _build_concordance(text, token_info)
    concordance_html = _render_concordance(concordance, run_root=run_dir)

    concordance_json = json.dumps(concordance, ensure_ascii=False, indent=2)

    css = """
    body { display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; font-family: Arial, sans-serif; margin: 0; padding: 1rem; }
    .pane { border: 1px solid #ccc; padding: 1rem; overflow: auto; max-height: 90vh; }
    .token { cursor: pointer; padding: 0 2px; }
    .token:hover { background: #fffae6; }
    .highlight { background: #d1e8ff; }
    .segment { margin-bottom: 0.75rem; }
    .segment-controls button { margin-right: 0.5rem; }
    .segment-translation.hidden { display: none; }
    .lemma-head { margin-bottom: 0.25rem; }
    .occurrence { cursor: pointer; margin-bottom: 0.25rem; }
    ruby rt { font-size: 0.75em; color: #555; }
    """

    js = """
    (() => {
      function playAudio(path) {
        if (!path) return;
        const audio = new Audio(path);
        audio.play().catch(() => {});
      }

      function clearHighlights() {
        document.querySelectorAll('.highlight').forEach(el => el.classList.remove('highlight'));
      }

      function highlightTokens(selector) {
        clearHighlights();
        document.querySelectorAll(selector).forEach(el => el.classList.add('highlight'));
      }

      document.addEventListener('click', (event) => {
        const target = event.target;
        if (target.dataset.audio) {
          playAudio(target.dataset.audio);
        }
        if (target.classList.contains('toggle-translation')) {
          const seg = target.closest('.segment');
          const translation = seg && seg.querySelector('.segment-translation');
          if (translation) translation.classList.toggle('hidden');
        }
        const lemma = target.dataset.lemma;
        if (lemma) {
          highlightTokens(`[data-lemma="${lemma}"]`);
        }
        const mwe = target.dataset.mweId;
        if (mwe) {
          highlightTokens(`[data-mwe-id="${mwe}"]`);
        }
      });

      document.addEventListener('mouseover', (event) => {
        const target = event.target;
        const mwe = target.dataset && target.dataset.mweId;
        if (mwe) highlightTokens(`[data-mwe-id="${mwe}"]`);
      });
      document.addEventListener('mouseout', () => clearHighlights());
    })();
    """

    html_doc = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>{_escape(str(title))}</title>
  <style>{css}</style>
</head>
<body>
  <div class=\"pane\" id=\"text-pane\">
    <h1>{_escape(str(title))}</h1>
    {text_html}
  </div>
  <div class=\"pane\" id=\"concordance-pane\">
    <h2>Concordance</h2>
    {concordance_html or '<p>No lemmas available.</p>'}
  </div>
  <script>window.concordance = {concordance_json};</script>
  <script>{js}</script>
</body>
</html>
"""

    html_path = run_dir / "index.html"
    html_path.write_text(html_doc, encoding="utf-8")
    telemetry.event(op_id, "info", "HTML written", {"path": str(html_path)})

    return {
        "html_path": str(html_path),
        "output_dir": str(run_dir),
        "concordance": concordance,
        "text": text,
    }


__all__ = ["CompileHTMLSpec", "compile_html"]
