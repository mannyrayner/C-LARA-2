# Community Dictionary pronunciation guidance

Prepared 5 October 2026; subsequent laptop acceptance reported by Manny. The small
dictionary test works, including chat and lit. Manny subsequently reports a
61-entry French AWS conversion/review, with four initial pronunciation issues and
two still unresolved after local remedies. See the [AWS trial record](../../experiments/community_dictionary/porting-aws-2026-10-05.md). Human recording remains the primary workflow.

## What changes

- English spelling overlaps are detected locally using a bundled English word
  list, including inflected forms. Matching ignores case but preserves accents;
  whole words within phrases are checked too. English target-language entries
  do not receive this warning. Detection makes no API call.
- A match adds one OpenAI text request for a target-language definition, IPA and
  sound description. The input is the exact word/phrase, target language and its
  available accepted meaning/commenting language. No image or human audio is sent
  by this step. The request uses the existing configured photo/porting model and
  the same personal/server key as speech. Guidance is private, uses `store=False`,
  and is still subject to the provider's retention rules.
- French, German, Swedish and Italian bare words use the exact enriched prompt
  templates from the v3 listening probe, populated with AI-generated hints.
  Phrases retain their supplied articles/words. Other supported languages use
  explicit language instructions with target-language hints.
- Speech uses the existing `gpt-4o-mini-tts` model and chosen named voice.
  A completed WAV with peak below 300 **or** RMS below 100 (16-bit PCM scale)
  is rejected and regenerated once. Two quiet results end the attempt without
  saving audio. There is no amplification, trimming or automatic pronunciation
  grading. Invalid files, timeouts, API errors and interrupted jobs are not retried.
- **Check pronunciation** appears on detected homographs in port results/review,
  entry audio generation/preview and saved synthetic recordings. Existing saved
  audio also acquires the warning without an API call. Warnings are advisory;
  reviewers can accept correct speech, regenerate, or record a human voice.

The English list contains uncommon words as well as common vocabulary, so some
warnings will be overcautious. It is a bounded ASCII English spelling list, not a
claim to recognise every English spelling, name or regional variant. Absence of a
warning does not certify pronunciation. Provenance is retained for guidance,
model, voice, prompt version, costs and speech attempts. The list and license
notices are in `platform_server/community_dictionary/data/`.

## Costs, review and withdrawal

Guidance incurs a text-model charge; the generation page shows its model, configured
rates and rough estimate. Porting estimates include guidance for every prospective
translated entry (the translated spelling is not known yet) and reserve room for
one silence retry. Only detected homographs actually incur a guidance request.
Both completed speech attempts count towards estimated cost, even if neither is
usable. Returned guidance token usage and estimated speech costs are recorded;
unknown provider usage stays explicitly unknown. No duplicate charge occurs when
a form is retried. The provider invoice remains authoritative.

Authority, current wording/meaning, payment route and source availability are
rechecked before guidance, speech and the optional retry. Saved recordings derived
from an accepted meaning depend on that contribution; withdrawing it removes the
associated preview/hints and derived shared recording through the existing custody
system. Editing that meaning makes the earlier guided recording stale. Ordinary
recordings that did not use a meaning continue to survive explanation edits.

The schema change is additive: migration **0013_tts_pronunciation_guidance** adds
private preview metadata. It does not change existing dictionary entries or audio.
Old estimates must be recreated; old queued jobs cannot silently acquire the extra
paid processing. Already generated previews can still be reviewed or discarded.

## Laptop installation (Cygwin with Windows Python)

Finish/cancel any running porting job and stop `runserver`. Save the incremental
patch as `/home/github/community_dictionary_tts_guidance.patch`. Keep any existing
uncommitted work; the patch only applies over the previously delivered porting fixes.

Back up SQLite outside the checkout:

```bash
cd /home/github/c-lara-2/platform_server
../.venv/Scripts/python.exe -E manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import sqlite3
from pathlib import Path
from datetime import datetime
from django.conf import settings
config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.sqlite3', 'Stop: not the laptop SQLite setup'
source = Path(config['NAME']).resolve()
assert source.is_file(), f'Missing database: {source}'
folder = Path.cwd().parent.parent / 'clara2-backups'
folder.mkdir(exist_ok=True)
backup = folder / ('before-tts-guidance-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)]
print('Database backup verified:', backup)
PY
```

Apply and validate, retaining `-E` for the laptop's Python environment:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_tts_guidance.patch &&
git apply --index ../community_dictionary_tts_guidance.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

No new dependency or API key is required. Expected: 275 app tests pass and migration
0013 is checked. Intentional simulated failures may print TimeoutError, SilentAudio
or Conflict warnings; the final test result must be `OK`.

Start with development static-file serving (the laptop keeps `DEBUG=False`):

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

## Try it

1. In the existing small French dictionary, open **chat** or **lit** and choose
   **Create spoken audio**. Check the warning/cost explanation, generate, listen,
   and save a good recording. Compare with a non-homograph such as **fromage**.
2. For the whole dictionary, return to the **source Swedish dictionary → Settings
   → Language versions → existing French version → Estimate an update**. Finish
   or discard old unsaved results first. The new speech recipe revisits earlier
   unedited outputs; it still protects human corrections. Approve the new estimate,
   review the flagged entries, and save good results. An individual protected entry
   can receive fresh audio through its own **Create spoken audio** control.
3. Try a small Italian version and inspect **pane**, **cane**, **sale**, **fine**.
   The warning remains even when the speech sounds correct.
4. Confirm normal non-AI recording still works. A silence retry only occurs when
   a provider response is actually quiet; there is no need to force one manually.

Laptop acceptance is now reported. Follow the [check-in and AWS runbook](community-language-porting-aws.md)
to back up, deploy all pending porting migrations through 0013, collect static files
and restart web/queue workers together. Then test the larger French and Italian
versions with fresh cost approval. The subsequent French AWS trial is now recorded;
the [review-UX follow-up](community-port-review.md) addresses its workflow feedback.

## Evidence

See [the dated experiment record](../../experiments/community_dictionary/tts-guidance-2026-10-05.md).
Automated checks exercise wiring, access, costs, retries and persistence, not whether
new AI-generated pronunciation hints produce correct speech. Manny reports success
on the small laptop dictionary; that does not establish broader accuracy. Official
speech API reference used for the existing model and instruction mechanism: https://developers.openai.com/api/docs/guides/text-to-speech .
