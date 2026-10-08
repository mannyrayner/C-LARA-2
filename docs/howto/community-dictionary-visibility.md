# Hide an older dictionary from the main list

8 October 2026. The owner can open **Settings → Dictionary visibility → Hide
dictionary**. The state changes immediately; there is no additional confirmation
because making it visible again is equally easy.

All dictionaries begin **Visible**. A hidden dictionary moves out of the normal
**Your dictionaries** list for every member, including its owner. It appears under
the collapsed **Hidden dictionaries** section instead. Pending invitations to it
also appear inside that section. A direct link still works for an authorized
member; a banner clearly labels the dictionary as hidden.

To reverse this, the owner opens **Hidden dictionaries → Visibility settings** and
chooses **Make dictionary visible**. Ordinary members and editors cannot change
the shared visibility setting. New dictionaries and image-only copies start
visible, even when their source is hidden.

This is a way to tidy the list, not to make the data more private or stop editing.
Membership, contribution ownership, provenance, saved media, AI work and account
charges are unchanged. Members retain their normal rights to view, withdraw and
restore their own contributions. Inactive/withdrawn members still have their
usual restricted participation view. Outsiders gain no access. Hiding the original
dictionary does not withdraw images linked into its newer copy.

Implementation: one `Dictionary.hidden` Boolean field, default false, in additive
migration **0017_dictionary_visibility**. The owner-only, CSRF-protected POST uses
an explicit desired state, so retrying it does not toggle the dictionary back.
Changes are recorded in the dictionary event log. Existing archive/withdrawal
rules are separate and unchanged; an archived dictionary must be reopened through
its normal participation flow before its owner can edit Settings.

See [installation](community-dictionary-visibility-install.md) and
[verification evidence](../../experiments/community_dictionary/visibility-2026-10-08.md).
