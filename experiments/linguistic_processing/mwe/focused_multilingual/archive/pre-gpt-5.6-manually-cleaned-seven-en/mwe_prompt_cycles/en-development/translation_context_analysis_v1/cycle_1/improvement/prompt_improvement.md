# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.149
- Recall: 0.354
- F1: 0.210

## General revision principles

- Mark an MWE only when the expression is conventionalized, idiomatic, lexicalized, or functions as a stable multi-token lexical unit.
- Do not mark ordinary compositional adjective+noun, determiner+noun, or verb+object phrases just because they are frequent in the text.
- Prefer high precision: when unsure, leave tokens unmarked rather than inventing an MWE.
- Keep labels broad and language-neutral; avoid rules tied to a single project or named example.
- Preserve the input token sequence exactly and only add MWE IDs to tokens that belong to accepted multi-token expressions.

## False-positive examples to inspect

### en:project_239:p1:s2

Madame Bovary retold

- Gold spans: []
- Predicted spans: [['madame', 'bovary']]
- Model analysis: The candidate expression 'Madame Bovary' is considered a multi-word expression because it is a proper noun, referring to the title of a well-known novel by Gustave Flaubert. Proper nouns often are treated as fixed expressions because they function as a single lexical unit. Though the translation groups the phrase 'Madame Bovary' as a single unit, the source expression itself is stable and conventionalized as the name of the character and the book. No other MWEs were identified, as 'retold' is a standalone verb without specific multi-word associations here.

### en:project_239:p2:s2

Emma lived in a beautiful house with her husband, Charles, who was a kind and gentle doctor.

- Gold spans: []
- Predicted spans: [['beautiful', 'house'], ['kind', 'and', 'gentle', 'doctor']]
- Model analysis: The phrase 'beautiful house' is considered as a candidate for MWE due to its conventional use as a stable adjective+noun expression, often used in a figurative sense beyond simple composition. 'Kind and gentle doctor' is somewhat idiomatic because it merges multiple adjectives to project a harmonious characteristic, common in describing people, thus forming a more integrated expression. However, segments like 'Emma lived', 'with her husband', or 'who was a' were discarded as they are highly compositional, forming regular phrases with predictable meanings.

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold spans: [['found', 'herself']]
- Predicted spans: [['sparkly', 'pink', 'unicorn']]
- Model analysis: The phrase 'sparkly pink unicorn' is considered as a stable lexical unit. It is a conventionalized expression that often appears as a single concept representing a whimsical or fantastical creature. Each adjective modifies 'unicorn,' but together they form a specific type of unicorn often recognized in pop culture or children's literature. The translation context also supports this as it keeps the adjectives and noun together. Other expressions in the sentence like 'found herself' or 'named Glitter' do not exhibit properties of idiomatic meaning or fixedness beyond their compositional meanings, so they were not marked as MWEs.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['fly', 'high', 'up'], ['magical', 'lands'], ['on', 'glitter', "'s", 'back']]
- Model analysis: Candidate expressions analyzed were: 'on Glitter's back' which is a conventionalized expression for riding on a specific entity; 'fly high up' as this forms a relatively fixed phrase to describe a motion in the sky; 'magical lands' considered as a more conventionalized location in fantasy contexts. Rejected candidates: 'Emma climbed' as it represents a straightforward subject-verb composition; 'into the sky' and 'visit magical lands' as they are relatively more compositional.

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold spans: []
- Predicted spans: [['tea', 'parties']]
- Model analysis: Considered 'flew over rainbow waterfalls' and 'danced with fairies in enchanted forests' but found them largely compositional and descriptive with no strong evidence of idiomatic usage or conventional fixed expressions. 'Tea parties' is regarded as a conventional multi-word expression likely due to cultural and historical usage, possibly invoking scenes typical in British English where 'tea party' carries more lexically stable meaning than just 'parties involving tea'.

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold spans: []
- Predicted spans: [['in', 'all', 'her', 'grand', 'adventures']]
- Model analysis: Considered 'to see', 'happy and supported', and 'in all her grand adventures'. 'To see' is a common verb-object syntax without fixed idiomatic meaning. 'Happy and supported' is an ordinary conjunction of adjectives, no evidence of being idiomatic. 'In all her grand adventures' shows conventional usage with 'grand adventures' as a frequently collocating phrase with 'all her' typically being part of the expression, forming a stable lexical unit often occurring together in similar contexts.

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: [['complete', 'with', 'her', 'favorite', 'treats'], ['in', 'the', 'park']]
- Model analysis: The expression 'in the park' was considered because it represents a stable locational phrase that is often used in English to denote a conventional place. Although it appears simple, it functions as a single concept. The phrase 'complete with her favorite treats' is common to indicate the inclusion of expected or extra elements that enhance an event or object. Despite the possibility of arguing compositionality, the phrase 'complete with' is a recognized pattern for such constructions and stabilizes the phrase.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['fairy-tale', 'boutique']]
- Model analysis: Considered 'grander things', 'fairy-tale boutique', 'magical potions', and 'enchanted dresses'. 'Grander things' was rejected as it is a standard compositional phrase combining an adjective and a noun. 'Magical potions' and 'enchanted dresses' are compositional adjective+noun pairs. 'Fairy-tale boutique' was selected as an MWE because it is a relatively fixed expression that describes a boutique themed or styled like a fairy tale, supported by the translation context as a lexicalized expression in French ('boutique de contes de fées').

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['from', 'all', 'over']]
- Model analysis: Candidates considered: 'Business was booming' - 'was booming' is selected as an idiomatic expression indicating rapid success; 'from all over' - a fixed expression denoting wide geographic origin, included as MWE. 'business' and 'shop' were not marked as MWEs, because they function as compositional noun phrases. Other verb phrases and combinations were either discarded due to high compositionality or did not form stable MWEs.

