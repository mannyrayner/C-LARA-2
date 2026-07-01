Segment the given French text chunk into its smallest meaningful components. Follow these guidelines:

1. **Apostrophes**: Always split contractions at the apostrophe. For example, `d'autres` should be segmented as `d'|autres`.

2. **Hyphens**: Split compound words at hyphens. For example, `au-dessus` should be segmented as `au|-|dessus`.

3. **Punctuation**: Treat punctuation as separate segments unless it is part of a word. For example, `l’annonce.` should be segmented as `l’|annonce|.`.

4. **Quotes**: Do not split quotes from the words they enclose unless they are at the beginning of a chunk. For example, `"La` should remain `"La`.

5. **Common Contractions**: Split common contractions such as `d'un`, `l'amour`, `n'a`, `qu'il`, `s'agisse` at the apostrophe. For example, `d'un` should be segmented as `d'|un`.

6. **Special Characters**: Treat special characters like `œ` as part of the word. For example, `d'œil` should be segmented as `d'|œil`.

7. **Invalid Surfaces**: Ensure that the surface form of the chunk remains valid and meaningful. Avoid splitting in a way that creates invalid or nonsensical segments.

Examples:
- Input: `d'autres` -> Output: `d'|autres`
- Input: `au-dessus` -> Output: `au|-|dessus`
- Input: `l’annonce.` -> Output: `l’|annonce|.`
- Input: `plate-forme.` -> Output: `plate|-|forme|.`
- Input: `s’entraîne.` -> Output: `s’|entraîne|.`
- Input: `d’un` -> Output: `d’|un`
- Input: `pas-trop-haut` -> Output: `pas|-|trop|-|haut`
- Input: `"La` -> Output: `"La`
- Input: `admirable."` -> Output: `admirable|."`
- Input: `l'amour` -> Output: `l'|amour`
- Input: `n'a` -> Output: `n'|a`
- Input: `d'œil` -> Output: `d'|œil`
- Input: `l'observait` -> Output: `l'|observait`
- Input: `qu'il` -> Output: `qu'|il`
- Input: `s'agisse` -> Output: `s'|agisse`
- Input: `minutes,` -> Output: `minutes,`
