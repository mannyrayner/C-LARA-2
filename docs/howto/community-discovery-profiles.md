# Discover dictionaries, request membership and introduce yourself

## Discoverability and public browsing

An owner can choose **Settings → Discoverability → Make dictionary discoverable**.
It is off by default, independently of public browsing. Find dictionaries, reached
without an account from the login page, advertises only the name, target and
commenting languages, and accepted entry/sentence/word counts. The signed-in home
page also shows these dictionary cards. No picture, word, recording or discussion
is exposed by discoverability alone. Counts exclude pending-only entries.

| Discoverable | Public browsing | Result |
| --- | --- | --- |
| Off | Off | Private and unlisted |
| On | Off | Metadata listed; content remains private; people can ask to join |
| Off | On | Unlisted, but anyone with the public link can browse accepted content |
| On | On | Listed, with public browsing and an option to request membership |

**Upgrade note:** migration 0021 leaves all dictionaries undiscoverable, including
ones already open to visitors. Their public links continue to work. Owners must
enable discoverability to put them in the directory again. Hidden, archived and
personal dictionaries never appear. Hiding turns both settings off; unhiding does
not turn either back on. Unlisting stops new requests but preserves requests
already sent for the owner to resolve.

## Membership requests

Open a listed dictionary's membership details. Log in to send **Request membership**,
optionally with a short message. Requests reveal the account username and message
to the current owner, not to other members or visitors. No email or AI call is made.

Owners see **Pending membership requests** on their home page, Profile and dictionary
Settings. **Approve membership** admits a new applicant as an ordinary contributing
member immediately; **Decline** closes the request. A later invitation remains
possible. The requester can see status and cancel a pending request in Profile.
There is one request per account/dictionary and at most 20 pending requests per
account. Repeated clicks do not create duplicate requests or memberships.

An existing invitation still needs its normal acceptance. Existing roles are not
changed, inactive members are not reactivated and withdrawn content is not restored
by this route. Membership moderation and withdrawal keep their existing controls.
The current owner sees pending requests after ownership handover. Decisions are
POST/CSRF protected, revision checked and recorded without copying private messages
into the shared audit event text.

## Profile and contributor listing

**Profile** in the Community Dictionaries header shows your username, account email,
password-change link, available AI credits, owned dictionaries and membership
requests. Existing email-recovery/account validation is unchanged. Account email
is read-only here; an administrator can correct it after checking identity.

**List me as a contributor** is off by default. Opting in requires a chosen public
name (a pseudonym is fine), and optionally a short introduction. About links to your
public contributor page, which also lists the discoverable dictionaries you own.
The public page does not reveal your login name, email, balance, API key or private
dictionaries. If you choose your login name as your public name, that is your choice.
Opting out removes the hosted listing immediately; it cannot recall saved copies.
Inactive accounts are not publicly listed.

Advanced profile preferences reuse the shared C-LARA timezone and optional personal
OpenAI-key settings. They are collapsed initially. Saved keys are never rendered in
the Community Dictionaries form; leaving the key blank retains it, and explicit
removal clears it. Changing these preferences does not modify dialogue language,
memory or other C-LARA preferences. Both apps use the same login and AI-credit
balance; no new payment system or credit transfer interface is introduced.

## About

The public **About** header link briefly describes manual and optional AI workflows,
practice, sharing choices and the iterative development approach. It includes a
publications section (the introductory report is explicitly in preparation), an
opt-in contributor directory and a project email contact. Existing practice games
make no paid AI calls. Hosting still has costs; optional AI processing can spend
credits. There is no published experimental-credit offer or AI-moderated forum in
this increment. The contact defaults to Manny's existing project address; an
operator may override `COMMUNITY_DICTIONARY_CONTACT_EMAIL` in Django settings.

## Verification and limits

The local tests cover privacy boundaries, owner-only toggles and decisions, stale
submissions, duplicate requests, approval/cancellation, existing membership and
withdrawal, profile opt-in/out, shared preferences, key removal and password change.
Disposable browser rehearsals cover phone-width and desktop layouts. They make no
live email/AI calls and are not physical-phone or production/PostgreSQL acceptance.

See [evidence](../../experiments/community_dictionary/discovery-profiles-2026-10-11.md)
and [installation instructions](community-discovery-profiles-install.md).
