from __future__ import annotations

import asyncio
from typing import Any

from django.test import SimpleTestCase

from pipeline.segmentation import SegmentationPhase2Spec, segmentation_phase_2


class FakeChunkClient:
    def __init__(self, responses: dict[str, list[str]]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    async def chat_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        for surface, parts in self.responses.items():
            if f'"chunk_surface": "{surface}"' in prompt:
                return {"parts": parts, "notes": "fixture"}
        return {"parts": []}


class SegmentationPhase2ChunkDecompositionTests(SimpleTestCase):
    def test_chunk_decomposition_splits_each_existing_token_and_preserves_whitespace(self):
        text = {
            "l2": "en",
            "surface": "opened, grandchildren",
            "pages": [
                {
                    "surface": "opened, grandchildren",
                    "segments": [
                        {
                            "surface": "opened, grandchildren",
                            "tokens": [
                                {"surface": "opened,"},
                                {"surface": " "},
                                {"surface": "grandchildren"},
                            ],
                            "annotations": {},
                        }
                    ],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakeChunkClient({"opened,": ["opened", ","], "grandchildren": ["grandchildren"]})

        annotated = asyncio.run(
            segmentation_phase_2(
                SegmentationPhase2Spec(
                    text=text,
                    language="en",
                    mechanism="chunk_decomposition",
                    chunk_prompt_cycle=2,
                ),
                client=client,  # type: ignore[arg-type]
            )
        )

        tokens = annotated["pages"][0]["segments"][0]["tokens"]
        self.assertEqual([token["surface"] for token in tokens], ["opened", ",", " ", "grandchildren"])
        self.assertEqual(len(client.prompts), 2)
        self.assertIn("Return only JSON", client.prompts[0])

    def test_chunk_decomposition_keeps_source_token_when_response_breaks_surface_invariant(self):
        text = {
            "l2": "en",
            "surface": "opened,",
            "pages": [
                {
                    "surface": "opened,",
                    "segments": [{"surface": "opened,", "tokens": [{"surface": "opened,"}], "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakeChunkClient({"opened,": ["opened"]})

        annotated = asyncio.run(
            segmentation_phase_2(
                SegmentationPhase2Spec(
                    text=text,
                    language="en",
                    mechanism="chunk_decomposition",
                    chunk_prompt_cycle=2,
                ),
                client=client,  # type: ignore[arg-type]
            )
        )

        tokens = annotated["pages"][0]["segments"][0]["tokens"]
        self.assertEqual([token["surface"] for token in tokens], ["opened,"])
