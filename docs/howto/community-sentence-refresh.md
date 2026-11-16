# Refresh words and audio after editing a sentence

Saving an accepted sentence's changed wording or meaning can automatically open a
[bilingual check and review](community-check-improve.md), with the optional AI
checkbox on the editing form. With checking disabled, it offers **Update words
and audio**, with an explicit estimate/processing permission and **Not now**.
Category-only changes do not interrupt the editor. The same action remains beside
**Edit words** on the sentence's page, including older edited entries.

The vocabulary-only processor receives the accepted target-language sentence as
fixed input. It cannot rewrite the sentence or translation. Existing lemma/sense
pages and current audio are reused. Changed relations are rebuilt for this sentence;
unrelated dictionary words and human recordings are retained. Existing corrected
contextual forms remain authoritative. Sentence, word and contextual-form audio
use the same configured provider policy as ordinary picture contributions,
including the Google fallback for Igbo.

Processing uses existing private PictureCapture/CaptureSpeech records with
`input_mode=refresh`; no database or model change is required. Permission, input
revisions, source availability, rates and audio policy are checked before calls
and again before publication. Repeated submissions/workers do not repeat claimed
requests. A concurrent editor cannot start a second update for the same input.
Uncertain requests time out as failed, never as an automatic paid retry. Explicit
audio retries create new claims only for still-missing clips, preserving successful
audio and avoiding a second vocabulary request. Progress polling is GET-only.

The normal laptop-first, human-tested AWS deployment boundary is unchanged.
