# MWE prompt score summary

- Split: `development`
- Records: 336
- Exact match: 130 (38.7%)
- Precision: 0.246
- Recall: 0.400
- F1: 0.304

## Error examples

### en:project_239:p1:s2

Madame Bovary retold

- Gold: []
- Predicted: [['madame', 'bovary']]
- Model analysis: Considered 'Madame Bovary' as a candidate because it is a well-known literary title, often treated as a single unit or name. Additionally, fixed titles of classic works are conventionalized expressions. 'Retold' does not form any conventional combination with 'Madame Bovary'.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold: [['little', 'bit', 'of']]
- Predicted: []
- Model analysis: Considered 'little bit of' as a conventional multi-word expression (MWE). It is a fixed phrase often used to indicate a small amount of something. The expression is lexicalized in English and functions as a single semantic unit. Other candidates such as 'sunny day' or any single words were rejected as they do not represent conventionalized multi-word expressions.

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold: [['found', 'herself']]
- Predicted: []
- Model analysis: Considered 'even found herself' as a potential phrasal or light-verb expression; however, it is more likely an ordinary verb and adverb construct. Considered 'found herself' as a potential reflexive verb; however, this is an ordinary reflexive construction and not idiomatic or conventional. No strong conventionalized or idiomatic phrases were identified in this segment, so no MWEs are marked.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold: [['high', 'up']]
- Predicted: [['fly', 'high', 'up']]
- Model analysis: Considered 'climbed on' since 'on Glitter's back' is a dependent phrase, marking 'on' alone suffices as part of the expression. 'Fly high up' considered due to its fixed nature as a phrasal verb expressing direction/intensity; includes verbs and necessary adverbial elements.

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold: []
- Predicted: [['tea', 'parties']]
- Model analysis: Considered 'flew over' and 'danced with' as potential MWEs but these are common verb-preposition and verb-object combinations. 'Enchanted forests' and 'talking animals' weren't selected as they are descriptive adjective-noun pairs. 'Tea parties' was marked as an MWE because it is a conventionalized term for a specific social gathering.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold: [['at', 'home']]
- Predicted: []
- Model analysis: not recorded

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold: [['complete', 'with']]
- Predicted: [['with', 'complete', 'with']]
- Model analysis: Considered 'complete with' as a candidate MWE because it is a conventional phrase meaning 'including'. It's a stable expression used in similar contexts often enough to be noted as fixed. 'With her favorite treats' and 'in the park' were rejected as they are not fixed expressions but rather ordinary prepositional phrases. No other MWEs were identified.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold: [['had', 'a', 'time']]
- Predicted: []
- Model analysis: Considered 'had a wonderful time' as a candidate MWE since it can behave as a fixed expression reflecting enjoyment, but 'wonderful time' itself does not appear as a fixed, conventionalized phrase. Verbal expressions 'playing games' and 'telling stories' are ordinary activity descriptions rather than conventional or idiomatic expressions. No stable multi-word expressions were identified with strong enough conventional use.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold: [['dreamt', 'of']]
- Predicted: [['fairy-tale', 'boutique']]
- Model analysis: Considered 'dreamt of', 'grander things', 'little fairy-tale', and 'magical potions and enchanted dresses'. 'Dreamt of' not selected as it's an ordinary verb + preposition. 'Grander things' is an ordinary adjective + noun. 'Little fairy-tale boutique' considered for 'fairy-tale boutique' since 'fairy-tale' serves as a compound descriptor for 'boutique', making it a conventional expression. 'Magical potions' and 'enchanted dresses' are descriptive adjective + noun structures, not fixed expressions.

### en:project_239:p6:s3

Emma became famous for her sparkling personality and beautiful shop.

- Gold: []
- Predicted: [['became', 'famous', 'for']]
- Model analysis: Considered the phrase 'became famous for' as a candidate MWE. 'Became famous for' is often used in a conventional sense to describe the reason someone is well-known. The translation suggests a similar conventional usage in French ('devenue célèbre pour'), reinforcing this interpretation. Rejected other combinations like 'sparkling personality' and 'beautiful shop' as they are more compositional and not fixed expressions.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold: [['heard', 'about']]
- Predicted: []
- Model analysis: Considered 'heard about' as a candidate because it is a potential phrasal verb composed of 'heard' and 'about'. This combination is often a stable multi-token lexical unit. Rejected marking 'King and Queen of France' because it is merely a proper noun phrase, and 'amazing Emma Bovary' as it's a descriptive phrase.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold: []
- Predicted: [['tea', 'party']]
- Model analysis: Considered 'grand palace' and 'tea party'. 'Grand palace' is not lexicalized and appears descriptive here. 'Tea party' is a conventional, lexicalized expression.

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold: []
- Predicted: [['royal', 'adventure', 'planner']]
- Model analysis: Considered 'Royal Adventure Planner' as a potential MWE due to its conventional use as a title or role name that appears to be lexicalized. Rejected shorter spans like 'Royal Adventure' as these are not commonly used independently in this context. No other combinations in the sentence present as a conventionalized or idiomatic MWE.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted: [['all', 'over'], ['from', 'then', 'on']]
- Model analysis: Candidates considered: 'From then on' - a fixed adverbial that indicates continuity from a certain point; commonly used and stable, marked as MWE. 'traveled all over the world' - considered 'all over' as a fixed adverbial meaning 'everywhere' without the following noun phrase, marked as MWE. Other combinations like 'making new friends' not marked due to being a common verb phrase without specific lexicalization or idiomatic usage.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold: [['lived', 'happily', 'ever', 'after']]
- Predicted: [['happily', 'ever', 'after']]
- Model analysis: Considered 'happily ever after' as a candidate. It is a fixed idiomatic expression commonly used as a conventionalized phrase typically at the end of fairy tales. No other multi-word expressions were present.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold: [['lived', 'happily', 'ever', 'after']]
- Predicted: [['ever', 'after']]
- Model analysis: Considered 'ever after' because it is a fixed phrase often used in storytelling to signify a continuous happy future. Rejected other combinations such as 'lived happily, sparkly, and joyfully' because they are descriptive and not conventional MWEs. Chose the minimal span 'ever after' as it is the core, stable lexical unit in this context.

