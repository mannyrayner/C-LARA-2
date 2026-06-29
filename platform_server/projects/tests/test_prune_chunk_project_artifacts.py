from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class PruneChunkProjectArtifactsTests(SimpleTestCase):
    def test_command_dry_run_does_not_rewrite_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "records.jsonl"
            records = [
                {"record_id": "keep", "project_id": 1, "project_title": "Keep"},
                {"record_id": "drop", "project_id": 2, "project_title": "Kok Kaper"},
            ]
            original = "".join(json.dumps(record) + "\n" for record in records)
            path.write_text(original, encoding="utf-8")

            call_command("prune_chunk_project_artifacts", root_dir=str(root), project_title="Kok Kaper")

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_command_applies_project_prune_across_nested_jsonl_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "nested"
            nested.mkdir()
            path_1 = root / "records.jsonl"
            path_2 = nested / "predictions.jsonl"
            path_1.write_text(
                "".join(
                    json.dumps(record, ensure_ascii=False) + "\n"
                    for record in [
                        {"record_id": "keep-1", "project_id": 1, "project_title": "Keep"},
                        {"record_id": "drop-1", "project_id": 2, "project_title": "Kok Kaper"},
                    ]
                ),
                encoding="utf-8",
            )
            path_2.write_text(
                "".join(
                    json.dumps(record, ensure_ascii=False) + "\n"
                    for record in [
                        {"record_id": "drop-2", "project_id": 2, "project_title": "Other title"},
                        {"record_id": "keep-2", "project_id": 3, "project_title": "Keep also"},
                    ]
                ),
                encoding="utf-8",
            )

            call_command("prune_chunk_project_artifacts", root_dir=str(root), project_id=2, apply=True)

            remaining_1 = [json.loads(line) for line in path_1.read_text(encoding="utf-8").splitlines()]
            remaining_2 = [json.loads(line) for line in path_2.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["record_id"] for record in remaining_1], ["keep-1"])
            self.assertEqual([record["record_id"] for record in remaining_2], ["keep-2"])

    def test_command_requires_project_filter(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(CommandError):
                call_command("prune_chunk_project_artifacts", root_dir=tmp)
