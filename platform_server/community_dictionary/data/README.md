# English spelling risk list

`english_spellings.txt.gz` contains 137,038 distinct lowercase English spellings,
derived from the locally installed SCOWL/Hunspell `en_US.dic` and `en_US.aff`.
Source: https://wordlist.aspell.net/ (Debian/Ubuntu hunspell-en-us distribution).
The full redistribution notices are in `english_spellings.LICENSE`.

Modifications: exclude initially capitalized names/acronyms, numbers and compound-only
forms; expand explicit prefix/suffix rules (including permitted cross-products);
retain apostrophes, deduplicate, add lowercase `i`, sort, and gzip with mtime=0.
Dictionary SHA256: 829a043cf078d1e80e886289a13823454977f442a239a859d2133ea61944aa60
Affix SHA256: 70fe5778717d097ce2f3326baaa5c1e4d2206d81a5a81d3ea8e11c4770806dd5
Expanded UTF-8 SHA256: 1d128806dd2a33d17973f6f063cb8b456c7d5b066ee8143130a31caaa661b3a2

This is a spelling-overlap warning, not a pronunciation assessor. It includes some
rare words/borrowings and can miss specialist vocabulary, names and non-US variants.
Accents are not stripped: e.g. Italian `sì` is not English `si`. The same list is
shipped on Windows and Linux; there is no runtime system dictionary dependency.
