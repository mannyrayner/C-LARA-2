# Image generation pipeline

This document expands Step 5 of the roadmap into a concrete plan for adding coherent per-page illustrations to C-LARA-2. The goal is to support image creation that is:

- **Style-consistent** across a project.
- **Entity-consistent** when the same person, object, place, or recurring visual motif appears on multiple pages.
- **Interactive**: users can review, edit, and regenerate intermediate artifacts before committing to a full set of page images.
- **Project-scoped and reproducible**: every generated prompt, image, and decision is stored with the project so later steps can reuse or regenerate the assets.

The design is inspired by the original C-LARA image flow, but reorganised into clearer pipeline stages and persistent artifacts.

## 1. High-level goals

We want a new optional branch of the pipeline that can run after text creation/segmentation and before or after linguistic annotation, depending on workflow. The image branch should:

1. Start from the project text and a short user-provided style brief.
2. Build an expanded project-level style specification.
3. Identify recurring visual elements that require consistency.
4. Build and refine per-element visual specifications plus reference images.
5. Determine, for each page, which recurring elements are relevant.
6. Generate one coherent image per page using the page text, project context, style specification, and relevant element references.
7. Persist all prompts, structured outputs, and binary image artifacts in a project-owned location.

## 2. Pipeline overview

The image pipeline is divided into three user-visible stages:

1. **Style**
2. **Elements**
3. **Page images**

Each stage includes:

- one or more GPT-style reasoning/substitution calls,
- one or more image-generation calls,
- persisted intermediate artifacts,
- a review/regeneration UI,
- explicit user confirmation before moving to the next stage.

At a high level, the flow is:

```text
project text
  + style brief
    -> expanded style description
    -> sample style image
    -> user review/edit/approve
      -> recurring element list
      -> user review/edit/approve
        -> expanded element descriptions
        -> element reference images
        -> user review/regenerate/approve
          -> per-page relevant-element selection
          -> per-page image prompts
          -> final page images
```

## 3. User workflow

### 3.1 Entry point

The Django project page should eventually expose an **Images** action or tab. Entering the image flow should show:

- current status for style/elements/pages,
- any previously approved artifacts,
- options to resume, restart a stage, or regenerate selected outputs.

### 3.2 Style stage

The user provides:

- a short **style brief**,
- optionally a target image model,
- optionally a GPT model for prompt expansion.

Example style brief:

- "soft watercolor storybook"
- "French ligne claire comic style"
- "bright anime-inspired classroom scenes"

The system then:

1. sends the project text plus the brief to a GPT model,
2. requests an expanded style description that reflects both the brief and the actual story content,
3. extracts representative textual material from the project,
4. sends the expanded style description plus the representative material to an image model,
5. stores and displays a **sample style image**,
6. lets the user edit the expanded style description and regenerate until satisfied,
7. records an approved style bundle.

### 3.3 Elements stage

The system next proposes a list of recurring elements, such as:

- named characters,
- unnamed but recurring roles (teacher, host mother, dentist),
- recurring animals,
- recurring places or settings,
- signature objects (bag, bicycle, red notebook),
- repeated motifs that should remain stable.

The user can:

- remove irrelevant elements,
- add missing elements,
- rename entries for clarity,
- optionally mark priority or type.

After approval of the element list, the system generates for each element:

1. an expanded element description, using the full text and the approved style description,
2. an element reference image,
3. optionally extra metadata such as negative constraints or invariants.

The user can then review the element cards and regenerate individual ones as needed.

### 3.4 Page image stage

Once style and element references are approved, the system:

1. analyses each page in parallel to decide which approved recurring elements are relevant,
2. builds a page-level image prompt using:
   - the page text,
   - the full project text for background,
   - the approved style description,
   - the relevant element descriptions,
   - the relevant element images,
3. generates the page image,
4. stores it and presents it in a grid or page-by-page editor,
5. allows regeneration of one page or a subset of pages.

## 4. Stage 1: style generation

### 4.1 Inputs

Required inputs:

- full project text,
- user style brief.

Optional inputs:

- project title,
- L1/L2 metadata,
- target audience/age,
- desired aspect ratio,
- desired colour palette hints,
- example exclusions (e.g. "avoid photorealism").

### 4.2 GPT expansion task

The GPT call should request a structured object something like:

