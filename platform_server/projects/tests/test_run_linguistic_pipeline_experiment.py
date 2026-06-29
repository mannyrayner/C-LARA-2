from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase

from projects.management.commands.run_linguistic_pipeline_experiment import (
    apply_stage_parameter_overrides,
    load_input_records,
    run_segmentation_phase_2_records,
    safe_record_id,
    text_obj_for_record,
    windows_long_path,
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

    def test_windows_long_path_adds_extended_prefix_for_windows_paths(self):
        class FakePath:
            def resolve(self):
                return "C:" + "\\" + "very" + "\\" + "long"

        with patch("projects.management.commands.run_linguistic_pipeline_experiment.os.name", "nt"):
            resolved = windows_long_path(FakePath())

        self.assertEqual(str(resolved), "\\\\?\\C:" + "\\" + "very" + "\\" + "long")

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
            with (
                patch("projects.management.commands.run_linguistic_pipeline_experiment.segmentation_phase_2", async_mock),
                patch(
                    "projects.management.commands.run_linguistic_pipeline_experiment._resolve_cli_path",
                    side_effect=lambda value, default: Path(value or default).resolve(),
                ) as resolve_mock,
            ):
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

            resolved_paths = [call_args.args[0] for call_args in resolve_mock.call_args_list]
            self.assertIn(str(input_path), resolved_paths)
            self.assertIn(str(params_path), resolved_paths)
            self.assertIn(str(output_root), resolved_paths)

            run_dir = output_root / "fixture-default"
            outputs = [json.loads(line) for line in (run_dir / "outputs.jsonl").read_text(encoding="utf-8").splitlines()]
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(outputs), 1)
            self.assertEqual(outputs[0]["record_id"], "r1")
            self.assertEqual(manifest["record_count"], 1)
            self.assertEqual(manifest["stage_parameters"]["segmentation_phase_2"]["fewshot_count"], "medium")
            self.assertTrue((run_dir / "stage_outputs" / "r1" / "stages" / "segmentation_phase_2.json").exists())

    def test_runner_passes_chunk_decomposition_parameters_to_segmentation_phase_2(self):
        record = load_input_records_from_payload({"record_id": "r1", "surface": "opened,", "split": "development"})[0]
        async_mock = AsyncMock(return_value=text_obj_for_record(record, language="en"))

        with patch("projects.management.commands.run_linguistic_pipeline_experiment.segmentation_phase_2", async_mock):
            outputs = asyncio.run(
                run_segmentation_phase_2_records(
                    [record],
                    language="en",
                    run_label="fixture",
                    stage_parameters={
                        "segmentation_phase_2": {
                            "mechanism": "chunk_decomposition",
                            "chunk_prompt_variant": "chunk_decomposition_multilingual_v1",
                            "chunk_prompt_cycle": 2,
                            "max_concurrency": 3,
                        }
                    },
                )
            )

        spec = async_mock.call_args.args[0]
        self.assertEqual(outputs[0]["record_id"], "r1")
        self.assertEqual(spec.mechanism, "chunk_decomposition")
        self.assertEqual(spec.chunk_prompt_variant, "chunk_decomposition_multilingual_v1")
        self.assertEqual(spec.chunk_prompt_cycle, 2)
        self.assertEqual(spec.max_concurrency, 3)


def load_input_records_from_payload(payload):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "records.jsonl"
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        return load_input_records(path)
