# Review acceptance and German AWS trial — 5 October 2026

## Human-reported acceptance

After restoring the accidentally modified laptop `settings.py`, Manny reports that
installation/checks worked and that a small Swedish dictionary could be ported to
German. He then reports that everything works and the new reviewing workflow is
much faster. The configuration failures do not establish 96 distinct review-feature
defects: missing runtime settings/pricing caused the test cascade, and restoring
the repository configuration resolved the reported blocker.

Manny subsequently reports the new release installed on AWS and used to create a
**German/English version of the 61-entry Swedish/English dictionary**. He noticed
one TTS problem, **curry**, but explicitly says his spoken German is weak enough
that other problems may have escaped notice. His general impression of both the
French and German ports is extremely positive.

This supersedes the earlier pending laptop/AWS acceptance of the review increment.
It is a participant report, not an independently instrumented production audit:
no deployed SHA, costs, timing, voice, full listening protocol or new phone/browser
matrix was supplied. Do not turn one noticed issue into a 60/61 accuracy claim.
Italian results, broader learner/community feedback and long-run maintenance
outcomes remain unreported. Human recording and listening review remain important.

## French stakeholder draft

Manny requests a short French update in LaTeX for partners working with Indigenous
languages, highlighting functionality shaped by Sophie's community-informed
suggestions and the speed of responding to feedback. The resulting
[three-page draft](../../docs/publications/community_dictionaries_update_fr/README.md)
describes current workflows and invites discussion; it does not imply that
Kowanyama or Nouméa communities have already trialled or endorsed this version.

Manny estimates roughly five hours of AI thinking/development time over roughly a
week, with his work consisting of installation, testing and feedback. This is an
informal retrospective estimate, not a stopwatch measurement or a model comparison.
The model/mode attribution follows his account; pre-existing C-LARA-2 infrastructure
and human participation are explicit. The draft names fully autonomous maintenance
as an objective, not an achieved property.

The source compiles with pdfLaTeX to three A4 pages and all three rendered pages
were visually reviewed. The documentation patch changes no runtime code and makes
no paid API requests. Existing application test evidence (286 tests) is retained;
no repeat suite was necessary for this documentation-only update. The French draft
has not yet been reviewed by Manny or circulated to partners.
