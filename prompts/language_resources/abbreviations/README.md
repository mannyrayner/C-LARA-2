# Abbreviation resources

These files list abbreviation surfaces that should normally remain a single
segmentation token even if a chunk prompt returns pipe-delimited punctuation,
for example `Mr|.` for `Mr.`.

- `common.json` applies to every language.
- `<language>.json` extends the common list for a language code such as `en` or
  `de`; regional tags such as `en-GB` fall back to `en`.
- `initialism_pattern: true` enables a conservative pattern for surfaces like
  `U.S.` or `U.K.`.

To add a language, create a new `<language>.json` file with an `abbreviations`
array and, if appropriate, `initialism_pattern`.
