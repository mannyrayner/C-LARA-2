from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.stage_artifacts import (
    read_stage_artifact,
    stage_artifact_path,
    write_stage_artifact,
)


class StageArtifactTests(unittest.TestCase):
    def test_write_stage_artifact_preserves_existing_json_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_demo"
            payload = {"surface": "Café", "pages": [{"segments": []}]}

            metadata = write_stage_artifact(run_dir, "lemma", payload)

            expected_path = run_dir / "stages" / "lemma.json"
            self.assertEqual(metadata.path, expected_path)
            self.assertEqual(stage_artifact_path(run_dir, "lemma"), expected_path)
            self.assertEqual(json.loads(expected_path.read_text(encoding="utf-8")), payload)
            self.assertEqual(read_stage_artifact(run_dir, "lemma"), payload)

    def test_read_stage_artifact_reads_pre_existing_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_existing"
            stage_dir = run_dir / "stages"
            stage_dir.mkdir(parents=True)
            legacy_payload = {"ok": True, "pages": []}
            (stage_dir / "gloss.json").write_text(
                json.dumps(legacy_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            self.assertEqual(read_stage_artifact(run_dir, "gloss"), legacy_payload)


if __name__ == "__main__":
    unittest.main()
