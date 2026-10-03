# Optional AI image generation — first cut

Prepared 3 October 2026 (Manny's Adelaide morning). No AWS installation or live
image-quality acceptance is claimed. Manny requested implementation after the
username-input correction, whose laptop/AWS login he reports successful. Axel's
iPhone username-casing confirmation remains outstanding.

## Request and scope

Add optional image generation with a shared style, following Sophie's request.
Keep camera input central and ordinary members' interface simple. Reuse C-LARA
infrastructure and preserve provenance, contributor withdrawal and private media.
Manny relays Sophie's photograph → understanding → generated illustration idea
explicitly for a later iteration. That workflow, automatic candidate ranking,
picture games and translated dictionary migration are not implemented here.

## Implemented

- Owner opt-in, default off; owner/editor/coordinator generation controls.
- Manually described shared style plus one generated sample, explicitly approved
  before entry pictures. Replacing a style leaves existing pictures unchanged.
- One text-only request per preview through the existing OpenAI image adapter,
  default `gpt-image-2.5-sunburst`, high quality, square output.
- Private preview, explicit save and normal review; no automatic replacement of
  an existing selected photograph. Generated labels and prompt/model provenance.
- Source-style dependencies participate in withdrawal/restoration. Styles are
  contributions on archived entries, hidden from ordinary lexicon browsing but
  visible in own-content/export. Cross-author dependent pictures follow custody.
- Committed receipts, no automatic provider retry, attempt limits, explicit
  outbound consent, actual-usage accounting and unknown-cost failure handling.
- Additive migration 0010; no existing participation/content reset.

## Verification

All **181 Community Dictionaries tests pass**, including 25 new image-generation
tests. The combined app and existing C-LARA style/page-image run has 220 tests:
218 pass and two existing page-image failures remain. Both were separately
reproduced on the unchanged username-input base:

- `test_generate_page_images_can_discourage_text_in_image`: existing prompt no
  longer contains the expected `comic-style sound effects` wording.
- `test_generate_page_images_trims_long_prompts_and_writes_telemetry`: existing
  prompt length 12127 exceeds the test's 12000 bound.

The new tests exercise default/role/cross-dictionary access, CSRF, consent,
style approval, requester-private media, publication/review, preserving an
existing picture, duplicate paid submissions/saves, credit/personal-key paths,
failure/invalid bytes/URL-only rejection, quotas, expiration, export, stale policy
or membership, withdrawal during generation, and style/author dependency holds.
Provider requests are mocked throughout. Django check and migration drift check
pass. No PostgreSQL concurrency/load experiment is claimed.

The reproducible `image_browser_rehearsal.py` uses a disposable SQLite database,
synthetic accounts and an injected local picture response, never a paid call.
Chromium 153 passes the enable → style sample → approval → entry preview → save
workflow at 390px, then checks the saved entry at 1280px. It verifies generated
labels, loaded media, ordinary-member visibility, no horizontal overflow and no
page JavaScript errors. Screenshots were inspected. This is desktop Chromium
with a phone-sized viewport, not physical iPhone/Safari or Android acceptance.
The original cached browser crashed before launch; a fresh extraction of its
bundled runtime with the package's required flags worked.

## Next human trial

Install on the laptop first, enable one trial dictionary, approve one simple
style and generate a few concrete subjects. Verify the selected photograph is
preserved when adding an alternative, then try a subject Sophie has previously
found difficult. Note fidelity, undesired details, style consistency, actual cost
and mobile friction. Test withdrawal in a disposable dictionary because a style
author's withdrawal intentionally affects dependent pictures by other authors.

No live provider result, real illustration quality, exact per-image price,
physical-phone result or autonomous operation has been demonstrated by this
patch. The US$0.50 UI allowance is a planning/minimum-credit value, not a price
guarantee or enforced spending cap. See the [feature guide](../../docs/howto/community-image-generation.md).

## Windows installation follow-up, 3 October

Manny's first backup command entered Django's interactive console under native
Windows Python in Cygwin. The corrected invocation explicitly executes stdin:
`manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())"`. He now reports a
verified SQLite backup and successful patch application. His 181-test run then
failed during temporary-file cleanup with WinError 32 on the audio response in
`test_shared_card_groups_components_with_read_only_own_and_reference_labels`.
The chained migration commands therefore did not execute.

The test checked a streaming response's status without consuming or closing it.
The same pattern occurred in the private-image check in `test_participation.py`.
Both now explicitly close the response even if the status assertion fails. No
application or migration changes are needed. An instrumented Linux run retained
references to response streams: two remained open before the repair; after it,
all 181 tests pass and all 12 captured FileResponse streams are closed. This
verifies handle release without claiming a native Windows rerun. Manny should
apply the small follow-up patch, rerun tests, then continue the forward migration
and live trial. The overall feature acceptance/deployment assessment is unchanged.


## Human laptop acceptance and Settings/photo follow-up

Manny now reports that the feature installs, starts and works in laptop testing.
He requests a Settings tab for dictionary configuration/style and clearer human
photo input after starting an entry with text. Code inspection finds no AI-driven
upload restriction: manual input is behind the generic Add a contribution route,
while word editing intentionally omits media controls. The follow-up adds a
visible Add a photo route beside generation and moves configuration into Settings.
Owner-only setting changes, editor style access, ordinary-member review and
withdrawn/inactive access restrictions are preserved. New photo submissions do
not edit text or replace selected media and retain retry protection.

189 tests pass. The updated Chromium rehearsal verifies camera-input/upload
paths after text-only entries with AI off/on, saved-style configuration, preserved
original pictures, member controls and 320/390/1280px layouts. Eight new tests cover
permissions, invalid settings, policy revocation, legacy settings submissions,
text provenance, retry receipts and CSRF. No paid API call was made for this
follow-up. Manny's report is broad acceptance, not measured quality/cost or a new
physical-phone trial. See [the instructions](../../docs/howto/community-settings-and-photos.md).
