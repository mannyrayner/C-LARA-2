# Simple picture contribution as the default

For a member with no saved workflow choice, a dictionary with picture
descriptions, saved audio and supported content/explanation languages now opens
**Picture, confirm and finish** from Add something. Settings selects the same
option. Existing manual and writing-practice choices, including the older
writing-session preference, are preserved. Unsupported or disabled AI workflows
continue to use the manual form.

The first picture screen includes the existing cost/privacy information and an
unchecked permission box. The first valid upload saves the member's scoped
permission; merely visiting a page does not create consent or start processing.
Subsequent pictures use the existing standing-consent flow. Changed prices,
providers or dictionary configuration still invalidate consent before a paid
request. Pictures stay private until their description is approved.

The default is computed from dictionary capabilities rather than changing the
database field default, so no migration or rewrite of saved preferences is
needed. The usual contribution form remains accessible from Help.

## Short public address

The existing project website (`mannyrayner/C-LARA`, published from `docs/` at
`www.c-lara.org`) can provide `https://c-lara.org/d` through the additive static
page `docs/d/index.html`. It offers **Browse without signing in**, linking to
the public `/community-dictionaries/browse/` page, and **Sign in or register**,
linking to the member home. The member route requests login when needed and
uses the remembered learning language for signed-in users. No new DNS record,
certificate, domain purchase or AWS service is needed.

The static landing page uses two fixed HTTPS links and works without JavaScript.
It does not automatically redirect, accept arbitrary redirect targets or carry
query parameters between sites. Existing application, login and dictionary URLs
remain valid. The browser's address bar shows the canonical application URL
after choosing a link; this is a short address to advertise and type, not a new
application host.

Publish and check the website page separately from the normal laptop/AWS
application release. The application change itself does not publish the short
address.