### en:project_239:p8:s5

The end.

- Gold: [['the', 'end']]
- Predicted: []
- Model analysis: Considered 'The end' as a potential MWE due to its fixed expression nature in certain contexts, such as films or stories. However, in this fragment, without additional context indicating it's used as a conventional expression, decided against marking it since it could function merely as an ordinary noun phrase. Therefore, no MWEs are marked.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold: [['first', 'responder']]
- Predicted: []
- Model analysis: Considered whether 'Correct Use of Definite, Indefinite and Null Articles' could be a multi-word expression, but it's a descriptive noun phrase, not a conventional phrase or idiom. No phrasal verbs, idioms, fixed adverbials, or compound verbs detected in the segment. No MWEs were identified.

### en:project_245:p2:s2

Not only does he save lives, but he loves to teach proper English grammar.

- Gold: []
- Predicted: [['not', 'only']]
- Model analysis: Considered 'Not only' and 'but' as multi-word expressions. 'Not only' is a fixed expression used to introduce a parallel structure, often a sign of a more complex construction in English involving a contrast, as evidenced by its use in phrase construction. 'But' alone does not usually qualify as a multi-word expression, but in the phrase 'Not only... but...' it functions as part of a conventionalized correlative conjunction pair, necessitating its inclusion to accurately capture the expression. Other words do not form multi-word expressions as they represent normal syntactic or object phrases, such as 'proper English grammar'.

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold: [['stuck', 'in']]
- Predicted: [['in', 'tree']]
- Model analysis: Considered 'in a tree' as a potential MWE because 'in a tree' can be seen as a common phrase denoting a specific location for being 'stuck'. Decided to mark 'in a tree' due to its conventional use in similar contexts.

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold: [['explained', 'to']]
- Predicted: [['climbed', 'to', 'save']]
- Model analysis: Considered 'climbed to save' as a candidate for multi-word expression. It's a lexicalized phrase indicating a specific action. Typically, 'to save' is part of a conventional phrase describing a purpose. Thus, 'climbed to save' qualifies as a phrasal expression for the specific action of climbing with intent to rescue. Other tokens form regular syntactic associations and not conventional MWEs.

### en:project_245:p4:s1

When Felix saw a dog, he said, "The dog is happy to see me.

- Gold: []
- Predicted: [['to', 'see']]
- Model analysis: Considered 'to see' as the phrasal verb candidate, which is a conventionalized expression indicating that the dog is perceiving the speaker with its eyes. Chose not to include 'The dog is happy', as it seems a more compositional phrase describing an emotional state, and the translation confirms this. 'See me' represents a syntactic structure, not a fixed expression.

### en:project_245:p4:s2

'The' is a definite article, referring to this specific dog."

- Gold: []
- Predicted: [['referring', 'to']]
- Model analysis: Candidate MWEs considered: 'definite article' and 'referring to'. 'Definite article' is a descriptive noun phrase and not conventionalized enough to mark as an MWE. 'Referring to' is a conventionalized phrasal verb pattern and thus marked as an MWE with minimal span.

### en:project_245:p5:s1

A little girl approached Felix to thank him.

- Gold: []
- Predicted: [['thank', 'him']]
- Model analysis: Considered 'thank him' as a potential MWE. This is recognized as a conventional light-verb expression where 'thank' is typically followed by a pronoun or noun, forming a stable phrase in this context. Other token groups were not deemed idiomatic or fixed.

### en:project_245:p6:s4

Felix asked, emphasizing ‘the barbecue’ they both knew about.

- Gold: [['knew', 'about']]
- Predicted: []
- Model analysis: Considered 'emphasizing‘ the barbecue’ but rejected as it is descriptive and context-specific. Considered 'knew about' as a candidate for a phrasal verb, since 'know about' is conventionalized in English as conveying familiarity or awareness, thus marked it as an MWE.

