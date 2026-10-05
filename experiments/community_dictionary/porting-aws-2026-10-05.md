# French AWS conversion and review feedback — 5 October 2026

## Human-reported production result

Manny deployed the porting/TTS update to AWS. Entry pages initially returned 500
errors while the dictionary page remained accessible. He suspects a missed service
stop; he reports that stopping/restarting restored entry access. There was no
traceback establishing the precise cause. The runbook now ends with **restart**,
since **start** does not reload services that are already running. DEBUG remains
false; public debug pages were not needed.

Manny then converted his **61-entry Swedish/English dictionary to French/English**
and reviewed the results. He reports four initially unsatisfactory recordings:

| Word | Reported issue | Follow-up |
| --- | --- | --- |
| curry | Normal English pronunciation | Regeneration did not improve it |
| mug | Normal English pronunciation | Regeneration did not improve it |
| lac | Close, but sounded more English than French | Satisfactory after regeneration |
| bus | Normal English pronunciation | Changed to autobus, then satisfactory |

The other 57 entries attracted no pronunciation complaint in this report. These
are one reviewer's observations of a real dictionary, not a controlled accuracy
benchmark. Two cases remain unresolved under the original wording. Regenerating
one word and choosing a different word for another are distinct interventions.
No exact cost, duration, browser/phone details or broader linguistic audit was
reported. This establishes live AWS conversion/review evidence, not universal TTS
reliability or long-run autonomous operation.

## Requested and prepared review changes

Manny asks to move directly to the next item after saving, display saved words
rather than entry numbers, and flag problems for later attention.

The prepared follow-up implements Save and next, current saved-word labels with
entry links, private flags/optional notes, an attention filter, and Flag for later
and next that preserves edits without publishing. Older job lists remain reachable.
Saved flags also work on existing jobs. Additive migration 0014 stores the review
metadata. The provider prompts, generation model, billing and human-recording
workflow are unchanged.

286 Django tests pass, including 11 new review tests. A real Django/Chromium run
with simulated provider output verifies flag/draft recovery, save/next, saved-word
labels, saved flags, filtering and resolution. Layouts at 390/1280px have no
horizontal overflow; 390px results/review screenshots were visually inspected.
Django checks and migration drift checks pass. No paid API call was made by the
assistant; the UI increment still awaits human laptop acceptance and AWS deployment.

Next: test the review update locally, deploy after acceptance, then continue
reviewing existing French entries and consider Italian. Retain human listening
review; further TTS prompt/provider work is not part of this increment.
