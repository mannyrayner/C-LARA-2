# Immediate restoration — 2 October 2026

## Human feedback and scope

Manny reports that the original-dictionary shortcut is an improvement, but asks
to remove its confirmation step and preserve the approval of previously reviewed
material so that restoring it has an immediate visible effect. This qualifies the
prior shortcut trial; it is not blanket acceptance of the contribution-control
or governance features.

This follow-up applies after the delivered Share back patch (result tree
`75881d1c63fe3def02b7a522a2f1dd89dd6ad2d1`), itself based on main `e4153586`.
It is prepared locally for Manny to apply. No production action was taken.

## Implementation

- Direct CSRF-protected POST buttons on the private entry and collection card;
  there is no confirmation page. Dedicated forms sit outside the bulk-selection
  form, so a card button cannot submit other cards' checked components.
- A signed, account/entry-bound selection captures only current owned components
  present when the page was rendered. Material filters apply on collection cards.
  Custody, entry availability and membership are checked again when committing.
- Same-origin voluntary withdrawal retains prior acceptance for unchanged parts.
  Withdrawal records now include actor, mode and a content fingerprint. Existing
  legacy withdrawals use the recorded status and original withdrawal audit event.
  Contribution contents/media are immutable through the app; private edits create
  new contributions and do not acquire the old approval.
- Later rejected/moderator-returned copies, new private content and unreviewed
  parts remain subject to review. Synthetic audio is published only when it matches
  accepted destination wording/language. Text restoration advances the relevant
  version counter and does not overwrite newer shared wording.
- Original attribution/private copies remain. Existing pending copies from the
  previous patch can retain approval without duplication. Receipt replay does not
  re-run an operation after a later withdrawal. Sharing elsewhere retains review.

No migrations or dependencies were added. Historical picture-word links are not
reconstructed. The earlier `share_back_browser.cjs` records the previous
confirmation-based workflow; use `immediate_restore_browser.cjs` for current checks.

## Controlled evidence

- **148 Django app tests passed**, including 20 focused restoration tests, using
  Python 3.12.14, Django 5.2.17, disposable SQLite and private test media.
- `manage.py check` passes; `makemigrations community_dictionary --check --dry-run`
  reports no changes.
- Chromium 153 rehearsal, iPhone 13 / Pixel 7 viewport presets and desktop width:
  ordinary-member withdrawal, collection-card restore, immediate visibility to
  another account without review, retained private media, repeat withdrawal and
  restore from the private-entry button, no restore dialogues, correct form
  ownership, membership revocation with a stale form, no horizontal overflow and
  no browser JavaScript errors.
- Prior account-input, AWS/device, governance and learning-outcome uncertainties
  remain separate. No real community data, paid provider or production database
  was used. PostgreSQL concurrency and physical Safari/Android were not exercised.

Human acceptance and deployment of this follow-up are pending.

## Subsequent feedback

Manny reports that this revision works, but requests a simpler conceptual model:
withdraw all contributions to leave a dictionary, view retained material read-only,
or restore everything to rejoin. See [the participation follow-up](participation-2026-10-02.md).
The evidence above belongs to the superseded per-entry interface.
