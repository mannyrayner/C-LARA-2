# Clearer saving and invitations

30 September 2026. Based on `main` at `c72c33b992db50365d2489fefb0a27598210abd6`.
This responds to Cathy's reported use and Manny's invitation-menu request.

## What changes

- Entry contributions and word edits have **Save** buttons at both the top and
  bottom of the form. They perform the same save.
- For media contributions, the sentence beside each Save button makes the click
  an explicit confirmation of permission to share with the dictionary. The
  separate checkbox is removed from that form; the server still requires the
  confirmation. Members' contributions still await editor review as before.
- Following a link with an unsaved contribution opens **Save before leaving?**,
  offering **Save and leave**, **Keep editing**, and **Leave without saving**.
  Save and leave confirms permission explicitly and only continues after the
  server confirms the save. Failed saves leave the form and media available.
- Local draft messages clearly distinguish recovery on this device from saving
  to the dictionary. A local write or restoration no longer suppresses warnings.
  Media selection counts as unsaved immediately, including while resizing a photo.
- **People → Invite an account or change a role** offers an alphabetical menu of
  active C-LARA usernames, excluding the owner. Only the owner sees that menu;
  it shows no email addresses. Current members are included for role changes.
  Partnership invitations similarly offer the dictionary's joined members.

Choosing Leave without saving keeps the recovery draft where browser storage
works. Reopen the same form on the same device, browser and account to recover it.
Choose Save to put the contribution into the dictionary. Discard local draft
explicitly deletes only that recovery copy.

Browser Back, reload and closing the tab use a native warning, where supported.
Browsers control its text and buttons, so it cannot offer our custom Save action.
Choose to stay and use Save. Mobile browsers can omit this warning, especially if
the app is killed, so the app also attempts local persistence when it is hidden.
Local drafts are best-effort recovery: browser-data clearing, disabled storage or
an OS termination can still remove/prevent them. These limits follow the browser's
[beforeunload](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event)
and [visibilitychange](https://developer.mozilla.org/en-US/docs/Web/API/Document/visibilitychange_event)
behaviour. No background server upload or permission is inferred from leaving.

This increment changes neither the entry-form introduction nor the deferred AI
image-generation feature. Photo interpretation and TTS keep their separate
provider-processing confirmations. No migration or dependency change is needed.

## Laptop installation

Stop the local server. Save `community_dictionary_save_ux.patch` in `/home/github`,
beside the checkout. From a clean checkout of the stated base (or a compatible
later main), run in Cygwin:

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_save_ux.patch &&
git apply --index ../community_dictionary_save_ux.patch
```

Then:

```bash
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Refresh the page (Ctrl+F5). Expect 70 tests; their intentional provider-error cases
may log TimeoutError/JSONDecodeError before the final OK, without any real API call.

Try adding a photo, choosing Browse, and trying Keep editing followed by Save and
leave. Try a normal Save from each end of the form and check the invitation menu.
The browser/device-specific check is to repeat this on Cathy's phone after deploy.

After laptop acceptance, commit the staged patch and push using the usual workflow:

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat &&
git commit -m "Clarify dictionary saving and protect unsaved contributions" &&
git push
```

On AWS, use the existing update runbook including `collectstatic --noinput` and
the Gunicorn restart. The existing cleanup timer requires no change. This patch
has not been installed on the production server by the assistant.

See the [implementation and validation record](../../experiments/community_dictionary/save-ux-2026-09-30.md).
