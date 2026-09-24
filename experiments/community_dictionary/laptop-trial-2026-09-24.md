# Laptop confirmation — 24 September 2026

Manny reports that direct recording now works in Community Dictionaries after
installing the iteration 2 repair. He identifies the previous failure as the
browser defaulting to the wrong input device. Selecting the correct microphone
resolved the reported laptop recording blocker.

This follows his successful picture/MP3 uploads and confirmation that words,
translations and categories work. The text changes in iteration 2 improve
visibility; they do not introduce previously missing text storage.

This is human-reported acceptance of direct recording on this laptop. It does
not establish iPhone/Safari or Android/Chrome compatibility, cross-device playback,
or the entire collaborative workflow on physical devices. Those remain the next
functional trial after check-in and HTTPS deployment.

## Code and verification provenance

- Bootstrap commit: `bc21188595bae9f2ee89c080243a76fdd4a960b1`.
- Prototype 1 patch SHA-256:
  `9a25630818a86c80356c075b38d4b7eae4fbf6082defc5420a6e6ff4355ebc77`.
- Repair 2 patch SHA-256:
  `10f833844106b53604356d7f1853cc819496d4340a79e33c8982a710d16bb1d9`.
- The 21 passing Django tests and controlled Chromium checks are recorded in
  [iteration 2](iteration-002.md). They were not rerun for this documentation-only
  follow-up. The earlier iteration record is retained as the pre-trial account.
- GitHub's feature branch was checked after Manny's report and still pointed to
  the bootstrap commit. Following the agreed patch workflow, Manny should commit
  the installed implementation, repair and this confirmation from the tested
  laptop checkout and push the feature branch.

This confirmation is follow-up evidence within iteration 2, not a third software
implementation iteration. No runtime code is changed. The original report is
preserved with derived global-workspace revision 14. No personal recordings,
local databases or credentials belong in the source commit.
