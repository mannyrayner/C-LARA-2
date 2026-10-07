# Picture descriptions: expressions, vocabulary editing and image-only copies

7 October 2026. This **incremental patch goes on top of the picture-description
patch already installed on your laptop**. It works whether that earlier patch is
still staged or already committed. It does not replace the earlier patch. There
are no new dependencies or migrations beyond **0015_picture_descriptions**.

## Apply and verify

Stop the laptop server with Ctrl-C. Save
`community_dictionary_picture_vocabulary.patch` beside the checkout in
`/home/github/`. Keep your existing SQLite backup. This patch itself does not
rewrite database content.

```bash
cd /home/github/c-lara-2
git status --short
git apply --check ../community_dictionary_picture_vocabulary.patch &&
git apply --index ../community_dictionary_picture_vocabulary.patch &&
git diff --cached --check
```

Existing staged first-cut files are expected. If the patch check fails, stop and
send the output; do not reset files, force the patch, or reapply the first cut.
`--index` requires the affected working files to match their staged versions.

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

Expected: **324 tests**, ending `OK`, and `[X] 0015_picture_descriptions`.
The tests deliberately log simulated provider failures; the final result must be OK.
No new `migrate` step is required for this follow-up.

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Reload any page left open from the previous run. Updated stylesheet/script URLs
avoid reusing the previous cached versions.

## Try it

1. As dictionary owner, choose **Settings → Create an image-only copy**. Give it a
   name, confirm permission, and create it. It should contain the images without
   words/audio; the original dictionary should remain unchanged. No AI charge is
   incurred by this copy operation. Only you initially have browsing access.
2. In that copy, use **Describe this picture** for Finley's image and enter
   **Katten sträcker ut sig på soffan**. Prepare a **new** suggestion: previously
   prepared previews are not retrospectively regenerated.
3. Open **Words and expressions — edit, add or remove**. The model is now instructed
   to offer **sträcka ut sig** as one expression. Check other expressions too; the
   prompt change still needs live-model evaluation.
4. Try modifying a word/meaning, ticking **Remove**, and adding a word. For an
   inflected expression, the optional sentence form can be **sträcker ut sig**;
   separated parts can use **sträcker … ut sig**. You can leave that field blank.
5. Choose **Yes — save and share**. Check the retained vocabulary, cross-links and
   audio. Existing identical lemma/sense entries are reused; their text and human
   recordings are not overwritten. You can keep up to 12 vocabulary items.
6. With spoken input, you can edit while spoken confirmation is being prepared;
   its arrival should leave the edits intact. Audio requires listening review as
   before.

Copied images retain their original contributor/custodian and withdrawal links.
Withdrawing source material also withdraws copies and dependent descriptions. Do
not treat the test copy as an independent archival backup.

The first cut did not run MWE identification. This revision reuses the C-LARA MWE
linguistic rules/examples inside the existing interpretation request; it does not
launch the whole annotation pipeline or add an extra MWE API call. Automated tests
and desktop/mobile-width Chromium checks use simulated AI responses. They verify
the workflow, not linguistic accuracy or physical-phone behaviour.

After these laptop checks, we can check in the first cut and this follow-up together
and deploy to AWS. AWS will still need **0015**, `collectstatic`, and restart of the
web and Q workers because the first cut has not yet been deployed there. Keep
DEBUG=False. The new image-only copy utility is intended for this testing phase.

Manny has now reported small-Swedish-dictionary laptop acceptance. Continue with the
[combined check-in/AWS runbook](community-picture-descriptions-aws.md). Further MWE
refinement is deferred until after the larger functionality trial.
