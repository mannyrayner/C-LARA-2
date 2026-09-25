# MWE prompt score summary

- Split: `development`
- Records: 336
- Exact match: 149 (44.3%)
- Precision: 0.276
- Recall: 0.434
- F1: 0.338

## Error examples

### en:project_239:p1:s2

Madame Bovary retold

- Gold: []
- Predicted: [['madame', 'bovary']]
- Model analysis: Considered 'Madame Bovary' as a candidate due to its usage as a proper name from literature. Although 'Madame Bovary' is a proper noun and often not marked, it is also an established cultural reference/formula. Therefore, it is marked as an MWE.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold: [['little', 'bit', 'of']]
- Predicted: [['little', 'bit']]
- Model analysis: Considered 'little bit' as a candidate for MWE as it forms a conventionalized, lexicalized expression to mean a small amount or degree, distinct from the literal meanings of 'little' and 'bit' in combination. It is a common expression conveying a specific nuance, justifying its inclusion.

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold: [['found', 'herself']]
- Predicted: []
- Model analysis: Considered potential MWEs: 'even found' and 'found herself'. 'Even found' is not a fixed idiomatic expression or phrasal verb, so it is not marked. 'Found herself' may work as a light-verb or idiomatic expression in some contexts indicating realization or self-discovery, but here it functions as a straightforward reflexive action, so it's rejected for MWE marking. Overall, no identifiable MWEs fitting the criteria were found.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold: [['high', 'up']]
- Predicted: [['fly', 'high', 'up']]
- Model analysis: Considered 'climbed on' for inclusion but rejected as it functions more as a standard verb-preposition construction than a lexicalized phrasal verb. 'Fly high up' was selected as it forms a phrasal verb, where the combination of 'fly', 'high', and 'up' is more than the sum of its parts and represents a conventionalized expression.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold: [['at', 'home']]
- Predicted: [['back', 'at', 'home']]
- Model analysis: Considered 'Back at home' as it is a fixed adverbial indicating a return to one's home, similar to 'De retour chez lui' in French, marking it as an MWE. Other parts of the sentence like 'busy helping the people in the village' were not marked as they represent ordinary adjective+object and prepositional phrases.

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold: []
- Predicted: [['in', 'all', 'her', 'grand', 'adventures']]
- Model analysis: Considered 'in all her grand adventures' as an MWE due to its conventional use as an expression suggesting support throughout significant experiences. It is somewhat lexicalized and idiomatic. 'Grand adventures' alone did not qualify as it could refer straightforwardly to large-scale undertakings without being idiomatic. The choice of including 'in all her grand adventures' as a single MWE was due to its function as a unit expressing involvement throughout all such activities, supporting the broader idiomatic sense.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold: [['had', 'a', 'time']]
- Predicted: [['time', 'playing']]
- Model analysis: Considered 'had a wonderful time' as a candidate MWE because it's a fixed idiomatic expression frequently used to describe enjoyment. It aligns with the French translation 'passé un moment merveilleux', indicating it functions as a phrase. Other sequences like 'playing games' or 'telling stories' are not marked because they are more compositional and straightforward descriptions of activities.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold: [['dreamt', 'of']]
- Predicted: [['fairy-tale', 'boutique']]
- Model analysis: Considered 'fairy-tale boutique' as a lexicalized compound because it likely names an established category of stores with a specific theme rather than an ad hoc description. Did not mark other sequences as MWEs, as they do not fulfill the criteria of conventionalized or idiomatic multi-word expressions.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold: [['all', 'over']]
- Predicted: [['from', 'all', 'over']]
- Model analysis: Considered 'was booming' as an MWE, but 'booming' alone is typically used idiomatically in this context as 'Business is booming' is a common fixed expression. 'from all over' is a recognized idiomatic expression signifying people coming from many different places, thus marked as MWE.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold: [['heard', 'about']]
- Predicted: [['emma', 'bovary'], ['king', 'queen', 'of', 'france']]
- Model analysis: Considered 'King and Queen of France' and 'Emma Bovary'. 'King and Queen of France' was marked due to being a well-known conventional expression describing royalty, rather than an ad hoc title. 'Emma Bovary' was considered but would typically be excluded as a proper name; however, it is a titled character in a famous novel and fixed enough to merit inclusion under stable MWEs mentioned in translation_context and literary contexts.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold: []
- Predicted: [['tea', 'party']]
- Model analysis: Considered 'grand palace', 'special tea party', 'tea party'. 'Grand palace' is not marked because it's a descriptive phrase rather than a conventional lexical unit. 'Special tea party' was not marked as the word 'special' is a modifier and not part of a fixed expression. 'Tea party' is marked as an MWE because it is a conventional and lexicalized expression referring to a specific type of social gathering.

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold: []
- Predicted: [['royal', 'adventure', 'planner']]
- Model analysis: Considered 'Royal Adventure Planner' as a candidate because it appears to be a conventionalized title for a role. Although it is capitalized, it functions as a set term, much like 'Chief Financial Officer'. Ultimately selected for its probable conventional use and stability as a nominal expression. Other candidates like 'King and Queen' were rejected as they are proper names, not fixed expressions beyond their specific references here.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted: [['all', 'over'], ['from', 'then', 'on']]
- Model analysis: Candidates considered: 'From then on' is a fixed adverbial that refers to a period starting at a certain time and continuing indefinitely, so it was accepted. 'all over' is often used as a fixed form to mean 'in various places' or 'throughout', thus accepted as a fixed adverbial/prepositional phrase. Other phrases like 'traveled all over the world' were considered but not marked as MWEs since they function as ordinary verb+prepositional phrases without lexicalized status.

