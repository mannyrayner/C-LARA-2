# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.430
- Recall: 0.331
- F1: 0.374

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
- Predicted spans: [['fly', 'high', 'up']]

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold spans: []
- Predicted spans: [['had', 'tea', 'parties'], ['with', 'animals']]

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold spans: []
- Predicted spans: [['in', 'all', 'her', 'grand', 'adventures']]

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['fairy-tale', 'boutique']]

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold spans: []
- Predicted spans: [['royal', 'adventure', 'planner']]

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['happily', 'ever', 'after']]

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['ever', 'after']]

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['of', 'definite', 'indefinite', 'and', 'null', 'articles']]

### en:project_245:p2:s2

Not only does he save lives, but he loves to teach proper English grammar.

- Gold spans: []
- Predicted spans: [['only', 'does']]

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['in', 'a', 'tree']]

### en:project_245:p7:s4

The shopkeeper smiled at this bit of wisdom.

- Gold spans: []
- Predicted spans: [['bit', 'of', 'wisdom']]

### en:project_245:p12:s1

At night, Felix read a book before bed.

- Gold spans: []
- Predicted spans: [['before', 'bed']]

### en:project_245:p16:s1

A child asked, "Why no articles sometimes?"

- Gold spans: []
- Predicted spans: [['articles', 'sometimes']]

### en:project_254:p3:s2

Many of them, having rarely heard the sing-song lilt of the accent, found it unfamiliar.

- Gold spans: []
- Predicted spans: [['sing-song', 'lilt']]

### en:project_254:p4:s2

Yet, as time passed, the initial mockery began to fade, and something unexpected happened.

- Gold spans: []
- Predicted spans: [['to', 'fade']]

### en:project_254:p4:s4

They heard in Leo's voice a sound they had long been told to hide.

- Gold spans: []
- Predicted spans: [['long', 'been', 'told']]

### en:project_254:p5:s1

Word spread within the community that there was a place where their accent—an accent that told the stories of their ancestors—was not just accepted, but institutionalized in the voice of an AI helper.

- Gold spans: [['there', 'was']]
- Predicted spans: [['in', 'the', 'voice', 'of', 'an', 'ai', 'helper']]

### en:project_254:p5:s3

Stories were exchanged, laughter rang through the aisles, and what began as a perceived programming flaw became a point of connection.

- Gold spans: []
- Predicted spans: [['point', 'of']]

### en:project_254:p7:s1

“As surely as the rain falls,” Leo replied in its melodic voice, warmth flowing through the mechanical tones.

- Gold spans: [['as', 'as']]
- Predicted spans: [['as', 'surely', 'as'], ['flowing', 'through']]

### en:project_254:p7:s2

The child beamed, hearing the familiar cadence spoken with the same pride that their grandmother shared tales at bedtime.

- Gold spans: []
- Predicted spans: [['at', 'bedtime']]


## False-negative examples to inspect

### en:project_239:p2:s3

Although Emma had everything she needed, she often dreamed of more exciting adventures.

- Gold spans: [['dreamed', 'of']]
- Predicted spans: []

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
- Predicted spans: [['fly', 'high', 'up']]

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold spans: [['filled', 'with']]
- Predicted spans: []

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: []

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

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: []

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: []

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['all', 'over'], ['from', 'then', 'on']]

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
- Predicted spans: [['ever', 'after']]

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
- Predicted spans: [['in', 'a', 'tree']]

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: []

