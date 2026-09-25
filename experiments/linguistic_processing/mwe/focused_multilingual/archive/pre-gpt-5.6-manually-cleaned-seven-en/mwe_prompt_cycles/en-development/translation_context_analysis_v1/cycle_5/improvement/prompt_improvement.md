# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.190
- Recall: 0.383
- F1: 0.254

## General revision principles

- Mark an MWE only when the expression is conventionalized, idiomatic, lexicalized, or functions as a stable multi-token lexical unit.
- Do not mark ordinary compositional adjective+noun, determiner+noun, or verb+object phrases just because they are frequent in the text.
- Prefer high precision: when unsure, leave tokens unmarked rather than inventing an MWE.
- Keep labels broad and language-neutral; avoid rules tied to a single project or named example.
- Preserve the input token sequence exactly and only add MWE IDs to tokens that belong to accepted multi-token expressions.

## False-positive examples to inspect

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['fly', 'high', 'up', 'into']]
- Model analysis: Considered various candidates: 'climbed on' is compositional (verb+prep). 'Fly high up into' functions as a verb and required particle/preposition pattern and is conventionalized as 'fly high up into the sky'. 'Magical lands' is compositional due to adjective+noun structure. Selected 'fly high up into' as MWE for its stability and requirement of particles/prepositions.

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold spans: []
- Predicted spans: [['tea', 'parties']]
- Model analysis: The candidate MWEs considered include 'flew over', 'rainbow waterfalls', 'danced with', 'enchanted forests', 'tea parties', and 'talking animals'. 'Tea parties' was marked as an MWE because it is a conventionalized compound noun frequently used to describe a certain type of social gathering. 'Flew over', 'danced with', 'rainbow waterfalls', 'enchanted forests', and 'talking animals' were rejected as MWEs as they are compositional in this context, with no strong evidence of being conventional or idiomatic expressions.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['back', 'at', 'home']]
- Model analysis: Considered 'Back at home' as a fixed adverbial phrase indicating a return to one's own residence. It is a stable expression commonly used as a discourse marker or narrative opening. Rejected 'helping the people', 'in the village', and other phrases as they are compositional and do not form conventionalized expressions.

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold spans: []
- Predicted spans: [['in', 'all', 'her', 'grand', 'adventures']]
- Model analysis: Considered 'loved to see' as a potential light-verb expression, but found it compositional and rejected. 'Supported her in all her grand adventures' was reviewed; marked 'in all her grand adventures' as a fixed temporal/spatial adverbial indicating a broad support context, common in usage. Excluded pre 'supported her' as compositional verb-object.

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: [['with', 'complete', 'with']]
- Model analysis: Considered 'complete with' as a multi-word expression based on the conventionalized use of 'complete with' meaning 'including'. Excluded other phrases since they appeared compositional. The MWE 'complete with' is commonly used to indicate inclusion of certain items and is idiomatic.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['decided', 'to'], ['fairy-tale', 'boutique'], ['of', 'grander', 'things']]
- Model analysis: Considered 'of grander things' as a fixed expression since it implies an idiomatic phrase of dreaming about things beyond the ordinary. 'Decided to' often represents a lexical pattern where 'decided' is conventionally followed by 'to' in English. 'Fairy-tale boutique' is marked as a compound noun, as it describes a specific type of shop using a conventionalized modifier.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['from', 'all', 'over']]
- Model analysis: Considered 'from all over' as a candidate because it is a fixed adverbial phrase indicating a wide extent or reach, often used to describe people coming from various places. Accepted this MWE. No other combinations in the sentence form recognizable MWEs according to guidelines.

### en:project_239:p6:s3

Emma became famous for her sparkling personality and beautiful shop.

