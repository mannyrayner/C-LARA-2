# Keep generated audio consistent with the entry

28 September 2026. Manny reports that the defaults/voice-menu patch works, but
that changing an entry from `en häst` to `häst` leaves both generated recordings
in the normal playback area. The new patch fixes this presentation problem.

The entry's **Listen and explore** area now includes accepted synthetic audio
only when its stored source wording and language match the entry's current
accepted wording and dictionary language. The same rule applies to browse-card
data and partnership request previews. Human recordings are unaffected: they do
not have an automatically verified transcript.

Older generated recordings remain in **Contributions & versions**, labelled
**Earlier generated audio** and showing their original spoken text. They are
kept for history, not deleted. Restoring matching wording/language makes an
accepted recording available again without generating it again. Translation and
category edits do not hide a recording whose spoken wording is unchanged.
Pending wording proposals do not replace the accepted text used for this check.

## Install after the defaults/voices patch

Stop the laptop server and save `community_dictionary_current_audio.patch` in
`/home/github`, beside the repository:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_current_audio.patch &&
git apply --index ../community_dictionary_current_audio.patch
```

If that succeeds:

```bash
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

No migration, new dependency, audio regeneration or manual cleanup is required.
Refresh the existing horse entry: its normal player should contain only matching
TTS. Older TTS remains accessible by expanding its labelled contribution history.
If applying the patch fails, stop rather than forcing it.

## Evidence

- Based on the preceding defaults/voices tree
  `70a2a28293b9274315d4e6e5479e5fb554210ef1`.
- 67 Django app tests pass (Python 3.12.14, Django 5.2.17, OpenAI SDK 3.19.2).
  Providers are mocked. Regression cases cover the reported article removal,
  retaining files/history, hiding old TTS before replacement, showing matching
  replacement audio, unchanged spoken text after meaning/category edits,
  restoration without another provider call, dictionary-language changes,
  unaffected human audio, and partnership/browse sample selection.
- The code changes only rendering selection and history labels; stored
  contribution status, permissions, review rules and export remain unchanged.
  No new browser/device or live-provider run is claimed for this small repair.
- Later on 28 September, Manny confirms the repair: he now sees only the audio
  matching the text. This is human laptop acceptance of the reported defect.
  He requests check-in of all changes and plans AWS deployment/mobile testing on
  29 September. That deployment and mobile result are not yet reported. No paid
  provider call or AWS deployment was performed by the assistant during this work.

Lookup remains deferred until discussion with Sophie. This is a bounded repair
from actual use, consistent with the priority of avoiding larger runtime additions.
