#!/usr/bin/env python3
"""Reproducible acquisition helpers for Gutenberg and Runeberg sources.

This module deliberately does no editorial normalisation.  Network downloads are
written atomically and originals are retained beside the derived literary text.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

USER_AGENT = "C-LARA-2 classical-corpus acquisition/1.0 (research use)"
START_RE = re.compile(r"^\*\*\* START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*\*\*\*\s*$", re.I | re.M)
END_RE = re.compile(r"^\*\*\* END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*\*\*\*\s*$", re.I | re.M)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    """Download *url* to a new file via ``.part``; never overwrite."""
    if destination.exists() or destination.with_suffix(destination.suffix + ".part").exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, part.open("xb") as output:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}: {url}")
            while block := response.read(1024 * 1024):
                output.write(block)
        if not part.stat().st_size:
            raise RuntimeError(f"empty response: {url}")
        os.replace(part, destination)
    except Exception:
        part.unlink(missing_ok=True)
        raise


def acquire_gutenberg(url: str, raw: Path, literary: Path, record: Path) -> None:
    if literary.exists() or record.exists():
        raise FileExistsError("derived output already exists")
    download(url, raw)
    text = raw.read_text(encoding="utf-8-sig")
    starts, ends = list(START_RE.finditer(text)), list(END_RE.finditer(text))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() >= ends[0].start():
        raise ValueError("expected exactly one ordered Gutenberg START/END marker pair")
    body = text[starts[0].end():ends[0].start()].strip() + "\n"
    literary.parent.mkdir(parents=True, exist_ok=True)
    literary.write_text(body, encoding="utf-8", newline="\n")
    _write_record(record, {
        "method": "gutenberg_explicit_wrapper_markers",
        "download_url": url,
        "raw_path": str(raw), "raw_sha256": sha256(raw),
        "literary_text_path": str(literary), "literary_text_sha256": sha256(literary),
        "transformations": ["decode UTF-8 (optional BOM)", "remove explicit Gutenberg wrapper", "normalize line endings to LF"],
    })


class VisibleText(HTMLParser):
    BLOCKED = {"script", "style", "nav", "header", "footer"}

    def __init__(self) -> None:
        super().__init__()
        self.blocked = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.BLOCKED:
            self.blocked += 1
        elif not self.blocked and tag.lower() in {"p", "br", "div", "h1", "h2", "h3", "pre"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCKED and self.blocked:
            self.blocked -= 1
        elif not self.blocked and tag.lower() in {"p", "div", "h1", "h2", "h3", "pre"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.blocked:
            self.parts.append(data)

    def text(self) -> str:
        value = html.unescape("".join(self.parts)).replace("\r", "")
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n[ \t]+", "\n", value)
        return re.sub(r"\n{3,}", "\n\n", value).strip() + "\n"


def acquire_runeberg(volume_url: str, first: int, last: int, width: int,
                      raw_dir: Path, literary: Path, record: Path) -> None:
    """Acquire a verified inclusive Runeberg URL-index range.

    ``first`` and ``last`` are URL indices established from the live contents
    links, not unverified printed page numbers.
    """
    if first > last:
        raise ValueError("first page must not follow last page")
    if literary.exists() or record.exists() or raw_dir.exists():
        raise FileExistsError("output already exists")
    pages, chunks = [], []
    try:
        for index in range(first, last + 1):
            name = f"{index:0{width}d}.html"
            url = volume_url.rstrip("/") + "/" + name
            target = raw_dir / name
            download(url, target)
            parser = VisibleText()
            parser.feed(target.read_text(encoding="utf-8", errors="strict"))
            visible = parser.text()
            if not visible.strip():
                raise ValueError(f"no visible OCR text in {target}")
            chunks.append(visible)
            pages.append({"url_index": index, "url": url, "path": str(target), "sha256": sha256(target)})
        literary.parent.mkdir(parents=True, exist_ok=True)
        literary.write_text("\n\n".join(chunk.rstrip() for chunk in chunks) + "\n", encoding="utf-8", newline="\n")
        _write_record(record, {
            "method": "runeberg_verified_url_index_range", "volume_url": volume_url,
            "first_url_index": first, "last_url_index": last, "pages": pages,
            "literary_text_path": str(literary), "literary_text_sha256": sha256(literary),
            "transformations": ["decode page HTML as UTF-8", "extract visible OCR text without editorial correction", "concatenate in URL-index order"],
        })
    except Exception:
        if literary.exists(): literary.unlink()
        raise


def _write_record(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    gutenberg = commands.add_parser("gutenberg")
    for flag in ("url", "raw", "literary", "record"): gutenberg.add_argument(f"--{flag}", required=True)
    runeberg = commands.add_parser("runeberg")
    runeberg.add_argument("--volume-url", required=True); runeberg.add_argument("--first", type=int, required=True)
    runeberg.add_argument("--last", type=int, required=True); runeberg.add_argument("--width", type=int, default=4)
    for flag in ("raw-dir", "literary", "record"): runeberg.add_argument(f"--{flag}", required=True)
    args = parser.parse_args()
    if args.command == "gutenberg":
        acquire_gutenberg(args.url, Path(args.raw), Path(args.literary), Path(args.record))
    else:
        acquire_runeberg(args.volume_url, args.first, args.last, args.width, Path(args.raw_dir), Path(args.literary), Path(args.record))


if __name__ == "__main__": main()
