# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.270
- Recall: 0.269
- F1: 0.269

## General revision principles

- Mark an MWE only when the expression is conventionalized, idiomatic, lexicalized, or functions as a stable multi-token lexical unit.
- Do not mark ordinary compositional adjective+noun, determiner+noun, or verb+object phrases just because they are frequent in the text.
- Prefer high precision: when unsure, leave tokens unmarked rather than inventing an MWE.
- Keep labels broad and language-neutral; avoid rules tied to a single project or named example.
- Preserve the input token sequence exactly and only add MWE IDs to tokens that belong to accepted multi-token expressions.

## False-positive examples to inspect

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['little', 'bit']]

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['fly', 'high', 'up'], ['on', 'back']]

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold spans: []
- Predicted spans: [['tea', 'parties']]

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['back', 'at', 'home']]

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['fairy-tale', 'boutique']]

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['all', 'over'], ['came', 'to']]

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: [['about', 'emma', 'bovary']]

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['traveled', 'all', 'over']]

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['happily', 'ever', 'after']]

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['of', 'definite', 'indefinite', 'and', 'null', 'articles']]

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['climbed', 'to', 'save', 'you']]

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold spans: [['a', 'little']]
- Predicted spans: [['little', 'better']]

### en:project_245:p4:s1

When Felix saw a dog, he said, "The dog is happy to see me.

- Gold spans: []
- Predicted spans: [['see', 'me']]

### en:project_245:p11:s3

We don't need an article here," he explained.

- Gold spans: [['don', "'", 't']]
- Predicted spans: [['don', "'", 't', 'need']]

### en:project_245:p12:s2

"A book is a friend," he thought, feeling wise.

- Gold spans: []
- Predicted spans: [['feeling', 'wise']]

### en:project_245:p13:s2

Felix smiled, "It's just a friend.

- Gold spans: []
- Predicted spans: [["'s", 'just']]

### en:project_245:p15:s2

"Let's drive a car," he said.

- Gold spans: []
- Predicted spans: [["let's", 'drive', 'a', 'car,"']]

### en:project_254:p2:s1

In a small town nestled between rolling hills and vibrant meadows, there emerged a new voice from the loudspeakers of the local library.

- Gold spans: []
- Predicted spans: [['between', 'rolling', 'hills', 'and', 'vibrant', 'meadows'], ['from', 'the', 'loudspeakers', 'of', 'the', 'local', 'library']]

### en:project_254:p2:s2

This voice belonged to an AI named Leo, designed to assist visitors with questions and information.

- Gold spans: [['belonged', 'to']]
- Predicted spans: [['assist', 'visitors', 'with', 'questions']]

### en:project_254:p3:s2

Many of them, having rarely heard the sing-song lilt of the accent, found it unfamiliar.

- Gold spans: []
- Predicted spans: [['heard', 'the', 'sing-song', 'lilt', 'of', 'the', 'accent']]


## False-negative examples to inspect

### en:project_239:p2:s1

Once upon a time, in a small village in France, there was a lovely lady named Emma Bovary.

- Gold spans: [['once', 'upon', 'a', 'time']]
- Predicted spans: []

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['little', 'bit']]

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold spans: [['took', 'a', 'walk']]
- Predicted spans: []

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold spans: [['found', 'herself']]
- Predicted spans: []

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['fly', 'high', 'up'], ['on', 'back']]

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold spans: [['filled', 'with']]
- Predicted spans: []

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['back', 'at', 'home']]

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: []

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: []

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['fairy-tale', 'boutique']]

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: [['about', 'emma', 'bovary']]

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['traveled', 'all', 'over']]

### en:project_239:p8:s1

In the end, Emma's dreams came true in the most delightful way possible.

- Gold spans: [['came', 'true'], ['in', 'the', 'end']]
- Predicted spans: [['came', 'true']]

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
- Predicted spans: [['of', 'definite', 'indefinite', 'and', 'null', 'articles']]

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: []

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['climbed', 'to', 'save', 'you']]

