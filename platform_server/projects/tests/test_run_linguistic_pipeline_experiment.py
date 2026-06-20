from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.run_linguistic_pipeline_experiment import (
    apply_stage_parameter_overrides,
    load_input_records,
    safe_record_id,
    text_obj_for_record,
)


class RunLinguisticPipelineExperimentTests(SimpleTestCase):
    def test_load_input_records_accepts_split_manifest_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "development.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "record_id": "project_1:p1:s1",
                        "surface": "Bonjour le monde.",
                        "project_id": 1,
                        "project_title": "Fixture",
                        "split": "development",
                        "page_index": 1,
                        "segment_index": 1,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            records = load_input_records(path)
            text_obj = text_obj_for_record(records[0], language="fr")

            self.assertEqual(records[0].record_id, "project_1:p1:s1")
            self.assertEqual(records[0].surface, "Bonjour le monde.")
            self.assertEqual(text_obj["pages"][0]["segments"][0]["surface"], "Bonjour le monde.")
            self.assertEqual(safe_record_id(records[0].record_id), "project_1_p1_s1")


    def test_apply_stage_parameter_overrides_parses_values(self):
        params = {"segmentation_phase_2": {"mechanism": "boundary_first", "fewshot_count": "small"}}

        merged = apply_stage_parameter_overrides(
            params,
            ["segmentation_phase_2.fewshot_count=12", "segmentation_phase_2.variant=clitic_compound_v2"],
        )

        self.assertEqual(merged["segmentation_phase_2"]["fewshot_count"], 12)
        self.assertEqual(merged["segmentation_phase_2"]["variant"], "clitic_compound_v2")
        self.assertEqual(params["segmentation_phase_2"]["fewshot_count"], "small")

    def test_command_writes_outputs_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "development.jsonl"
            input_path.write_text(
                json.dumps({"record_id": "r1", "surface": "Salut !", "split": "development"}) + "\n",
                encoding="utf-8",
            )
            params_path = tmp_path / "params.json"
            params_path.write_text(json.dumps({"segmentation_phase_2": {"mechanism": "json_direct"}}), encoding="utf-8")
            output_root = tmp_path / "runs"

            async_mock = AsyncMock(
                return_value={
                    "l2": "fr",
                    "surface": "Salut !",
                    "pages": [
                        {
                            "surface": "Salut !",
                            "segments": [{"surface": "Salut !", "tokens": [{"surface": "Salut"}, {"surface": " "}, {"surface": "!"}]}],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            )
            with patch("projects.management.commands.run_linguistic_pipeline_experiment.segmentation_phase_2", async_mock):
                call_command(
                    "run_linguistic_pipeline_experiment",
                    input_records_jsonl=str(input_path),
                    start_stage="segmentation_phase_2",
                    end_stage="segmentation_phase_2",
                    stage_parameters_file=str(params_path),
                    run_label="fixture-default",
                    output_root=str(output_root),
                    language="fr",
                    set_stage_parameter=["segmentation_phase_2.fewshot_count=medium"],
                    overwrite=True,
                )

            run_dir = output_root / "fixture-default"
            outputs = [json.loads(line) for line in (run_dir / "outputs.jsonl").read_text(encoding="utf-8").splitlines()]
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(outputs), 1)
            self.assertEqual(outputs[0]["record_id"], "r1")
            self.assertEqual(manifest["record_count"], 1)
            self.assertEqual(manifest["stage_parameters"]["segmentation_phase_2"]["fewshot_count"], "medium")
            self.assertTrue((run_dir / "stage_outputs" / "r1" / "stages" / "segmentation_phase_2.json").exists())
