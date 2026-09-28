# Learn from a photo: first phone trial

Implemented in the 28 September 2026 patch against main
`b7cb356e0a548b730c159bdf48a9bcb7dd31ced8`. Later on 28 September, Manny reported a
successful live laptop trial: a horse image produced **en häst**, good device-voice
playback, and saved wording after editing. See the
[trial and follow-up proposals](../../experiments/community_dictionary/photo-laptop-trial-2026-09-28.md).
AWS deployment and physical-phone acceptance of this addition remain unreported. The previously deployed
human-photo/recording workflow remains available with AI disabled.

## Follow-up: use an existing entry and keep generated audio

The [entry-photo/audio follow-up](community-entry-photo-audio.md) adds **Learn from
this photo** on any saved entry with a picture, and separately enabled generation,
preview and saving of synthetic recordings from accepted wording. Returning to an
older image is supported without another upload. Install migration 0003 before
using these additions. Local dictionary lookup remains deferred until discussion
with Sophie. Manny subsequently reports this increment is working. The later
[defaults and named-voice follow-up](community-voices-and-defaults.md) enables both
AI options on new-dictionary forms, adds a remembered voice menu and migration
0004. Existing settings remain as chosen. The original capture-first path below
remains available.

## Enable and try

Startup correction, later 28 September: apply `community_dictionary_photo_import_fix.patch`
after the original photo patch. The adapter now uses C-LARA's protected, lazy SDK
loader so `src/httpx.py` cannot shadow the installed HTTPX dependency on a cold start.
The corrected suite has 41 passing tests with OpenAI SDK 2.8.1 and 3.19.2 on Linux.
See [the repair record](../../experiments/community_dictionary/photo-import-fix-2026-09-28.md).

For Windows Python under Cygwin, activation may fail because of CRLF line endings.
From the repository root, use `./.venv/Scripts/python.exe` directly; from
`platform_server`, use `../.venv/Scripts/python.exe`. Activation is not required.
If pip reports dependencies under the global Python installation, inspect
`.venv/pyvenv.cfg` and compare `./.venv/Scripts/python.exe -m pip --version` with
`./.venv/Scripts/python.exe -E -m pip --version` before further package changes.
`sys.prefix != sys.base_prefix` confirms venv identity but not complete package isolation.
The source import fix and this environment diagnosis are separate issues.

1. As dictionary owner, open **People → Dictionary settings** and enable
   **Learn from a photo (OpenAI)**. Set the target language and explanation language
   (English is used if the latter is blank). Enable only where the community agrees
   to external processing and the model supports the language.
2. Return to Browse and choose **Learn from a photo**. Photograph one intended
   subject. Other objects in the background are fine.
   After enabling the checkbox, press **Save settings**. Ordinary entry uploads do
   not invoke analysis; use the entry’s **Learn from this photo** action for a picture already saved there.
3. Confirm permission to send the photo to OpenAI and tap **Identify this object**.
   The page shows the provider/model, token prices and who pays.
4. Read the proposed identification in the explanation language. Confirm it or
   discard it and retake. Unclear/unsupported results cannot be saved as AI suggestions.
5. See the target-language word and meaning. **Listen (device voice)** appears only
   when saved TTS is disabled and the browser supplies a matching language voice.
   This synthetic preview is
   not an OpenAI TTS request or a saved recording; device speech services may process
   the word. After saving and accepting the wording, **Create spoken audio** on the
   entry generates a separate saveable recording when the owner enables it. Human
   recordings can be added as before.
6. Optionally expand **Save the photo and word**, edit the wording, confirm sharing
   with the dictionary, and save. Ordinary members submit for review; editors may
   accept immediately. Confirming a pictured object does not validate its translation.

Try a clear familiar object, an object off-centre, and a deliberately cluttered photo.
Check the name/article, confirmation language, time taken, pronunciation and saved
entry. Record phone/OS/browser and whether the process was enjoyable without coaching.
An AI can confidently be wrong: this flow gathers usability evidence, not an accuracy
guarantee. A poor identification should be rejected, not saved because it looks polished.

If the connection is interrupted, reopen Learn from a photo and inspect **Your recent
photos**. GET/refresh never starts a paid request. The same submitted receipt cannot
start a second analysis. An interrupted provider request may have incurred a charge
even if no result/usage was recovered; it is never automatically resent. A fresh photo
is a new attempt. HEIC decoding depends on the browser; if rejected, choose JPEG/PNG.

## Configuration and deployment

The patch adds migration `0002_photo_learning`. Install requirements, run `check`,
`migrate` and `collectstatic --noinput`, then restart Gunicorn using the existing shared
deployment runbook. Back up the database and private media first as for other schema
changes. No new public media alias, queue or background AI worker is required.

