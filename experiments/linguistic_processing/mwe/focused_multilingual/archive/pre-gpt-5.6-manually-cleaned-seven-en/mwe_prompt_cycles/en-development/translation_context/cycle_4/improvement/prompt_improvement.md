# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.180
- Recall: 0.251
- F1: 0.210

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
- Predicted spans: [['climbed', 'on'], ['fly', 'high', 'up']]

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold spans: []
- Predicted spans: [['tea', 'parties']]

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold spans: []
- Predicted spans: [['in', 'all', 'her', 'grand', 'adventures']]

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: [['complete', 'with'], ['in', 'the', 'park']]

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['a', 'little', 'fairy-tale', 'boutique']]

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['from', 'all', 'over']]

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold spans: []
- Predicted spans: [['tea', 'party']]

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['from', 'then', 'on'], ['traveled', 'all', 'over', 'the', 'world']]

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['happily', 'ever', 'after']]

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['definite', 'indefinite', 'null', 'articles']]

### en:project_245:p2:s2

Not only does he save lives, but he loves to teach proper English grammar.

- Gold spans: []
- Predicted spans: [['not', 'only']]

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['explaining', 'articles'], ['in', 'a', 'tree']]

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['save', 'you']]

### en:project_245:p4:s1

When Felix saw a dog, he said, "The dog is happy to see me.

- Gold spans: []
- Predicted spans: [['to', 'see']]

### en:project_245:p5:s1

A little girl approached Felix to thank him.

- Gold spans: []
- Predicted spans: [['thank', 'him']]

### en:project_245:p7:s3

"An apple a day keeps the doctor away," he mused.

- Gold spans: [['keeps', 'away']]
- Predicted spans: [['an', 'apple', 'a', 'day', 'keeps', 'the', 'doctor', 'away']]

### en:project_245:p7:s4

The shopkeeper smiled at this bit of wisdom.

- Gold spans: []
- Predicted spans: [['this', 'bit', 'of', 'wisdom']]

### en:project_245:p9:s4

"There, I used 'the' because we all know which sky."

- Gold spans: []
- Predicted spans: [['know', 'which'], ['used', 'the']]

### en:project_245:p12:s2

"A book is a friend," he thought, feeling wise.

- Gold spans: []
- Predicted spans: [['feeling', 'wise']]

### en:project_245:p15:s3

"Any car will do."

- Gold spans: [['will', 'do']]
- Predicted spans: [['any', 'car', 'will', 'do']]


## False-negative examples to inspect

### en:project_239:p2:s1

Once upon a time, in a small village in France, there was a lovely lady named Emma Bovary.

- Gold spans: [['once', 'upon', 'a', 'time']]
- Predicted spans: []

### en:project_239:p2:s3

Although Emma had everything she needed, she often dreamed of more exciting adventures.

- Gold spans: [['dreamed', 'of']]
- Predicted spans: []

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold spans: [['found', 'herself']]
- Predicted spans: []

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['climbed', 'on'], ['fly', 'high', 'up']]

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold spans: [['filled', 'with']]
- Predicted spans: []

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: []

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: []

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['a', 'little', 'fairy-tale', 'boutique']]

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['from', 'all', 'over']]

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: []

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['from', 'then', 'on'], ['traveled', 'all', 'over', 'the', 'world']]

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['happily', 'ever', 'after']]

### en:project_239:p8:s3

Every day was a new adventure filled with laughter, magic, and love.

- Gold spans: [['filled', 'with']]
- Predicted spans: []

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: []

### en:project_239:p8:s5

The end.

- Gold spans: [['the', 'end']]
- Predicted spans: []

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['definite', 'indefinite', 'null', 'articles']]

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['explaining', 'articles'], ['in', 'a', 'tree']]

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['save', 'you']]

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold spans: [['a', 'little']]
- Predicted spans: []

### en:project_245:p5:s3

Felix replied, "Thank you!

- Gold spans: [['thank', 'you']]
- Predicted spans: []

