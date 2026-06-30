# Chunk decomposition multilingual v1 prompts

This directory records generated whitespace-chunk segmentation prompts promoted
from the `experiments/linguistic_processing/segmentation_phase_2/chunk_decomposition_multilingual`
workbench.

The prompts are stored by language, source split, and development cycle so that
we can preserve the evaluated artifacts before wiring selected prompts into the
runtime `segmentation_phase_2` pipeline.

Use the prompts by setting the phase-2 mechanism to `chunk_decomposition`. The
pipeline fans out each non-whitespace token/chunk in a segment to the selected
language prompt and then fans the validated chunk decompositions back into the
segment token list. If `chunk_prompt_cycle` is omitted, the loader uses the
latest available cycle for the selected language, split, and variant.

Example stage parameters:

```json
{
  "segmentation_phase_2": {
    "mechanism": "chunk_decomposition",
    "chunk_prompt_variant": "chunk_decomposition_multilingual_v1",
    "chunk_prompt_split": "development",
    "chunk_prompt_cycle": 2,
    "max_concurrency": 20
  }
}
```

Promoted prompt cycles are listed in `manifest.json`.
