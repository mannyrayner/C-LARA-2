# Google speech fallback for additional languages

Community Dictionaries keeps OpenAI for its existing supported languages and
respects explicit named Google Cloud word-voice selections there. For an
explicitly mapped additional language, including Igbo, it selects Google
Gemini 3.8 Flash TTS with Kore before the user approves generation. Target
word and sentence audio share this route. Explanation-language feedback can
still use OpenAI when that language is supported there.

This selection is based on capability. A timeout or failed OpenAI request does
not cause an additional paid request to Google. A Gemini attempt is one request
without automatic retry. Its preview must still be listened to and explicitly
saved. Reports retain the actual provider, model, voice, recipe and usage or
labelled cost estimate. This does not establish Igbo pronunciation quality;
the planned fluent-speaker review remains necessary.

## Google setup

The existing Google Cloud WaveNet/Neural2 integration does not itself supply
Igbo. The [Gemini 3.8 language list and REST API](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/text-to-speech/overview)
document the additional provider. Gemini 3.8 is not available through the old
Cloud Text-to-Speech `synthesizeSpeech` endpoint. The adapter uses the documented
Agent Platform REST endpoint with the existing user ADC or reviewed AWS workload
identity credentials. No Google API key or new SDK dependency is required.

The site administrator must verify, on both laptop and AWS:

1. `C_LARA_GOOGLE_TTS_ENABLED=1`, the existing project configuration and ADC/WIF
   credential file are correct. Use the established Connect/Check Google
   procedure; keep credential contents out of logs and the repository.
2. The configured project has billing and the Agent Platform API
   (`aiplatform.googleapis.com`) enabled. Existing Cloud TTS API enablement alone
   does not establish this.
3. The actual authenticated identity has prediction permission for the model
   (`aiplatform.endpoints.predict`, normally supplied through the reviewed
   Vertex AI/Agent Platform user role). Check the impersonated service account
   used on AWS separately from the laptop's user ADC. Changing these API/IAM
   settings is an operator setup action, not an application code deployment.
4. The dictionary's administrator owner enables saved spoken audio. This
   preserves the existing restriction on authorizing shared Google project
   charges. Members then see Google in the generation/processing consent.
5. Create a short Igbo preview and listen before saving. A permission error
   reports the missing API/prediction setup; it does not fall back to English,
   a test tone or another paid provider.

Google project charges remain independent of personal OpenAI keys. Individual
Google previews require C-LARA credit where credit charging is enabled, even
when the user has a personal OpenAI key. New Gemini batch quotes require the
existing credit/server payment path; mixed personal-OpenAI/project-Google batch
settlement is not silently inferred. Picture processing accounts for Google
audio independently of personal OpenAI text processing.

## Pricing and limits

The adapter records returned prompt/output token counts when available. If
usage is absent but a usable recording is returned, it uses a labelled input
byte/duration estimate, not invented measured token counts. Estimates use the
standard $1/million input and $18/million output rates, excluding temporary
promotional credits. See [Google's pricing](https://cloud.google.com/model-garden/pricing).
The provider invoice is authoritative. A completed but invalid response may
still incur charges; an interrupted request remains uncertain and is not retried.

Input remains bounded to 255 characters; the existing WAV format, duration and
audibility validation also applies. Queued work freezes provider, project,
owner, language, recipe and pricing policy. Changes invalidate pending consent
and quotes. The named-Cloud-voice replacement/comparison tools remain separate
from this Gemini path.

For an Igbo dictionary previously created with saved audio disabled, enable
saved spoken audio in Settings after installing this version and verifying
the Google project setup. Human recording remains available independently.
