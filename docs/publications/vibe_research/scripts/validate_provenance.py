#!/usr/bin/env python3
"""Validate the generated Vibe Research provenance edition."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RAW_SHA256 = "7ec2eced0e1c7f7263d4bbfb788022ad4dda151794e6e0403537ea058a556b56"

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    errors=[]
    raw=ROOT/'provenance/raw/session_transcript_original.txt'
    if sha(raw)!=EXPECTED_RAW_SHA256: errors.append('raw transcript hash differs from the exact uploaded source')
    manifest=load(ROOT/'provenance/manifest.json')
    if manifest['raw_trace']['sha256']!=EXPECTED_RAW_SHA256: errors.append('manifest raw hash mismatch')
    exchanges=[json.loads(line) for line in (ROOT/'provenance/exchanges/exchanges.jsonl').read_text(encoding='utf-8').splitlines()]
    chunks=load(ROOT/'provenance/metadata/chunks.json')
    artifacts=load(ROOT/'provenance/metadata/artifacts.json')
    decisions=load(ROOT/'provenance/metadata/decisions.json')
    if len(exchanges)!=62: errors.append(f'expected 62 exchanges, found {len(exchanges)}')
    expected_ids=[f'VR-E{i:04d}' for i in range(1,63)]
    ids=[e['exchange_id'] for e in exchanges]
    if ids!=expected_ids: errors.append('exchange IDs are not the canonical continuous sequence')
    source_lines=raw.read_text(encoding='utf-8').splitlines()
    for e in exchanges:
        for name,speaker in [('human_turn','MANNY'),('ai_turn','AI')]:
            turn=e[name]
            if turn['speaker']!=speaker: errors.append(f"{e['exchange_id']} has incorrect {name} speaker")
            start,end=turn['source_lines']
            if not (1<=start<=end<=len(source_lines)): errors.append(f"{turn['turn_id']} has invalid source span")
    covered=[]
    for c in chunks:
        first=int(c['first_exchange'][4:]); last=int(c['last_exchange'][4:])
        if c['exchange_count']!=last-first+1: errors.append(f"{c['chunk_id']} count/range mismatch")
        covered += [f'VR-E{i:04d}' for i in range(first,last+1)]
        if not (ROOT/f"provenance/chunks/{c['chunk_id']}.md").exists(): errors.append(f"missing file for {c['chunk_id']}")
    if covered!=expected_ids: errors.append('chunks do not cover each exchange once in order')
    artifact_ids={a['artifact_id'] for a in artifacts}
    for a in artifacts:
        path=ROOT/a['path']
        if not path.exists(): errors.append(f"missing artifact {a['path']}")
        elif sha(path)!=a['sha256']: errors.append(f"stale hash for {a['artifact_id']}")
    for e in exchanges:
        for aid in e['artifacts']:
            if aid not in artifact_ids: errors.append(f"{e['exchange_id']} references unknown artifact {aid}")
    for d in decisions:
        if any(e not in expected_ids for e in d['exchanges']): errors.append(f"{d['decision_id']} references unknown exchange")
        if any(c not in {x['chunk_id'] for x in chunks} for c in d['chunks']): errors.append(f"{d['decision_id']} references unknown chunk")
    normalized=(ROOT/'provenance/exchanges/transcript_normalized.md').read_text(encoding='utf-8')
    for eid in expected_ids:
        if len(re.findall(rf'^### {eid}$', normalized, re.M))!=1: errors.append(f'normalized transcript missing or duplicates {eid}')
    for rel in manifest['derived_files']:
        if not (ROOT/rel).exists(): errors.append(f'manifest derived file missing: {rel}')
    if errors:
        print('\n'.join(f'ERROR: {e}' for e in errors))
        raise SystemExit(1)
    print(f"Validated {len(exchanges)} exchanges, {len(chunks)} semantic chunks, {len(artifacts)} artifacts, and {len(decisions)} decisions.")
    print(f"Raw transcript SHA-256: {EXPECTED_RAW_SHA256}")

if __name__=='__main__': main()
