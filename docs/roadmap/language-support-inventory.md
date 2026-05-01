# Language support inventory (single reference)

This file collects the places where adding a new language may require explicit updates.

## Canonical UI language list
- `platform_server/projects/forms.py`
  - `ProjectForm.LANGUAGE_CHOICES`
  - Source of truth for project language selectors, glossing selectors, and profile dialogue language.

## Prompt construction: language-specific inserted text
- `src/pipeline/text_gen.py`
  - `_build_story_prompt()` uses `language_labels` to insert natural language names in generation prompts.
- `platform_server/projects/views.py`
  - `_build_page_image_prompt()` has:
    - `language_instructions` (fully localized prompt lead-in lines; currently explicit for a subset of languages, fallback to English)
    - `language_labels` used in prompt metadata lines.
- `src/pipeline/audio.py`
  - `_tts_language_hint()` uses `language_map` to insert friendly language hints for TTS engines.

## Prompt templates / few-shots by language
- `prompts/<operation>/<language>/template.txt`
- `prompts/<operation>/<language>/fewshots.json`
- Fallback behavior and defaulting are implemented in:
  - `src/pipeline/annotation_prompts.py`
  - Operation modules in `src/pipeline/` (e.g. `gloss.py`, `segmentation.py`, `lemma.py`, `mwe.py`, `translation.py`, `text_gen.py`).

## Validation and allow-lists that derive from UI language choices
- `platform_server/projects/views.py`
  - Pivot-language validation and target-language validation pull from `ProjectForm.LANGUAGE_CHOICES`.

## Current status for recently requested languages
Requested: Danish (`da`), Norwegian (`no`), Polish (`pl`), Swedish (`sv`).

- [x] Added to canonical UI language list.
- [x] Added to text-generation language labels.
- [x] Added to page-image prompt language labels.
- [ ] Add full localized page-image prompt instruction lines for these languages (optional; currently falls back safely to English).
- [ ] Add per-operation prompt templates/few-shots where quality requires language-specific examples.
