"""Compile annotated text JSON into interactive HTML outputs.

We mirror the original C-LARA layout by emitting one HTML page per text page
and one concordance page per lemma. Each text page hosts navigation controls,
an embedded concordance pane (via ``<iframe>``), and JS that coordinates
cross-pane highlighting and audio playback.
"""
from __future__ import annotations

import html
from collections import defaultdict
import os
import json
import uuid
import textwrap
import hashlib
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

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


def _encode_lemma_for_filename(lemma: str) -> str:
    """Encode lemma text so concordance filenames are filesystem-safe."""

    if not lemma:
        return "unknown"

    encoded = quote(lemma, safe="~()*!.'-_")
    return encoded or "unknown"


def _escape(text: str) -> str:
    # Normalize to NFC to keep accents intact, then emit numeric character
    # references for any non-ASCII symbols so browsers render them correctly
    # regardless of local encodings.
    normalized = unicodedata.normalize("NFC", text)
    escaped = html.escape(normalized, quote=True)
    return escaped.encode("ascii", "xmlcharrefreplace").decode("ascii")


def _audio_path(path_str: str | None, root: Path) -> str | None:
    """Return an audio path relative to the HTML run root when possible."""

    if not path_str:
        return None

    try:
        path = Path(path_str)
        path_abs = path if path.is_absolute() else path.resolve()
        # Prefer a relative path so opening ``page_X.html`` directly can locate audio.
        rel = os.path.relpath(path_abs, root)
        return rel.replace("\\", "/")
    except Exception:
        try:
            return Path(path_str).as_posix()
        except Exception:
            return path_str


class _AudioResolver:
    """Copy audio into the run directory and return paths relative to HTML."""

    def __init__(self, artifact_root: Path, html_root: Path):
        self.artifact_root = artifact_root
        self.html_root = html_root
        self.audio_dir = artifact_root / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[Path, str] = {}

    def resolve(self, path_str: str | None) -> str | None:
        if not path_str:
            return None

        try:
            src = Path(path_str)
            if src.exists():
                key = src.resolve()
                if key in self._cache:
                    return self._cache[key]

                digest = hashlib.sha1(str(key).encode("utf-8")).hexdigest()
                suffix = src.suffix or ".wav"
                dest = self.audio_dir / f"{digest}{suffix}"
                shutil.copy2(key, dest)
                rel = os.path.relpath(dest, self.html_root)
                rel_posix = Path(rel).as_posix()
                self._cache[key] = rel_posix
                return rel_posix
        except Exception:
            pass

        # Fallback to best-effort relative path without copying.
        return _audio_path(path_str, self.html_root)


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
    resolver: _AudioResolver,
    token_info: list[dict[str, Any]],
    highlight_lemma: str | None = None,
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
        classes: list[str] = ["token"]
        if token_id:
            data_attrs.append(f'data-token-id="{token_id}"')
        lemma = annotations.get("lemma")
        gloss = annotations.get("gloss")
        mwe_id = annotations.get("mwe_id")
        pos = annotations.get("pos")
        audio_meta = annotations.get("audio")
        audio_path = None
        if isinstance(audio_meta, dict):
            audio_path = resolver.resolve(audio_meta.get("path"))

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
        if highlight_lemma and lemma and str(lemma) == highlight_lemma:
            classes.append("concordance-highlight")

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
        class_attr = " ".join(classes)
        data_attr_str = " ".join(data_attrs)
        rendered.append(
            f'<span class="{class_attr}" {data_attr_str}>{content}</span>'
        )
    return "".join(rendered)


def _token_ids(text: dict[str, Any]) -> dict[tuple[int, int, int], str]:
    token_ids: dict[tuple[int, int, int], str] = {}
    counter = 0
    for p_idx, page in enumerate(text.get("pages", [])):
        for s_idx, segment in enumerate(page.get("segments", [])):
            for t_idx, _token in enumerate(segment.get("tokens", [])):
                token_ids[(p_idx, s_idx, t_idx)] = f"t{counter}"
                counter += 1
    return token_ids


