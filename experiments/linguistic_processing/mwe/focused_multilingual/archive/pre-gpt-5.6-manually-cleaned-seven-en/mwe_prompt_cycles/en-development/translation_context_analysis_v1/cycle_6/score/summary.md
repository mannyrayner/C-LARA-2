# MWE prompt score summary

- Split: `development`
- Records: 336
- Exact match: 126 (37.5%)
- Precision: 0.248
- Recall: 0.434
- F1: 0.316

## Error examples

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold: [['little', 'bit', 'of']]
- Predicted: [['little', 'bit']]
- Model analysis: Considered 'One sunny day' and 'little bit of' as potential MWEs. 'One sunny day' was rejected as it is a descriptive temporal expression without evidence of conventionalization or lexicalization. 'Little bit' was accepted as an MWE because it is a strongly lexicalized quantity expression, often functioning together as a fixed phrase in English.

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold: [['found', 'herself']]
- Predicted: []
- Model analysis: Considered 'found herself' as a candidate for a light-verb expression but found it not strongly lexicalized or conventionalized; it functions more as a reflexive structure here. No strongly idiomatic or conventionalized MWEs were found in this text segment.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold: [['high', 'up']]
- Predicted: [['high', 'up'], ['on', 'glitter']]
- Model analysis: Candidates considered: 1) 'climbed on' could be a particle verb but is not strongly lexicalized. 2) 'on Glitter' seems fixed but is more of a possessive use. 'fly high up' considered as a multi-word expression because 'high up' is a common idiomatic locative expression. Final MWEs selected: 'on Glitter' (stable configuration for referring to a mount), 'high up' (common idiomatic use indicating elevation).

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold: []
- Predicted: [['tea', 'parties']]
- Model analysis: Considered 'rainbow waterfalls', 'enchanted forests', and 'tea parties' as potential MWEs. 'Rainbow waterfalls' and 'enchanted forests' are compositional descriptions, while 'tea parties' is a conventionalized, lexicalized expression due to its idiomatic usage.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold: [['at', 'home']]
- Predicted: [['back', 'at', 'home']]
- Model analysis: Candidates considered: 'Back at home' and 'helping the people in the village'. 'Back at home' was marked as an MWE because it is a fixed adverbial phrase indicating a return to one's residence, commonly used in English. 'Helping the people in the village' is a compositional phrase and was not marked.

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold: []
- Predicted: [['in', 'all', 'her']]
- Model analysis: Considered 'in all her grand adventures' for potential multi-word expressions. 'In all her' was identified as a possible fixed adverbial consisting of 'in all', which often functions together as a set phrase in various contexts. 'Grand adventures' is compositional and describing a category, not lexicalized as an MWE.

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold: [['complete', 'with']]
- Predicted: [['complete', 'with'], ['in', 'the', 'park']]
- Model analysis: Considered 'One day' as a potential temporal formula and marked it as an MWE due to its fixed use in narrative openings. 'In the park' looked like a compositional phrase but is common as a fixed locative adverbial indicating a general rather than specific location. 'Complete with' was marked because it functions as a fixed expression meaning 'including', with the preposition 'with' being part of the expression.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold: [['had', 'a', 'time']]
- Predicted: []
- Model analysis: Considered 'wonderful time' as a conventionalized, lexicalized expression often used to describe an enjoyable experience. 'Playing games' and 'telling stories' were not marked as they are ordinary compositional expressions.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold: [['dreamt', 'of']]
- Predicted: [['fairy-tale', 'boutique']]
- Model analysis: Considered 'fairy-tale boutique' as a strong lexicalized compound naming an established concept, accepted as MWE. 'dreamt of', 'grander things', 'magical potions', 'enchanted dresses' were considered but rejected as they appear compositional.

### en:project_239:p6:s3

Emma became famous for her sparkling personality and beautiful shop.

- Gold: []
- Predicted: [['famous', 'for']]
- Model analysis: Considered 'famous for' as a candidate since 'famous for' is a conventionalized English expression indicating the reason or cause of fame, thus selected as an MWE. Other sequences do not show idiomatic or fixed expression characteristics.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold: [['heard', 'about']]
- Predicted: []
- Model analysis: Considered 'One day' as a story-opening expression, a conventional way to start narratives; accepted it. 'Heard about' is a conventional verb + particle combination; accepted. Other combinations like 'King and Queen of France' rejected due to being a proper name and compositional.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold: []
- Predicted: [['tea', 'party']]
- Model analysis: Considered 'tea party' as a possible MWE because it is a strongly lexicalized compound naming an established general concept and not merely compositional. No other strong candidates found; the rest of the phrase is a simple narrative description with no conventionalized expressions.

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold: []
- Predicted: [['royal', 'adventure', 'planner']]
- Model analysis: Considered 'Royal Adventure Planner' as a candidate for an MWE because it functions as a strongly lexicalized compound naming an established general role. The combination of 'Royal', 'Adventure', and 'Planner' is indicative of a title that is more conventionalized and stable, thus qualifying as a multi-word expression. No other expressions in the sentence meet the criteria for MWEs.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted: [['all', 'over'], ['from', 'then', 'on']]
- Model analysis: Considered 'From then on' as it is a stable temporal adverbial expression marking a moment in time, confirmed by the translation 'À partir de ce moment'. 'All over' is another MWE as a fixed adverbial phrase indicating widespread location; it's a conventional expression also seen in 'partout'. Both are non-compositional, hence marked.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold: [['lived', 'happily', 'ever', 'after']]
- Predicted: [['happily', 'ever', 'after']]
- Model analysis: Considered 'happily ever after' as a candidate due to its status as a fixed idiom expressing a conventional notion of a blissful, indefinite period following an event. Decided to mark 'happily ever after' as MWE since it is idiomatic and well-established. No other phrases met the criteria for MWEs in this context.

