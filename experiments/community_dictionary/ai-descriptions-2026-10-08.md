# Three description modes — 8 October 2026

## Human evidence and scope

Manny reports that dictionary visibility works (environment unspecified). Cathy
prefers AI-generated descriptions to composing them herself. Manny requests equal
Type/Speak/AI options with a remembered preference and uniform processing. He
explicitly puts WordPress access/email-password-reset work on hold. No email
configuration or incoming-agent mailbox is implemented in this increment.

GitHub main was observed at `6a9de727f00476b80a3062a807c54e6131da12f0`,
“Add reversible dictionary visibility controls”. The patch is based on the accepted
visibility release. No AWS checkout, real user data or paid provider call was used.

## Implementation

- Accepted-image entry and capture form offer Type, Speak, Suggest a description.
  The older competing photo control remains only where capture is unavailable.
- AI mode uses the existing image/description adapter with a grounded beginner
  sentence prompt, existing structured schema and language-specific MWE guidance.
- Common preview/edit/confirm/publication, audio, source dependencies and provenance;
  mode `ai` records that no human input description was supplied.
- User/dictionary-specific mode memory; revising an AI proposal prefills Type in
  the chosen feedback language without replacing the normal starting preference.
- Checked-radio-only local draft snapshots; unused recording/text excluded on
  submission and server validation. Existing permission, balance, allowance and
  receipt checks apply. Mode selection/GET never calls a provider.
- CSS and script cache versions updated; no model, migration or dependency change.

## Verification

Python 3.12, Django 5.2.17, SQLite:

- `manage.py test community_dictionary`: **365 tests, OK**, 89.742 seconds.
- Nine focused tests cover AI confirmation/publication/audio/provenance, unused
  inputs, legacy fallback, preferences/correction language, edited vocabulary,
  unclear images/failure, consent/allowance/access/CSRF, and actual adapter payload.
- `manage.py check`: no issues. `makemigrations community_dictionary --check
  --dry-run`: no changes. JavaScript syntax and patch whitespace checks pass.
- Chromium on Linux at 390/1280px: three entry options; AI preview and correction;
  save and next-picture default; text draft reload; voice-to-AI excludes old inputs;
  separate user preferences; no JavaScript errors or horizontal overflow.
  Providers were mocked; synthetic pictures/recordings and isolated database used.
  The rehearsal caught and corrected a radio CSS specificity problem before release.

These are software checks, not a measured improvement in description/MWE accuracy,
real TTS quality, Windows behaviour or physical-phone acceptance. Laptop/phone
experimentation by Manny and Cathy is the next evidence needed. The recorded
visibility success supersedes earlier pending acceptance, without asserting an
unreported deployment or a completed systematic user trial.

See [workflow](../../docs/howto/community-ai-descriptions.md) and
[installation](../../docs/howto/community-ai-descriptions-install.md).