```json
{
  "style_name": "storybook watercolor",
  "expanded_style_description": "...",
  "palette_notes": ["..."],
  "composition_notes": ["..."],
  "character_rendering_notes": ["..."],
  "background_rendering_notes": ["..."],
  "negative_constraints": ["..."],
  "sample_prompt_material": "..."
}
```

The prompt should explicitly ask the model to:

- preserve the user brief,
- adapt it to the actual story,
- mention recurring visual concerns relevant to the text,
- provide enough detail to drive downstream image generation,
- avoid overfitting to a single page.

### 4.3 Style sample image generation

A second call to an image model should use:

- the expanded style description,
- representative project material,
- a request for a single image that captures the approved visual idiom.

Representative material might include:

- the project title,
- a summary,
- selected page excerpts,
- mentions of key characters/settings.

### 4.4 User interaction

The style review screen should display:

- original brief,
- expanded style description in editable text form,
- sample image,
- regenerate button,
- approve button.

Important requirement: the user must be able to edit the expanded style description directly before regenerating.

### 4.5 Persisted artifacts

Suggested persisted records:

- `style_brief.txt`
- `style_expansion_prompt.json`
- `style_expansion_response.json`
- `style_description.txt`
- `style_sample_prompt.json`
- `style_sample_image.png`
- `style_status.json`

## 5. Stage 2: recurring elements

### 5.1 Element discovery task

A GPT call should examine the full text and return recurring visual elements that appear on at least two pages or otherwise need visual consistency.

A structured response might look like:

```json
{
  "elements": [
    {
      "name": "Celine",
      "type": "character",
      "page_refs": [1, 2, 4],
      "why_consistency_matters": "main character"
    },
    {
      "name": "host mother",
      "type": "character",
      "page_refs": [1, 3],
      "why_consistency_matters": "recurring supporting character"
    }
  ]
}
```

The system should not automatically trust the list; it should always be user-reviewable.

### 5.2 User curation of element list

The review UI should allow the user to:

- add/remove elements,
- merge duplicates,
- rename entries,
- change the type,
- mark an item as "do not create image reference" if a textual reference is enough.

### 5.3 Element expansion task

For each approved element, run a GPT call in parallel to create a richer element description using:

- element name,
- full text,
- approved style description,
- optional nearby text snippets where the element appears.

Expected structured output could include:

```json
{
  "name": "Celine",
  "expanded_description": "...",
  "visual_invariants": ["same hair colour", "same approximate age"],
  "optional_variants": ["different clothes allowed by scene"],
  "negative_constraints": ["avoid making her look elderly"]
}
```

### 5.4 Element image generation

Each approved expanded element description is then sent to the image model to generate a reference image.

The element image request should aim to produce:

- a neutral reference image,
- visually clean composition,
- enough detail for downstream reuse,
- minimal scene clutter.

### 5.5 User interaction

The UI should show an **element card** per approved element with:

- element name/type,
- editable expanded description,
- generated reference image,
- regenerate button,
- approve/reject state.

Regeneration should be available per element so users do not need to rerun the whole batch.

### 5.6 Persisted artifacts

Suggested project storage:

```text
images/
  style/
    ...
  elements/
    elements_list.json
    <element_slug>/
      definition.json
      expansion_prompt.json
      expansion_response.json
      description.txt
      image_prompt.json
      reference.png
      status.json
```

## 6. Stage 3: page images

### 6.1 Per-page element relevance

Before generating page images, the system should decide which recurring elements are relevant to each page.

This should be done with a GPT call per page, using:

- the page text,
- the approved element list,
- optionally brief element descriptions.

Structured output might be:

```json
{
  "page_number": 3,
  "relevant_elements": ["Celine", "host mother", "blue suitcase"],
  "notes": "Celine is foreground; host mother is background; suitcase may be omitted if composition is crowded."
}
```

### 6.2 Page image generation inputs

Each page image request should combine:

- page text,
- full project text or summary for background,
- approved expanded style description,
- approved relevant element descriptions,
- approved relevant element reference images,
- page-specific composition instructions.

### 6.3 Parallelism

Page relevance calls can run in parallel, and page image generation can also run in parallel, subject to:

- API rate limits,
- cost limits,
- queue capacity,
- image model concurrency limitations.

### 6.4 User interaction

The page image review UI should support:

- gallery view,
- per-page detail view,
- regenerate one page,
- regenerate selected pages,
- final approve/publish-ready state.

### 6.5 Persisted artifacts

Suggested structure:

