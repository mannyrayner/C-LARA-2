# Community Dictionaries: optional AI pictures

First cut, 3 October 2026. Manny now reports successful laptop use; AWS
deployment is still pending. The [Settings/photo follow-up](community-settings-and-photos.md)
addresses the two remaining discovery problems he identifies. No paid provider call or community quality trial was performed
while building this patch. See the [verification record](../../experiments/community_dictionary/image-generation-2026-10-03.md).

## Try it

1. As dictionary owner, open **Settings → Dictionary settings**, tick **Enable AI
   picture generation (OpenAI)** and save. It is off by default, including for
   existing dictionaries. It is independent of photo recognition and TTS.
2. Open **Image style** from the dictionary page, or **Set up or view image style**
   under Settings. Describe a visual style and a simple sample subject in the
   explanation language. Confirm permission/cost and generate one sample.
3. Inspect it, then **Approve this style**. A rejected sample can be discarded
   and another requested. Each request may cost money. A replacement style is
   used only after approval and does not regenerate existing pictures.
4. Open an entry and choose **Generate a picture**. Type what the illustration
   should show, confirm permission/cost, and generate a preview. Text-only entries
   are supported: **Add entry**, type words, and save first.
5. Check meaning, details and cultural appropriateness, then **Save picture to
   entry**. Editors can accept it immediately or leave it for review. Existing
   photographs are preserved; an existing selected picture stays selected. Use
   the entry's normal contribution/review controls to choose another picture.

Only owners, editors and coordinators see generation controls. Ordinary members
see accepted pictures and their AI-generated label. No additional setup is
required for taking photographs or making recordings.

## What is sent and retained

The request contains the manually typed subject, the approved style description,
and fixed illustration instructions. It does **not** contain dictionary words,
translations, photographs, recordings, history, or the sample image automatically.
The exact prompt is available in preview details. This first version reuses the
C-LARA OpenAI image adapter and the shared-style workflow, using style **text**
for subsequent pictures; it does not guarantee identical visual style.

Previews are private to their requester, expire after 24 hours, and are copied
into ordinary private-media contributions only on explicit save. Saved pictures
record the provider, model, prompt, style, requester and review action. They are
labelled AI-generated in the entry, picture/word lists and own-content display.
The existing `expire_photo_studies` command now also deletes expired image drafts;
run it daily under the service environment. This patch does not install a timer.
Expiry blocks access even if cleanup has not yet run. Backup retention is separate.

The approved style description and sample are contributions on a hidden style
entry, visible in their author's own-content view. Generated pictures depend on
that style contribution. Withdrawing it therefore also withdraws dependent
pictures into their contributors' retained collections; they return when all
applicable withdrawal holds are lifted. A picture author's own withdrawal also
withdraws their generated pictures. Pending previews are cancelled and purged
when the requester or source style withdraws. Restoring does not repeat paid calls.
The UI explains this dependency before style approval. Local withdrawal cannot
recall material already sent to OpenAI; its provider retention rules still apply.

## Provider and accounting

Default: `gpt-image-2.5-sunburst`, high quality, 1024×1024. Model access must be
available to the server's OpenAI account or the user's configured personal key.
The adapter uses the direct Images API, not ChatGPT's included subscription
allowance. It requires inline image bytes, validates/re-encodes them and does not
fetch a provider-returned URL. There is no silent model/provider fallback.

Settings (environment variables):

| Variable | Default | Meaning |
| --- | --- | --- |
| `CLARA_COMMUNITY_IMAGE_MODEL` | `gpt-image-2.5-sunburst` | Also accepts `gpt-image-2.5-flare` and `gpt-image-2`; explicit administrator choice |
| `CLARA_COMMUNITY_IMAGE_DAILY_LIMIT` | `20` | Attempts per rolling 24 hours, per user and dictionary; includes samples and failures |
| `CLARA_COMMUNITY_IMAGE_ALLOWANCE_USD` | `0.50` | Displayed planning allowance and minimum C-LARA credit balance before starting |

The allowance is **not an exact price, reservation or hard spending cap**. Actual
image-token usage varies. Current configured standard rates are US$5/million
text input tokens and US$30/million image output tokens. Reported usage determines
the internal charge; the provider invoice is authoritative. If returned usage is
missing after an interruption, cost remains unknown. A discarded or failed attempt
may still incur cost. Personal-key use is not deducted from C-LARA credits.

Submission receipts prevent resending the same request after a lost response.
The SDK makes one attempt without automatic retries, with a 240-second timeout.
Only one recent in-flight attempt per user is allowed. **Your recent attempts**
provides a recovery route. Interrupted requests are not silently restarted. A
process crash between provider completion and saving can leave an unknown-cost
attempt or an orphan file; reconciliation and provider budgets remain operational
responsibilities. PostgreSQL load/concurrency testing has not been performed.

Official references checked for this implementation:
[image guide](https://developers.openai.com/api/docs/guides/image-generation),
[model](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst),
[pricing](https://developers.openai.com/api/docs/pricing).

## Later experiments

Sophie proposes a photograph → image understanding → generated illustration
workflow. Manny explicitly places this in a later iteration. It should show the
interpreted description for correction before generation, obtain permission for
the separate outbound image/text steps, preserve the original photograph and
record source dependencies. This patch does not implement it.

Multiple candidates and automated filtering also remain later work. The first
quality experiment is for Sophie/Manny to compare a few genuinely difficult
subjects under one style, noting misleading details and needed corrections.
Human judgement remains necessary, especially for cultural appropriateness.

## Migration and deployment

`0010_image_generation` adds dictionary settings and the private attempt table.
It does not rewrite existing entries, media, participation states or memberships.
It leaves generation off. Apply the normal forward migration and collect static
files when deploying; do not rerun the old experimental reset or reverse 0009.
Use the existing working virtual environment; this patch adds no dependencies.
The supplied installation guide starts with laptop checks before a live trial.