### en:project_239:p6:s3

Emma became famous for her sparkling personality and beautiful shop.

- Gold spans: []
- Predicted spans: [['beautiful', 'shop'], ['sparkling', 'personality']]
- Model analysis: Considering candidate expressions: 'sparkling personality' is a fixed idiomatic expression used to describe someone with an engaging and lively character. It is a recognized collocation and more than the sum of its parts, so it is marked as a fixed idiom. 'Beautiful shop' is less clear-cut; while it could be compositional, it seems to have been used with some lexicalization here, possibly due to the translation context or familiarity. Given the translation implies it as a notable feature, it is marked as a conventional expression, though this is less conventional than 'sparkling personality'.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold spans: []
- Predicted spans: [['grand', 'palace'], ['special', 'tea', 'party']]
- Model analysis: The candidates considered were 'grand palace' and 'special tea party'. 'Grand palace' can be considered a fixed adverbial or stable lexical unit, not entirely compositional, often used to describe elaborate buildings. 'Special tea party' is considered a fixed phrase, as 'tea party' is a culturally established concept, and the qualifier 'special' directly modifies it, forming a stable expression. Other combinations like 'invited her', 'tea party', etc., are more compositional, as they are regular verb-object or adjective-noun pairs.

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold spans: []
- Predicted spans: [['royal', 'adventure', 'planner']]
- Model analysis: Considered 'The King and Queen', 'so impressed', 'made Emma the Royal Adventure Planner'. 'The King and Queen' is largely compositional and refers to titles, hence not a strong MWE. 'so impressed' is a typical compositional adjective phrase. 'made Emma the Royal Adventure Planner' contains the expression 'Royal Adventure Planner', which is a proper noun and can be seen as a conventionalized title, making it a strong candidate for a stable lexical unit MWE.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['all', 'over', 'the', 'world'], ['from', 'then', 'on']]
- Model analysis: Considered several candidate MWEs: 1) 'From then on' is a fixed adverbial phrase indicating time, conventionally used to signal the start of a new phase or period, hence marked as MWE. 2) 'all over the world' is a conventional expression implying global or widespread action; it is a stable idiomatic unit, thus marked as MWE. Other phrases like 'hosting magical events' and 'making new friends' are more compositional verb+noun phrases without strong idiomatic use, so they were not marked as MWEs.

### en:project_239:p8:s1

In the end, Emma's dreams came true in the most delightful way possible.

- Gold spans: [['came', 'true'], ['in', 'the', 'end']]
- Predicted spans: [['came', 'true'], ['in', 'the', 'most', 'delightful', 'way', 'possible']]
- Model analysis: Considered: 'In the end' is a fixed adverbial expression commonly used to denote conclusion; 'came true' is a phrasal verb expressing realization of dreams or wishes; 'in the most delightful way possible' is a fixed phrase often used to describe the positive manner in which something occurs, although it is longer, its cohesive usage with similar structure supports it as an MWE. Single or obviously compositional expressions like 'Emma's dreams' and 'the most delightful way possible' were not marked as MWEs by themselves as they are ordinary and compositional.

### en:project_239:p8:s3

