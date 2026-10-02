# My contributions: entry context

> Historical revision. The current [dictionary-wide participation model](community-participation.md)
> replaces individual withdrawal/sharing, editable personal collections and the
> per-entry return shortcut. Use its runbook for the new migration and laptop trial.


Prepared 1 October 2026 as a follow-up to the installed contribution-control
revision. Apply this patch **after** `community_dictionary_contribution_control.patch`.
It changes presentation and adds tests; there are no new migrations or dependencies.

## What to expect

My contributions now groups material into complete entry cards, with pictures,
word/phrase, translation, category and recordings together. A card has a link to
the normal entry when the viewer can open it. Additional picture-word links keep
their listening/translation controls. Comments and earlier owned revisions are
available under the same card, so historical contributions are still withdrawable.

- Your components have a **Yours** label and a checkbox.
- Other people's components have a grey background and **For reference** label.
  They remain readable/playable but cannot be selected, withdrawn or reshared.
- Filters choose entries containing your matching material. The rest of the entry
  remains visible for context; only your matching components are selectable.
- Pagination counts entries (12 per page), so components of one entry stay together.
- A private collection can show live context from its original shared entry while
  you still have access. It is labelled for reference and is not copied into your
  collection or included when you share selected material. If your membership
  becomes inactive, or the source material is withdrawn, that context disappears.
- Inactive members still see and control their own material, without gaining
  access to other people's text, pictures, recordings or linked words.

This does not change attribution, withdrawal, sharing, review or membership rules.

## Laptop installation

Save `community_dictionary_contributions_by_entry.patch` one directory above the
checkout. Stop the development server with Ctrl-C. The previous patch can remain
staged; it does not have to be committed first. Preserve any unrelated local edits.

```bash
cd /home/github/c-lara-2
git apply --check ../community_dictionary_contributions_by_entry.patch &&
git apply --index ../community_dictionary_contributions_by_entry.patch
```

Only continue if that succeeds. Then:

```bash
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

The expected test count is **128**. The deliberate TimeoutError/JSONDecodeError
provider-failure log messages are expected if the final result is `OK`.
No `migrate`, package installation or new database backup is needed for this
presentation-only follow-up. The original contribution-control migration/backup
instructions still apply to machines that have not yet installed that revision.

In My contributions, try an entry with Cathy's picture/translation and Manny's
Swedish word/audio. Each account should see the whole entry but only its own
components should have checkboxes. Try the Pictures filter: the wording/audio
should remain visible. Test withdrawal/resharing on a disposable sample entry.

For later AWS deployment, commit/push the combined changes and use the existing
runbook, including `collectstatic --noinput` and restarting Gunicorn. Static CSS
has a new cache version. A browser refresh should be enough on the laptop.

## Evidence

128 app tests pass, including ten new entry-display/access tests. A disposable
Chromium rehearsal checks both members' views, inline reference playback,
filtering, withdrawal, private context and inactive access at phone/desktop sizes.
See [the evidence record](../../experiments/community_dictionary/contribution-display-2026-10-01.md).
These are browser viewports, not a new physical-phone acceptance claim.

Manny subsequently confirms successful laptop testing of My contributions on
1 October and requests check-in. New AWS/physical-phone acceptance remains pending.
The account-form capitalisation investigation is separate and has no code changes
in this revision.

## 2 October: returning withdrawn material

Manny confirms the return workflow works but found the entry selector easy to
miss. After trying the prominent Share back shortcut, he requests a further
simplification. The [immediate-restoration follow-up](community-immediate-restore.md)
returns current material to its original entry in one click, retaining prior
approval where still valid. Private copies and reference-only context remain.
148 app tests and a Chromium rehearsal pass; human acceptance and new server/phone
validation are pending. No migration is added.
