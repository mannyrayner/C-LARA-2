# Dictionary-wide participation — 2 October 2026

## Human evidence and agreed change

Manny reports that the one-click per-entry return works, but considers the overall
contribution-control model too complicated. He proposes a dictionary-wide departure
and return model, with read-only retained material and no browsing/contribution
while withdrawn. He accepts withdrawal confirmation, owner handover (or archiving
if no successor exists), and restoration without recovering former ownership.

Manny explicitly authorises restoring the laptop's experimental private content
as the initial migration baseline. He reports that AWS has no withdrawals; that
assumption remains to be checked on AWS before migration. He requests a new version
for careful laptop testing before server deployment and reiterates that withdrawal
for personal reasons is a critical anticipated community use case.

This patch follows the delivered immediate-restore tree
`c02e269907298a8869adb9d72a2ddb966f91f7b0` (main base `e4153586` plus local follow-ups).
No new remote commit or production deployment is claimed.

## Implemented model

- Participation belongs to a person and shared dictionary. Voluntary withdrawal
  is separate from membership suspension. Prominent dictionary/home controls show
  the current state; withdrawn readers see only their own saved contributions.
- Withdrawal is confirmed once and returns all owned contribution records to
  private custody, including histories and shared dependents. A per-source hold
  prevents overlapping withdrawals from releasing one another's material.
- Restoration moves records back, preserving IDs and provenance rather than making
  more copies. Unchanged previous approval is retained, newer text stays current,
  and moderated material needs review. Archived entries remain archived. Request
  relationships and picture-word links return where still applicable; later
  explicit request-state decisions are respected.
- Personal collections are not independently browseable/editable dictionaries.
  Former component-selection/sharing endpoints refuse changes. Normal browser,
  media, export, AI and contribution routes enforce participation on the server.
  Editors cannot attribute new content to someone who has withdrawn.
- Ownership transfer and withdrawal are one transaction. A restored former owner
  is a member. With no active successor, the owner can archive/restore the dictionary.
  If departures leave only one coordinator under two-person governance, the current
  owner may appoint a second active coordinator as an audited recovery action;
  other protected changes still need two people. The policy is not silently disabled.
- Migration 0008 adds state/hold records; 0009 returns the explicitly authorised
  experimental private material. Duplicate copies become historical records,
  retaining attribution and ancestry. Newer shared text remains current. A read-only
  preflight supports `--expect-empty` before first AWS migration. No safe data reverse
  is claimed; use the pre-upgrade database and matching code/media backup.

## Controlled checks

- **156 app tests passed**, Python 3.12.14 / Django 5.2.17 / SQLite, including
  25 participation cases and five old-schema migration fixtures.
- Existing provenance, workflow, recording, TTS/photo, lexicon, review and governance
  regressions remain covered. Obsolete tests expecting component selectors and
  per-entry sharing were replaced or adapted to the newly agreed behaviour.
- Chromium 153 with phone viewport presets and desktop width exercised confirmation
  and cancellation, read-only contribution/context views, complete withdrawal,
  private viewing without foreign context, blocked old entry/new-entry URLs,
  home-page restoration without a dialog, approval visible from another account,
  repeated cycles without new copies, and ownership handover without later reversal.
- Screenshots were inspected. Dictionary cards now use the full mobile width so
  Restore remains legible. No horizontal overflow or browser JavaScript errors.
- Django check and migration-drift checks pass. Global-state rendering/archive and
  patch application are checked before delivery.

All browser/database/media fixtures are disposable. No community data, paid API,
AWS deployment, physical phone or PostgreSQL concurrency test was used. Careful
human acceptance is still required, especially for the conceptual model and UX.
The older share-back/immediate-restore browser scripts describe superseded revisions;
use `participation_browser.cjs` with `browser_rehearsal.py` for the current workflow.

## Subsequent human acceptance and server plan

On 2 October Manny reports that the revision appears fully working and is much
better than the previous model. He considers the conceptual structure essentially
ready, subject to possible cosmetic suggestions from Sophie, and proposes AWS
deployment to test with a substantial dictionary. He confirms that the server has
not been updated to the recent versions while the model was being reconsidered.
This is broad human-reported laptop acceptance, not evidence that every checklist
item or device was exercised.

The [deployment sequence](../../docs/howto/community-participation-aws.md) therefore
handles an older server schema: back up the database/media with writers stopped,
update the reviewed code, migrate forward to 0008, audit private content, and only
then allow the one-time reset in 0009. Unexpected private content blocks that step.
No new runtime code is included in this documentation follow-up, and no AWS result
is claimed yet.

Manny subsequently adds that he tested ownership handover on the laptop and it
appeared to work correctly. This supplies specific human acceptance for that
workflow as well; server migration and larger-dictionary/phone checks remain open.
