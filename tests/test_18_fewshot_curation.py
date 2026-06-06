from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from pipeline.fewshot_curation import (
    FewshotCurationSpec,
    FewshotReviewSpec,
    generate_candidate_batch,
    review_candidate_batch,
    store_candidate_batch,
    _filesystem_path,
    _write_json,
    validate_segmentation_phase_2_candidate,
)


class FakeCurationClient:
    def __init__(self, payload):
        self.payload = payload
        self.prompts: list[str] = []
        self.models: list[str | None] = []

    async def chat_json(self, prompt: str, *, model: str | None = None, **_kwargs):
        self.prompts.append(prompt)
        self.models.append(model)
        return self.payload


class FakeFanoutCurationClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.prompts: list[str] = []
        self.models: list[str | None] = []

    async def chat_json(self, prompt: str, *, model: str | None = None, **_kwargs):
        self.prompts.append(prompt)
        self.models.append(model)
        return self.payloads.pop(0)


class FakeReviewClient(FakeFanoutCurationClient):
    pass


class FewshotCurationTests(unittest.IsolatedAsyncioTestCase):
    def test_validates_segmentation_phase_2_candidate(self) -> None:
        candidate = {
            "input": "C'est bon.",
            "output": {
                "surface": "C'est bon.",
                "tokens": [
                    {"surface": "C"},
                    {"surface": "'est"},
                    {"surface": " "},
                    {"surface": "bon"},
                    {"surface": "."},
                ],
                "annotations": {},
            },
        }

        result = validate_segmentation_phase_2_candidate(candidate)

        self.assertTrue(result["schema_pass"])
        self.assertEqual([], result["errors"])
        self.assertEqual(5, result["token_count"])

    def test_rejects_candidate_that_does_not_preserve_surface(self) -> None:
        candidate = {
            "input": "C'est bon.",
            "output": {
                "surface": "C'est bon.",
                "tokens": [{"surface": "C'est"}, {"surface": "bon"}, {"surface": "."}],
                "annotations": {},
            },
        }

        result = validate_segmentation_phase_2_candidate(candidate)

        self.assertFalse(result["schema_pass"])
        self.assertIn("concatenated token surfaces must exactly match input", result["errors"])

    async def test_generation_repairs_missing_surface_gap_tokens(self) -> None:
        client = FakeCurationClient(
            {
                "candidates": [
                    {
                        "input": "Je t'aime.",
                        "phenomenon": "clitic",
                        "rationale": "Generated without the required inter-word space token.",
                        "output": {
                            "surface": "Je t'aime.",
                            "tokens": [
                                {"surface": "Je"},
                                {"surface": "t'"},
                                {"surface": "aime"},
                                {"surface": "."},
                            ],
                            "annotations": {},
                        },
                    }
                ]
            }
        )
        spec = FewshotCurationSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="clitic_compound_v2",
            count=1,
            model="fake-model",
            request_id="20260606-repair",
        )

        batch = await generate_candidate_batch(spec, client=client)

        record = batch["records"][0]
        self.assertEqual("schema_validated", record["status"])
        self.assertEqual({"inserted_missing_surface_gaps": 1}, record["normalization"])
        self.assertEqual(
            ["Je", " ", "t'", "aime", "."],
            [token["surface"] for token in record["candidate"]["output"]["tokens"]],
        )

    async def test_generates_stores_and_promotes_valid_candidates(self) -> None:
        client = FakeCurationClient(
            {
                "candidates": [
                    {
                        "input": "C'est bon.",
                        "phenomenon": "French clitic",
                        "rationale": "Separates C + 'est while preserving surface text.",
                        "output": {
                            "surface": "C'est bon.",
                            "tokens": [
                                {"surface": "C"},
                                {"surface": "'est"},
                                {"surface": " "},
                                {"surface": "bon"},
                                {"surface": "."},
                            ],
                            "annotations": {},
                        },
                    },
                    {
                        "input": "broken",
                        "phenomenon": "bad example",
                        "rationale": "Should fail validation.",
                        "output": {
                            "surface": "broken",
                            "tokens": [{"surface": "broke"}],
                            "annotations": {},
                        },
                    },
                ]
            }
        )
        spec = FewshotCurationSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="clitic_compound_v2",
            phenomena=("clitic", "compound"),
            count=2,
            model="fake-model",
            request_id="20260602-test",
        )

        batch = await generate_candidate_batch(spec, client=client)

        self.assertIn("Requested phenomena: clitic, compound", client.prompts[0])
        self.assertEqual(["fake-model"], client.models)
        self.assertEqual("schema_validated", batch["records"][0]["status"])
        self.assertEqual("validation_failed", batch["records"][1]["status"])

        with tempfile.TemporaryDirectory() as tmpdir:
            result = store_candidate_batch(
                batch,
                repo_root=Path(tmpdir),
                accept_valid=True,
                write_prompt_variant=True,
            )
            root = Path(result["root"])

            self.assertTrue((root / "requests" / "20260602-test.json").exists())
            self.assertTrue((root / "candidates" / "20260602-test-EXAMPLE-0001.json").exists())
            self.assertTrue((root / "accepted" / "20260602-test-EXAMPLE-0001.json").exists())
            self.assertFalse((root / "accepted" / "20260602-test-EXAMPLE-0002.json").exists())
            prompt_example = (
                Path(tmpdir)
                / "prompts"
                / "segmentation_phase_2"
                / "variants"
                / "clitic_compound_v2"
                / "fewshots"
                / "example1.json"
            )
            self.assertTrue(prompt_example.exists())
            self.assertEqual(2, result["manifest"]["candidate_count"])
            self.assertEqual(1, result["manifest"]["accepted_count"])
            self.assertEqual(
                ["prompts/segmentation_phase_2/variants/clitic_compound_v2/fewshots/example1.json"],
                result["manifest"]["prompt_files"],
            )

    async def test_generation_fans_out_and_traces_shards(self) -> None:
        client = FakeFanoutCurationClient(
            [
                {
                    "candidates": [
                        {
                            "input": "Je l'aime.",
                            "output": {
                                "surface": "Je l'aime.",
                                "tokens": [
                                    {"surface": "Je"},
                                    {"surface": " "},
                                    {"surface": "l'"},
                                    {"surface": "aime"},
                                    {"surface": "."},
                                ],
                                "annotations": {},
                            },
                        }
                    ]
                },
                {
                    "candidates": [
                        {
                            "input": "C'est vrai.",
                            "output": {
                                "surface": "C'est vrai.",
                                "tokens": [
                                    {"surface": "C"},
                                    {"surface": "'est"},
                                    {"surface": " "},
                                    {"surface": "vrai"},
                                    {"surface": "."},
                                ],
                                "annotations": {},
                            },
                        }
                    ]
                },
            ]
        )
        traces: list[str] = []
        spec = FewshotCurationSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="clitic_compound_v2",
            count=2,
            batch_size=1,
            max_concurrency=2,
            model="fake-model",
            request_id="20260602-fanout",
        )

        batch = await generate_candidate_batch(spec, client=client, trace=traces.append)

        self.assertIn('Every inter-word space must appear as its own token', client.prompts[0])
        self.assertIn('input "Je t\'aime." -> tokens "Je", " ", "t\'", "aime", "."', client.prompts[0])
        self.assertEqual(2, len(client.prompts))
        self.assertEqual(["fake-model", "fake-model"], client.models)
        self.assertEqual(["EXAMPLE-0001", "EXAMPLE-0002"], [record["example_id"] for record in batch["records"]])
        self.assertEqual([1, 2], [record["shard_index"] for record in batch["records"]])
        self.assertEqual(2, len(batch["prompts"]))
        self.assertIn("generating 2 candidate examples as 2 shard(s)", traces[0])
        self.assertTrue(any("completed generation shard 1" in message for message in traces))
        self.assertTrue(any("validated 2 candidates" in message for message in traces))

    async def test_prompt_variant_export_appends_to_existing_examples(self) -> None:
        client = FakeCurationClient(
            {
                "candidates": [
                    {
                        "input": "Je l'aime.",
                        "phenomenon": "French object clitic",
                        "rationale": "Separates l' from aime.",
                        "output": {
                            "surface": "Je l'aime.",
                            "tokens": [
                                {"surface": "Je"},
                                {"surface": " "},
                                {"surface": "l'"},
                                {"surface": "aime"},
                                {"surface": "."},
                            ],
                            "annotations": {},
                        },
                    }
                ]
            }
        )
        spec = FewshotCurationSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="existing_set",
            count=1,
            model="fake-model",
            request_id="20260602-topup",
        )

        batch = await generate_candidate_batch(spec, client=client)

        with tempfile.TemporaryDirectory() as tmpdir:
            existing = (
                Path(tmpdir)
                / "prompts"
                / "segmentation_phase_2"
                / "variants"
                / "existing_set"
                / "fewshots"
            )
            existing.mkdir(parents=True)
            (existing / "example1.json").write_text('{"input":"old","output":{}}\n', encoding="utf-8")

            result = store_candidate_batch(
                batch,
                repo_root=Path(tmpdir),
                accept_valid=True,
                write_prompt_variant=True,
            )

            self.assertTrue((existing / "example1.json").exists())
            self.assertTrue((existing / "example2.json").exists())
            self.assertEqual(
                ["prompts/segmentation_phase_2/variants/existing_set/fewshots/example2.json"],
                result["manifest"]["prompt_files"],
            )

    async def test_review_candidate_batch_creates_template_and_reviews(self) -> None:
        generation_client = FakeCurationClient(
            {
                "candidates": [
                    {
                        "input": "Je l'aime.",
                        "phenomenon": "French object clitic",
                        "output": {
                            "surface": "Je l'aime.",
                            "tokens": [
                                {"surface": "Je"},
                                {"surface": " "},
                                {"surface": "l'"},
                                {"surface": "aime"},
                                {"surface": "."},
                            ],
                            "annotations": {},
                        },
                    },
                    {
                        "input": "L'ami de Marie habite ici.",
                        "phenomenon": "invalid missing spaces",
                        "output": {
                            "surface": "L'ami de Marie habite ici.",
                            "tokens": [
                                {"surface": "L'"},
                                {"surface": "ami"},
                                {"surface": "Marie"},
                                {"surface": "habite"},
                                {"surface": "ici"},
                                {"surface": "."},
                            ],
                            "annotations": {},
                        },
                    }
                ]
            }
        )
        generation_spec = FewshotCurationSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="clitic_compound_v2",
            count=1,
            model="fake-generator",
            request_id="20260603-review",
        )
        batch = await generate_candidate_batch(generation_spec, client=generation_client)

        review_client = FakeReviewClient(
            [
                {
                    "template_text": "Review French elision carefully: {candidate_json}",
                    "language_specific_risks": ["French object clitics"],
                    "checklist": ["surface preservation"],
                    "severity_definitions": {"fatal": "bad", "serious": "problem", "minor": "small", "none": "ok"},
                },
                {
                    "template_text": "Check apostrophes and clitics: {candidate_json}",
                    "language_specific_risks": ["apostrophes"],
                    "checklist": ["clitic boundaries"],
                    "severity_definitions": {"fatal": "bad", "serious": "problem", "minor": "small", "none": "ok"},
                },
                {
                    "template_text": "Find the strongest French boundary defect using marker {boundary_marker} and return JSON: {candidate_json}",
                    "language_specific_risks": ["French elision", "clitic boundaries"],
                    "checklist": ["surface preservation", "apostrophes"],
                    "severity_definitions": {"fatal": "unusable", "serious": "misleading", "minor": "cosmetic", "none": "no defect"},
                    "reconciliation_rationale": "Combines both drafts.",
                },
                {
                    "severity": "none",
                    "issue_type": "none",
                    "critique": "No defect found.",
                    "suggested_repair": "",
                    "confidence": 0.82,
                    "recommended_status": "accepted_experimental",
                },
            ]
        )
        review_spec = FewshotReviewSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="clitic_compound_v2",
            request_id="20260603-review",
            model="fake-reviewer",
            template_model="fake-template",
            template_versions=2,
            max_concurrency=1,
        )
        traces: list[str] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            store_candidate_batch(batch, repo_root=Path(tmpdir))
            result = await review_candidate_batch(
                review_spec,
                repo_root=Path(tmpdir),
                client=review_client,
                trace=traces.append,
            )
            root = Path(result["root"])

            self.assertTrue((root / "review_templates" / "template.json").exists())
            self.assertTrue((root / "reviews" / "20260603-review-EXAMPLE-0001.review.json").exists())
            self.assertFalse((root / "reviews" / "20260603-review-EXAMPLE-0002.review.json").exists())
            self.assertTrue((root / "reviews" / "20260603-review.summary.json").exists())
            items_file = root / "reviews" / "20260603-review.items.json"
            self.assertTrue(items_file.exists())
            items_json = json.loads(items_file.read_text(encoding="utf-8"))
            self.assertEqual("EXAMPLE-0001", items_json["items"][0]["example_id"])
            self.assertEqual("Je¦ ¦l'¦aime¦.", items_json["items"][0]["boundary_marked"])
            self.assertEqual("none", items_json["items"][0]["severity"])
            self.assertIn("items_path", result["summary"])
            self.assertEqual(1, result["summary"]["review_count"])
            self.assertEqual(1, result["summary"]["skipped_validation_failed_count"])
            self.assertEqual("EXAMPLE-0002", result["summary"]["skipped_validation_failed"][0]["example_id"])
            self.assertIn(
                "concatenated token surfaces must exactly match input",
                result["summary"]["skipped_validation_failed"][0]["validation_errors"],
            )
            self.assertEqual({"fatal": 0, "serious": 0, "minor": 0, "none": 1}, result["summary"]["severity_counts"])
            self.assertEqual(4, len(review_client.prompts))
            self.assertEqual(["fake-template", "fake-template", "fake-template", "fake-reviewer"], review_client.models)
            self.assertIn("linguistic units", review_client.prompts[0])
            self.assertIn("bubble¦gum", review_client.prompts[0])
            self.assertIn("bar¦becue", review_client.prompts[0])
            self.assertIn("Donne¦-¦le¦-¦moi", review_client.prompts[0])
            self.assertIn("Do NOT say that clitics or elided forms should always be kept together", review_client.prompts[0])
            self.assertIn("Multi Word Expression identification stage", review_client.prompts[0])
            self.assertNotIn("token", review_client.prompts[0].lower())
            self.assertTrue(any("creating 2 review-template draft" in message for message in traces))
            self.assertTrue(any("skipping 1 validation-failed candidate" in message for message in traces))
            self.assertTrue(any("reviewed 1 candidates" in message for message in traces))
            self.assertIn("Je¦ ¦l'¦aime¦.", review_client.prompts[-1])
            self.assertIn("boundary_marked", review_client.prompts[-1])
            self.assertIn("interpretation_notes", review_client.prompts[-1])
            self.assertIn("Donne¦-¦le¦-¦moi", review_client.prompts[-1])
            self.assertIn("l'¦ai", review_client.prompts[-1])
            self.assertIn("Do NOT reject a candidate merely because a French clitic", review_client.prompts[-1])
            self.assertIn("decision", review_client.prompts[-1])
            self.assertNotIn("{boundary_marker}", review_client.prompts[-1])
            self.assertIn("Return your answer as a JSON object", review_client.prompts[-1])
            review_file = root / "reviews" / "20260603-review-EXAMPLE-0001.review.json"
            review_json = __import__("json").loads(review_file.read_text(encoding="utf-8"))
            self.assertEqual("Je l'aime.", review_json["candidate"]["input"])
            self.assertEqual("Je¦ ¦l'¦aime¦.", review_json["candidate"]["boundary_marked"])
            self.assertIn("candidate_path", review_json)

    async def test_review_candidate_batch_reconciles_repeated_review_passes(self) -> None:
        generation_client = FakeCurationClient(
            {
                "candidates": [
                    {
                        "input": "J'aime la glace.",
                        "phenomenon": "French elision",
                        "output": {
                            "surface": "J'aime la glace.",
                            "tokens": [
                                {"surface": "J'"},
                                {"surface": "aime"},
                                {"surface": " "},
                                {"surface": "la"},
                                {"surface": " "},
                                {"surface": "glace"},
                                {"surface": "."},
                            ],
                            "annotations": {},
                        },
                    }
                ]
            }
        )
        generation_spec = FewshotCurationSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="clitic_compound_v2",
            count=1,
            model="fake-generator",
            request_id="20260606-repeated-review",
        )
        batch = await generate_candidate_batch(generation_spec, client=generation_client)
        review_client = FakeReviewClient(
            [
                {
                    "template_text": "Review boundary example and return JSON: {candidate_json}",
                    "severity_definitions": {"fatal": "bad", "serious": "problem", "minor": "small", "none": "ok"},
                },
                {
                    "template_text": "Review boundary example and return JSON: {candidate_json}",
                    "severity_definitions": {"fatal": "bad", "serious": "problem", "minor": "small", "none": "ok"},
                    "reconciliation_rationale": "Single template.",
                },
                {"decision": "reject", "severity": "serious", "explanation": "One reviewer over-penalised the split."},
                {"decision": "accept", "severity": "none", "explanation": "The elided clitic boundary is useful."},
                {"decision": "accept", "severity": "none", "explanation": "Downstream MWE can merge if necessary."},
            ]
        )
        review_spec = FewshotReviewSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="clitic_compound_v2",
            request_id="20260606-repeated-review",
            model="fake-reviewer",
            template_model="fake-template",
            template_versions=1,
            review_passes=3,
            max_concurrency=1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store_candidate_batch(batch, repo_root=Path(tmpdir))
            result = await review_candidate_batch(review_spec, repo_root=Path(tmpdir), client=review_client)
            root = Path(result["root"])
            review_file = root / "reviews" / "20260606-repeated-review-EXAMPLE-0001.review.json"
            review_json = json.loads(review_file.read_text(encoding="utf-8"))

            self.assertEqual("accept", review_json["review"]["decision"])
            self.assertEqual("none", review_json["severity"])
            self.assertEqual(3, review_json["review_pass_count"])
            self.assertEqual(3, len(review_json["review_passes"]))
            self.assertEqual({"fatal": 0, "serious": 0, "minor": 0, "none": 1}, result["summary"]["severity_counts"])
            self.assertEqual(3, result["summary"]["review_passes"])
            self.assertIn("Independent review pass 2 of 3", review_client.prompts[-2])

    def test_filesystem_path_adds_windows_long_path_prefix(self) -> None:
        path = Path("/tmp/review-output.json")

        filesystem_path = _filesystem_path(path, os_name="nt")

        self.assertTrue(str(filesystem_path).startswith("\\\\?\\"))

    def test_write_json_recreates_parent_if_removed_between_mkdir_and_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "nested" / "payload.json"
            original_write_text = Path.write_text
            attempts = {"count": 0}

            def flaky_write_text(path: Path, *args, **kwargs):
                if path == target and attempts["count"] == 0:
                    attempts["count"] += 1
                    shutil.rmtree(path.parent)
                    raise FileNotFoundError(str(path))
                return original_write_text(path, *args, **kwargs)

            with mock.patch.object(Path, "write_text", flaky_write_text):
                _write_json(target, {"ok": True})

            self.assertEqual({"ok": True}, json.loads(target.read_text(encoding="utf-8")))
            self.assertEqual(1, attempts["count"])

    async def test_custom_curation_root_keeps_experiment_artifacts_out_of_docs(self) -> None:
        client = FakeCurationClient(
            {
                "candidates": [
                    {
                        "input": "Je l'aime.",
                        "phenomenon": "French object clitic",
                        "rationale": "Separates l' from aime while preserving the space.",
                        "output": {
                            "surface": "Je l'aime.",
                            "tokens": [
                                {"surface": "Je"},
                                {"surface": " "},
                                {"surface": "l'"},
                                {"surface": "aime"},
                                {"surface": "."},
                            ],
                            "annotations": {},
                        },
                    }
                ]
            }
        )
        spec = FewshotCurationSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="clitic_compound_v2",
            phenomena=("clitic",),
            count=1,
            model="fake-model",
            request_id="20260605-experiment-root",
        )
        batch = await generate_candidate_batch(spec, client=client)
        review_client = FakeReviewClient(
            [
                {
                    "template_text": "Review this marked example: {candidate_json}",
                    "language_specific_risks": [],
                    "checklist": [],
                    "severity_definitions": {"fatal": "bad", "serious": "problem", "minor": "small", "none": "ok"},
                },
                {
                    "template_text": "Review this marked example: {candidate_json}",
                    "language_specific_risks": [],
                    "checklist": [],
                    "severity_definitions": {"fatal": "bad", "serious": "problem", "minor": "small", "none": "ok"},
                    "reconciliation_rationale": "Single experiment-root template.",
                },
                {"severity": "none", "critique": "No defect found."},
            ]
        )
        review_spec = FewshotReviewSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="clitic_compound_v2",
            request_id="20260605-experiment-root",
            model="fake-reviewer",
            template_model="fake-template",
            template_versions=1,
            max_concurrency=1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            curation_root_base = (
                repo_root
                / "experiments"
                / "linguistic_processing"
                / "segmentation_phase_2"
                / "fr_boundary_first_clitic_compound_v2"
                / "generated"
                / "few_shot_curation"
            )
            stored = store_candidate_batch(batch, repo_root=repo_root, curation_root_base=curation_root_base)
            stored_root = Path(stored["root"])

            self.assertTrue(stored_root.is_relative_to(curation_root_base))
            self.assertTrue((stored_root / "requests" / "20260605-experiment-root.json").exists())
            self.assertFalse((repo_root / "docs" / "few_shot_curation").exists())

            reviewed = await review_candidate_batch(
                review_spec,
                repo_root=repo_root,
                client=review_client,
                curation_root_base=curation_root_base,
            )
            review_root = Path(reviewed["root"])
            review_file = review_root / "reviews" / "20260605-experiment-root-EXAMPLE-0001.review.json"
            review_json = json.loads(review_file.read_text(encoding="utf-8"))

            self.assertTrue(review_root.is_relative_to(curation_root_base))
            self.assertTrue(review_file.exists())
            self.assertTrue(review_json["candidate_path"].startswith("experiments/"))
            self.assertTrue(reviewed["summary"]["template_path"].startswith("experiments/"))
            self.assertFalse((repo_root / "docs" / "few_shot_curation").exists())

    async def test_review_checks_request_before_creating_template(self) -> None:
        review_client = FakeReviewClient([{"template_text": "unused"}])
        review_spec = FewshotReviewSpec(
            operation="segmentation_phase_2",
            language="fr",
            mechanism="boundary_first",
            target_set="clitic_compound_v2",
            request_id="missing-request",
            model="fake-reviewer",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            request_dir = (
                Path(tmpdir)
                / "docs"
                / "few_shot_curation"
                / "segmentation_phase_2"
                / "fr"
                / "boundary_first"
                / "clitic_compound_v2"
                / "requests"
            )
            request_dir.mkdir(parents=True)
            (request_dir / "request1.json").write_text("{}\n", encoding="utf-8")

            with self.assertRaises(FileNotFoundError) as cm:
                await review_candidate_batch(review_spec, repo_root=Path(tmpdir), client=review_client)

            self.assertIn("Available request IDs: request1", str(cm.exception))
            self.assertEqual([], review_client.prompts)



if __name__ == "__main__":
    unittest.main()
