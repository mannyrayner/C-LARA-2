# Community Dictionaries: initial report

Stakeholder discussion draft, 26 September 2026. The self-contained LaTeX source
is [community_dictionaries_initial.tex](latex/community_dictionaries_initial.tex).
It describes implemented behaviour, AI-led development, the confirmed AWS and
phone trial, remaining deployment work and the proposed Icelandic pilot.

Build with a standard pdfLaTeX installation:

```bash
cd docs/publications/community_dictionaries_initial/latex
pdflatex -interaction=nonstopmode -halt-on-error community_dictionaries_initial.tex
pdflatex -interaction=nonstopmode -halt-on-error community_dictionaries_initial.tex
```

No separate bibliography, image files or shell escape are required. Generated
PDFs and auxiliary files need not be committed. A compiled PDF accompanies the
circulation copy.

The reviewed code snapshot is `a7e88702dff965ff1cacac7fd2a8a366f49291c4`.
New human evidence is recorded in
[the AWS/phone trial](../../../experiments/community_dictionary/aws-phone-trial-2026-09-25.md).
Timing claims remain participant estimates. The report does not claim a full
mobile compatibility matrix, demonstrated learning gains or a completed
security review. No tester photographs or recordings are included.
