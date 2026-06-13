# 3. User-Facing Functionality (Concise Draft Plan)

## 3.1 Functional overview

- C-LARA-2 supports end-to-end creation and publication of multimodal language-learning content.
- The report should not try to catalogue every feature inherited from C-LARA.
- Instead, it should highlight user-facing work that illustrates what has become newly useful or more coherent in C-LARA-2.

## 3.2 Major capabilities to foreground

- **Picture dictionaries**: initially a supporting feature, but now a more interesting and useful component than expected. They support image-backed vocabulary work, picture glossing, picture flashcards, and reuse in learner activities. Recent work also makes them more dependable by carrying “no visible text” image constraints into organiser regeneration prompts.
- **Low-resource-language support**: more coherent workflows for languages where AI models or TTS are weak, including structured/manual editing, advisory AI diagnostics for word/gloss language-confusion errors, and future reliance on community audio.
- **Text and annotation pipeline**: segmentation, linguistic layers, and compiled outputs remain central but should be summarized briefly because they continue the LARA/C-LARA tradition.
- **Image generation workflows**: style, recurring elements, and page imagery remain important as part of multimodal content creation.
- **Exercise generation**: cloze, flashcard, and related workflows can reuse curated project artifacts, including picture-dictionary material. The first picture-clue word-scramble exercise is a useful report example because it shows a new community-requested activity being added quickly within the AI-authored platform: as a tentative implementation-process estimate, it required roughly **twelve minutes of AI time** and about **one hour of human AI-expert steering/review time**. This estimate should be presented narrowly: it covers platform implementation and review, not Sophie’s community/end-user consultation or any culturally required permission process.
- **Published content browsing and social-facing interactions**: useful to mention briefly, with continuing enhancement rather than completion implied.

## 3.3 Why picture dictionaries matter

- Picture dictionaries connect vocabulary, imagery, and activities in a way that is easy for learners to understand.
- They allow image-based glossing, where a picture can supplement or sometimes replace text explanation.
- They create a natural path to picture flashcards and other low-text learner activities.
- They may be especially valuable for young learners, beginning learners, and low-resource languages where textual resources are limited.

## 3.4 Low-resource-language emphasis

- Low-resource-language support should be one of the main user-facing themes.
- C-LARA-2 needs to support settings where high-quality TTS, ASR, dictionaries, and model-generated linguistic annotation are unreliable or unavailable.
- This motivates structured editing, human/community correction, mobile access, and direct platform audio recording.

## 3.5 Candidate user-impact examples to include in full draft

- Picture glossing, picture flashcards, and picture-clue word scrambles from a picture dictionary.
- Text-free picture-dictionary image generation: the “Disallow visible text in images” setting now reaches organiser-requested image regeneration, which matters directly for image → word and word → image flashcards.
- AI-based low-resource dictionary diagnostics: the organiser review flow can flag likely cases where a low-resource source word and English/French gloss have been mixed up, while exposing a trace table for human review.
- A low-resource language workflow where human editing compensates for weak AI resources.
- Exercise generation from curated project artifacts.
- Legacy project migration enabling reuse of prior investments.

## 3.6 Rapid AI-centered functionality example

The no-visible-text image constraint and dictionary language-confusion diagnostics are a useful report example because they arose from concrete user testing, were iteratively corrected through human critique, and became user-facing platform behavior quickly. They show the development pattern the report should emphasize: the AI can wire backend logic, templates, caching, tests, and documentation rapidly, while the human expert supplies the real-world error cases, judges whether alerts are useful rather than overconfident, and decides when the result is good enough as an advisory tool.

## 3.7 Validation questions for project members

- Which picture-dictionary examples are most persuasive?
- Which low-resource-language examples should be named explicitly?
- For the picture-clue word-scramble example, what can Sophie and the relevant community/end-users permit us to say publicly, if anything? Australian Aboriginal communities can be highly protective of their languages, so the report may need to keep this example generic or anonymized.
- Are there important user-facing pain points that should be included candidly?