- Gold spans: []
- Predicted spans: [['famous', 'for']]
- Model analysis: Considered 'famous for' as a candidate MWE since it is a conventionalized pattern where 'famous' requires the preposition 'for' to indicate the reason for fame. Rest of the text has ordinary compositional phrases with no other idiomatic or stable multi-word expressions.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold spans: []
- Predicted spans: [['tea', 'party']]
- Model analysis: Considered plausible candidates: 'grand palace', 'tea party'. 'Tea party' is marked as a fixed expression because it denotes a conventional social event and functions as a lexicalized compound. 'Grand palace' was rejected as an MWE because it appears compositional, combining descriptively and does not meet the criteria of idiomatic or strong lexicalization beyond the immediate context.

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold spans: []
- Predicted spans: [['royal', 'adventure', 'planner']]
- Model analysis: Considered 'Royal Adventure Planner' as a candidate. It is a strongly lexicalized compound naming a common established role. Not a compositional phrase and the lexical components are typically used together, often capitalized to indicate a formal title. Rejected other compositional phrases such as 'King and Queen' and 'so impressed that' as they are neither idiomatic nor fixed.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['all', 'over', 'the', 'world'], ['from', 'then', 'on']]
- Model analysis: Considered 'From then on' as a fixed adverbial phrase indicating a specific time reference, which is conventionally used in English. 'All over the world' was identified as a fixed expression commonly used to describe global extent or coverage. Both expressions are idiomatic and stable, fitting the criteria for MWEs. Other parts such as 'hosting magical events' or 'making new friends' are more compositional and context-specific, not meeting necessary criteria for MWEs.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['ever', 'after']]
- Model analysis: Considered 'ever after' as a candidate MWE, which is a conventional idiomatic phrase used in story conclusions and thus marked as a fixed idiom. Other segments like 'lived happily' and 'happily, sparkly, and joyfully' were rejected as they are compositional and descriptive.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['use', 'of']]
- Model analysis: Considered 'First Responder' and found it to be a strongly lexicalized compound referring to a specific established role, thus marked as a noun phrase. 'Correct Use of Definite, Indefinite, and Null Articles' was broken down to consider 'Use of' as a potential MWE. However, only 'Use of' was marked as it represents a fixed prepositional pattern, typically seen in expressions about application or utilization. Other phrases, such as 'Correct Use' and 'Definite, Indefinite, and Null Articles,' were deemed compositional and specific to this context.

### en:project_245:p2:s2

Not only does he save lives, but he loves to teach proper English grammar.

- Gold spans: []
- Predicted spans: [['not', 'only']]
- Model analysis: Considered 'Not only' as a fixed expression: a common phrase used in conjunction with a coordinating structure 'but also'. It is idiomatic and fixed in its usage, so it was marked as an MWE. The rest of the sentence appears to be compositional with no additional MWEs found.

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['stuck', 'in'], ['used', 'downtime']]
- Model analysis: Considered 'One day' as a conventional temporal expression often used to begin stories or sentences; selected it as an MWE. 'Stuck in' was chosen as a verb+particle pattern because 'stuck' often requires 'in' to indicate a situation. 'Used downtime' is selected as it functions as a light verb expression where 'used' works with 'downtime' to convey a specific meaning of using one's spare time.

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['to', 'save']]
- Model analysis: Considered: 'to save' as a potential light-verb expression. 'To save' is a common phrase where 'to' is necessary to form the infinitive verb structure. Other phrases like 'explained to' or 'climbed to save' were considered compositional as they follow ordinary syntax and semantics in this context. 'To save' was deemed appropriate for marking due to its fixed structure in such an expression.

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold spans: [['a', 'little']]
- Predicted spans: [['understanding', 'a', 'little', 'better']]
- Model analysis: Considered 'understanding a little better' as a potential MWE. It functions as a degree or quantity expression indicating slight improvement in understanding, which is conventional and stable enough to be considered a multi-word expression.

### en:project_245:p4:s1

When Felix saw a dog, he said, "The dog is happy to see me.

- Gold spans: []
- Predicted spans: [['to', 'see']]
- Model analysis: Considered 'happy to see' as a potential MWE. However, 'happy' is a common adjective that can take various complements, and 'to see' forms a coherent unit often used together, suggesting 'to see' is a required particle pattern common in English.

### en:project_245:p5:s1

A little girl approached Felix to thank him.

- Gold spans: []
- Predicted spans: [['to', 'thank']]
- Model analysis: Considered 'to thank' as a candidate because it is a common verb + infinitive structure. It is treated as an MWE here due to its conventional use in this context. The other token groups were straightforward and did not constitute MWEs. 'A little girl' and 'approached Felix' are compositional and do not meet MWE criteria.

