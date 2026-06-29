from __future__ import annotations

import asyncio
from typing import Any

from django.test import SimpleTestCase

from pipeline.segmentation import SegmentationPhase2Spec, segmentation_phase_2


class FakeChunkClient:
    def __init__(self, responses: dict[str, list[str]]) -> None:
        self.responses = responses
        self.prompts: list[str] = []
        self.kwargs: list[dict[str, Any]] = []

    async def chat_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.kwargs.append(kwargs)
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
        self.assertNotIn("temperature", client.kwargs[0])

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

    def test_chunk_decomposition_uses_whitespace_chunks_not_editable_token_boundaries(self):
        text = {
            "l2": "fr",
            "surface": " Il l'aime bien.",
            "pages": [
                {
                    "surface": " Il l'aime bien.",
                    "segments": [{"surface": " Il l'aime bien.", "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakeChunkClient(
            {
                "Il": ["Il"],
                "l'aime": ["l'", "aime"],
                "bien.": ["bien", "."],
            }
        )

        annotated = asyncio.run(
            segmentation_phase_2(
                SegmentationPhase2Spec(
                    text=text,
                    language="fr",
                    mechanism="chunk_decomposition",
                    chunk_prompt_cycle=3,
                ),
                client=client,  # type: ignore[arg-type]
            )
        )

        prompts = "\n".join(client.prompts)
        segment = annotated["pages"][0]["segments"][0]
        tokens = segment["tokens"]
        trace = segment["annotations"]["segmentation_phase_2_chunk_trace"]
        self.assertIn('"chunk_surface": "l\'aime"', prompts)
        self.assertNotIn('"chunk_surface": "l"', prompts)
        self.assertEqual([token["surface"] for token in tokens], [" ", "Il", " ", "l'", "aime", " ", "bien", "."])
        self.assertIn(
            {
                "token_index": 3,
                "op_id": "segmentation_phase_2-chunk-p0-s0-t3",
                "chunk_surface": "l'aime",
                "predicted_parts": ["l'", "aime"],
                "surface_preserved": True,
                "raw_response": {"parts": ["l'", "aime"], "notes": "fixture"},
            },
            trace,
        )

    def test_chunk_decomposition_splits_pipe_delimited_part_inside_response_list(self):
        text = {
            "l2": "fr",
            "surface": " cordes.",
            "pages": [
                {
                    "surface": " cordes.",
                    "segments": [{"surface": " cordes.", "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakeChunkClient({"cordes.": ["cordes|."]})

        annotated = asyncio.run(
            segmentation_phase_2(
                SegmentationPhase2Spec(
                    text=text,
                    language="fr",
                    mechanism="chunk_decomposition",
                    chunk_prompt_cycle=3,
                ),
                client=client,  # type: ignore[arg-type]
            )
        )

        segment = annotated["pages"][0]["segments"][0]
        trace = segment["annotations"]["segmentation_phase_2_chunk_trace"]
        self.assertEqual([token["surface"] for token in segment["tokens"]], [" ", "cordes", "."])
        self.assertEqual(trace[0]["predicted_parts"], ["cordes", "."])
        self.assertTrue(trace[0]["surface_preserved"])

    def test_chunk_decomposition_repairs_quote_glyphs_to_preserve_surface(self):
        text = {
            "l2": "fr",
            "surface": " «Bonjour»",
            "pages": [
                {
                    "surface": " «Bonjour»",
                    "segments": [{"surface": " «Bonjour»", "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakeChunkClient({"«Bonjour»": ['"|Bonjour|"']})

        annotated = asyncio.run(
            segmentation_phase_2(
                SegmentationPhase2Spec(
                    text=text,
                    language="fr",
                    mechanism="chunk_decomposition",
                    chunk_prompt_cycle=3,
                ),
                client=client,  # type: ignore[arg-type]
            )
        )

        segment = annotated["pages"][0]["segments"][0]
        trace = segment["annotations"]["segmentation_phase_2_chunk_trace"]
        self.assertEqual([token["surface"] for token in segment["tokens"]], [" ", "«", "Bonjour", "»"])
        self.assertEqual(trace[0]["predicted_parts"], ["«", "Bonjour", "»"])
        self.assertTrue(trace[0]["surface_preserved"])

    def test_chunk_decomposition_repairs_dash_glyphs_to_preserve_surface(self):
        text = {
            "l2": "fr",
            "surface": " au‑dessus",
            "pages": [
                {
                    "surface": " au‑dessus",
                    "segments": [{"surface": " au‑dessus", "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakeChunkClient({"au‑dessus": ["au|-|dessus"]})

        annotated = asyncio.run(
            segmentation_phase_2(
                SegmentationPhase2Spec(
                    text=text,
                    language="fr",
                    mechanism="chunk_decomposition",
                    chunk_prompt_cycle=3,
                ),
                client=client,  # type: ignore[arg-type]
            )
        )

        segment = annotated["pages"][0]["segments"][0]
        trace = segment["annotations"]["segmentation_phase_2_chunk_trace"]
        self.assertEqual([token["surface"] for token in segment["tokens"]], [" ", "au", "‑", "dessus"])
        self.assertEqual(trace[0]["predicted_parts"], ["au", "‑", "dessus"])
        self.assertTrue(trace[0]["surface_preserved"])

    def test_chunk_decomposition_repairs_apostrophe_glyph_to_preserve_surface(self):
        text = {
            "l2": "fr",
            "surface": " qu’il",
            "pages": [
                {
                    "surface": " qu’il",
                    "segments": [{"surface": " qu’il", "annotations": {}}],
                    "annotations": {},
                }
            ],
            "annotations": {},
        }
        client = FakeChunkClient({"qu’il": ["qu'|il"]})

        annotated = asyncio.run(
            segmentation_phase_2(
                SegmentationPhase2Spec(
                    text=text,
                    language="fr",
                    mechanism="chunk_decomposition",
                    chunk_prompt_cycle=3,
                ),
                client=client,  # type: ignore[arg-type]
            )
        )

        segment = annotated["pages"][0]["segments"][0]
        trace = segment["annotations"]["segmentation_phase_2_chunk_trace"]
        self.assertEqual([token["surface"] for token in segment["tokens"]], [" ", "qu’", "il"])
        self.assertEqual(trace[0]["predicted_parts"], ["qu’", "il"])
        self.assertTrue(trace[0]["surface_preserved"])
