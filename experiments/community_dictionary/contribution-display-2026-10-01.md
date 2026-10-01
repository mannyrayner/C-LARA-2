# Entry context in My contributions — 1 October 2026

Manny reports that the contribution-control revision installs, the server restarts
without issues and a new entry can be added. He reports that My contributions
shows the material but fails to make its entry associations clear. He requests
whole-entry presentation with other people's components greyed/marked for reference.
This is basic human installation/use evidence, not complete withdrawal/governance
acceptance or a specifically identified AWS/physical-phone test.

The follow-up groups by entry, shows each visible component with its contributor,
limits selection to the user's matching material, and retains owned revisions in
entry-level disclosure panels. Linked-word listening/translation remains usable.
Private entries may show live shared-entry context only while authorized; it is
not copied and cannot be selected for sharing. No schema or data migration changes.

Validation on Python 3.12 / Django 5.2 with disposable SQLite:

- **128 passing app tests** (118 existing plus ten display/access checks).
- New coverage: both contributors' views; inactive and archived-entry restrictions;
  withdrawal/rejected/private exclusion; live private source context; material
  filters; entry pagination; earlier text/TTS history; pending-only entries; and
  linked-word access. Forged selection of reference material is refused.
- No model changes detected by `makemigrations --check --dry-run`.
- `contribution_display_browser.cjs` through `browser_rehearsal.py`: two accounts,
  synthetic image/audio, current attribution and reference playback, matching-only
  selection, actual image withdrawal, live private context and access revocation.
  Chromium 153 passes at a 390-pixel phone viewport and 1360-pixel desktop width,
  without JavaScript errors or horizontal overflow. Screenshots of shared/private
  cards were visually inspected. These are not physical Safari/Android results.

No real user data, AWS or paid provider calls were used. Logged provider failures
in the test suite are deliberate mocked failures. At the time of the automated rehearsal, human acceptance was still pending.
Install instructions are in
[the follow-up runbook](../../docs/howto/community-contributions-by-entry.md).

## Subsequent human acceptance

Later on 1 October, Manny reports that he has tested the new My contributions
functionality and that it works as intended. He requests check-in. This confirms
human acceptance of the entry-context display on his laptop. It does not identify
individual governance/withdrawal test cases or establish deployment of these new
revisions to AWS. The previously recorded 128 app tests and browser rehearsal
remain the automated evidence; this acceptance update changes documentation only.

GitHub main is still `ffbbef9d24873cd930cb866d979e1bd3a735e41b` at the pre-check-in
read. The contribution-control and entry-display patches are to be committed
together with this evidence update. Their combined diff passes the whitespace
check. No remote commit or AWS deployment has been performed by the assistant.
Axel's login-input investigation remains separate, awaiting device/browser details;
no account-form changes are included in this revision.