The default model is `gpt-6-sol`, low reasoning effort, one Responses API call per
attempt, maximum 1,400 output tokens, SDK retries disabled and 20-second HTTP timeout.
The HTTP timeout is not a guaranteed total wall-clock limit. Allow at least 60 seconds
for the Gunicorn/proxy request if the existing configuration has a shorter timeout.
An unavailable model, refusal, timeout, malformed or incomplete output yields an error;
there is no fallback provider, model or language. No live API call was made while
building this patch. The later laptop trial confirms a usable live answer in Manny's
configuration, but the selected model, measured latency and cost were not reported.

- `OPENAI_API_KEY`: existing server key, or the requesting user's enabled personal
  key. An enabled but empty personal key does not fall back to the server key.
- Existing C-LARA credit rules apply to the requesting user when using the server
  key. Personal-key usage is paid directly to OpenAI. Failed/unclear outputs with
  returned usage are still accounted for.
- `C_LARA_COMMUNITY_PHOTO_MODEL`: optional model override. It must support image input,
  strict JSON-schema Responses and `reasoning.effort=low`. Configure its exact price in
  the existing model-pricing table first; the generic default price is not accepted.
- `C_LARA_COMMUNITY_PHOTO_DAILY_LIMIT`: default **20**, applied independently per user
  across dictionaries and per dictionary across users, over a rolling 24 hours.
  Failed and discarded attempts count. Set to `0` to block new calls globally.

The initial rate entry is $2/million input and $10/million output tokens for
`gpt-6-sol`, checked against OpenAI standard pricing on 28 September. Billing uses
existing C-LARA estimates, conservatively counting cached input at the normal rate;
the OpenAI invoice is authoritative. This is an attempt/output limit, not a hard
server-wide dollar budget. Configure the provider account's own spend controls too.

Install the included daily cleanup units once on the described AWS host:

```bash
sudo install -m 644 /srv/C-LARA-2/deploy/systemd/community-photo-cleanup.service /etc/systemd/system/
sudo install -m 644 /srv/C-LARA-2/deploy/systemd/community-photo-cleanup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now community-photo-cleanup.timer
sudo systemctl start community-photo-cleanup.service
sudo systemctl status --no-pager community-photo-cleanup.timer
```

These units use the previously reported `ubuntu:www-data` service identity,
`/srv/C-LARA-2/.venv` and `/etc/clara2.env`. Adjust if deploying elsewhere.
`python manage.py expire_photo_studies` is also available manually on a laptop.
Draft access expires after 24 hours. Physical deletion follows on the next cleanup
run, normally within a further day; saved dictionary media is a separate copy.
Backup retention and OpenAI's retention rules are separate from this local cleanup.

To pause the feature, uncheck it in dictionary settings, or set the daily limit to
zero and restart Gunicorn. Existing dictionary entries remain usable. A code rollback
to the pre-patch commit can leave the additive migration in place; do not unapply it
unless intentionally discarding the new policy, draft and provenance data.

## Implementation boundaries and checks

The sanitized, metadata-stripped photo (up to 1,024 pixels per side for OpenAI) and
two language names are the only outbound user data. The Responses request uses
`store=False`; this is not a promise of zero provider retention. No media URL, other
entries, conversation history or tools are supplied. Drafts are accessible only to
their creator while still a dictionary member, including against other editors or
the dictionary owner. Ordinary invited-dictionary sharing begins only on save.

`PhotoStudy` is the durable claim/receipt. Its transaction commits before the network
call; no database lock is held during inference. Save locks the attempt and creates
one entry even on repeat submission. AI-assisted text has provenance and normal
review; export includes that provenance and labels mixed origins. Private drafts
are excluded from dictionary export. A process crash after provider success but
before recording usage can lose local accounting evidence; reconcile with provider
usage if this occurs. This prototype does not claim exactly-once provider billing.

```bash
cd platform_server
python manage.py test community_dictionary
python manage.py makemigrations --check --dry-run
python manage.py check
```

The original SDK repair passed 41 tests; the entry/audio follow-up has 58, with provider
responses mocked; the startup regression constructs a real client without sending
a request. A separate disposable browser rehearsal is provided in
`experiments/community_dictionary/photo_browser_rehearsal.py`; it also mocks OpenAI.
See the dated experiment record for executed browser results. No boxes, multiple-object
selection, video, generated illustrations, sentence lessons or operational
autonomy agent are added. Saved TTS is provided by the later entry/audio follow-up.

API references: [vision](https://developers.openai.com/api/docs/guides/images-vision),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[pricing](https://developers.openai.com/api/docs/pricing),
[data controls](https://developers.openai.com/api/docs/guides/your-data).
