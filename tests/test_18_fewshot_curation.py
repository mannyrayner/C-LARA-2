from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.fewshot_curation import (
    FewshotCurationSpec,
    generate_candidate_batch,
    store_candidate_batch,
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


if __name__ == "__main__":
    unittest.main()
