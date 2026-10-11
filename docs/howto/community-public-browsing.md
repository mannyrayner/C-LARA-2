# Public browsing without an account

This optional first version lets people explore a dictionary without registering.
New dictionaries start with public browsing **off**; migration 0020 also left existing dictionaries off. No guest
account, shared password or anonymous membership is created.

## Owner workflow

Open a dictionary's **Settings → Public browsing**. Confirm that its contributors
permit public access to the accepted material, including future accepted content,
then choose **Enable public browsing**. This is a separate decision from sharing
within an invited group. Public browsing permits access through its link, which is not a secret access token.
Listing it in **Find dictionaries** additionally requires the separate default-off
**Discoverability** setting. See [discovery and profiles](community-discovery-profiles.md).

Settings then shows **View as a visitor**, a link to share, and **Turn off public
browsing**. Member pages display a public-access notice. Only the owner can change
this setting; members, editors and coordinators cannot.

Visitors choose **Browse without logging in** on the dictionary login page, or
follow the owner's link. Existing users also have a **Find dictionaries**
link on their home page. Public routes work for signed-in outsiders too. Withdrawing
from a project still blocks member access and contributions, but cannot stop someone
viewing material that the remaining community has made available to everyone.

## Available to visitors

- Pictures, Words and Sentences tabs, search and category filtering.
- Current accepted text, translations, categories, pictures and recordings.
- Word/sentence/picture links, inline translations and audio playback.
- Dictionary name, target language, commenting language and accepted word/sentence counts.

Pending/rejected/removed contributions, historical text, discussions, contributor
details, prompts, private collections and audit records are excluded. Generated
images and synthetic recordings retain their simple AI labels. Synthetic audio
must match the current accepted wording, language and recorded meaning dependency.

Visitor routes only accept GET/HEAD. They grant no contribution, editing, review,
AI-generation, export or practice permissions, and make no AI calls. Existing
member routes keep their existing permission checks. Normal hosting/bandwidth
costs still apply.

## Withdrawal and visibility

Every public page and media request checks live dictionary and contribution access.
Disabling public browsing blocks subsequent requests, including saved media links.
Hiding a dictionary turns public browsing off; unhiding does not turn it back on.
Archived dictionaries and personal collections are never public.

Withdrawal removes the contributor's material and its held dependencies from the
public view through the existing participation workflow. Restoring accepted material
can make it public again if the dictionary is still public. Access to material
already received by a visitor cannot be revoked: screenshots, downloads, an already
loaded page or an in-progress response cannot be recalled.

Responses request no caching and no search indexing. These headers are not a
security boundary or a guarantee against copying; anyone can request public content.
Private files remain outside the public media root and use the permission-checked
streaming endpoint, including byte-range audio playback.

## Implementation and validation

Migration `community_dictionary.0020_public_browsing` adds the default-off setting
and a revision counter for stale Settings submissions. No package, environment,
static-file or email configuration changes are needed.

`public_browsing.py` projects accepted learning fields explicitly rather than using
the member view's pending-text fallback. `public_views.py` supplies separate visitor
routes and the owner's CSRF-protected setting. The existing private member views
are not relaxed.

See [installation instructions](community-public-browsing-install.md) and the
[development evidence](../../experiments/community_dictionary/public-browsing-2026-10-11.md).
Manny reports that anonymous browsing works and is deployed on AWS (11 October).
The newer discoverability/profile increment has separate local verification and
awaits its own laptop/AWS acceptance; see the linked discovery documentation.
