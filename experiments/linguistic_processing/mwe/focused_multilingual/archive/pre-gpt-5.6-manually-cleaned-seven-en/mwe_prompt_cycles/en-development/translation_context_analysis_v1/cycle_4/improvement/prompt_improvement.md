# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.244
- Recall: 0.429
- F1: 0.311

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
- Model analysis: Madame Bovary considered as a candidate due to its use as a recognized proper name in literature. While it's a title and typically excluded, it's also a common lexical reference to a specific literature character and novel, thus accepted as a fixed expression.

### en:project_239:p2:s2

Emma lived in a beautiful house with her husband, Charles, who was a kind and gentle doctor.

- Gold spans: []
- Predicted spans: [['with', 'her', 'husband']]
- Model analysis: Considered 'with her husband' as a candidate. It is a common phrase referring to the concept of living together with a spouse and is slightly idiomatic in nature. Despite being slightly compositional, it has a relatively conventionalized usage. 'Kind and gentle doctor' was rejected as it is purely descriptive.

### en:project_239:p2:s3

Although Emma had everything she needed, she often dreamed of more exciting adventures.

- Gold spans: [['dreamed', 'of']]
- Predicted spans: [['of', 'more', 'exciting', 'adventures']]
- Model analysis: The segment contains the phrase 'of more exciting adventures'. This can be considered as a conventional expression that functions as a fixed phrase indicating a desire for greater excitement. While 'exciting adventures' could be seen as compositional, the inclusion of 'of more' creates a contextually stable expression that reflects the desire for something beyond the ordinary, hence it is marked as a lexical compound. Other potential candidates were assessed but found to be compositional, such as 'Emma had everything she needed', which forms a standard descriptive sentence without idiomatic meaning.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['little', 'bit']]
- Model analysis: Considered 'little bit' as a candidate. It is a conventional expression meaning a small amount, often used as a degree expression, thus marking it as an MWE. Excluded 'One sunny day' as it is a compositional phrase describing a time context. 'Decided she wanted' is a typical verb construction, not an MWE. 'In her life' is a typical prepositional phrase, not an MWE.

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold spans: []
- Predicted spans: [['tea', 'parties']]
- Model analysis: Considered 'rainbow waterfalls' and 'enchanted forests', but they are compositional adjective+noun pairs. 'Tea parties' could be a light-verb expression indicating a conventional social gathering, hence marked as a fixed expression.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['back', 'at', 'home']]
- Model analysis: Considered 'Back at home' as a candidate. It was accepted as a fixed adverbial expression indicating a location or state, commonly used in English to refer to being in one's home area, often after being away. Other parts of the segment were evaluated but found to be ordinary compositional phrases, thus not marked.

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold spans: []
- Predicted spans: [['all', 'her', 'grand', 'adventures']]
- Model analysis: Considered 'all her grand adventures' as a MWE due to its potential as a conventional phrase indicating a type of established or recognized exploration or series of daring activities. It combines a common pattern for indicating scope ('all') with a descriptor ('grand') and noun ('adventures'), which often appears together in literary contexts.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['fairy-tale', 'boutique']]
- Model analysis: Considered 'fairy-tale boutique' as a candidate for MWE due to its established use as a lexical compound describing a specific type of boutique. The expression is idiomatic and represents a conventionalized category, distinct from ordinary compositional noun phrases. No other expressions in the segment displayed similar lexicalized or idiomatic usage.

### en:project_239:p6:s3

Emma became famous for her sparkling personality and beautiful shop.

