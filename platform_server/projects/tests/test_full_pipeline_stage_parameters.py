from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase

from pipeline.full_pipeline import FullPipelineSpec, run_full_pipeline


class FullPipelineStageParameterTests(SimpleTestCase):
    def test_segmentation_phase_2_receives_chunk_decomposition_parameters(self):
        text_obj = {
            "l2": "en",
            "surface": "opened,",
            "pages": [{"surface": "opened,", "segments": [{"surface": "opened,"}], "annotations": {}}],
            "annotations": {},
        }
        async_mock = AsyncMock(return_value=text_obj)

        with patch("pipeline.full_pipeline.segmentation_phase_2", async_mock):
            result = asyncio.run(
                run_full_pipeline(
                    FullPipelineSpec(
                        text_obj=text_obj,
                        language="en",
                        start_stage="segmentation_phase_2",
                        end_stage="segmentation_phase_2",
                        stage_parameters={
                            "segmentation_phase_2": {
                                "mechanism": "chunk_decomposition",
                                "chunk_prompt_variant": "chunk_decomposition_multilingual_v1",
                                "chunk_prompt_split": "development",
                                "chunk_prompt_cycle": 2,
                                "max_concurrency": 3,
                            }
                        },
                    ),
                    client=object(),  # type: ignore[arg-type]
                )
            )

        spec = async_mock.call_args.args[0]
        self.assertEqual(result["text"], text_obj)
        self.assertEqual(spec.mechanism, "chunk_decomposition")
        self.assertEqual(spec.chunk_prompt_variant, "chunk_decomposition_multilingual_v1")
        self.assertEqual(spec.chunk_prompt_split, "development")
        self.assertEqual(spec.chunk_prompt_cycle, 2)
        self.assertEqual(spec.max_concurrency, 3)