### en:project_245:p5:s5

'A' can mean any hero."

- Gold spans: []
- Predicted spans: [['any', 'hero']]
- Model analysis: Considered 'any hero' as an MWE. It is a strongly lexicalized compound often used as a set phrase to refer to an unspecified hero, making it a good candidate for marking. Excluded 'A can mean' as it appears more compositional and does not have the same stable idiomatic sense.


## False-negative examples to inspect

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold spans: [['found', 'herself']]
- Predicted spans: []
- Model analysis: Considered whether any parts of the sentence form MWEs. The phrase 'sparkly pink unicorn' was examined but found to be a compositional adjective + noun phrase describing a specific type of unicorn, not a fixed expression. No other plausible multi-word expressions present considering the given guidelines.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['fly', 'high', 'up', 'into']]
- Model analysis: Considered various candidates: 'climbed on' is compositional (verb+prep). 'Fly high up into' functions as a verb and required particle/preposition pattern and is conventionalized as 'fly high up into the sky'. 'Magical lands' is compositional due to adjective+noun structure. Selected 'fly high up into' as MWE for its stability and requirement of particles/prepositions.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['back', 'at', 'home']]
- Model analysis: Considered 'Back at home' as a fixed adverbial phrase indicating a return to one's own residence. It is a stable expression commonly used as a discourse marker or narrative opening. Rejected 'helping the people', 'in the village', and other phrases as they are compositional and do not form conventionalized expressions.

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: [['with', 'complete', 'with']]
- Model analysis: Considered 'complete with' as a multi-word expression based on the conventionalized use of 'complete with' meaning 'including'. Excluded other phrases since they appeared compositional. The MWE 'complete with' is commonly used to indicate inclusion of certain items and is idiomatic.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: []
- Model analysis: Considered 'a wonderful time' as a candidate. This phrase is a fixed expression commonly used to convey the idea of having an enjoyable experience. The translation context also reflects it as 'un moment merveilleux', indicating a strong fixed sense. No other MWEs were identified in the text as all other phrases appear to be compositional or straightforward descriptions without idiomatic meaning.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['decided', 'to'], ['fairy-tale', 'boutique'], ['of', 'grander', 'things']]
- Model analysis: Considered 'of grander things' as a fixed expression since it implies an idiomatic phrase of dreaming about things beyond the ordinary. 'Decided to' often represents a lexical pattern where 'decided' is conventionally followed by 'to' in English. 'Fairy-tale boutique' is marked as a compound noun, as it describes a specific type of shop using a conventionalized modifier.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['from', 'all', 'over']]
- Model analysis: Considered 'from all over' as a candidate because it is a fixed adverbial phrase indicating a wide extent or reach, often used to describe people coming from various places. Accepted this MWE. No other combinations in the sentence form recognizable MWEs according to guidelines.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: []
- Model analysis: Candidates considered were 'heard about', 'King and Queen', 'Queen of France'. 'Heard about' was marked as a verb+particle MWE because 'about' is a required function word in this meaning. 'King and Queen' and 'Queen of France' were rejected as they are compositional titles and not conventionalized MWEs.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['all', 'over', 'the', 'world'], ['from', 'then', 'on']]
- Model analysis: Considered 'From then on' as a fixed adverbial phrase indicating a specific time reference, which is conventionally used in English. 'All over the world' was identified as a fixed expression commonly used to describe global extent or coverage. Both expressions are idiomatic and stable, fitting the criteria for MWEs. Other parts such as 'hosting magical events' or 'making new friends' are more compositional and context-specific, not meeting necessary criteria for MWEs.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: []
- Model analysis: Considered the phrase "happily ever after" as a candidate since it is a conventionalized idiom with a stable form often used to signify a fairytale-like ending. No other combinations in the sentence appeared to be multi-word expressions by the defined criteria, as "with Charles, Glitter, and all their new friends" is compositional and not idiomatic.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['ever', 'after']]
- Model analysis: Considered 'ever after' as a candidate MWE, which is a conventional idiomatic phrase used in story conclusions and thus marked as a fixed idiom. Other segments like 'lived happily' and 'happily, sparkly, and joyfully' were rejected as they are compositional and descriptive.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['use', 'of']]
- Model analysis: Considered 'First Responder' and found it to be a strongly lexicalized compound referring to a specific established role, thus marked as a noun phrase. 'Correct Use of Definite, Indefinite, and Null Articles' was broken down to consider 'Use of' as a potential MWE. However, only 'Use of' was marked as it represents a fixed prepositional pattern, typically seen in expressions about application or utilization. Other phrases, such as 'Correct Use' and 'Definite, Indefinite, and Null Articles,' were deemed compositional and specific to this context.

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['to', 'save']]
- Model analysis: Considered: 'to save' as a potential light-verb expression. 'To save' is a common phrase where 'to' is necessary to form the infinitive verb structure. Other phrases like 'explained to' or 'climbed to save' were considered compositional as they follow ordinary syntax and semantics in this context. 'To save' was deemed appropriate for marking due to its fixed structure in such an expression.

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold spans: [['a', 'little']]
- Predicted spans: [['understanding', 'a', 'little', 'better']]
- Model analysis: Considered 'understanding a little better' as a potential MWE. It functions as a degree or quantity expression indicating slight improvement in understanding, which is conventional and stable enough to be considered a multi-word expression.

