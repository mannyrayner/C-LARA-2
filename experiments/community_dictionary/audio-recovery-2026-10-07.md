# AWS acceptance and repaired-audio return path

Manny reports testing the deployed app from laptop Chrome on AWS, using typed and
spoken descriptions in both English and Swedish. It worked very well overall.
The only obvious error he reported was a timeout for `i bakgrunden`: he regenerated
its audio from the word page but could not access it on returning to the example.
He plans a fresh-eye test with Cathy on 8 October, subject to availability, before
specifying further workflow changes. This is laptop/Chrome acceptance, not new
physical-phone acceptance or a controlled linguistic-accuracy measurement.

GitHub main was observed at `0659b966efa21cb769a0f0913b4347c98234357b`.
The original AWS exception, navigation path, and replacement save/review state were
not inspected. Current server queries already read accepted, current shared audio
for word rows on both the saved capture and ordinary sentence pages. Private
previews and pending recordings intentionally do not appear there.

Two code-level gaps are confirmed: after jobs have finished, a browser-restored
example does not recheck audio; and the original failed attempt continues to produce
an error notice even after a replacement has been accepted. The patch adds read-only
refresh on persisted pageshow / return from a hidden tab, preserving unchanged
players and open translations. It hides obsolete failure notices using the same
accepted/current recording selection as the displayed rows. Attempts/costs are
not rewritten; refresh never generates or bills new audio. The browser-cache
explanation is plausible for this incident, not independently established.

Verification: 338 app tests passed (four new recovery cases), with mocked providers.
The new accepted-replacement test first failed on the stale error notice, then
passed after the repair. Private previews, pending contributions, withdrawn audio
and outdated synthetic audio do not bypass sharing/review rules. No migration.
Chromium with synthetic data reproduced timeout -> manual preview/save -> repaired
example. A deliberately dispatched persisted-pageshow event tested return refresh;
ordinary Back navigation was also checked. New Listen controls, retained open
translation, unchanged playing audio and duplicated word rows on the sentence page
were checked. This does not establish native Chrome/iOS history-cache coverage.
An initial browser script assumed Create spoken audio was directly on the word page;
correcting it to follow Open original entry and discussion completed the actual flow.

No live provider requests, AWS changes or stakeholder messages were made by the
assistant. Patch acceptance remains pending. The code fix can precede Cathy's trial;
other UX changes and broader MWE work should await more evidence.

[Installation and immediate workaround](../../docs/howto/community-audio-recovery.md).
