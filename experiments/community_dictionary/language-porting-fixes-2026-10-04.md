# Language-porting first laptop feedback and follow-up — 4 October 2026

## Human evidence

Manny reports that the small Swedish/English dictionary ports to French/English and
nearly everything works. Three failures: category `djur` remains Swedish; French
`chat` is spoken as English; an intentionally humorous picture illustrating
`kung`/`king` causes a blocking image-mismatch result. This is partial laptop
acceptance of the first porting increment, not AWS or phone acceptance.

## Response

- Category-language inference uses up to five examples within existing entry calls.
  A per-run shared decision avoids divergent categories under concurrency; valid
  decisions persist across updates. Ambiguity keeps the original label editable.
- TTS already had a language hint. The shared engine now gives stronger native-
  language instructions and explicitly addresses ambiguous spellings. Porting
  tracks the instruction version and can replace earlier generated speech.
- Words/explanations determine intent; pictures disambiguate without vetoing jokes
  or metaphors. Unclear/unsupported results allow tentative suggestions or manual
  entry, including first-release blocked previews. Speech for an edited or uncertain
  word can be generated from the saved entry.
- Additive migration 0012 stores category context/decisions. Examples and shared
  decisions have source dependencies: changed/withdrawn inputs invalidate previews;
  withdrawn inputs hide saved derivatives under the existing participation model.
- Version-aware update estimates offer first-release unedited entries again; human
  corrections remain protected. Old previews are never mislabeled as newly generated.

## Verification and limits

257 app tests pass (42 porting); six shared audio unit tests pass. Tests inspect the
French request through streaming and non-streaming SDK branches and verify that
language instructions are not silently dropped. Category tests cover both language
roles, consistency, changed context, withdrawal/restoration and manual review.

The updated Chromium rehearsal at 320/390px passes through two actual Django-Q2
1.11.1 worker processes with two overlapping simulated calls, eight entries,
image/audio previews, uncertain-result save and incremental skip. No browser errors.
No paid provider request was made by the assistant. Translation/category accuracy
and the pronunciation of French `chat` require Manny's new listening/review test.
AWS PostgreSQL migration and physical-phone acceptance of porting remain pending.
