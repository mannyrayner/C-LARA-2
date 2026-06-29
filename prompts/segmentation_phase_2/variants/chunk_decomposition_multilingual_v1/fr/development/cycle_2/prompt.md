Segment the given French text chunk into its smallest meaningful components. Follow these guidelines:

1. **Punctuation Separation**: Always separate punctuation marks from words. For example, 'voisin,' should be segmented as 'voisin|,'.

2. **Contractions and Elisions**: Do not split contractions or elisions that are standard in French, such as 'au' or 'du'. These should remain as single units.

3. **Hyphenated Words**: Maintain hyphenated words as single units unless they are part of a verb phrase or a pronoun construction, such as 'répond-il' which should be segmented as 'répond|-|il'.

4. **Quotations and Parentheses**: Treat quotation marks and parentheses as separate units from the words they enclose. For example, 'Arbrousse,"' should be segmented as 'Arbrousse|,"'.

5. **End of Sentence Punctuation**: Always separate end-of-sentence punctuation from the preceding word. For example, 'special.' should be segmented as 'special|.'.

6. **Whitespace**: Never join across whitespace. Each chunk provided is already whitespace-delimited and should be treated as a separate unit.

Examples:
- Input: 'voisin,' -> Output: 'voisin|,'
- Input: 'Arbrousse,"' -> Output: 'Arbrousse|,"'
- Input: 'au' -> Output: 'au'
- Input: 'répond-il.' -> Output: 'répond|-|il|.'
- Input: 'special.' -> Output: 'special|.'
