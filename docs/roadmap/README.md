# Roadmap documents for reimplementation of C-LARA (C-LARA-2)

**Overall goal**  
Reimplement [C-LARA](https://www.c-lara.org/) in a more rational way, learning from the initial project.

## Brief description of core C-LARA-2 functionality

- **Functionality from C-LARA:** We want to reproduce the core C-LARA functionality.
	- Use AI to create multimodal text documents suitable for language learners. These should at a minimum include illustrations, translations, lemma tagging, glosses and audio. 
	- It is essential to support multi-word expressions (MWEs) and have them interact cleanly with lemma tagging and glossing. In the final generated document, clicking or hovering over one element of an MWE accesses information attached to the whole MWE.
	- It is essential to support creation of high-quality images that are consistent both in style (different images have the same style) and content (when a person, object etc occurs in more than one image it is depicted similarly).
	- C-LARA-2 should be sufficiently downward-compatible that C-LARA projects can easily be imported.
	- It should be possible to post the multimodal documents on the web, in a social-network like structure that permits rating, commenting etc.
	- Full information about C-LARA can be found in numerous papers posted on the C-LARA site.
- **New functionality:** User feedback suggests some new functionality would be much appreciated.
	- Teachers want it to be easier to create the texts. Instead of providing a detailed description of the text they want to generated, they would prefer to give a brief description and then enter a dialogue with the AI to refine it. If they have a group of related texts, they want to describe the group as a whole, maybe in terms of the intended functionality and users, and have the AI suggest possible texts.
	- Learners want to have the option of accessing non-traditional audio/image oriented texts that work well on mobile phones, e.g. audiobooks, podcasts, manga.

## Important subgoals

- **Involve the AI more:** Various versions of OpenAI's GPT already played an important part in the first version of C-LARA. Here, we want to increase the AI's involvement:
	- The AI should understand the platform (functionality, software architecture, history etc) as well as possible.
	- The AI should play as large a part as possible in implementing the new code.
	- The AI should to as large an extent as possible be able to explain and discuss the platform.
- **Better documentation:** In order to be able to involve the AI in the way described above, the documentation needs to be much better:
	- All code files will be systematically documented (docstrings etc) according to a recognised standard.
	- There will be global web-accessible documentation in the Github repo, i.e. here.
	- The AI will play a central role in _developing_ the documentation. 
	- As we proceed with the project, we will constantly check that the AI is in practice able to use the doc, and revise if necessary.
	
## Main steps in roadmap

### 1. Set up GitHub repository and add initial documentation.

Status: **Done.** The C-LARA-2 repo is at https://github.com/mannyrayner/C-LARA-2.

### 2. Initial core functionality: text generation and segmentation

Status: **Done.** The foundational pieces for the text pipeline are implemented and tested:

- Annotated text representation and utilities.
- OpenAI wrapper with heartbeat, telemetry, retries, and unit/integration coverage.
- Text generation (`text_gen`) to produce starter texts from descriptions.
- Segmentation phase 1 (pages/segments) and phase 2 (tokenization) using the generic annotation harness.
- Generic per-segment annotation fan-out/fan-in infrastructure reused by later steps.
- Prompts and few-shots for the above operations.
- Tests under `tests/` (OpenAI-gated where applicable); run with `make -C tests test`.

See `docs/roadmap/segmentation-pipeline.md` for the specification that guided these implementations.

### 3. Full linguistic annotation pipeline

Status: **In progress.** The detailed plan lives in `docs/roadmap/linguistic-pipeline.md`.

- Implemented: translation (EN→FR), MWE detection, lemma tagging, glossing, Chinese pinyin annotation (via `pypinyin`), and audio annotation with caching (TTS stub), with prompts/few-shots where AI-backed.
- Planned/next: HTML compilation hooks and richer audio ingestion (human-recorded, phonetic-text paths).

Each operation has (or will have) prompts under `prompts/<operation>/<lang>/` plus unit and integration tests (OpenAI-gated).

### 4. Write spec for basic Django platform functionality, and implement it

In this step, we will add the basic Django platform  functionality. Most of this can probably be adapted easily from C-LARA.
- Top-level Django functionality with menu for core actions like creating new project, editing existing project, listing existing content, etc. We need appropriate search functionality.
- Support for posting a piece of compiled content.
- Support for rating and commenting a piece of compiled content.
- Unit tests for all of the above.

### 5. Write spec for image creation functionality, and implement it

In this step, we will add the basic image creation functionality. This will be conceptually based on the corresponding functionality in C-LARA, but rationalised and reimplemented.
- We have the same three-stage pipeline:
	- Create style. A brief description is expanded by the AI into a detaile style description and an example image.
	- Create element names. Generate