Every day was a new adventure filled with laughter, magic, and love.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['filled', 'with', 'laughter', 'magic', 'and', 'love']]
- Model analysis: The expression 'filled with laughter, magic, and love' was considered as a candidate MWE. It is a fixed expression that conveys a specific, non-compositional meaning related to the presence of positive and whimsical elements. Although the separate elements ('laughter', 'magic', 'love') could be interpreted individually, their combination into a stable phrase indicates a conventionalized meaning in the context of describing an experience or scenario. The rest of the sentence elements, such as 'Every day was a new adventure', appear to be more compositional and straightforward in their interpretations, consisting of ordinary adjective+noun or verb+object structures.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['ever', 'after']]
- Model analysis: Candidate MWEs considered include 'happily, sparkly, and joyfully', and 'ever after'. 'Happily, sparkly, and joyfully' is a list of adverbs, likely combined for stylistic reasons, and lacks sufficient conventionalization as a unit. 'Ever after' is a fixed expression commonly used in narrations, especially in fairy tales, and has a recognized meaning beyond its parts. The translation supports 'pour toujours' as a phrase in French, confirming it as an MWE in English.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['use', 'of', 'definite', ',', 'indefinite', 'and', 'null', 'articles']]
- Model analysis: The main candidate for an MWE is 'Correct Use of Definite, Indefinite and Null Articles'. This expression functions as a conventional multi-word nominal phrase that expresses a specific concept about article usage. The phrase is lexicalized when discussing grammar or linguistics, particularly in educational or linguistic contexts. Other token groups were examined but did not meet the criteria as they were mostly basic noun phrases or compositional phrases with no special linguistic significance.

### en:project_245:p2:s2

Not only does he save lives, but he loves to teach proper English grammar.

- Gold spans: []
- Predicted spans: [['but', 'he', 'loves']]
- Model analysis: Candidate MWE 'Not only' is a common conjunction used to set up a sentence structure that will contrast with 'but'; it is conventionalized and requires the fixed pairing with 'but'. 'But he loves' is less conventional as an MWE on its own but could be seen as part of the complementary structure 'Not only... but (also)...'. Other parts like 'save lives' or 'teach proper English grammar' are more likely compositional verb-object phrases and not fixed MWEs.

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['stuck', 'in', 'a', 'tree']]
- Model analysis: Candidates considered: 'One day' is not an MWE as it is compositional (adj+noun). 'Stuck in a tree' is selected as an MWE because 'stuck in a tree' is a conventionalized expression to describe a common scenario with fixed word order. Other combinations are rejected due to being ordinary compositional verb+object or other typical constructions.

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['climbed', 'to', 'save', 'you']]
- Model analysis: Considered 'explained to the cat', but it's an ordinary compositional verb+object. Considered 'tree is what', but this is fully compositional with no evidence of idiomatic meaning. 'climbed to save you' is treated as a stable expression due to its conventional use as describing a rescue scenario, though it remains slightly compositional. The translation supports the cohesion of the entire thought.


## False-negative examples to inspect

### en:project_239:p2:s1

Once upon a time, in a small village in France, there was a lovely lady named Emma Bovary.

