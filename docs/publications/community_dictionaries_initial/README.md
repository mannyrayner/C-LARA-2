# Community Dictionaries: situated learning and AI autonomy

Version 3 stakeholder discussion paper, 26 September 2026. The self-contained
[LaTeX source](latex/community_dictionaries_initial.tex) compiles to two pages.
It brings together language pedagogy, picture dictionaries, Indigenous communities
and increasing AI autonomy, while distinguishing the working phone prototype from
proposed sentence, personal-history, AI-media and operational capabilities.

The implementation was assistant-written without human coding assistance; Manny
provided direction, installation, deployment and testing, and Cathy tested the
phone workflow. The roughly two-day development/deployment period is a participant
account, not an audited productivity comparison. GPT-6 Astra Extra High is the
model/mode identified by Manny in the development conversation; independent API
model, reasoning-budget and total-cost records are not available in these files.
The report does not claim measured learning gains, broad device compatibility,
completed production hardening or autonomous maintenance.

Build with a standard pdfLaTeX installation:

```bash
cd docs/publications/community_dictionaries_initial/latex
pdflatex -interaction=nonstopmode -halt-on-error community_dictionaries_initial.tex
pdflatex -interaction=nonstopmode -halt-on-error community_dictionaries_initial.tex
```

No separate bibliography, image files or shell escape are required. Generated
PDFs and auxiliary files need not be committed. A compiled PDF accompanies the
circulation copy. Version 2 remains in Git history at `6ad49ee` and version 1 at
`e3b94b0`. This revision updates documentation only.

The reviewed source is `6ad49ee2baa042a03fec573985875bcae34691a9`. Evidence and detail:

- [AWS/phone trial](../../../experiments/community_dictionary/aws-phone-trial-2026-09-25.md)
- [Earlier AI-media and maintenance direction](../../../experiments/community_dictionary/direction-review-2026-09-26.md)
- [Situated-learning discussion and this revision](../../../experiments/community_dictionary/situated-learning-review-2026-09-26.md)
- [Detailed next-stage roadmap](../../roadmap/community-dictionary-ai-and-maintenance.md)

The short report deliberately leaves detailed implementation and acceptance criteria
in the roadmap and how-to documentation. No tester photographs or recordings are included.
