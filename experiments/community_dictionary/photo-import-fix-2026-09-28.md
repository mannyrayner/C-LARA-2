# Photo-learning startup import repair — 28 September 2026

Manny's laptop trace uses Windows Python 3.11.1 under Cygwin. Calling the new
virtual environment's executable directly works, but `manage.py check` fails:
the photo adapter's eager OpenAI import resolves HTTPX to `src/httpx.py`, whose
offline shim does not provide `URL`. The traceback uses OpenAI SDK 2.8.1.
The preceding pip output also finds global Python packages. The reason for that
environment leakage remains undiagnosed; the venv identity check alone was insufficient.
The gTTS/Click resolver warning is not the reported startup exception.

The exact import failure was reproduced on Linux with SDK 2.8.1. The original
40-test check used SDK 3.19.2 and did not cover the older SDK's import behaviour.
The repair removes the eager SDK import and constructs the client lazily through
the existing `core.ai_api._ensure_openai_installed` source-path protection.
It does not change project-wide import order or remove the offline shim.

Validation: `manage.py check` succeeds with 2.8.1; all **41** dictionary tests pass
with both 2.8.1 and 3.19.2. The added regression uses a fresh interpreter to resolve
Django URLs, confirm the optional SDK was not imported on startup, and construct
the real installed SDK client through the adapter. It checks path restoration and
HTTPX origin when loaded. No API request is sent. Provider calls in workflow tests
remain mocked. No new browser test is needed for this import-only change; Windows,
AWS, real provider calls and the new physical-phone flow still await confirmation.

The follow-up patch applies on top of `community_dictionary_photo_01.patch` and
adds no migration or dependency-version requirement. Apply it before deployment.
Read-only laptop diagnostics inspect `pyvenv.cfg` and compare pip origins with and
without Python's `-E` flag; do not downgrade Click or reinstall global packages as
a speculative response to this trace.

Input-retention decision: the short accompanying human message is archived
verbatim for revision 19. The uploaded installation log is retained in the
conversation; local machine paths and its long dependency inventory are not copied
into the public repository. The relevant exception and version evidence are
summarised here. Human-owned project intentions are unchanged.