def _render_segment(
    segment: dict[str, Any],
    *,
    page_index: int,
    segment_index: int,
    token_ids: dict[tuple[int, int, int], str],
    resolver: _AudioResolver,
    token_info: list[dict[str, Any]],
    highlight_lemma: str | None = None,
    include_translation: bool = True,
) -> str:
    seg_audio = (segment.get("annotations", {}) or {}).get("audio")
    seg_audio_path = None
    if isinstance(seg_audio, dict):
        seg_audio_path = resolver.resolve(seg_audio.get("path"))
    translation = None
    if include_translation:
        translation = (segment.get("annotations", {}) or {}).get("translation")

    parts: list[str] = [f'<div class="segment" data-segment="{segment_index}">']
    controls: list[str] = ["<div class=\"segment-controls\">"]
    if include_translation:
        controls.append("<button class=\"toggle-translation\" data-target='translation'>Show translation</button>")
    if seg_audio_path:
        controls.append(
            f' <button class="play" data-audio="{_escape(seg_audio_path)}">Play audio</button>'
        )
    controls.append("</div>")
    parts.append("".join(controls))

    tokens_html = _render_tokens(
        segment.get("tokens", []),
        page_index=page_index,
        segment_index=segment_index,
        token_ids=token_ids,
        resolver=resolver,
        token_info=token_info,
        highlight_lemma=highlight_lemma,
    )
    parts.append(f"<div class=\"segment-surface\">{tokens_html}</div>")
    if translation:
        parts.append(f'<div class="segment-translation hidden">{_escape(str(translation))}</div>')
    parts.append("</div>")
    return "".join(parts)


def _render_page(
    *,
    text: dict[str, Any],
    page_index: int,
    token_ids: dict[tuple[int, int, int], str],
    resolver: _AudioResolver,
    token_info: list[dict[str, Any]],
    total_pages: int,
    title: str | None,
) -> str:
    page = text.get("pages", [])[page_index]
    page_audio = (page.get("annotations", {}) or {}).get("audio")
    page_audio_path = None
    if isinstance(page_audio, dict):
        page_audio_path = resolver.resolve(page_audio.get("path"))

    nav = ["<nav class=\"nav-bar\">"]
    first = 1
    last = total_pages
    current = page_index + 1
    nav.append(f'<a href="page_{first}.html" class="">&#x21E4;</a>')
    prev_page = max(first, current - 1)
    nav.append(f'<a href="page_{prev_page}.html" class="">&#x2190;</a>')
    next_page = min(last, current + 1)
    nav.append(f'<a href="page_{next_page}.html" class="">&#x2192;</a>')
    nav.append(f'<a href="page_{last}.html" class="">&#x21E5;</a>')
    nav.append("</nav>")

    header_parts = ["<header>"]
    display_title = title or "Annotated text"
    header_parts.append(f"<p>{_escape(display_title)} p. {current}/{last}</p>")
    header_parts.append("".join(nav))
    header_parts.append("</header>")

    segments_html: list[str] = []
    for s_idx, segment in enumerate(page.get("segments", [])):
        segments_html.append(
            _render_segment(
                segment,
                page_index=page_index,
                segment_index=s_idx,
                token_ids=token_ids,
                resolver=resolver,
                token_info=token_info,
            )
        )

    page_audio_control = ""
    if page_audio_path:
        page_audio_control = (
            f"<p><button class=\"play\" data-audio=\"{_escape(page_audio_path)}\">Play page audio</button></p>"
        )

    body = (
        "<div class=\"page-container\">"
        "<div class=\"main-text-pane-wrapper\">"
        f"<div class=\"page\" id=\"main-text-pane\">{page_audio_control}{''.join(segments_html)}</div>"
        "</div>"
        "<div class=\"concordance-pane-wrapper\"><iframe id=\"concordance-pane\" src=\"\" frameborder=\"0\" class=\"concordance-iframe\"></iframe></div>"
        "</div>"
    )

    html_doc = f"""<!DOCTYPE html>
<html lang=\"en\" dir=\"ltr\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>Page {current}</title>\n  <link rel=\"stylesheet\" href=\"./static/clara_styles_main.css\">\n</head>\n<body>\n{''.join(header_parts)}\n{body}\n<footer>{''.join(nav)}</footer>\n<script src=\"./static/clara_scripts.js\"></script>\n</body>\n</html>\n"""
    return html_doc