### en:project_239:p8:s1

In the end, Emma's dreams came true in the most delightful way possible.

- Gold: [['came', 'true'], ['in', 'the', 'end']]
- Predicted: [['came', 'true']]
- Model analysis: Considered 'in the end' as a candidate, but it functions here more as a simple prepositional phrase rather than a fixed expression. 'Came true' is accepted as an MWE because it is a conventionalized expression meaning to become a reality, not compositional from 'come' and 'true'.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold: [['lived', 'happily', 'ever', 'after']]
- Predicted: [['happily', 'ever', 'after']]
- Model analysis: Considered 'happily ever after' as a fixed idiomatic expression commonly used in storytelling to indicate a happy ending. Other surrounding words are ordinary sentence elements and not part of any fixed expressions.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold: [['lived', 'happily', 'ever', 'after']]
- Predicted: [['ever', 'after']]
- Model analysis: Considered 'ever after' as a candidate because it's a conventionalized and idiomatic expression indicating continuation into the future. It matches a typical idiom pattern and appears as a fixed expression in English. Other combinations like 'lived happily', 'happily, sparkly, and joyfully', while descriptive, are not conventional MWE candidates as they lacked idiomatic or fixed phrase status. 'Lived happily ever after' is often used together but 'ever after' is the minimal stable component.

### en:project_239:p8:s5

The end.

- Gold: [['the', 'end']]
- Predicted: []
- Model analysis: Considered 'The end' as a candidate MWE. It could be a conventionalized expression in certain contexts (e.g., film or story terminations). However, without additional contextual evidence, it lacks strong idiomatic or lexicalized properties. Rejected as it may function more as a descriptive phrase rather than a stable lexical unit.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold: [['first', 'responder']]
- Predicted: [['use', 'of', 'definite', 'indefinite', 'and', 'null', 'articles']]
- Model analysis: Considered 'Correct Use of Definite, Indefinite, and Null Articles' as a candidate. This is a conventional phrase referring to the grammatical topic of article usage. Chose to group it all as one MWE due to the conventional nature and fixed order of terms referring to categories of articles in grammar discussions. Rejected separate or shorter spans because they do not independently form recognized expressions.

### en:project_245:p2:s1

Hunky Felix is a fearless first responder.

- Gold: [['first', 'responder']]
- Predicted: []
- Model analysis: Considered 'fearless first responder' as a possible MWE due to its usage in certain contexts as a composite noun phrase. However, it was not marked as an MWE since 'first responder' is a more established term on its own, and 'fearless' functions as a standard adjective, making the phrase more of an ordinary description rather than a conventionalized MWE.

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold: [['explained', 'to']]
- Predicted: []
- Model analysis: Considered candidates for MWEs were 'explained to', 'climbed to save', and 'save you'. 'Explained to' is typically a more free-form expression rather than a fixed idiom. 'Climbed to save' was considered, but 'to save' seems like an infinitive expressing purpose rather than a fixed expression. 'Save you' is a common verb-object combination and not a lexicalized phrase. No fixed, conventionalized MWEs were identified in the segment.

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold: [['a', 'little']]
- Predicted: []
- Model analysis: Considered 'a little better' and 'understanding a little better'. 'A little' is a conventional adverbial phrase meaning a small amount or to a small degree, and its stability and idiomatic use justify marking it as an MWE. However, 'a little better' was not marked because its core is 'a little'. 'Understanding a little better' was not marked as it is compositional and not idiomatic.

### en:project_245:p4:s2

'The' is a definite article, referring to this specific dog."

- Gold: []
- Predicted: [['definite', 'article']]
- Model analysis: Considered 'definite article' as a candidate for MWE because it is a fixed lexicalized expression that describes a specific grammatical element, namely a type of article in English grammar. Rejected other token groups as they did not form conventionalized, idiomatic, or fixed expressions.

### en:project_245:p4:s3

The dog wagged its tail, clearly pleased with the lesson.

- Gold: [['pleased', 'with']]
- Predicted: [['with', 'the', 'lesson']]
- Model analysis: Considered 'wagged its tail' as an MWE, but it did not meet the criteria for a fixed idiomatic expression. 'pleased with the lesson' is a potential idiomatic or conventional expression; however, 'pleased with' on its own is more of a collocation than a full MWE. Thus, marked 'with the lesson' for its potential as a set phrase conveying satisfaction contextually.

### en:project_245:p5:s5

'A' can mean any hero."

- Gold: []
- Predicted: [['can', 'mean']]
- Model analysis: Considered 'can mean' as a candidate for multi-word expression due to conventional phrasal verb structure. Rejected other possibilities: 'any hero' is a typical adjective+noun pattern, not an idiomatic or conventional expression.

### en:project_245:p7:s1

Our hero, Felix, went to the grocery store next.

- Gold: [['grocery', 'store']]
- Predicted: []
- Model analysis: Candidates considered: 'grocery store'. Rejected because it functions as an ordinary noun phrase (adjective + noun) rather than a lexicalized compound naming a common category. No other plausible MWEs identified in the segment.

