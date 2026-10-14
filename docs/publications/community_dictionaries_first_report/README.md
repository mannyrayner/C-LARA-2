# Community Dictionaries: first public report

Prepared and revised 13 October 2026. Manny reports publication on **AiraXiv on
13 October** and **ResearchGate on 14 October**, followed by a human-written
Goodreads review inviting users and potential study partners.

- [AiraXiv: 2610.0032](https://airaxiv.com/papers/view/2610.0032/)
- [ResearchGate](https://www.researchgate.net/publication/415734280_Community_Dictionaries_Everyday_Pictures_Rapid_Human-AI_Development)

These publication URLs were supplied by Manny. Direct web retrieval was unavailable
during the repository update; publication status is human-reported. No Goodreads
URL or participant outcomes have yet been supplied. The paper is an initial
application report; the automated review is not empirical validation of the app.

Authors: ChatGPT C-LARA-Instance and Manny Rayner. Acknowledgements name Cathy
Chua, Sophie Rendina and Branislav Bédi, and close with Finley. Earlier stakeholder notes are preserved.

The report is five A4 pages, about 2,000 words including captions and page furniture,
with two French screenshots and four full references. It presents an evolving app and an invitation to participate,
not a completed system, controlled productivity comparison or learning-outcome study.
The entire text was written and revised by the AI from the discussion and project evidence.

## Overleaf / local build

Upload the contents of `latex/` to Overleaf and select
`community_dictionaries_first_report.tex` as the main document. Use **pdfLaTeX**.
The downloadable Overleaf ZIP already places this file and `figures/` at its root.
No external bibliography, special font, shell escape or API call is required.

The original AiraXiv source remains `latex/community_dictionaries_first_report.tex`.
The ResearchGate copy is `latex/community_dictionaries_first_report_researchgate.tex`;
its only textual change acknowledges the AiraXiv publication and adds its URL in
§6. It shares the same `figures/` directory and also compiles with pdfLaTeX.

```bash
cd docs/publications/community_dictionaries_first_report/latex
latexmk -pdf -interaction=nonstopmode -halt-on-error community_dictionaries_first_report.tex
```

Two ordinary `pdflatex` runs also work. Compiled PDFs and intermediate LaTeX files
do not need to be committed. The delivered PDF has been rendered and all five pages
visually inspected. Installing this documentation does not need a migration, test
suite, collectstatic or server restart. The accompanying About-page link update
does need the web service reloaded after deployment; see the
[publication update runbook](../../howto/community-publications-install.md).

## Evidence and editorial choices

- Baseline `176df90`, the automatic-workflow release. On 13 October Manny reports
  that everything works and is installed on AWS. This is operator-reported
  acceptance, not an independent production audit.
- The prior release's 654-test suite used mocked AI calls. The draft does not treat
  this as provider-quality testing or proof of unattended maintenance.
- About 150 illustrated sentences and six public languages were verified in the
  public directory while capturing figures on 13 October. Counts differ between
  versions, so no exact summed dataset size is asserted. Draft 5 reports Manny's
  informal impression of over 95% correctness from non-exhaustive browsing;
  this is explicitly not an independently measured accuracy rate.
- The two-and-a-half-week period is Manny's approximate account. An earlier
  five-hour estimate is not reused as a total for the expanded app, and no timed
  comparison with another model is claimed. The model/mode designation comes from
  Manny's description of the development conversation.
- Practice games use existing content and make no paid AI calls. The inherited
  `word scramble` is a word-search puzzle, not an anagram activity.
- Free manual use is described under the present hosted arrangement. Optional AI
  processing costs money. Manny has confirmed funds for US$10 / up to US$50
  trial support for up to ten groups; this bounded offer is included in the report.
  Revision 6 specifies that support beyond the initial US$10 is conditional on
  allowing the team to inspect the initial dictionaries produced.
  No credits have been issued and no groups enrolled through this revision.
- Draft 5 adds Manny's rough US$15–20 estimate per trial dictionary of about
  150 existing images and 250–400 word entries, for AI language content and audio.
  This is a user-reported guide to cost, not a fresh ledger reconciliation,
  provider invoice audit, fixed tariff or estimate for generating the images.
- Ordinary use is separate from research participation. The proposed pilot would
  agree data use and credit in advance, distinguish public examples from private
  contributions, and distinguish publication/reuse from approved provider processing.
- Community authority is referenced to the primary
  [CARE Principles page](https://www.gida-global.org/careprinciples), checked on
  13 October. The paper claims neither Indigenous-community endorsement nor that
  app permissions alone establish data sovereignty.

## Figures

Screenshots were captured anonymously from the deployed public site on 13 October,
using the browser viewport. LaTeX crops surrounding navigation and blank margins;
the application content is unchanged. These are desktop screenshots, not a new
physical-phone test. The photographs are credited to Cathy Chua in the captions.

- `latex/figures/sentence.jpg`:
  <https://c-lara-2.c-lara.org/community-dictionaries/browse/13/entries/1977/>
- `latex/figures/word-contexts.jpg`:
  <https://c-lara-2.c-lara.org/community-dictionaries/browse/13/words/1986/>

The images are included for the requested paper; this does not assert a general
reuse licence over other users' dictionary media.

## Revision 2 (13 October)

Manny judged the first draft close to posting and requested clearer ancestry,
the development-speed experiment, the choice of AiraXiv, surname usage for Chua,
and French examples. The revised PDF remains four pages. It now:

- traces C-LARA → C-LARA-2 → Community Dictionaries, citing the two requested
  papers and retaining the repository link;
- attributes simplicity/mobile requirements to Rendina and Bédi, and particular
  Indigenous-community requirements to Rendina;
- records Manny's ChatGPT-5/Codex → ChatGPT-6 Astra Extra High account and the
  observation of generally sub-hour installable patches, separately from later
  installation/testing/fixes and from a controlled model comparison;
- describes a fresh user-facing application while retaining the documented
  reuse of C-LARA-2 infrastructure;
- links the intended AiraXiv posting to the short feedback cycle, citing Pan et al.
  (2026), whose report documents rapid AI review in a specific conference trial;
- replaces the two Swedish captures with the corresponding French sentence and
  shared `fauteuil` word page; no public dictionary was edited.

The model/media account is the participant's reported motivation, not an
independent benchmark or survey of media coverage. AiraXiv is the intended venue;
the draft does not assert that this paper has already been posted. The previous
Swedish screenshots are preserved in the first delivered version. The new complete
patch supersedes the earlier unapplied paper patch; it is not an incremental patch
for an installation where draft 1 has already been applied.

## Revision 3 (13 October)

Manny again judged the paper close to posting and supplied five further changes.
The revised PDF has five pages, with acknowledgements and references together on
the last page. It now:

- makes clear that Swedish was the original dictionary and the other five
  languages were created using subsequently added automatic conversion;
- specifies that conversion combines source text with the image and generates
  new TTS audio;
- identifies the French figures as converted material and explicitly discusses
  `fauteuil` / `armchair`: Rayner rejects the English label for that object but
  tentatively accepts the French, illustrating the difference between a usual
  translation pair and fitness to a particular image;
- plans a rapid sequence of reports, with an empirical second paper hoped for;
- removes named communities and cites the requested 2025 collaborative-development
  extended abstract, verified on ResearchGate; neither author claims to represent
  the communities concerned;
- ends the acknowledgements by thanking Finley.

The furniture judgement is attributed to Rayner, with uncertainty about the
French preserved. It is not a new accuracy measurement or proof of where in the
pipeline a questionable label originated. No dictionary contents were changed.
The complete documentation patch supersedes earlier **unapplied** paper patches.

## Revision 4 (13 October)

Manny requested six further refinements. The five-page fourth draft:

- introduces the screenshots neutrally, reserving the furniture discussion for §4;
- identifies Astra's greatly improved implementation and revision capabilities as
  the most important factor in the pace, explicitly as the authors' assessment;
- replaces the tentative furniture judgement with a sourced distinction:
  the Académie defines `fauteuil` as having arms, while French commercial usage
  also includes `fauteuil de bureau` for armless padded chairs. Given Manny's
  description of the object, the AI recommends `chaise de bureau` / `office chair`.
  This does not assert that the French term is categorically impossible;
- removes the representation disclaimer and uses “our initial trials” in the
  community-suitability qualification;
- specifies funded pilot support for up to ten groups, replacing the uncertainty
  about available project funds;
- expands all four references with complete author lists and fuller publication
  information, checked against the cited copies and ACL Anthology.

Furniture sources checked on 13 October:
[Académie française, ninth edition](https://www.dictionnaire-academie.fr/article/A9F0338)
and [Concept Bureau's KIVO description](https://www.concept-bureau.fr/fauteuil-et-chaise-de-bureau/25646-chaise-de-bureau-sans-accoudoirs-design-kivo.html).
Both are linked in the paper. The screenshots and public dictionary remain unchanged.
The PDF compiles without warnings and all five pages have been visually checked.
The complete documentation patch supersedes earlier **unapplied** paper patches.

## Revision 5 (13 October)

Manny again judges the paper nearly ready and requests five small changes:

- identify Chua on first mention as the human author's partner;
- include his approximate dictionary size and cost observations beside the pilot
  invitation in §6;
- emphasise easy withdrawal into private storage and restoration as important
  functionality for shared-content projects. The wording preserves the actual
  withdrawal confirmation step and describes one-click restoration;
- replace the failure-led summary with his positive, informal correctness estimate,
  introducing the furniture example as a remaining subtlety;
- move the AiraXiv and publication-sequence paragraph into §6, with references
  reordered to follow first citation.

The PDF remains five pages, compiles without warnings, and has been visually
checked throughout. No live content, application behaviour, financial records or
publication status changed. The complete patch supersedes earlier **unapplied**
paper patches.

## Revision 6 / submission candidate (13 October)

Manny suggests three final refinements and asks whether the report is ready for
AiraXiv. The revised version:

- uses his invitation-first abstract, distinguishing the AI's implementation,
  one human's strategic direction and another human's initial content;
- describes the screenshots as parts of a French dictionary;
- offers an initial US$10 to each of up to ten groups, with support up to US$50
  total conditional on permission to inspect their initial dictionaries. The
  following confidentiality and separate study-consent provisions are retained;
- replaces discussion-draft labels with a clean date and “Initial report” header
  for submission. It remains five pages, compiled and visually checked.

The AI recommends submission as an initial application report. AiraXiv's public
pages on 13 October list an AI-generated track and an Application category; the
detailed submission form requires sign-in. No upload or submission was attempted.
The complete documentation patch replaces earlier **unapplied** paper patches.

## Revision 7 / access clarification (13 October)

Manny points out that ordinary use does not require contacting the project.
The report now explicitly distinguishes anonymous browsing, self-service
registration (Log in → Create an account), and optional AI use with a personal
OpenAI API key entered under Profile. The contact invitation is specifically
for discussing free pilot credit. The route is based on Manny's current report
and the repository's profile controls; no account or credential was created
or tested during this revision.

The five-page PDF has been rebuilt and visually checked. This is an editorial
clarification of existing access, with no change to the app, credit offer or
submission status. The project-management assessment remains unchanged.
The complete documentation patch replaces earlier **unapplied** paper patches.

## Publication and outreach (14 October)

Manny has posted the first report on both services and his own Goodreads review.
The next research dependency is independent participants or collaborators willing
to carry out a real experiment. No study has been completed or participant cohort
recruited through this update. The first paper remains unchanged in response to
the AiraXiv review; possible empirical questions belong to a subsequent study.

About now lists the paper title, authors and both publication links. The existing
public-page test has been updated to check those links instead of a placeholder.
No dictionary data, AI workflow, privacy setting or credit balance changes.

## Next step

Install the About-page links and publication records, then use feedback from
outreach to agree a manageable first empirical study. The ten-group credit budget and inspection
condition are confirmed; study procedures still need agreement with participants.
The document deliberately leaves the more elaborate cleanup workflow for later,
when a real reviewer is available to help design it. A later empirical report
depends on recruitment and consent; no collection schedule or number of enrolled
participants has been promised. Credit will reflect contribution and participants' preferences.