- Gold spans: []
- Predicted spans: [['beautiful', 'shop'], ['sparkling', 'personality']]
- Model analysis: Examined 'sparkling personality' and 'beautiful shop'. These are conventional compound nouns describing established categories: a lively personality and an aesthetically pleasing shop, respectively. Rejected other candidates such as 'became famous for' as they appeared to be compositional.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: [['emma', 'bovary'], ['king', 'queen', 'of', 'france']]
- Model analysis: Candidates considered: 'King and Queen of France', 'Emma Bovary'. 'King and Queen of France' could be a composite proper noun; however, 'King of France' and 'Queen of France' are common conventional roles, so 'King and Queen of France' could collectively be considered a lexicalized expression, marking 'King Queen of France' as such. 'Emma Bovary' is a proper noun, usually avoided, but contextually it is the known main character name from literature, treated as an established lexical unit in contexts discussing that work.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold spans: []
- Predicted spans: [['grand', 'palace'], ['tea', 'party']]
- Model analysis: Considered 'grand palace' and 'tea party' as candidate MWEs. 'Grand palace' is a common lexical compound indicating a specific type of building, accepted. 'Tea party' is also a common lexical compound used to denote a social event focused on tea, accepted. Other combinations such as 'special tea' or 'invited to' were considered compositional and not accepted as MWEs.

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold spans: []
- Predicted spans: [['royal', 'adventure', 'planner']]
- Model analysis: Considered 'Royal Adventure Planner' as a candidate MWE. It functions as a common lexical compound naming an established role. The compound is a conventionalized phrase used to denote a specific position or title, fitting the category of common lexical compounds describing roles. No evidence of additional MWEs in other parts of the text such as 'The King and Queen' which are proper names and not lexical expressions in the target sense.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['all', 'over', 'the', 'world'], ['from', 'then', 'on']]
- Model analysis: Considered 'From then on' as a fixed temporal expression marking a start point; it is a conventionalized phrase with a stable meaning, thus marked. Considered 'all over the world' as it is a common lexical expression indicating widespread travel; it is fixed and non-compositional, hence marked. 'hosting magical events and making new friends' were considered but deemed compositional and not stable, lexicalized expressions.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['happily', 'ever', 'after']]
- Model analysis: Considered the expression 'happily ever after', which is a fixed idiom typically used to indicate a storybook or fairy tale ending. It is a conventionalized expression and thus marked as an MWE. Other parts of the sentence were either proper nouns or compositional and did not form fixed expressions.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['ever', 'after']]
- Model analysis: Considered the phrase 'ever after' as a candidate for MWE. It is a fixed and conventional expression often used in storytelling to indicate a happily continued state, usually following a tale's conclusion. Despite additional adjectives and commas within the sentence, 'ever after' remains a standalone expression with a stable meaning, traditionally translated in French as 'pour toujours'. Optional descriptive adjectives ('happily', 'sparkly', 'joyfully') are not part of this core fixed expression and were therefore not included in the MWE.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['first', 'responder'], ['use', 'of', 'definite', 'indefinite', 'and', 'null', 'articles']]
- Model analysis: Considered 'First Responder' as a compound that refers to a role commonly understood in English, so it's marked as a fixed compound. The 'Use of Definite, Indefinite and Null Articles' could be seen as a compositional sequence but is marked due to its long-standing conventional usage in discussions of grammar. However, included the minimal span necessary for the expression.

### en:project_245:p2:s2

Not only does he save lives, but he loves to teach proper English grammar.

- Gold spans: []
- Predicted spans: [['not', 'only']]
- Model analysis: Considered 'Not only' as a potential MWE because it forms a fixed expression often used to introduce additive or emphatic information. It's a linguistic formula that serves a specific discourse function. The word 'but' is often paired with 'Not only' in conventional structures such as 'Not only... but also'. However, in this context, 'but' functions as a separate discourse connector. No other MWEs were identified as the rest of the phrases are compositional.

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['in', 'tree']]
- Model analysis: Considered 'stuck in a tree' as a candidate. Focused on 'in a tree' as a lexicalized pattern to describe a situation where something is lodged in a tree, which is a common and recognized condition. Excluded 'stuck' as it is a description rather than a fixed part of the multi-word expression. Other parts of the sentence are compositional and do not form conventionalized expressions. 'Downtime' seems like a lexical compound but is a single token here, and 'explaining articles' is compositional.

### en:project_245:p3:s2

'A' is an indefinite article."