### en:project_245:p6:s4

Felix asked, emphasizing ‘the barbecue’ they both knew about.

- Gold spans: [['knew', 'about']]
- Predicted spans: []
- Model analysis: Considered 'emphasizing ‘ the barbecue ’ they both knew about'. Only 'knew about' has a potential fixed verb+particle pattern as it often denotes familiarization or awareness and is used conventionally in English. Other parts of the sentence seem compositional and context-specific, thus not meeting criteria for MWEs as per guidance.

### en:project_245:p7:s3

"An apple a day keeps the doctor away," he mused.

- Gold spans: [['keeps', 'away']]
- Predicted spans: [['an', 'apple', 'a', 'day', 'keeps', 'the', 'doctor', 'away']]
- Model analysis: Considered 'An apple a day keeps the doctor away' as a potential MWE. It is a well-known English idiom and proverb recognized as a conventionalized expression, encouraging healthy eating habits by suggesting that eating an apple daily can keep one in good health. Thus, it qualifies as an idiom and was selected as an MWE. No other MWEs found in the segment.

### en:project_245:p8:s2

Felix corrected, "I'm a first responder.

- Gold spans: [['first', 'responder']]
- Predicted spans: [['a', 'first', 'responder']]
- Model analysis: Considered 'a first responder' as a candidate for lexicalized compound. It is a strongly lexicalized compound naming an established role. Excluded the other tokens as they are not part of any conventionalized or idiomatic phrase.

### en:project_245:p9:s3

The kids all looked up in wonder.

- Gold spans: [['in', 'wonder'], ['looked', 'up']]
- Predicted spans: [['looked', 'up']]
- Model analysis: Considered 'looked up' and 'looked up in wonder' as potential MWEs. 'Looked up' is identified as a conventional verb + particle pattern meaning to physically turn one's gaze upwards or search for information, and is confirmed by translation context 'levé les yeux'. 'Looked up in wonder' was not selected as it adds a descriptive extension to the existing particle verb, which 'looked up' covers sufficiently.

### en:project_245:p15:s3

"Any car will do."

- Gold spans: [['will', 'do']]
- Predicted spans: []
- Model analysis: Considered 'Any car will do.' as a possible fixed expression. The sequence 'will do' was identified as a light-verb expression, which forms a conventional phrase meaning 'is acceptable' or 'suffices.' Therefore, 'will do' was marked as an MWE since it functions as a unit in contexts like optional choices or sufficiency.

### en:project_245:p16:s2

Felix grinned and said, "We don't use articles before languages or nationalities.

- Gold spans: [['don', "'", 't']]
- Predicted spans: [['languages', 'or', 'nationalities'], ['we', 'don', "'", 't']]
- Model analysis: Considered 'don't' as an MWE since it is a conventional contraction for negation, hence 'We don ' t' marked as negation. Considered 'use articles before languages or nationalities' as a possible MWE, but ultimately rejected this longer span as it is an explanation, not a fixed expression. 'Languages or nationalities' functions as a conventional coordinate phrase within context, slightly more established compared to individual compositional analysis.