### en:project_239:p8:s3

Every day was a new adventure filled with laughter, magic, and love.

- Gold: [['filled', 'with']]
- Predicted: [['magic', 'and', 'love'], ['with', 'laughter']]
- Model analysis: Considered 'filled with laughter' as a potential MWE since 'filled with X' can be a conventional expression, but ultimately 'with laughter' is a better fit as a more fixed postpositive structure. 'Magic and love' is a common collocation pointing to a concept or idea greater than the sum of its parts in literary contexts. Other word combinations present were mostly compositional or did not meet MWE criteria.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold: [['lived', 'happily', 'ever', 'after']]
- Predicted: [['ever', 'after']]
- Model analysis: Considered 'happily ever after' as a complete expression, but 'ever after' is the strongly lexicalized part and functions as a temporal adverbial in idiomatic 'happily ever after' phrases. 'Happily' is optional and adds emphasis but is not required for the adverbial meaning. Chose 'ever after' as the core MWE.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold: [['first', 'responder']]
- Predicted: []
- Model analysis: Considered 'Correct Use of' as a light-verb expression, but determined it's a compositional phrase. No MWEs found as all phrases are either compositional or descriptive.

### en:project_245:p2:s2

Not only does he save lives, but he loves to teach proper English grammar.

- Gold: []
- Predicted: [['not', 'only']]
- Model analysis: Considered 'Not only' as an MWE because it is a fixed expression often used for emphasis or contrast; marked it as such. 'but' is considered part of the correlative conjunction 'not only...but...'; it serves as a necessary discourse connector to complete the expression started by 'Not only'. Checked for any other MWEs and determined the rest are ordinary language constructs.

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold: [['stuck', 'in']]
- Predicted: [['in', 'tree']]
- Model analysis: Considered 'in a tree' for lexicalization. 'In a tree' is a common locative expression and is kept minimal by marking 'in tree' as the MWE. 'One day' as a temporal mark has a broader connotation, and 'downtime explaining articles' is more compositional, related to activity described.

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold: [['explained', 'to']]
- Predicted: [['to', 'save']]
- Model analysis: Candidates considered: 'to save you' - While 'to save' appears to be a common verb + infinitive structure, 'save' functions here grammatically as a unit with 'to', forming a purpose infinitive indicative of lexicalized function, thus is annotated as a MWE. Other phrases like 'explained to' and 'climbed to save' were considered compositional and not idiomatic, thus not marked.

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold: [['a', 'little']]
- Predicted: [['little', 'better']]
- Model analysis: Considered 'a little better' as a potential MWE. It is a common degree expression indicating improvement in understanding. Decided to mark 'a little better' since it functions as a conventionalized degree expression in this context. No other multi-word expressions found; individual clauses and phrases are compositional.

### en:project_245:p4:s1

When Felix saw a dog, he said, "The dog is happy to see me.

- Gold: []
- Predicted: [['happy', 'to', 'see']]
- Model analysis: Considered 'happy to see'. While 'happy' and 'see' are compositional, the phrase 'happy to see' functions idiomatically to convey a specific sentiment and can be considered conventionalized in expressing that the dog is pleased in a friendly or affectionate sense. It aligns with expressions in other languages like French 'content de voir'. No other MWEs found; other phrases are simply compositional.

### en:project_245:p4:s2

'The' is a definite article, referring to this specific dog."

- Gold: []
- Predicted: [['definite', 'article'], ['referring', 'to']]
- Model analysis: Considered 'definite article' as a lexicalized compound since it is a conventional way to describe a grammatical element. 'Referring to' was marked as verb + required preposition since 'to' is essential to the lexical meaning of the verb 'referring'. Other groups like 'a definite article' or 'this specific dog' were rejected as they are compositional and do not form stable lexical units.

### en:project_245:p6:s4

Felix asked, emphasizing ‘the barbecue’ they both knew about.

- Gold: [['knew', 'about']]
- Predicted: [['emphasizing', 'the']]
- Model analysis: Considered 'emphasizing the' as a candidate because 'emphasize the NP' is a fixed pattern often used in particular contexts, although it's not idiomatic enough alone without an NP, the phrase's structure suggests conventional collocation; marked as part of an MWE. 'knew about' is a typical verb + preposition pair where the preposition helps complete the meaning of 'knew,' thus marked as MWE.