- Gold spans: [['once', 'upon', 'a', 'time']]
- Predicted spans: []
- Model analysis: Candidate MWEs considered: 'Once upon a time' is a fixed expression often used to start stories and does not vary in form. It fits the criteria for a stable, conventionalized multi-token expression. Other sequences like 'small village' or 'lovely lady' are compositional adjective+noun phrases and do not qualify as MWEs due to their openness and ordinary compositionality. The translation context provides evidence that 'Once upon a time' is a stable and conventionalized phrase, translated as 'Il était une fois'. This reinforces its status as an MWE.

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold spans: [['found', 'herself']]
- Predicted spans: [['sparkly', 'pink', 'unicorn']]
- Model analysis: The phrase 'sparkly pink unicorn' is considered as a stable lexical unit. It is a conventionalized expression that often appears as a single concept representing a whimsical or fantastical creature. Each adjective modifies 'unicorn,' but together they form a specific type of unicorn often recognized in pop culture or children's literature. The translation context also supports this as it keeps the adjectives and noun together. Other expressions in the sentence like 'found herself' or 'named Glitter' do not exhibit properties of idiomatic meaning or fixedness beyond their compositional meanings, so they were not marked as MWEs.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['fly', 'high', 'up'], ['magical', 'lands'], ['on', 'glitter', "'s", 'back']]
- Model analysis: Candidate expressions analyzed were: 'on Glitter's back' which is a conventionalized expression for riding on a specific entity; 'fly high up' as this forms a relatively fixed phrase to describe a motion in the sky; 'magical lands' considered as a more conventionalized location in fantasy contexts. Rejected candidates: 'Emma climbed' as it represents a straightforward subject-verb composition; 'into the sky' and 'visit magical lands' as they are relatively more compositional.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: []
- Model analysis: Considered 'Back at home' as an MWE: This expression serves as a fixed prepositional phrase indicating location with idiomatic usage, often functioning as a set phrase. No determiners or incidental modifiers were included as 'Back', 'at', and 'home' conventionally co-occur in this lexicalized structure. Other expressions (e.g., 'helping the people in the village') are more compositional and do not meet MWE criteria as they are easily interpretable by their individual components without fixed collocation or idiomatic meaning beyond the literal.

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: [['complete', 'with', 'her', 'favorite', 'treats'], ['in', 'the', 'park']]
- Model analysis: The expression 'in the park' was considered because it represents a stable locational phrase that is often used in English to denote a conventional place. Although it appears simple, it functions as a single concept. The phrase 'complete with her favorite treats' is common to indicate the inclusion of expected or extra elements that enhance an event or object. Despite the possibility of arguing compositionality, the phrase 'complete with' is a recognized pattern for such constructions and stabilizes the phrase.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: []
- Model analysis: Considered multi-word expressions: 'a wonderful time', 'playing games', 'telling stories'. 'A wonderful time' is selected as an MWE as it is a fixed expression often used to describe an enjoyable experience. It appeared in the French translation as 'un moment merveilleux', supporting its status as a fixed expression. 'Playing games' and 'telling stories' are not selected as MWEs; while they can occur together, they are more compositional and flexible, describing two separate and straightforward actions without additional idiomatic meaning.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['fairy-tale', 'boutique']]
- Model analysis: Considered 'grander things', 'fairy-tale boutique', 'magical potions', and 'enchanted dresses'. 'Grander things' was rejected as it is a standard compositional phrase combining an adjective and a noun. 'Magical potions' and 'enchanted dresses' are compositional adjective+noun pairs. 'Fairy-tale boutique' was selected as an MWE because it is a relatively fixed expression that describes a boutique themed or styled like a fairy tale, supported by the translation context as a lexicalized expression in French ('boutique de contes de fées').

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['from', 'all', 'over']]
- Model analysis: Candidates considered: 'Business was booming' - 'was booming' is selected as an idiomatic expression indicating rapid success; 'from all over' - a fixed expression denoting wide geographic origin, included as MWE. 'business' and 'shop' were not marked as MWEs, because they function as compositional noun phrases. Other verb phrases and combinations were either discarded due to high compositionality or did not form stable MWEs.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: []
- Model analysis: Considered 'One day', 'King and Queen', and 'heard about' as possible MWEs. 'One day' is a common time expression but too broad and compositional here. 'King and Queen' of France seems like an appropriate compound title but is still mainly compositional. 'Heard about' can be considered as a phrasal verb, but is quite general, without strong idiomatic binding. No MWEs identified according to strict criteria.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['all', 'over', 'the', 'world'], ['from', 'then', 'on']]
- Model analysis: Considered several candidate MWEs: 1) 'From then on' is a fixed adverbial phrase indicating time, conventionally used to signal the start of a new phase or period, hence marked as MWE. 2) 'all over the world' is a conventional expression implying global or widespread action; it is a stable idiomatic unit, thus marked as MWE. Other phrases like 'hosting magical events' and 'making new friends' are more compositional verb+noun phrases without strong idiomatic use, so they were not marked as MWEs.

### en:project_239:p8:s1

In the end, Emma's dreams came true in the most delightful way possible.

- Gold spans: [['came', 'true'], ['in', 'the', 'end']]
- Predicted spans: [['came', 'true'], ['in', 'the', 'most', 'delightful', 'way', 'possible']]
- Model analysis: Considered: 'In the end' is a fixed adverbial expression commonly used to denote conclusion; 'came true' is a phrasal verb expressing realization of dreams or wishes; 'in the most delightful way possible' is a fixed phrase often used to describe the positive manner in which something occurs, although it is longer, its cohesive usage with similar structure supports it as an MWE. Single or obviously compositional expressions like 'Emma's dreams' and 'the most delightful way possible' were not marked as MWEs by themselves as they are ordinary and compositional.

### en:project_239:p8:s3