def _build_concordance(
    text: dict[str, Any], token_info: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    concordance: dict[str, dict[str, Any]] = {}
    # For MWEs, multiple tokens share the same lemma; we only want to list each
    # segment once per MWE so the concordance does not show duplicate lines.
    seen_mwe: dict[str, set[tuple[Any, Any, Any]]] = defaultdict(set)
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

        mwe_id = meta.get("mwe_id")
        if mwe_id is not None:
            dedup_key = (mwe_id, meta.get("page_index"), meta.get("segment_index"))
            if dedup_key in seen_mwe[lemma_key]:
                continue
            seen_mwe[lemma_key].add(dedup_key)

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


def _render_concordance_page(
    *,
    entry: dict[str, Any],
    text: dict[str, Any],
    token_ids: dict[tuple[int, int, int], str],
    resolver: _AudioResolver,
) -> str:
    lemma = entry.get("lemma") or ""
    heading = _escape(str(lemma))

    def segments_for_occurrences(occurrences: Iterable[dict[str, Any]]) -> list[str]:
        seg_parts: list[str] = []
        for occ in occurrences:
            p_idx = occ.get("page_index", 0)
            s_idx = occ.get("segment_index", 0)
            page = text.get("pages", [])[p_idx]
            segment = page.get("segments", [])[s_idx]
            back_arrow = (
                f'<span class="back-arrow-icon" data-segment-index="{s_idx}" data-page-number="{p_idx + 1}" data-token-id="{_escape(str(occ.get("token_id")))}">&#x2190;</span> '
            )
            tokens_html = _render_tokens(
                segment.get("tokens", []),
                page_index=p_idx,
                segment_index=s_idx,
                token_ids=token_ids,
                resolver=resolver,
                token_info=[],
                highlight_lemma=str(lemma),
            )
            seg_audio = (segment.get("annotations", {}) or {}).get("audio")
            seg_audio_path = None
            if isinstance(seg_audio, dict):
                seg_audio_path = resolver.resolve(seg_audio.get("path"))
            seg_attrs = [f'data-segment-index="{s_idx}"']
            if seg_audio_path:
                seg_attrs.append(f'data-segment-audio="{_escape(seg_audio_path)}"')
            seg_parts.append(
                f"<span class=\"segment\" {' '.join(seg_attrs)}>{back_arrow}{tokens_html}</span>"
            )
        return seg_parts

    body = "\n".join(segments_for_occurrences(entry.get("occurrences", [])))

    html_doc = f"""<!DOCTYPE html>
<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>Concordance: {heading}</title>\n  <link rel=\"stylesheet\" href=\"./static/clara_styles_concordance.css\">\n</head>\n<body>\n  <div class=\"concordance\" id=\"concordance_{heading}\">\n    <h1>{heading}</h1>\n    {body}\n  </div>\n  <script src=\"./static/clara_scripts.js\"></script>\n</body>\n</html>\n"""
    return html_doc


def _write_static_assets(root: Path) -> None:
    static_dir = root / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "clara_styles_main.css").write_text(
        """body { font-family: Arial, sans-serif; margin: 0; padding: 1rem; }
nav a { margin-right: 0.5rem; }
.page-container { display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; }
.main-text-pane-wrapper, .concordance-pane-wrapper { border: 1px solid #ccc; padding: 1rem; max-height: 90vh; overflow: auto; }
.segment { display: block; margin-bottom: 0.75rem; }
.segment-controls button { margin-right: 0.5rem; }
.segment-translation.hidden { display: none; }
.token { cursor: pointer; padding: 0; }
.token:hover { background: #fffae6; }
.concordance-highlight { background: #d1e8ff; }
.mwe-highlight { background: #cce2ff; }
.mwe-group-hover { background: #e1f1ff; }
.gloss-popup { position: absolute; background: rgba(0,0,0,0.85); color: #fff; padding: 4px 8px; border-radius: 3px; font-size: 0.9em; z-index: 20; }
.page audio { margin: 0.5rem 0; }
.concordance-iframe { width: 100%; height: 85vh; border: none; }
""",
        encoding="utf-8",
    )

    (static_dir / "clara_styles_concordance.css").write_text(
        """body { font-family: Arial, sans-serif; margin: 1rem; }
.segment { display: block; margin-bottom: 0.75rem; }
.word { cursor: pointer; padding: 0; }
.word:hover { background: #fffae6; }
.concordance-highlight { background: #d1e8ff; }
.mwe-group-hover { background: #e1f1ff; }
.back-arrow-icon { cursor: pointer; margin-right: 0.35rem; }
.gloss-popup { position: absolute; background: rgba(0,0,0,0.85); color: #fff; padding: 4px 8px; border-radius: 3px; font-size: 0.9em; z-index: 20; }
.translation-popup { position: absolute; background: rgba(0,0,0,0.8); color: #fff; padding: 4px 10px; border-radius: 3px; z-index: 10; }
""",
        encoding="utf-8",
    )

    js = textwrap.dedent("""
        function removeClassAfterDuration(element, className, duration) {
          setTimeout(() => { element.classList.remove(className); }, duration);
        }

      function loadConcordance(lemma, contextDocument) {
        const targetDoc = contextDocument || document;
        const pane = targetDoc.getElementById('concordance-pane');
        const encoded = encodeURIComponent(lemma);
        const target = `concordance_${encoded}.html`;
        if (pane) { pane.src = target; }
        if (window.parent !== window) {
          window.parent.postMessage({ type: 'loadConcordance', data: { lemma } }, '*');
        }
      }

        function postMessageToParent(type, data) {
          if (window.parent !== window) {
            window.parent.postMessage({ type, data }, '*');
          }
        }

        function setUpEventListeners(contextDocument) {
          const doc = contextDocument || document;
          const tokens = doc.querySelectorAll('.token, .word');
          const speakerIcons = doc.querySelectorAll('.speaker-icon');
          const translationIcons = doc.querySelectorAll('.translation-icon');
          const translationToggleButtons = doc.querySelectorAll('.toggle-translation');
          const playButtons = doc.querySelectorAll('.play');
          let glossPopup = null;

    tokens.forEach(token => {
        token.addEventListener('click', () => {
            const audioSrc = token.dataset.audio;
            if (audioSrc) { const audio = new Audio(audioSrc); audio.play().catch(() => {}); }
            const lemma = token.dataset.lemma;
            if (lemma) { loadConcordance(lemma, doc); }
            const mwe = token.dataset.mweId;
            if (mwe) { highlightMwe(mwe, doc, token); }
        });

        token.addEventListener('mouseover', () => {
            const gloss = token.dataset.gloss;
            if (gloss) {
                if (glossPopup) { glossPopup.remove(); }
                glossPopup = document.createElement('div');
                glossPopup.classList.add('gloss-popup');
                glossPopup.innerText = gloss;
                const rect = token.getBoundingClientRect();
                glossPopup.style.top = `${rect.top + window.scrollY - 28}px`;
                glossPopup.style.left = `${rect.left + window.scrollX}px`;
                (doc.body || document.body).appendChild(glossPopup);
            }
            const mwe = token.dataset.mweId;
            if (mwe) {
              token.classList.add('mwe-group-hover');
              doc.querySelectorAll(`[data-mwe-id="${mwe}"]`).forEach(el => el.classList.add('mwe-group-hover'));
            }
        });

        token.addEventListener('mouseout', () => {
            if (glossPopup) { glossPopup.remove(); glossPopup = null; }
            const mwe = token.dataset.mweId;
            if (mwe) {
              token.classList.remove('mwe-group-hover');
              doc.querySelectorAll(`[data-mwe-id="${mwe}"]`).forEach(el => el.classList.remove('mwe-group-hover'));
            }
        });
    });

          speakerIcons.forEach(icon => {
            icon.addEventListener('click', () => {
              const seg = icon.closest('.segment');
              const audioSrc = seg && seg.dataset.segmentAudio;
              if (audioSrc) { const audio = new Audio(audioSrc); audio.play().catch(() => {}); }
            });
          });

          playButtons.forEach(btn => {
            btn.addEventListener('click', () => {
              const audioSrc = btn.dataset.audio;
              if (audioSrc) { const audio = new Audio(audioSrc); audio.play().catch(() => {}); }
            });
          });

          translationIcons.forEach(icon => {
            icon.addEventListener('click', () => {
              const translationText = icon.dataset.translation;
              const popup = document.createElement('div');
              popup.classList.add('translation-popup');
              popup.innerText = translationText || '';
              const rect = icon.getBoundingClientRect();
              popup.style.top = `${rect.top + window.scrollY + 20}px`;
              popup.style.left = `${rect.left + window.scrollX}px`;
              document.body.appendChild(popup);
              document.addEventListener('click', function removePopup(event) {
                if (!popup.contains(event.target) && event.target !== icon) {
                  popup.remove();
                  document.removeEventListener('click', removePopup);
                }
              });
            });
          });

          translationToggleButtons.forEach(btn => {
            btn.addEventListener('click', () => {
              const seg = btn.closest('.segment');
              const translation = seg && seg.querySelector('.segment-translation');
              if (translation) translation.classList.toggle('hidden');
            });
          });
        }

function highlightMwe(mweId, contextDocument, sourceToken) {
  const doc = contextDocument || document;
  doc.querySelectorAll('.mwe-highlight').forEach(el => el.classList.remove('mwe-highlight'));
  doc.querySelectorAll(`[data-mwe-id="${mweId}"]`).forEach(el => el.classList.add('mwe-highlight'));
  if (sourceToken) sourceToken.classList.add('mwe-highlight');
}

        function setUpBackArrowEventListeners(contextDocument) {
          const doc = contextDocument || document;
          const icons = doc.querySelectorAll('.back-arrow-icon');
          icons.forEach(icon => {
            icon.addEventListener('click', () => {
              const segmentIndex = icon.dataset.segmentIndex;
              const pageNumber = icon.dataset.pageNumber;
              postMessageToParent('scrollToSegment', { segmentIndex, pageNumber });
            });
          });
        }

        window.addEventListener('message', (event) => {
          if (event.data.type === 'loadConcordance') {
            loadConcordance(event.data.data.lemma, document);
          }
        });

        document.addEventListener('DOMContentLoaded', () => {
          setUpEventListeners(document);
          setUpBackArrowEventListeners(document);
        });
        """
    )
    (static_dir / "clara_scripts.js").write_text(js, encoding="utf-8")