```text
images/
  pages/
    page_001/
      page_text.txt
      relevant_elements.json
      prompt.json
      image.png
      status.json
    page_002/
      ...
```

## 7. Data model and persistence

At each stage, generated information should be stored in a way that associates it with the project and preserves history.

### 7.1 Storage principles

- Store both **structured JSON** and **human-editable text** where appropriate.
- Store every prompt/response pair for auditing and regeneration.
- Store binary images under project-owned media paths.
- Support multiple runs or versions rather than destructive overwrite.

### 7.2 Project associations

The Django layer will likely need models roughly analogous to:

- `ProjectImageStyle`
- `ProjectImageElement`
- `ProjectPageImage`
- `ProjectImageRun` or version/checkpoint records

Exact schema can be decided during implementation, but the roadmap requirement is clear: image artifacts must be queryable per project and reusable across regeneration steps.

## 8. Suggested directory layout

A pipeline-run-oriented layout could look like:

```text
media/
  users/<user_id>/
    projects/project_<id>/
      image_runs/image_run_<timestamp>/
        style/
        elements/
        pages/
        logs/
```

An alternative is to keep image artifacts inside the existing `runs/run_<timestamp>/` tree. That may be preferable if image generation is treated as another pipeline branch attached to a compile run. We should decide this during implementation.

## 9. Relationship to the existing text pipeline

This image flow should be **optional** and **restartable by stage**, following the same design principle already used by `run_full_pipeline`.

Questions to settle during implementation:

- Does image generation live inside `run_full_pipeline`, or in a sibling image pipeline service?
- Can image generation start from raw text only, or should it require segmented pages?
- Should page images be regenerated automatically when text changes, or only on explicit user request?
- How do published HTML pages discover and display the final page images?

My current view is:

- page-image generation should depend on page segmentation being available,
- style generation can happen earlier,
- image generation logic is cleaner as a sibling pipeline service rather than being folded into the existing linguistic pipeline immediately.

## 10. API/model considerations

We should keep model selection configurable at each substep.

Typical defaults might be:

- GPT-style text expansion/reasoning: `gpt-4o` or other selected chat model,
- image generation: `gpt-image-1` or a configured image backend.

Configuration should support:

- per-project defaults,
- per-stage overrides,
- safe fallbacks,
- future support for non-OpenAI backends.

## 11. Regeneration and approval semantics

A key part of the design is **human approval checkpoints**:

- style must be approved before element generation,
- element list must be approved before element references are generated,
- element references should be approved before page images are generated.

Regeneration should be granular:

- regenerate style sample only,
- regenerate one element,
- regenerate one page,
- regenerate a selected subset.

## 12. Failure handling and observability

This pipeline will be long-running and expensive enough that background execution and progress reporting are essential.

We should reuse the newer monitor/task-update pattern already introduced for compile tasks:

- queue image tasks in the background,
- store progress events in the database,
- poll from a monitor page,
- show stage-specific errors cleanly,
- preserve partial outputs when possible.

Important examples of recoverable failures:

- style expansion succeeds but style sample image generation fails,
- element list succeeds but a subset of element images fail,
- some page images fail while others succeed.

## 13. Testing strategy

Implementation should eventually include:

- unit tests for prompt builders,
- unit tests for structured response normalisation,
- tests for element-list editing logic,
- tests for artifact persistence,
- tests for background-task progress reporting,
- integration tests with fake AI/image clients,
- optional gated live tests for real providers.

## 14. Implementation sketch

A likely implementation sequence is:

1. add roadmap/spec documentation,
2. define project storage/model requirements,
3. add style-stage backend functions and fake-client tests,
4. add style review UI,
5. add element discovery/curation backend,
6. add element reference generation and review UI,
7. add page relevance + page image generation backend,
8. wire the whole flow into Django background tasks and monitor screens,
9. connect approved page images into published HTML/project views.

## 15. Open design questions

Before implementation, we should discuss at least these points:

1. Should image artifacts live inside compile runs or in a separate image-run namespace?
2. Do we want one approved style per project, or multiple named style variants?
3. Should users be able to upload their own reference images as replacements for generated element images?
4. How tightly should page images be coupled to page segmentation versions?
5. Do we want the first implementation to generate a single image per page only, or also support panel/manga-style layouts later?

## 16. Proposed status in roadmap

This work should remain marked as **planned/in design** until the style stage backend and UI are implemented.