- Gold spans: []
- Predicted spans: [['indefinite', 'article']]
- Model analysis: Candidates considered include 'indefinite article'. It represents a fixed category term in grammar description. Accepted because it's a common and established category name.

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold spans: [['a', 'little']]
- Predicted spans: [['a', 'little', 'better']]
- Model analysis: Examined the phrases 'a little better' and 'understanding a little better now'. 'A little better' can be considered an idiomatic expression for minor improvement or understanding and thus marked as an MWE. 'Understanding a little better now' was considered but rejected as it is more of a compositional phrase showing the action of the verb.


## False-negative examples to inspect

### en:project_239:p2:s3

Although Emma had everything she needed, she often dreamed of more exciting adventures.

- Gold spans: [['dreamed', 'of']]
- Predicted spans: [['of', 'more', 'exciting', 'adventures']]
- Model analysis: The segment contains the phrase 'of more exciting adventures'. This can be considered as a conventional expression that functions as a fixed phrase indicating a desire for greater excitement. While 'exciting adventures' could be seen as compositional, the inclusion of 'of more' creates a contextually stable expression that reflects the desire for something beyond the ordinary, hence it is marked as a lexical compound. Other potential candidates were assessed but found to be compositional, such as 'Emma had everything she needed', which forms a standard descriptive sentence without idiomatic meaning.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['little', 'bit']]
- Model analysis: Considered 'little bit' as a candidate. It is a conventional expression meaning a small amount, often used as a degree expression, thus marking it as an MWE. Excluded 'One sunny day' as it is a compositional phrase describing a time context. 'Decided she wanted' is a typical verb construction, not an MWE. 'In her life' is a typical prepositional phrase, not an MWE.

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold spans: [['took', 'a', 'walk']]
- Predicted spans: []
- Model analysis: not recorded

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: []
- Model analysis: Considered 'climbed on' and 'fly high up' for MWEs. Chose 'on back' as a conventional expression for mounting or riding, often used in fixed contexts. 'High up' is a common adverbial phrase indicating direction or location. 'Climbed on Glitter's back' seems compositional otherwise. 'Fly high up' focuses on 'high up' as being more fixed, omitting the verb for precision.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['back', 'at', 'home']]
- Model analysis: Considered 'Back at home' as a candidate. It was accepted as a fixed adverbial expression indicating a location or state, commonly used in English to refer to being in one's home area, often after being away. Other parts of the segment were evaluated but found to be ordinary compositional phrases, thus not marked.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: []
- Model analysis: not recorded

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['fairy-tale', 'boutique']]
- Model analysis: Considered 'fairy-tale boutique' as a candidate for MWE due to its established use as a lexical compound describing a specific type of boutique. The expression is idiomatic and represents a conventionalized category, distinct from ordinary compositional noun phrases. No other expressions in the segment displayed similar lexicalized or idiomatic usage.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: [['emma', 'bovary'], ['king', 'queen', 'of', 'france']]
- Model analysis: Candidates considered: 'King and Queen of France', 'Emma Bovary'. 'King and Queen of France' could be a composite proper noun; however, 'King of France' and 'Queen of France' are common conventional roles, so 'King and Queen of France' could collectively be considered a lexicalized expression, marking 'King Queen of France' as such. 'Emma Bovary' is a proper noun, usually avoided, but contextually it is the known main character name from literature, treated as an established lexical unit in contexts discussing that work.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['all', 'over', 'the', 'world'], ['from', 'then', 'on']]
- Model analysis: Considered 'From then on' as a fixed temporal expression marking a start point; it is a conventionalized phrase with a stable meaning, thus marked. Considered 'all over the world' as it is a common lexical expression indicating widespread travel; it is fixed and non-compositional, hence marked. 'hosting magical events and making new friends' were considered but deemed compositional and not stable, lexicalized expressions.

### en:project_239:p8:s1

In the end, Emma's dreams came true in the most delightful way possible.

