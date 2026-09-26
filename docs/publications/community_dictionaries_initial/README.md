# Community Dictionaries: initial report and next-stage proposal

Version 2 stakeholder discussion draft, 26 September 2026. The self-contained LaTeX source
is [community_dictionaries_initial.tex](latex/community_dictionaries_initial.tex).
The five-page revision describes the working prototype and trial evidence,
optional image generation and TTS as the next proposed increment, data sovereignty,
and a staged experiment in reducing Manny's operational involvement. It distinguishes
implemented behaviour from planned capabilities and links two primary governance
sources. The detailed companion is
[the AI-media and maintenance roadmap](../../roadmap/community-dictionary-ai-and-maintenance.md).

Version 1 remains in Git history at `e3b94b0`; this source replaces the current
circulation draft. No runtime code or deployment permission is changed by revision 2.

Build with a standard pdfLaTeX installation:

```bash
cd docs/publications/community_dictionaries_initial/latex
pdflatex -interaction=nonstopmode -halt-on-error community_dictionaries_initial.tex
pdflatex -interaction=nonstopmode -halt-on-error community_dictionaries_initial.tex
```

No separate bibliography, image files or shell escape are required. Generated
PDFs and auxiliary files need not be committed. A compiled PDF accompanies the
circulation copy.

The reviewed code snapshot is `e3b94b08d0d493e88e6966781323df2753f0bdfa`.
New human evidence is recorded in
[the AWS/phone trial](../../../experiments/community_dictionary/aws-phone-trial-2026-09-25.md).
The new direction and successful Assistant retest are recorded in
[the 26 September direction review](../../../experiments/community_dictionary/direction-review-2026-09-26.md).
Timing claims remain participant estimates. The report does not claim a full
mobile compatibility matrix, demonstrated learning gains or a completed
security review. No tester photographs or recordings are included.