Every day was a new adventure filled with laughter, magic, and love.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['filled', 'with', 'laughter', 'magic', 'and', 'love']]
- Model analysis: The expression 'filled with laughter, magic, and love' was considered as a candidate MWE. It is a fixed expression that conveys a specific, non-compositional meaning related to the presence of positive and whimsical elements. Although the separate elements ('laughter', 'magic', 'love') could be interpreted individually, their combination into a stable phrase indicates a conventionalized meaning in the context of describing an experience or scenario. The rest of the sentence elements, such as 'Every day was a new adventure', appear to be more compositional and straightforward in their interpretations, consisting of ordinary adjective+noun or verb+object structures.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['ever', 'after']]
- Model analysis: Candidate MWEs considered include 'happily, sparkly, and joyfully', and 'ever after'. 'Happily, sparkly, and joyfully' is a list of adverbs, likely combined for stylistic reasons, and lacks sufficient conventionalization as a unit. 'Ever after' is a fixed expression commonly used in narrations, especially in fairy tales, and has a recognized meaning beyond its parts. The translation supports 'pour toujours' as a phrase in French, confirming it as an MWE in English.

### en:project_239:p8:s5

The end.

- Gold spans: [['the', 'end']]
- Predicted spans: []
- Model analysis: The expression 'the end' is commonly used in English as a fixed noun phrase to indicate the conclusion of a text, such as a book or movie. However, 'the end' is often seen as compositional, consisting of a typical determiner + noun structure. Despite its frequent use in specific contexts, it is not strongly idiomatic or conventionally lexicalized enough to be considered a multi-word expression by more rigorous criteria. Therefore, no MWEs have been marked.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['use', 'of', 'definite', ',', 'indefinite', 'and', 'null', 'articles']]
- Model analysis: The main candidate for an MWE is 'Correct Use of Definite, Indefinite and Null Articles'. This expression functions as a conventional multi-word nominal phrase that expresses a specific concept about article usage. The phrase is lexicalized when discussing grammar or linguistics, particularly in educational or linguistic contexts. Other token groups were examined but did not meet the criteria as they were mostly basic noun phrases or compositional phrases with no special linguistic significance.

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['stuck', 'in', 'a', 'tree']]
- Model analysis: Candidates considered: 'One day' is not an MWE as it is compositional (adj+noun). 'Stuck in a tree' is selected as an MWE because 'stuck in a tree' is a conventionalized expression to describe a common scenario with fixed word order. Other combinations are rejected due to being ordinary compositional verb+object or other typical constructions.

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['climbed', 'to', 'save', 'you']]
- Model analysis: Considered 'explained to the cat', but it's an ordinary compositional verb+object. Considered 'tree is what', but this is fully compositional with no evidence of idiomatic meaning. 'climbed to save you' is treated as a stable expression due to its conventional use as describing a rescue scenario, though it remains slightly compositional. The translation supports the cohesion of the entire thought.

### en:project_245:p4:s3

The dog wagged its tail, clearly pleased with the lesson.

- Gold spans: [['pleased', 'with']]
- Predicted spans: []
- Model analysis: Considered the expression 'wagged its tail' as a candidate MWE. It is identified as a phrasal verb with a fixed usage to describe the action of a dog's tail moving back and forth, conventionally recognized as a singular unit of meaning. Other segments like 'clearly pleased' were rejected because they are ordinary adjective+past participle combinations. The prepositional phrase 'with the lesson' was also rejected for being a compositional verb+prepositional object construction.

### en:project_245:p5:s3

Felix replied, "Thank you!

- Gold spans: [['thank', 'you']]
- Predicted spans: []
- Model analysis: Considered 'Thank you !' as a candidate MWE. It's a fixed expression often used as a polite remark to express gratitude, not fully compositional since 'Thank' and 'you' together form a conventional expression beyond their literal meanings. Final decision: Mark 'Thank you !' as a fixed, conventional expression; no other MWEs in this segment.

### en:project_245:p6:s4

Felix asked, emphasizing ‘the barbecue’ they both knew about.

- Gold spans: [['knew', 'about']]
- Predicted spans: [['emphasizing', 'the', 'barbecue'], ['they', 'both', 'knew', 'about']]
- Model analysis: For MWE (1), 'emphasizing the barbecue' seems like a fixed expression given the context emphasis on 'the barbecue' they both knew, as indicated by the translation segment emphasizing this noun phrase. For MWE (2), 'they both knew about' forms a stable unit due to the collective knowledge portrayed; however, it could also be seen as compositional. Due to the context provided, both expressions are considered as they appear to convey a fixed meaning.

