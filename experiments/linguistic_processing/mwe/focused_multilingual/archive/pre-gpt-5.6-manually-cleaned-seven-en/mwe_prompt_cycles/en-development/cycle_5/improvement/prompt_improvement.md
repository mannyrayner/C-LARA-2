# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.329
- Recall: 0.269
- F1: 0.296

## General revision principles

- Mark an MWE only when the expression is conventionalized, idiomatic, lexicalized, or functions as a stable multi-token lexical unit.
- Do not mark ordinary compositional adjective+noun, determiner+noun, or verb+object phrases just because they are frequent in the text.
- Prefer high precision: when unsure, leave tokens unmarked rather than inventing an MWE.
- Keep labels broad and language-neutral; avoid rules tied to a single project or named example.
- Preserve the input token sequence exactly and only add MWE IDs to tokens that belong to accepted multi-token expressions.

## False-positive examples to inspect

### en:project_239:p2:s1

Once upon a time, in a small village in France, there was a lovely lady named Emma Bovary.

- Gold spans: [['once', 'upon', 'a', 'time']]
- Predicted spans: [['upon', 'a', 'time']]

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
- Predicted spans: [['had', 'tea', 'parties']]

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['from', 'all', 'over']]

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['happily', 'ever', 'after']]

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['in', 'a', 'tree']]

### en:project_245:p4:s1

When Felix saw a dog, he said, "The dog is happy to see me.

- Gold spans: []
- Predicted spans: [['see', 'me']]

### en:project_245:p9:s4

"There, I used 'the' because we all know which sky."

- Gold spans: []
- Predicted spans: [['know', 'which', 'sky']]

### en:project_245:p12:s1

At night, Felix read a book before bed.

- Gold spans: []
- Predicted spans: [['before', 'bed']]

### en:project_254:p4:s1

Leo, equipped with awareness but designed without ego, continued to assist patrons, answering questions with its distinctive voice.

- Gold spans: [['equipped', 'with']]
- Predicted spans: [['with', 'voice']]

### en:project_254:p4:s4

They heard in Leo's voice a sound they had long been told to hide.

- Gold spans: []
- Predicted spans: [['had', 'long', 'been', 'told']]

### en:project_254:p5:s3

Stories were exchanged, laughter rang through the aisles, and what began as a perceived programming flaw became a point of connection.

- Gold spans: []
- Predicted spans: [['point', 'of', 'connection'], ['rang', 'through']]

### en:project_254:p6:s3

"Can you help me with this story?" the child asked, their voice hesitant but filled with curiosity.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['with', 'curiosity']]

### en:project_254:p7:s1

“As surely as the rain falls,” Leo replied in its melodic voice, warmth flowing through the mechanical tones.

- Gold spans: [['as', 'as']]
- Predicted spans: [['flowing', 'through'], ['surely', 'as']]

### en:project_254:p8:s1

Leo guided the reading, voice steady and engaging, until the child was reading confidently alongside the AI.

- Gold spans: []
- Predicted spans: [['alongside', 'the', 'ai']]

### en:project_254:p9:s2

For many, it served as a reminder that differences were not to be mocked, but celebrated.

- Gold spans: [['served', 'as'], ['were', 'to', 'be']]
- Predicted spans: [['as', 'a', 'reminder']]

### en:project_254:p10:s2

Instead, Leo was a hero, revered for reminding everyone that every voice tells a story worth hearing,

- Gold spans: []
- Predicted spans: [['for', 'reminding'], ['worth', 'hearing']]

### en:project_254:p10:s3

that diversity is woven with threads of dignity and love.

- Gold spans: []
- Predicted spans: [['with', 'of']]

### en:project_255:p3:s1

Commander Elena Reyes was calibrating a new set of sensors when a soft mew echoed through the module.

- Gold spans: [['echoed', 'through']]
- Predicted spans: [['through', 'the', 'module']]


## False-negative examples to inspect

### en:project_239:p2:s1

Once upon a time, in a small village in France, there was a lovely lady named Emma Bovary.

- Gold spans: [['once', 'upon', 'a', 'time']]
- Predicted spans: [['upon', 'a', 'time']]

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
- Predicted spans: []

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['from', 'all', 'over']]

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: []

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
- Predicted spans: []

### en:project_245:p2:s1

Hunky Felix is a fearless first responder.

- Gold spans: [['first', 'responder']]
- Predicted spans: []

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['in', 'a', 'tree']]