- Gold spans: [['came', 'true'], ['in', 'the', 'end']]
- Predicted spans: [['came', 'true']]
- Model analysis: Considered 'In the end' as a candidate but narrowed it to 'end' as it forms a common fixed adverbial structure known as a conclusion or closure phrase. 'Came true' was marked as it functions as an established phrasal verb indicating the realization of dreams or wishes. No other multi-word expressions identified as they are either compositional or modified.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['happily', 'ever', 'after']]
- Model analysis: Considered the expression 'happily ever after', which is a fixed idiom typically used to indicate a storybook or fairy tale ending. It is a conventionalized expression and thus marked as an MWE. Other parts of the sentence were either proper nouns or compositional and did not form fixed expressions.

### en:project_239:p8:s3

Every day was a new adventure filled with laughter, magic, and love.

- Gold spans: [['filled', 'with']]
- Predicted spans: []
- Model analysis: Considered 'filled with', which is a common phrasal verb structure, but decided not to mark because 'filled with' does not form a conventional light verb expression or idiomatic expression in this context. No other conventionalized multi-word expressions were identified in the given segment.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['ever', 'after']]
- Model analysis: Considered the phrase 'ever after' as a candidate for MWE. It is a fixed and conventional expression often used in storytelling to indicate a happily continued state, usually following a tale's conclusion. Despite additional adjectives and commas within the sentence, 'ever after' remains a standalone expression with a stable meaning, traditionally translated in French as 'pour toujours'. Optional descriptive adjectives ('happily', 'sparkly', 'joyfully') are not part of this core fixed expression and were therefore not included in the MWE.

### en:project_245:p2:s1

Hunky Felix is a fearless first responder.

- Gold spans: [['first', 'responder']]
- Predicted spans: []
- Model analysis: Considered 'fearless first responder' as a potential MWE but 'fearless' is an adjective that can be used flexibly with various nouns. 'First responder', however, is a conventional lexical compound naming a role, thus marked as an MWE.

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['in', 'tree']]
- Model analysis: Considered 'stuck in a tree' as a candidate. Focused on 'in a tree' as a lexicalized pattern to describe a situation where something is lodged in a tree, which is a common and recognized condition. Excluded 'stuck' as it is a description rather than a fixed part of the multi-word expression. Other parts of the sentence are compositional and do not form conventionalized expressions. 'Downtime' seems like a lexical compound but is a single token here, and 'explaining articles' is compositional.

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: []
- Model analysis: Considered 'explained to' as a potential MWE, but this is a common verb + preposition construction and not fixed. Considered 'climbed to save you' but found only 'save you' as a light-verb expression, capturing a fixed pattern in English where 'save' frequently combines with a pronoun like 'you'.

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold spans: [['a', 'little']]
- Predicted spans: [['a', 'little', 'better']]
- Model analysis: Examined the phrases 'a little better' and 'understanding a little better now'. 'A little better' can be considered an idiomatic expression for minor improvement or understanding and thus marked as an MWE. 'Understanding a little better now' was considered but rejected as it is more of a compositional phrase showing the action of the verb.

### en:project_245:p6:s4

Felix asked, emphasizing ‘the barbecue’ they both knew about.

- Gold spans: [['knew', 'about']]
- Predicted spans: []
- Model analysis: Considered 'emphasizing the barbecue' as a potential MWE due to its idiomatic structure. However, 'emphasizing' is used in a compositional sense here, and 'the barbecue' seems to refer to a specific known event rather than an idiomatic expression. No stable, idiomatic, or conventionalized expressions found within token boundaries.

### en:project_245:p7:s3

"An apple a day keeps the doctor away," he mused.

- Gold spans: [['keeps', 'away']]
- Predicted spans: []
- Model analysis: Considered 'An apple a day keeps the doctor away' as a plausible MWE. It's a fixed, idiomatic expression with a widely recognized meaning beyond the literal composition of its parts, thus marked as an MWE. Other tokens do not form conventionalized expressions.

### en:project_245:p8:s3

'An' is used before an amazing adjective starting with a vowel."

- Gold spans: [['starting', 'with']]
- Predicted spans: [["'an'", 'before'], ['an', 'with']]
- Model analysis: Considered 'An' before as a fixed expression recognizing the use of 'An' before vowel sounds, marking it as an MWE. 'an with' identified as a preposition pattern common in explaining the grammatical rule of using 'an' with vowel starting words.

