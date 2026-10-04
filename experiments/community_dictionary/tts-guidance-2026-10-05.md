# Homograph-aware TTS follow-up — 5 October 2026

## Human evidence

Manny reports that category translation and the non-blocking king/roi picture
interpretation now work on the laptop. Bare French chat and lit remained unstable,
although adding an article helped. His ElevenLabs trial also produced English
pronunciation of ambiguous French words. These reports do not establish comparative
provider rankings. The Google probe never reached synthesis, owing to credentials.

The uploaded `multilingual-tts-v3-listening-results.json` contains 96 attempts using
`gpt-4o-mini-tts`, Marin, with six prepared words per language and two takes per
condition. Export run: `multilingual-v3-20261004-211734-1b4159`. Counts below are
Manny's ratings, not an independent assistant listening assessment.

| Language | Simple instructions correct / attempted | Enriched guidance correct / attempted |
| --- | ---: | ---: |
| French | 9 / 12 | 11 / 12 |
| German | 12 / 12 | 12 / 12 |
| Swedish | 5 / 12 | 7 / 12 |
| Italian | 11 / 12 | 12 / 12 |
| Total | 37 / 48 | 42 / 48 |

The simple condition includes two technical near-silence rejections. Every reported
pronunciation error and both rejections concern English spelling overlaps; all 32
non-homograph control recordings were rated correct. Swedish red and gift failed
both enriched takes. This deliberately selected, small word set does not establish
production accuracy. Hints in this experiment were prepared in advance.

Manny elects to bound the investigation: human recording remains central, and
language porting is optional. His requested change is AI-generated enrichment for
English homographs, silence detection with regeneration, and a review warning.

## Prepared implementation

The shared Community Dictionary TTS adapter now uses a local English spelling list,
one structured guidance call for matches, the successful four-language prompt
frames, and at most two speech attempts. Only completed quiet speech is retried.
Source text and meaning remain data; speech input is unchanged. The model and named
voice remain as before. Guidance and both speech attempts enter costs; port estimates
and consent cover them. Interrupted calls are not retried. Private previews and
saved provenance track the method. Meaning-derived recordings follow withdrawal.
Old cost estimates/queued jobs require renewed approval for the new processing.

The additive migration is 0013. An approved update revisits unedited older speech
recipes, retaining protected human corrections. Warnings are advisory and are also
computed for older saved synthetic audio. The English spelling list is broad but
not exhaustive; no absent warning is a guarantee.

## Verification performed by the assistant

- 275 Community Dictionary Django tests pass on Python 3.12 / SQLite, including 18
  new guidance/retry/integration tests. Tests cover ordinary-word bypass, all 16
  probe homographs, native instructions, unchanged speech input, guidance usage,
  silence retry/retry exhaustion, no timeout retry, private dependency withdrawal,
  access loss before retry, duplicate requests, costs and port recipe updates.
- Six shared audio unit tests pass; two provider integration tests remain skipped.
- Django system checks and migration drift check pass; the test database applies
  migration 0013 normally. Existing media/entries require no rewrite.
- Real Django start, preview and saved-entry pages rendered with simulated provider
  output show warnings without horizontal overflow at 390px and 1280px. The 390px
  preview was visually inspected. This is not a new physical-phone trial.
- No paid API call was made by the assistant. No provider credentials were read.
  At preparation time, live pronunciation with automatically generated hints,
  Cygwin/Windows application, PostgreSQL deployment and larger French/Italian
  trials remained pending. See the subsequent human report below.

## Subsequent human laptop acceptance

Manny reports successful generation of **chat** and **lit**, followed by a successful
small-dictionary test, and asks to check in and try the larger dictionary on AWS.
These are live human reports, not independently repeated provider tests. They do
not specify an exhaustive case list or establish general pronunciation accuracy.

An intervening unstyled-page report exposed a mistake in the supplied local startup
instructions: `runserver` omitted `--insecure` despite `DEBUG=False`. The corrected
command serves development static files without changing DEBUG. The runbook is
corrected; no stylesheet/application change is required for this issue. AWS uses
nginx and does not use this development flag.

Next: [check in and deploy](../../docs/howto/community-language-porting-aws.md), then
review the larger French version before trying Italian. PostgreSQL deployment,
larger live costs and new phone acceptance remain pending. No AWS action was
performed by the assistant, and no claim is made that TTS accuracy is solved.
