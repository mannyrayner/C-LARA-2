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
	
## Main steps in roadmap (so far, only initial steps filled in)

### 1. Set up GitHub repository and add initial documentation.

We have done this. The C-LARA-2 repo is at https://github.com/mannyrayner/C-LARA-2.

### 2. Write spec for initial core functionality, and implement it

The most complex part of the platform is the text creation and annotation pipeline. This consists of a sequence of operations. In each operation, the current representation of the text is processed, using calls to the AI, to add more annotations. In this step of the roadmap, we will only implement enough functionality to perform the first two operations in the pipeline. Specifically, we will implement initial versions of the following:

- Spec for representation of annotated text object.
- Basic utilities for manipulation of annotated text objects, initially reading and writing.
- Function that wraps API calls to the AI. This should provide a heartbeat mechanism since we will in general be making multiple concurrent API calls and wish to keep the user informed of their progress.
- Function that generates a piece of text from a user-supplied spec. (Interactive creation of texts will be in a later step).
- Function that converts a piece of text into an annotated text object that contains segmentation information. The text will be divided into pages, each page will be divided into segments, and each segment into tokens. 
- The function that converts plain text into a segmented text object is divided into two parts:
	- Segmentation part 1. This converts a plain text string into an annotated text object which is divided hierarchically into pages and segments. Segments are however not further divided.
	- Segmentation part 2. This takes the output of segmentation part 1 and in parallel replaces each segment representation with a further annotated version which also includes a list of tokens. This operation is performed using a generic processing function which will be used for all the other linguistic annotation operations as well.
	- The generic linguistic annotation function works schematically as follows:
		- Recursively descend through the text object to reach all the segment representation.
		- For each segment representation, construct a suitable annotation prompt. Input to this prompt construction function includes the segment representation itself, a prompt template, and a list of few-shot examples. The prompt template and the few-shot examples are specific to the operation and source language.
		- In parallel, pass each annotation prompt the AI (fan-out)
		- Gather the results and substitute them into the input text object to create the output text object (fan-in)-
- Unit tests for all of the above.

### 3. Write spec for full linguistic annotation pipeline, and implement it

In this step of the roadmap, we will build on the preceding step to add support for all the other functionality needed to implement the complete pipeline, from plain text to HTML form. Specifically, we need the following:
- Support for other linguistic annotation operations. As noted above, the Segmentation part 2 operation is implemented using a generic function. We will extend it to cover the other operations by creating suitable prompt templates and few-shot examples.
- Support for adding audio. This will involve integration of TTS engines. The recipes in C-LARA can probably be adapted easily, though we want to clean and rationalise it.
- Support for conversion of the final annotated linguistic form into compiled form (HTML). Again, the recipe in C-LARA can probably be adapted easily.
	- We want to include some version of the C-LARA JavaScript which ensures that hovering over one component of an MWE highlights the whole MWE.
- Unit tests for all of the above.

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
