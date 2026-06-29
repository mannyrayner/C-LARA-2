Segment the given German text chunk into its smallest meaningful components. Follow these guidelines:

1. **Punctuation Separation**: Always separate punctuation marks from words. For example, 'notiert:' should be segmented as 'notiert|:'.

2. **Compound Words**: Decompose compound words into their individual components. For example, 'Wirkungsgrad-Folie' should be segmented as 'Wirkungs|grad|-|Folie'.

3. **Numbers and Symbols**: Separate numbers from following punctuation. For example, '3.' should be segmented as '3|.'.

4. **Hyphenated Words**: Treat hyphens as separate components unless they are part of a compound word. For example, 'Labor­koordinator' should be segmented as 'Labor|­|koordinator'.

5. **Quotations and Parentheses**: Separate quotation marks and parentheses from the words they enclose. For example, '„Natürlich."' should be segmented as '„|Natürlich|.|"'.

6. **Common Particles and Conjunctions**: Do not split common particles or conjunctions unless they are followed by punctuation. For example, 'Beim' should remain 'Beim', but 'sich;' should be segmented as 'sich|;'.

7. **Avoid Over-Splitting**: Ensure that words are not split into non-meaningful parts. For example, 'unkompliziert' should remain 'unkompliziert'.

Examples:
- Input: 'notiert:' -> Output: 'notiert|:'
- Input: '3.' -> Output: '3|.'
- Input: 'Wirkungsgrad-Folie' -> Output: 'Wirkungs|grad|-|Folie'
- Input: '„Natürlich."' -> Output: '„|Natürlich|.|"'
- Input: 'Labor­koordinator' -> Output: 'Labor|­|koordinator'
- Input: 'sich;' -> Output: 'sich|;'
- Input: 'unkompliziert' -> Output: 'unkompliziert'
