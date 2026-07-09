import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from projects.management.commands.run_mwe_prompt_experiment import load_mwe_records, record_to_text_obj
from projects.management.commands.export_mwe_gold_subset import build_translation_context_map
from projects.management.commands.score_mwe_prompt_outputs import score_record, summarize_scores
from projects.models import Project


class MWEPromptExperimentCommandTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.tmpdir, PIPELINE_OUTPUT_ROOT=Path(self.tmpdir) / "users")
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="mweuser", password="pw")
        self.project = Project.objects.create(owner=self.user, title="MWE Gold", source_text="take off", language="en")

    def test_snapshot_mwe_experiment_projects_dry_run_marks_gold_components(self):
        out = StringIO()
        call_command(
            "snapshot_mwe_experiment_projects",
            project_ids=str(self.project.id),
            dry_run=True,
            stdout=out,
        )
        payload_text = out.getvalue()[out.getvalue().find("{") :]
        payload = json.loads(payload_text)
        self.assertEqual(payload["project_ids"], [self.project.id])
        self.assertEqual(payload["gold_standard_components"], ["MWE annotations", "gloss annotations", "lemma annotations"])
        self.assertTrue(payload["snapshots"][0]["would_save"])

    def test_record_to_text_obj_preserves_tokens_for_mwe_prompt_run(self):
        text_obj = record_to_text_obj(
            {
                "segment_surface": "take off now",
                "token_surfaces": ["take", "off", "now"],
            }
        )
        tokens = text_obj["pages"][0]["segments"][0]["tokens"]
        self.assertEqual([token["surface"] for token in tokens], ["take", "off", "now"])



    def test_record_to_text_obj_can_include_translation_context_for_mwe_prompt_run(self):
        text_obj = record_to_text_obj(
            {
                "segment_surface": "take off now",
                "token_surfaces": ["take", "off", "now"],
                "translation_context": [{"language": "fr", "source": "latest_translation_stage", "text": "décoller maintenant"}],
            },
            use_translation_context=True,
        )
        annotations = text_obj["pages"][0]["segments"][0]["annotations"]
        self.assertEqual(annotations["mwe_translation_context"][0]["text"], "décoller maintenant")

    def test_build_translation_context_map_reads_segment_translations(self):
        payload = {
            "pages": [
                {
                    "segments": [
                        {"annotations": {"translation": "prendre son envol"}},
                        {"annotations": {}},
                    ]
                }
            ]
        }

        context = build_translation_context_map(payload, target_language="fr")

        self.assertEqual(context[(1, 1)][0]["language"], "fr")
        self.assertEqual(context[(1, 1)][0]["text"], "prendre son envol")
        self.assertNotIn((1, 2), context)

    def test_load_mwe_records_filters_explicit_project_ids(self):
        input_path = Path(self.tmpdir) / "records.jsonl"
        records = [
            {"record_id": "keep", "project_id": self.project.id, "token_surfaces": ["take", "off"]},
            {"record_id": "drop", "project_id": self.project.id + 1, "token_surfaces": ["look", "up"]},
        ]
        input_path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

        loaded = load_mwe_records(input_path, project_ids={self.project.id})

        self.assertEqual([record["record_id"] for record in loaded], ["keep"])

    def test_score_record_exact_span_metrics(self):
        scored = score_record(
            {
                "record_id": "r1",
                "segment_surface": "take off now",
                "gold_mwes": [{"tokens": ["take", "off"]}],
                "predicted_mwes": [{"tokens": ["take", "off"]}, {"tokens": ["off", "now"]}],
            }
        )
        self.assertEqual(scored["true_positive"], 1)
        self.assertEqual(scored["false_positive"], 1)
        self.assertEqual(scored["false_negative"], 0)
        summary = summarize_scores([scored], split="development", outputs_path=Path("outputs.jsonl"))
        self.assertAlmostEqual(summary["precision"], 0.5)
        self.assertAlmostEqual(summary["recall"], 1.0)




    def test_export_mwe_gold_subset_writes_all_selected_records_and_summary(self):
        run_stage = self.project.artifact_dir() / "runs" / "gold_run" / "stages" / "mwe.json"
        run_stage.parent.mkdir(parents=True, exist_ok=True)
        run_stage.write_text(
            json.dumps(
                {
                    "pages": [
                        {
                            "segments": [
                                {
                                    "surface": "take off now",
                                    "tokens": [
                                        {"surface": "take", "annotations": {"mwe_id": "m1"}},
                                        {"surface": "off", "annotations": {"mwe_id": "m1"}},
                                        {"surface": "now"},
                                    ],
                                    "annotations": {},
                                },
                                {
                                    "surface": "ordinary text",
                                    "tokens": [{"surface": "ordinary"}, {"surface": "text"}],
                                    "annotations": {},
                                },
                            ]
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        output_jsonl = Path(self.tmpdir) / "gold" / "selected_segments.jsonl"
        summary_json = Path(self.tmpdir) / "gold" / "summary.json"
        review_markdown = Path(self.tmpdir) / "gold" / "review.md"

        call_command(
            "export_mwe_gold_subset",
            project_ids=str(self.project.id),
            language="en",
            split="development",
            output_jsonl=str(output_jsonl),
            summary_json=str(summary_json),
            review_markdown=str(review_markdown),
            require_gold=True,
            overwrite=True,
            stdout=StringIO(),
        )

        records = [json.loads(line) for line in output_jsonl.read_text(encoding="utf-8").splitlines()]
        summary = json.loads(summary_json.read_text(encoding="utf-8"))
        self.assertEqual(len(records), 2)
        self.assertEqual(summary["record_count"], 2)
        self.assertEqual(summary["records_with_gold_mwes"], 1)
        self.assertEqual(summary["gold_mwe_count"], 1)
        self.assertEqual(records[0]["gold_mwes"], [{"id": "m1", "tokens": ["take", "off"]}])
        self.assertIn("take off now", review_markdown.read_text(encoding="utf-8"))

    def test_run_mwe_prompt_experiment_passes_template_file_to_mwe_spec(self):
        input_path = Path(self.tmpdir) / "records.jsonl"
        output_dir = Path(self.tmpdir) / "template-runs"
        template_path = Path(self.tmpdir) / "template.txt"
        template_path.write_text("Find only conservative MWEs.", encoding="utf-8")
        input_path.write_text(
            json.dumps(
                {
                    "record_id": "r1",
                    "split": "development",
                    "language": "en",
                    "project_id": self.project.id,
                    "project_title": self.project.title,
                    "segment_surface": "take off now",
                    "token_surfaces": ["take", "off", "now"],
                    "gold_mwes": [{"tokens": ["take", "off"]}],
                    "translation_context": [{"language": "fr", "text": "décoller maintenant"}],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        seen_template_paths = []

        async def fake_annotate(spec):
            seen_template_paths.append(spec.template_path)
            segment_annotations = spec.text["pages"][0]["segments"][0]["annotations"]
            self.assertEqual(segment_annotations["mwe_translation_context"][0]["text"], "décoller maintenant")
            return {
                "pages": [
                    {
                        "segments": [
                            {
                                "annotations": {"mwes": []},
                                "tokens": [{"surface": "take"}, {"surface": "off"}, {"surface": "now"}],
                            }
                        ]
                    }
                ]
            }

        with patch("projects.management.commands.run_mwe_prompt_experiment.annotate_mwes", side_effect=fake_annotate):
            out = StringIO()
            call_command(
                "run_mwe_prompt_experiment",
                input_records_jsonl=str(input_path),
                output_dir=str(output_dir),
                run_label="template-run",
                template_file=str(template_path),
                overwrite=True,
                use_translation_context=True,
                stdout=out,
            )

        manifest = json.loads((output_dir / "template-run" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(seen_template_paths, [template_path])
        self.assertEqual(manifest["template_file"], str(template_path))
        self.assertTrue(manifest["use_translation_context"])
        self.assertEqual(manifest["translation_context_record_count"], 1)
        self.assertIn("Translation context enabled: 1/1", out.getvalue())

    def test_score_command_filters_explicit_project_ids(self):
        outputs_path = Path(self.tmpdir) / "outputs.jsonl"
        output_dir = Path(self.tmpdir) / "scores"
        records = [
            {
                "record_id": "keep",
                "project_id": self.project.id,
                "gold_mwes": [{"tokens": ["take", "off"]}],
                "predicted_mwes": [{"tokens": ["take", "off"]}],
            },
            {
                "record_id": "drop",
                "project_id": self.project.id + 1,
                "gold_mwes": [{"tokens": ["look", "up"]}],
                "predicted_mwes": [],
            },
        ]
        outputs_path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

        call_command(
            "score_mwe_prompt_outputs",
            outputs_jsonl=str(outputs_path),
            output_dir=str(output_dir),
            split="development",
            project_ids=str(self.project.id),
            overwrite=True,
            stdout=StringIO(),
        )

        summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
        scored_lines = (output_dir / "per_record_scores.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(summary["record_count"], 1)
        self.assertEqual(summary["project_ids"], [self.project.id])
        self.assertEqual(json.loads(scored_lines[0])["record_id"], "keep")


    def test_propose_command_filters_scored_records_by_project_ids(self):
        score_dir = Path(self.tmpdir) / "scores_for_proposal"
        output_dir = Path(self.tmpdir) / "proposal"
        score_dir.mkdir()
        summary = {
            "record_count": 2,
            "precision": 0.5,
            "recall": 0.5,
            "f1": 0.5,
            "exact_match_count": 0,
            "exact_match_rate": 0.0,
            "true_positive": 1,
            "false_positive": 1,
            "false_negative": 1,
        }
        (score_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        records = [
            {
                "record_id": "keep",
                "project_id": self.project.id,
                "segment_surface": "take off now",
                "gold_spans": [["take", "off"]],
                "predicted_spans": [],
                "true_positive": 0,
                "false_positive": 0,
                "false_negative": 1,
                "exact_match": False,
            },
            {
                "record_id": "drop",
                "project_id": self.project.id + 1,
                "segment_surface": "look up later",
                "gold_spans": [],
                "predicted_spans": [["look", "up"]],
                "true_positive": 0,
                "false_positive": 1,
                "false_negative": 0,
                "exact_match": False,
            },
        ]
        (score_dir / "per_record_scores.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )

        out = StringIO()
        call_command(
            "propose_mwe_prompt_improvement",
            score_dir=str(score_dir),
            output_dir=str(output_dir),
            project_ids=str(self.project.id),
            overwrite=True,
            stdout=out,
        )

        report = (output_dir / "prompt_improvement.md").read_text(encoding="utf-8")
        self.assertIn("using 1 after PROJECT_IDS filter", out.getvalue())
        self.assertIn("- Project IDs: [", report)
        self.assertIn("keep", report)
        self.assertNotIn("drop", report)

    def test_run_mwe_prompt_experiment_writes_incremental_progress(self):
        input_path = Path(self.tmpdir) / "records.jsonl"
        output_dir = Path(self.tmpdir) / "runs"
        input_path.write_text(
            json.dumps(
                {
                    "record_id": "r1",
                    "split": "development",
                    "language": "en",
                    "project_id": self.project.id,
                    "project_title": self.project.title,
                    "segment_surface": "take off now",
                    "token_surfaces": ["take", "off", "now"],
                    "gold_mwes": [{"tokens": ["take", "off"]}],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        async def fake_annotate(spec):  # noqa: ARG001
            return {
                "pages": [
                    {
                        "segments": [
                            {
                                "annotations": {"mwes": [{"id": "m1", "tokens": ["take", "off"]}]},
                                "tokens": [{"surface": "take"}, {"surface": "off"}, {"surface": "now"}],
                            }
                        ]
                    }
                ]
            }

        with patch("projects.management.commands.run_mwe_prompt_experiment.annotate_mwes", side_effect=fake_annotate):
            out = StringIO()
            call_command(
                "run_mwe_prompt_experiment",
                input_records_jsonl=str(input_path),
                output_dir=str(output_dir),
                run_label="test-run",
                overwrite=True,
                project_ids=str(self.project.id),
                stdout=out,
            )

        self.assertIn("[1/1] running MWE prompt for r1", out.getvalue())
        self.assertIn("[1/1] finished r1", out.getvalue())
        progress_lines = (output_dir / "test-run" / "progress.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["status"] for line in progress_lines], ["running", "finished"])
        output_payload = json.loads((output_dir / "test-run" / "outputs.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(output_payload["predicted_mwes"][0]["tokens"], ["take", "off"])

    def test_revise_mwe_prompt_from_report_writes_ai_revision(self):
        cycle_dir = Path(self.tmpdir) / "cycle_1"
        improvement_dir = cycle_dir / "improvement"
        improvement_dir.mkdir(parents=True)
        current_template = cycle_dir / "template.txt"
        report = improvement_dir / "prompt_improvement.md"
        guidance = improvement_dir / "candidate_prompt_guidance.txt"
        output_template = improvement_dir / "template_revision.txt"
        output_json = improvement_dir / "template_revision.json"
        current_template.write_text("Current prompt\nReturn JSON.\n", encoding="utf-8")
        report.write_text("# Report\nFalse positives include overly long spans.\n", encoding="utf-8")
        guidance.write_text("Prefer precision.\n", encoding="utf-8")

        async def fake_chat_json(prompt, **kwargs):
            self.assertIn("Current prompt", prompt)
            self.assertIn("False positives", prompt)
            self.assertIsNone(kwargs.get("temperature"))
            return {
                "prompt": "Revised prompt\nReturn JSON.",
                "rationale": "Tightened span boundaries.",
                "changes": ["Prefer shorter lexicalized spans."],
                "risks": ["May reduce recall."],
            }

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            chat_json = staticmethod(fake_chat_json)

        with patch("projects.management.commands.revise_mwe_prompt_from_report.OpenAIClient", FakeClient):
            out = StringIO()
            call_command(
                "revise_mwe_prompt_from_report",
                current_template=str(current_template),
                improvement_report=str(report),
                candidate_guidance=str(guidance),
                output_template=str(output_template),
                output_json=str(output_json),
                overwrite=True,
                stdout=out,
            )

        self.assertEqual(output_template.read_text(encoding="utf-8"), "Revised prompt\nReturn JSON.\n")
        metadata = json.loads(output_json.read_text(encoding="utf-8"))
        self.assertEqual(metadata["rationale"], "Tightened span boundaries.")
        self.assertIn("Revised prompt template", out.getvalue())

    def test_summarize_mwe_prompt_cycles_collects_score_and_prompt_lengths(self):
        base_dir = Path(self.tmpdir) / "cycles"
        for cycle, f1, prompt in [(1, 0.25, "short prompt\n"), (2, 0.40, "longer prompt\nwith rule\n")]:
            cycle_dir = base_dir / f"cycle_{cycle}"
            (cycle_dir / "score").mkdir(parents=True)
            (cycle_dir / "improvement").mkdir()
            (cycle_dir / "template.txt").write_text(prompt, encoding="utf-8")
            (cycle_dir / "improvement" / "template_revision.txt").write_text(prompt + "revision\n", encoding="utf-8")
            (cycle_dir / "score" / "summary.json").write_text(
                json.dumps(
                    {
                        "record_count": 3,
                        "precision": f1,
                        "recall": f1,
                        "f1": f1,
                        "exact_match_rate": 0.1,
                        "true_positive": cycle,
                        "false_positive": cycle + 1,
                        "false_negative": cycle + 2,
                    }
                ),
                encoding="utf-8",
            )

        output_json = Path(self.tmpdir) / "cycle_comparison.json"
        output_markdown = Path(self.tmpdir) / "cycle_comparison.md"
        out = StringIO()
        call_command(
            "summarize_mwe_prompt_cycles",
            cycle_base_dir=str(base_dir),
            output_json=str(output_json),
            output_markdown=str(output_markdown),
            overwrite=True,
            stdout=out,
        )

        payload = json.loads(output_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["cycle_count"], 2)
        self.assertEqual(payload["best_cycle"]["cycle"], 2)
        report = output_markdown.read_text(encoding="utf-8")
        self.assertIn("cycle 2", report.lower())
        self.assertIn("Prompt chars", report)
        self.assertIn("MWE cycle summary", out.getvalue())
