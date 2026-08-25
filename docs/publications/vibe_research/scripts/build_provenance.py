#!/usr/bin/env python3
"""Build the curated Vibe Research provenance edition.

The raw transcript is immutable input. Structural parsing and indexes are
reproducible; semantic chunk boundaries and descriptions are reviewed editorial
metadata declared below. The script uses only the Python standard library.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "provenance/raw/session_transcript_original.txt"
GENERATOR = "scripts/build_provenance.py"
FORMAT_VERSION = 1
DATE_RE = re.compile(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b")
SPEAKER_RE = re.compile(r"^(MANNY|MR|AI):\s*(.*)$")
MARKER_RE = re.compile(r"\[(Version\s+\d+(?:,\s*section\s*1|\s+changes)?|References\s+\d+(?:\s+new)?|Casey Newton article)[\]\)]", re.I)

ARTIFACTS = {
    "Version 1": ("VR-DRAFT-001", "drafts/version_1.tex", "complete manuscript"),
    "Version 2": ("VR-DRAFT-002", "drafts/version_2.tex", "complete manuscript"),
    "Version 3": ("VR-DRAFT-003", "drafts/version_3.tex", "complete manuscript"),
    "Version 4": ("VR-DRAFT-004", "drafts/version_4.tex", "complete manuscript"),
    "References 1": ("VR-BIB-001", "bibliography_snapshots/references_1.bib", "bibliography snapshot"),
    "Casey Newton article": ("VR-SOURCE-001", "sources/casey_newton_article_summary.md", "source summary"),
    "Version 5": ("VR-DRAFT-005", "drafts/version_5.tex", "complete manuscript"),
    "References 2": ("VR-BIB-002", "bibliography_snapshots/references_2.bib", "bibliography snapshot"),
    "Version 6": ("VR-DRAFT-006", "drafts/version_6.tex", "complete manuscript"),
    "References 3": ("VR-BIB-003", "bibliography_snapshots/references_3.bib", "bibliography snapshot"),
    "Version 7": ("VR-DRAFT-007", "drafts/version_7.tex", "complete manuscript"),
    "Version 9": ("VR-DRAFT-009", "drafts/version_9.tex", "complete manuscript"),
    "Version 10, section 1": ("VR-DRAFT-010", "drafts/version_10_section_1.tex", "replacement section"),
    "Version 11 changes": ("VR-DRAFT-011", "drafts/version_11_changes.tex", "replacement passages"),
    "References 4 new": ("VR-BIB-004", "bibliography_snapshots/references_4_new.bib", "bibliography snapshot"),
    "Version 12": ("VR-DRAFT-012", "drafts/version_12.tex", "complete manuscript"),
    "Version 13": ("VR-DRAFT-013", "drafts/version_13.tex", "complete manuscript"),
}

# Boundaries were chosen after reading the complete trace. Counts deliberately
# vary: spoken fragments stay together, while very long research exchanges stand alone.
CHUNKS = [
    ("VR-C001", 1, 1, "The initial Vibe Research proposal", "Manny proposes the paper; the AI identifies the software/research asymmetry, prior uses of the term, authorship tensions, and possible empirical work.", ["paper conception", "vibe coding", "vibe research", "AI authorship"]),
    ("VR-C002", 2, 2, "Accountability and public access", "The discussion sharpens the paper around distributed expertise, institutional accountability, provenance, and public access to project-grounded AI collaborators.", ["accountability", "distributed expertise", "public access", "provenance"]),
    ("VR-C003", 3, 16, "Voice discussion: responsibility, expertise, and provenance", "A spoken exchange develops the senior-researcher analogy, contingent access to AI expertise, and the decision to frame the practical issue around provenance rather than deserving authorship.", ["authorship", "ephemeral expertise", "provenance", "responsibility"]),
    ("VR-C004", 17, 26, "Framing the asymmetry without moralising", "The collaborators decide to present different treatment of vibe coding and vibe research as a descriptive puzzle, avoiding moralising or evangelising language.", ["academic norms", "framing", "software engineering", "tone"]),
    ("VR-C005", 27, 38, "Prevalence as an empirical question", "The discussion considers whether vibe research is already widespread and develops a cautious invitation to collect self-reports rather than assume prevalence.", ["prevalence", "questionnaire", "research design", "researcher disclosure"]),
    ("VR-C006", 39, 39, "First outline and Version 1", "After returning to text mode, Manny requests an outline and the AI supplies the first structured draft, with the asymmetry as the organising puzzle.", ["outline", "paper structure", "Version 1"]),
    ("VR-C007", 40, 40, "First critique and Version 2", "Manny requests a title, abstract, broader examples, earlier treatment of authorship, and a more concrete public-provenance account; the AI produces Version 2.", ["abstract", "authorship", "paper revision", "Version 2"]),
    ("VR-C008", 41, 42, "Major restructuring and Version 3", "A long structural review removes repetition, strengthens the software analogy, separates accountability from provenance, and leads to Version 3.", ["accountability", "paper revision", "provenance", "Version 3"]),
    ("VR-C009", 43, 45, "Policy citations and Version 4", "The collaborators refine authorship-policy claims, the three examples, and public interrogation of provenance; Version 4 and the first bibliography are produced.", ["bibliography", "publication policy", "source verification", "Version 4"]),
    ("VR-C010", 46, 46, "The Casey Newton article", "A newly supplied Casey Newton article is analysed for its discussion of distributed editorial expertise, AI-supported writing, disclosure, and the boundary between assistance and authorship.", ["Casey Newton", "distributed expertise", "editorial automation", "writing"]),
    ("VR-C011", 47, 49, "ACL policy history and Version 5", "The discussion investigates whether governance reflects older AI paradigms, checks ACL policy history, narrows claims to public evidence, and produces Version 5 plus a policy bibliography.", ["ACL", "governance lag", "publication policy", "Version 5"]),
    ("VR-C012", 50, 51, "Precision edits and Codex handoff", "Detailed edits improve the responsibility/accountability distinction and concrete examples; Version 6 is prepared as a handoff for repository work by Codex.", ["Codex handoff", "paper revision", "provenance examples", "Version 6"]),
    ("VR-C013", 52, 53, "Reworking the central puzzle and Version 7", "The abstract, transitions, ACL analysis, and Grok provenance are tightened; the revised argument is emitted as Version 7.", ["ACL", "central argument", "How Woke is Grok?", "Version 7"]),
    ("VR-C014", 54, 55, "Final handoff review and Version 9", "Minor conceptual and mechanical issues are resolved, citations are checked, and Version 9 becomes the clean handoff document for Codex.", ["Codex handoff", "citation checking", "paper revision", "Version 9"]),
    ("VR-C015", 56, 58, "The Castle analogy and replacement introduction", "After Codex repository work, the collaborators develop The Castle as a framing device for making an initially comic practice institutionally legible and produce a replacement introduction.", ["The Castle", "institutional legibility", "paper introduction", "Version 10"]),
    ("VR-C016", 59, 59, "Vibe coding claims and mathematical evidence", "A long exchange checks stronger claims about vibe coding and surveys difficult mathematical results and Go as independent evidence of substantive AI contributions.", ["Go", "mathematics", "non-trivial results", "vibe coding"]),
    ("VR-C017", 60, 60, "Mathematics section and Version 11 changes", "The collaborators retain the mathematical evidence but defer Go, carefully calibrate claims, and produce replacement passages and bibliography additions.", ["claim calibration", "mathematics", "Version 11"]),
    ("VR-C018", 61, 61, "Human compression and review of Version 12", "Manny supplies a substantially compressed Version 12; the AI endorses the three-explanation structure and identifies conceptual overstatements and mechanical corrections.", ["human editing", "paper structure", "three explanations", "Version 12"]),
    ("VR-C019", 62, 62, "Final requested revision and Version 13", "Manny accepts the review and requests the final revision; the AI reports incorporating the agreed conceptual fixes into Version 13.", ["final revision", "Version 13"]),
]

@dataclass
class Turn:
    speaker: str
    text: str
    start: int
    end: int
    session: str
    original_speaker: str


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_turns() -> tuple[list[Turn], dict]:
    lines = RAW.read_text(encoding="utf-8").splitlines()
    session = ""
    blocks: list[Turn] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if DATE_RE.match(line):
            session = line
            i += 1
            continue
        match = SPEAKER_RE.match(line)
        if not match:
            i += 1
            continue
        original, initial = match.groups()
        start = i + 1
        content = [initial] if initial else []
        i += 1
        while i < len(lines) and not SPEAKER_RE.match(lines[i]) and not DATE_RE.match(lines[i]):
            content.append(lines[i])
            i += 1
        text = "\n".join(content).strip()
        blocks.append(Turn("MANNY" if original == "MR" else original, text, start, i, session, original))

    empty = [b for b in blocks if not b.text]
    nonempty = [b for b in blocks if b.text]

    # The export duplicates the beginning of the Sunday message: lines 1027 and
    # 1032 start identically, but only the MR block continues with the new idea.
    duplicate = next(b for b in nonempty if b.start == 1027)
    nonempty.remove(duplicate)

    report = {
        "source_lines": len(lines),
        "speaker_blocks": len(blocks),
        "nonempty_blocks_before_editorial_deduplication": len(nonempty) + 1,
        "retained_turns": len(nonempty),
        "discarded_empty_blocks": len(empty),
        "discarded_duplicate_blocks": [{"source_lines": [duplicate.start, duplicate.end], "reason": "truncated duplicate of the MR turn beginning at source line 1032"}],
        "speaker_aliases": {"MR": "MANNY"},
        "structural_corrections": [{"source": "[Version 13)", "normalized": "Version 13", "source_line": 1301}],
    }
    return nonempty, report


def marker_key(raw: str) -> str:
    key = re.sub(r"\s+", " ", raw.strip())
    return key[0].upper() + key[1:]


def artifacts_in(text: str) -> list[str]:
    found = []
    for match in MARKER_RE.finditer(text):
        key = marker_key(match.group(1))
        if key == "Version 13":
            pass
        if key not in ARTIFACTS:
            raise ValueError(f"Unmapped artifact marker: {key}")
        found.append(ARTIFACTS[key][0])
    return found


def render_text(value: str) -> str:
    """Normalize line-final whitespace in Markdown renderings only."""
    return "\n".join(line.rstrip() for line in value.splitlines())


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    turns, report = parse_turns()
    if len(turns) != 124:
        raise ValueError(f"Expected 124 retained turns, got {len(turns)}")
    for i, turn in enumerate(turns):
        expected = "MANNY" if i % 2 == 0 else "AI"
        if turn.speaker != expected:
            raise ValueError(f"Unexpected speaker {turn.speaker} at retained turn {i + 1}; expected {expected}")

    exchanges = []
    artifact_exchange = {}
    for i in range(0, len(turns), 2):
        number = i // 2 + 1
        human, ai = turns[i], turns[i + 1]
        eid = f"VR-E{number:04d}"
        human_id, ai_id = f"VR-T{i + 1:04d}-M", f"VR-T{i + 2:04d}-A"
        refs = artifacts_in(human.text) + artifacts_in(ai.text)
        for artifact_id in refs:
            artifact_exchange[artifact_id] = eid
        exchanges.append({
            "exchange_id": eid,
            "sequence": number,
            "session_heading": human.session,
            "human_turn": {"turn_id": human_id, "speaker": "MANNY", "original_speaker_label": human.original_speaker, "source_lines": [human.start, human.end], "text": human.text},
            "ai_turn": {"turn_id": ai_id, "speaker": "AI", "original_speaker_label": ai.original_speaker, "source_lines": [ai.start, ai.end], "text": ai.text},
            "artifacts": refs,
        })

    if len(exchanges) != 62:
        raise ValueError(f"Expected 62 exchanges, got {len(exchanges)}")

    # JSONL exchange record.
    exchange_path = ROOT / "provenance/exchanges/exchanges.jsonl"
    exchange_path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in exchanges), encoding="utf-8")

    # Human-readable normalized transcript.
    normalized = ["# Normalized Vibe Research session transcript", "", "This rendering preserves substantive utterance wording while adding stable identifiers and repository links. See [`../EDITORIAL_METHOD.md`](../EDITORIAL_METHOD.md).", ""]
    last_session = None
    for e in exchanges:
        if e["session_heading"] != last_session:
            normalized += [f"## {e['session_heading']}", ""]
            last_session = e["session_heading"]
        normalized += [f"### {e['exchange_id']}", "", f"**MANNY ({e['human_turn']['turn_id']})**", "", render_text(e["human_turn"]["text"]), "", f"**AI ({e['ai_turn']['turn_id']})**", "", render_text(e["ai_turn"]["text"]), ""]
    (ROOT / "provenance/exchanges/transcript_normalized.md").write_text("\n".join(normalized).rstrip() + "\n", encoding="utf-8")

    chunk_records = []
    exchange_to_chunk = {}
    for cid, first, last, title, summary, topics in CHUNKS:
        selected = exchanges[first - 1:last]
        for e in selected:
            if e["exchange_id"] in exchange_to_chunk:
                raise ValueError(f"Duplicate chunk assignment: {e['exchange_id']}")
            exchange_to_chunk[e["exchange_id"]] = cid
        artifact_ids = list(dict.fromkeys(a for e in selected for a in e["artifacts"]))
        record = {"chunk_id": cid, "title": title, "first_exchange": selected[0]["exchange_id"], "last_exchange": selected[-1]["exchange_id"], "exchange_count": len(selected), "session_headings": list(dict.fromkeys(e["session_heading"] for e in selected)), "summary": summary, "topics": topics, "artifacts": artifact_ids}
        chunk_records.append(record)
        body = [f"# {cid}: {title}", "", "## Editorial metadata", "", f"- **Exchange range:** [{record['first_exchange']}](../exchanges/transcript_normalized.md#{record['first_exchange'].lower()})–[{record['last_exchange']}](../exchanges/transcript_normalized.md#{record['last_exchange'].lower()})", f"- **Sessions:** {', '.join(record['session_headings'])}", f"- **Topics:** {', '.join(topics)}", f"- **Artifacts:** {', '.join(artifact_ids) if artifact_ids else 'None'}", "", summary, "", "## Exchanges", ""]
        for e in selected:
            body += [f"### {e['exchange_id']}", "", "**MANNY**", "", render_text(e["human_turn"]["text"]), "", "**AI**", "", render_text(e["ai_turn"]["text"]), ""]
        (ROOT / f"provenance/chunks/{cid}.md").write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")

    if len(exchange_to_chunk) != len(exchanges):
        missing = [e["exchange_id"] for e in exchanges if e["exchange_id"] not in exchange_to_chunk]
        raise ValueError(f"Unchunked exchanges: {missing}")

    artifact_records = []
    for marker, (aid, relpath, kind) in ARTIFACTS.items():
        path = ROOT / relpath
        if not path.exists():
            raise FileNotFoundError(path)
        artifact_records.append({"artifact_id": aid, "marker": marker, "path": relpath, "kind": kind, "introduced_at": artifact_exchange.get(aid), "sha256": sha(path)})
    # Files present in the repository but not explicitly attached in this trace.
    for aid, relpath, kind, note in [
        ("VR-DRAFT-008", "drafts/version_8.tex", "complete manuscript", "No explicit Version 8 marker occurs in the uploaded trace."),
        ("VR-PAPER-CURRENT", "paper/main.tex", "current manuscript", "Canonical manuscript at the time of reorganization."),
        ("VR-BIB-CURRENT", "paper/references.bib", "current bibliography", "Canonical consolidated bibliography."),
    ]:
        path = ROOT / relpath
        artifact_records.append({"artifact_id": aid, "marker": None, "path": relpath, "kind": kind, "introduced_at": None, "note": note, "sha256": sha(path)})

    write_json(ROOT / "provenance/metadata/chunks.json", chunk_records)
    write_json(ROOT / "provenance/metadata/artifacts.json", artifact_records)
    write_json(ROOT / "provenance/metadata/normalization_report.json", report)

    topics = defaultdict(list)
    for chunk in chunk_records:
        for topic in chunk["topics"]:
            topics[topic].append(chunk["chunk_id"])
    write_json(ROOT / "provenance/indexes/keywords.json", {k: topics[k] for k in sorted(topics, key=str.casefold)})

    chronological = ["# Chronological index", ""]
    for chunk in chunk_records:
        chronological += [f"## [{chunk['chunk_id']}: {chunk['title']}](../chunks/{chunk['chunk_id']}.md)", "", f"{chunk['first_exchange']}–{chunk['last_exchange']} · {', '.join(chunk['session_headings'])}", "", chunk["summary"], ""]
    (ROOT / "provenance/indexes/chronological.md").write_text("\n".join(chronological).rstrip() + "\n", encoding="utf-8")

    topic_md = ["# Topic index", "", "Topics are editorial discovery metadata; follow links to the underlying exchanges before treating a summary as evidence.", ""]
    by_id = {c["chunk_id"]: c for c in chunk_records}
    for topic in sorted(topics, key=str.casefold):
        topic_md += [f"## {topic}", ""]
        for cid in topics[topic]:
            topic_md.append(f"- [{cid}: {by_id[cid]['title']}](../chunks/{cid}.md)")
        topic_md.append("")
    (ROOT / "provenance/indexes/topics.md").write_text("\n".join(topic_md).rstrip() + "\n", encoding="utf-8")

    artifact_md = ["# Artifact index", "", "The `introduced at` links identify the exchange containing the uploaded-session marker, not necessarily the file's original creation event.", ""]
    for item in artifact_records:
        intro = item.get("introduced_at") or "not marked in trace"
        artifact_md += [f"## {item['artifact_id']}", "", f"- **Path:** [`{item['path']}`](../../{item['path']})", f"- **Kind:** {item['kind']}", f"- **Introduced at:** {intro}", f"- **SHA-256:** `{item['sha256']}`"]
        if item.get("note"):
            artifact_md.append(f"- **Note:** {item['note']}")
        artifact_md.append("")
    (ROOT / "provenance/indexes/artifacts.md").write_text("\n".join(artifact_md).rstrip() + "\n", encoding="utf-8")

    manifest = {
        "format_version": FORMAT_VERSION,
        "publication": "Vibe Research",
        "canonical_manuscript": "paper/main.tex",
        "canonical_bibliography": "paper/references.bib",
        "raw_trace": {"path": "provenance/raw/session_transcript_original.txt", "sha256": sha(RAW)},
        "generator": GENERATOR,
        "counts": {"exchanges": len(exchanges), "chunks": len(chunk_records), "artifacts": len(artifact_records)},
        "derived_files": ["provenance/exchanges/exchanges.jsonl", "provenance/exchanges/transcript_normalized.md", "provenance/metadata/chunks.json", "provenance/metadata/artifacts.json", "provenance/metadata/normalization_report.json", "provenance/indexes/keywords.json", "provenance/indexes/chronological.md", "provenance/indexes/topics.md", "provenance/indexes/artifacts.md"] + [f"provenance/chunks/{c['chunk_id']}.md" for c in chunk_records],
    }
    write_json(ROOT / "provenance/manifest.json", manifest)


if __name__ == "__main__":
    main()
