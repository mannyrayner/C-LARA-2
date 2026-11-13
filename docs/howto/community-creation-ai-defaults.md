# AI defaults when creating a dictionary

The creation form starts with AI picture generation and Picture descriptions
selected. As the owner enters a language, untouched defaults follow the same
language names/codes supported by the saved-audio flow, including Google
fallback languages such as Igbo. Unsupported languages leave these defaults
off. Picture descriptions also require saved audio and a supported explanation
language.

An owner can turn either option off. Editing the language later does not undo
that explicit choice, and validation errors retain submitted values. Existing
dictionaries' Settings are not reset. The creation page includes the support
list through Django's escaped JSON output; no provider call is needed to decide
the defaults.

Enabling a feature does not generate content. Existing permission, preview,
confirmation and payment steps still apply to each workflow. The help text no
longer describes the features as off by default; French and Slovak translations
are included.

Model defaults remain unchanged for imports and programmatic dictionary
creation, so this is a code-only form/static-asset update without a migration.
