# Community dictionary app

Status: bootstrap scaffold; no user-facing functionality yet.

This app will support mobile construction and discussion of shared picture/audio
dictionaries, including partnerships that divide picture and recording work.
The first prototype uses phone photographs and human recordings. AI content
generation and dedicated practice activities are later increments.

- [Specification and development workflow](../../docs/roadmap/community-dictionary.md)
- [Setup and testing guide](../../docs/howto/community-dictionary.md)
- [Development experiment](../../experiments/community_dictionary/README.md)

Keep new feature code, templates, static files, migrations and Django tests in
this app. Inspect existing account, community and dictionary models before
choosing reuse boundaries. Store uploaded media outside Git, with access checks.

The bootstrap includes an app configuration but deliberately does not add it to
`INSTALLED_APPS`, expose a URL, define database models, or alter existing behaviour.
Those integration changes belong to the first functional implementation.
