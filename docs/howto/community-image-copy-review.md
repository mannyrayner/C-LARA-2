# Image-only copies: selection and fresh review

8 October 2026. Follow-up to the accepted Type/Speak/AI-description update.

**Settings → Create an image-only copy** now offers **Accepted**, **Awaiting review**,
or **Both** as source choices, defaulting to Both. Counts are shown for all three;
duplicate derivatives of one original image count once within each choice. Rejected,
removed, withdrawn and archived material is excluded. Missing files abort the copy.
All copied pictures start **Awaiting review**, independently of their source status.
The new dictionary opens on that tab so the copy does not appear empty.

The original dictionary, words and review states are unchanged. As before, only
images are copied, with attribution/custody, source links and withdrawal/restore
dependencies retained. No AI request is made by copying. Existing copies are not
retrospectively changed. Create a fresh copy to include the newly eligible pictures;
the old copy can be hidden if it is no longer useful.

## Describe and accept together

Accepted images already support description; Accepted was never a completed-
description marker. The previous implementation instead blocked the description
route on pending pictures. Changing copy status alone would have made this worse.

Owners/editors can now open a pending image, choose Type, Speak or Suggest a
description and prepare the normal private preview. The UI explains that
**Yes — save and share** also accepts that picture. This approval and publication
commit together. Preparing, correcting, failing or discarding a suggestion does
not approve the picture. Language checking remains a separate action.

After confirmation, the sentence appears in Accepted, the copied image leaves
Awaiting review and the otherwise empty source card is hidden in normal browse,
using the existing source-card rules. **Next picture** includes eligible pending
pictures for owners/editors; other members are offered accepted pictures only.
Each provider/publication stage rechecks permissions and source state. A rejected,
withdrawn or archived image, or loss of editor access, blocks the pending-image
route. The standard Accept button remains available without using AI.

Copies retain the source's AI settings. If the older dictionary has Picture
descriptions off, enable **Settings → Picture descriptions (OpenAI)** and saved
spoken audio in the new copy. The copy form now calls this out when relevant.

## Verification and installation

No migration, database rewrite, dependency or credential change.
See [installation and a short trial](community-image-copy-review-install.md) and
[verification evidence](../../experiments/community_dictionary/image-copy-review-2026-10-08.md).
The original AI-mode release now has Manny's positive human report; this follow-up
still needs his laptop experiment and subsequent deployment/phone testing.
