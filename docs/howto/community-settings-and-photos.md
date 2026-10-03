# Settings and text-first photo contributions

3 October 2026. Manny reports successful laptop use of optional image generation,
then identifies two usability problems before check-in/AWS deployment. This small
follow-up makes configuration and human pictures easier to find. It has no schema
or dependency changes and makes no paid provider requests during verification.

## Visible changes

- **Settings** is a top-level dictionary tab for owners, editors and coordinators.
  It groups **Dictionary settings** and **Set up or view image style**. Only the
  owner may save name/language/AI settings; editors/coordinators retain style
  access when generation is enabled. Ordinary members' navigation stays simple.
- **People** contains membership and partnership controls. Existing settings
  forms opened before the update can still submit with the original permissions.
- Every entry shows **Add a photo**, including entries started with words and
  entries that already have a photograph or generated illustration. It opens
  **Take photo**, **Or choose a picture**, a preview and top/bottom **Save picture**
  controls. Adding a photo requires no AI setting or style and makes no AI call.
- **Generate a picture** remains alongside it when available. Manual and
  generated images can coexist. Adding another image preserves the selected
  picture; accepted alternatives have **Use as main picture** in contributions.
- Word-editing pages also link directly to **Add a photo** and **Record audio**.
  Adding a picture preserves all existing words, attribution and recordings.

## Apply on the laptop

Stop the development server. Save `community_dictionary_settings_and_photos.patch`
in `/home/github/`. This is incremental over the installed image-generation patch
and Windows test-cleanup patch; do not reapply those patches.

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_settings_and_photos.patch &&
git apply --index ../community_dictionary_settings_and_photos.patch
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary
```

Expect 189 tests and `OK`. The logged simulated API failures are intentional.
No migration is needed for this follow-up. Start as usual:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Check Settings, then save a word-only entry and use Add a photo. Try both a camera
picture and an uploaded image if convenient. Existing words should stay in place.
After acceptance, the accumulated staged changes can be committed and pushed.
AWS will need the original image-generation migration 0010 plus `collectstatic`
and the normal application restart. Manny subsequently reports successful laptop acceptance and AWS installation on
3 October; see the practice experiment record for this human report.

## Evidence and limits

189 app tests pass, including eight new permission/photo workflow checks. A
simulated-provider Chromium rehearsal covers Settings, manual camera-input and
file-upload paths after text entry with AI off/on, generation as an alternative
without replacing a photograph, ordinary-member controls and layouts at 320,
390 and 1280 pixels. Screenshots were inspected. The camera input receives a
synthetic file in this rehearsal; physical camera/device behaviour needs human
testing. No new live output-quality, price or AWS claim is made.