def compile_html(spec: CompileHTMLSpec) -> dict[str, Any]:
    """Render annotated text to multi-page HTML and return paths/metadata."""

    telemetry = spec.telemetry or NullTelemetry()
    run_id = spec.run_id or uuid.uuid4().hex[:8]
    if spec.output_dir is not None:
        run_root = Path(spec.output_dir).resolve()
    else:
        artifact_root = Path("artifacts") / "runs"
        run_root = (artifact_root / f"run_{run_id}").resolve()
    html_root = run_root / "html"
    html_root.mkdir(parents=True, exist_ok=True)
    resolver = _AudioResolver(run_root, html_root)

    _write_static_assets(html_root)

    token_ids = _token_ids(spec.text)
    token_info: list[dict[str, Any]] = []

    total_pages = len(spec.text.get("pages", [])) or 1
    page_paths: list[Path] = []
    for p_idx in range(total_pages):
        html_doc = _render_page(
            text=spec.text,
            page_index=p_idx,
            token_ids=token_ids,
            resolver=resolver,
            token_info=token_info,
            total_pages=total_pages,
            title=spec.title,
        )
        page_path = html_root / f"page_{p_idx + 1}.html"
        page_path.write_text(html_doc, encoding="utf-8")
        page_paths.append(page_path)

    concordance = _build_concordance(spec.text, token_info)
    for entry in concordance:
        lemma_key = entry.get("lemma")
        if not lemma_key:
            continue
        conc_html = _render_concordance_page(
            entry=entry, text=spec.text, token_ids=token_ids, resolver=resolver
        )
        lemma_slug = _encode_lemma_for_filename(str(lemma_key))
        conc_path = html_root / f"concordance_{lemma_slug}.html"
        conc_path.write_text(conc_html, encoding="utf-8")

    telemetry.event(spec.op_id or "compile_html", "info", f"wrote HTML pages under {html_root}")
    return {
        "html_path": str(page_paths[0]),
        "run_root": str(run_root),
        "html_root": str(html_root),
        "concordance": concordance,
    }
