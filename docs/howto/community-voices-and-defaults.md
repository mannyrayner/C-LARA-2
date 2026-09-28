# AI defaults and remembered voices

28 September 2026 follow-up to the working entry-photo/saved-audio patch.
Manny reports that increment is working. This smaller patch makes the AI options
visible during dictionary creation and adds a remembered named-voice menu.

Manny subsequently reports this patch works. The small
[current-audio repair](community-current-audio.md) fixes an additional issue found
in use: outdated TTS belongs in history rather than normal playback.

## Install on the laptop

Stop the local server with Ctrl-C. Save
`community_dictionary_voices_defaults.patch` in `/home/github`, beside the
repository. Apply it after the already installed entry-photo/audio patch:

```bash
cd /home/github/c-lara-2
git apply --check --whitespace=nowarn ../community_dictionary_voices_defaults.patch &&
git apply --index --whitespace=nowarn ../community_dictionary_voices_defaults.patch

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

The suite has 64 tests; the final result should be **OK**. Simulated provider
failure messages are expected. No new dependency is required. Migration
`0004_ai_defaults_and_voices` adds voice preferences and changes defaults for
new dictionaries; it does not change existing dictionaries' saved flags or
recordings. Keep the usual database backup before migrating. If patch checking
fails, stop rather than forcing it. `--whitespace=nowarn` preserves a verbatim
archived message with a trailing space; it does not relax patch matching.
`--insecure` is only for local static serving.

## What to try

- **New dictionary:** both **Learn from a photo** and **saved spoken audio** are
  visibly checked. Uncheck either if unsuitable for the community. Unsupported
  TTS languages require unchecking saved spoken audio. Human microphone recording
  always works independently of these options. These are photo interpretation
  and speech synthesis; AI image generation has not been added.
- **Existing dictionary:** its settings remain as chosen. If previously disabled,
  the owner can enable either option under **People → Dictionary settings**.
- **An entry with accepted wording:** choose **Create spoken audio**, select a
  **Voice**, then generate and listen to the preview. Save it as before, or choose
  **Try another voice**. Each generation is a separate paid request; changing the
  menu alone sends nothing.
- **Another visit or entry:** your last submitted voice is preselected for this
  dictionary. It is personal to your account and persists beyond preview expiry.
  Saved audio displays its voice name and continues to use its original voice.

The default voice is Marin. The menu also offers Cedar, Alloy, Ash, Ballad, Coral,
Echo, Fable, Nova, Onyx, Sage, Shimmer and Verse. OpenAI recommends Marin and Cedar
for quality. Its Speech API exposes names, not a gender field or a gender-labelled
catalogue for these voices, so this menu does not invent such labels. Listen in
the actual target language to choose a preferred sound. Keeping the same voice
provides a consistent speaker choice, not a guarantee of identical delivery.

When saved TTS is enabled, the photo confirmation page directs the user to save
the final wording and generate that audio. It no longer offers a competing device
voice. Device preview remains available where saved TTS is disabled and the
browser supports the language. Per-request confirmation, costs, private previews
and contribution review remain in place.

Development verification: 64 Django tests and Chromium 153 rehearsals at iPhone
13/Pixel 7 viewport sizes pass. Providers are mocked and playback uses a tone
fixture. These checks cover voice propagation, saved provenance, persistence,
invalid choices and duplicate submissions; they do not evaluate actual voice
quality or physical-phone compatibility. See the
[evidence record](../../experiments/community_dictionary/voices-and-defaults-2026-09-28.md).

For later AWS installation, use the existing deployment runbook including
`migrate`, `collectstatic --noinput` and the Gunicorn restart. This patch requires
no additional service. It has not been deployed by the assistant.

Official references checked 28 September 2026:
[TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech) and
[Speech API](https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create).
