# Community Dictionaries — French stakeholder update

First discussion draft, 5 October 2026, for Sophie and partners working with
Indigenous languages, including possible Kanak-language trials with Nouméa
colleagues. The standalone [LaTeX source](latex/community_dictionaries_update_fr.tex)
compiles to **three A4 pages**. It preserves the earlier
[English discussion paper](../community_dictionaries_initial/README.md) as a
historical document rather than overwriting it.

The first page explicitly states that ChatGPT C-LARA-Instance wrote the entire
text of the note, based on its discussions with Manny Rayner.

## Read and build

Upload `community_dictionaries_update_fr.tex` as the main file in an Overleaf
project and choose **pdfLaTeX** (TeX Live 2023 or newer). No pictures, bibliography,
external files, API calls or shell escape are needed. A compiled PDF accompanies
the downloadable source. With a local TeX installation:

```bash
cd docs/publications/community_dictionaries_update_fr/latex
pdflatex -interaction=nonstopmode -halt-on-error community_dictionaries_update_fr.tex
pdflatex -interaction=nonstopmode -halt-on-error community_dictionaries_update_fr.tex
```

The source uses Babel's French locale, Latin Modern, microtype, geometry, xcolor,
enumitem, fancyhdr and hyperref. Generated PDF/auxiliary files need not be committed.

## Scope and evidence

The note prioritises photographs and human recordings, collaboration, picture/word
links, games, reversible withdrawal, optional AI media, and practical adaptation
from community feedback. The existing “word scramble” is a word-search game;
the French text therefore correctly calls it **mots mêlés**, not anagrams.
Image-style reuse is described as a shared description, not guaranteed visual
identity. Photo-to-generated-image transformation and automatic community-language
lookup are not claimed implemented.

The model/mode name is Manny's identification in the development conversation.
Approximately five hours of AI work over approximately one week is his retrospective
estimate, not metered inference time, total human effort or a controlled comparison
with Sol. The note acknowledges inherited C-LARA-2 infrastructure and human
installation/testing/feedback. It does not claim autonomous operations, measured
learning gains, community endorsement or Indigenous-language AI validation.

The latest production evidence is Manny's successful German/English version of
his 61-entry Swedish/English AWS dictionary. He reports only noticing a problem
with “curry” but explicitly qualifies his German listening ability. This is not
a pronunciation accuracy benchmark. See:

- [French trial and prepared review update](../../../experiments/community_dictionary/porting-aws-2026-10-05.md)
- [Review acceptance and German trial](../../../experiments/community_dictionary/german-port-review-2026-10-05.md)
- [Practice](../../howto/community-practice.md) and [multiple choice](../../howto/community-practice-choices.md)
- [Image generation](../../howto/community-image-generation.md)
- [Withdrawal and restoration](../../howto/community-participation.md)

The draft is for Manny's and partners' review. Nothing has been sent to stakeholders.
This patch changes documentation only: no database migration, app test rerun,
service restart or paid generation is needed merely to install it.
