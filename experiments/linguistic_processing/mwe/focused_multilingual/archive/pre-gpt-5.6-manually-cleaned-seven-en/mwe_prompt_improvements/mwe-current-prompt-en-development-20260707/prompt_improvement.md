# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.333
- Recall: 0.297
- F1: 0.314

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
- Predicted spans: [['on', 'back']]

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold spans: []
- Predicted spans: [['tea', 'parties']]

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['little', 'fairy-tale']]

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold spans: []
- Predicted spans: [['royal', 'adventure', 'planner']]

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['from', 'then', 'on'], ['traveled', 'all', 'over']]

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['happily', 'ever', 'after']]

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['happily', 'joyfully', 'ever', 'after']]

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['climbed', 'to', 'save']]

### en:project_245:p7:s3

"An apple a day keeps the doctor away," he mused.

- Gold spans: [['keeps', 'away']]
- Predicted spans: [['apple', 'a', 'day', 'keeps', 'the', 'doctor', 'away']]

### en:project_245:p14:s3

She handed him the specific book he wanted.

- Gold spans: []
- Predicted spans: [['handed', 'him']]

### en:project_254:p2:s2

This voice belonged to an AI named Leo, designed to assist visitors with questions and information.

- Gold spans: [['belonged', 'to']]
- Predicted spans: [['designed', 'to', 'assist'], ['with', 'questions', 'information']]

### en:project_254:p3:s2

Many of them, having rarely heard the sing-song lilt of the accent, found it unfamiliar.

- Gold spans: []
- Predicted spans: [['sing-song', 'lilt']]

### en:project_254:p3:s3

Some in the community struggled to listen without judgment, and whispers and giggles often accompanied Leo's efforts to help.

- Gold spans: []
- Predicted spans: [['accompanied', 'to', 'help']]

### en:project_254:p4:s2

Yet, as time passed, the initial mockery began to fade, and something unexpected happened.

- Gold spans: []
- Predicted spans: [['began', 'to', 'fade']]

### en:project_254:p4:s4

They heard in Leo's voice a sound they had long been told to hide.

- Gold spans: []
- Predicted spans: [['long', 'been', 'told']]

### en:project_254:p5:s1

Word spread within the community that there was a place where their accent—an accent that told the stories of their ancestors—was not just accepted, but institutionalized in the voice of an AI helper.

- Gold spans: [['there', 'was']]
- Predicted spans: [['told', 'the', 'stories', 'of', 'their', 'ancestors']]

### en:project_254:p5:s3

Stories were exchanged, laughter rang through the aisles, and what began as a perceived programming flaw became a point of connection.

- Gold spans: []
- Predicted spans: [['of', 'connection'], ['programming', 'flaw'], ['through', 'the', 'aisles']]

### en:project_254:p7:s2

The child beamed, hearing the familiar cadence spoken with the same pride that their grandmother shared tales at bedtime.

- Gold spans: []
- Predicted spans: [['shared', 'tales']]

### en:project_254:p8:s1

Leo guided the reading, voice steady and engaging, until the child was reading confidently alongside the AI.

- Gold spans: []
- Predicted spans: [['alongside', 'the', 'ai']]


## False-negative examples to inspect

### en:project_239:p2:s3

Although Emma had everything she needed, she often dreamed of more exciting adventures.

- Gold spans: [['dreamed', 'of']]
- Predicted spans: []

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['little', 'bit']]

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold spans: [['took', 'a', 'walk']]
- Predicted spans: []

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['on', 'back']]

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
- Predicted spans: [['little', 'fairy-tale']]

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
- Predicted spans: [['from', 'then', 'on'], ['traveled', 'all', 'over']]

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
- Predicted spans: [['happily', 'joyfully', 'ever', 'after']]

### en:project_239:p8:s5

The end.

- Gold spans: [['the', 'end']]
- Predicted spans: []

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: []

### en:project_245:p2:s1

Hunky Felix is a fearless first responder.

- Gold spans: [['first', 'responder']]
- Predicted spans: []

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: []

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['climbed', 'to', 'save']]

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold spans: [['a', 'little']]
- Predicted spans: []

