# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.113
- Recall: 0.234
- F1: 0.152

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
- Predicted spans: [['0', '1', '2', '3']]
- Model analysis: Selected 'Once upon a time' as a fixed_expression due to its conventionalized use in storytelling and its translation as a single phrase 'Il était une fois' in French. Rejected all other candidates as they were deemed compositional or descriptive with no strong MWE properties.

### en:project_239:p2:s2

Emma lived in a beautiful house with her husband, Charles, who was a kind and gentle doctor.

- Gold spans: []
- Predicted spans: [['1', '2']]
- Model analysis: Selected 'lived in' as a phrasal verb due to source-token evidence and translation context. Rejected all other candidates as they are ordinary compositional phrases.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['8', '9', '10']]
- Model analysis: Selected 'a little bit' as a fixed_expression due to its conventionalized usage and translation as a single unit 'un peu' in French. All other candidate phrases are rejected due to either compositional translation or being ordinary descriptive phrases.

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold spans: [['took', 'a', 'walk']]
- Predicted spans: [['2', '3', '4']]
- Model analysis: Selected 'took a walk' as a fixed expression due to its conventional use and translation as a single phrase 'fait une promenade.' All other phrases are compositional or routine and were rejected.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['climbed', 'on'], ['fly', 'high', 'up']]
- Model analysis: Selected 'climbed on' as a phrasal verb, a conventional verb-particle construction, supported by glossing evidence in French ('montait sur'). Selected 'fly high up' as a fixed expression indicating specific directional flight, translated as a phrase in French ('s'envolaient haut'). Other candidate phrases are compositional and thus rejected.

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold spans: []
- Predicted spans: [['1', '2'], ['15', '16', '17']]
- Model analysis: Selected 'flew over' as a phrasal verb due to translation as 'survolé' in French, indicating it's not suitable for word-by-word glossing. 'Had tea parties' is considered a fixed_expression due to cultural connotations and its translation into French as 'pris le thé', which suggests conventional use.

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['3', '4']]
- Model analysis: Selected 'filled with' as a phrasal verb; expression is commonly stable and translated as 'remplies de' in the context. Rejected 'joy and laughter' and 'Emma's days' as compositional phrases.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['back', 'at', 'home']]
- Model analysis: Selected 'Back at home' as a fixed expression because it is translated non-compositionally as 'De retour chez lui', suggesting conventional usage.

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold spans: []
- Predicted spans: [['grand', 'adventures']]
- Model analysis: The expression 'grand adventures' is selected as a fixed_expression based on lexicalization evidence and specific meaning. All other candidate expressions were rejected as they represent compositional phrases.

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: [['complete', 'with'], ['one', 'day']]
- Model analysis: Selected 'One day' as a fixed expression as it is used to introduce stories and carries translation evidence ('Un jour'). Selected 'complete with' as a fixed expression due to translation as a single unit ('accompagné de') and its fixed nature.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: [['had', 'a', 'wonderful', 'time']]
- Model analysis: The expression 'had a wonderful time' is selected as a light-verb expression, supported by its consistent translation as 'a passé un moment merveilleux' and its function as a unit meaning 'enjoyable experience.' Other candidate expressions were rejected due to their compositional nature.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['14', '15'], ['2', '3']]
- Model analysis: Selected 'dreamt of' as a phrasal verb with high confidence and translation evidence supporting a fixed expression. 'Fairy-tale boutique' selected based on translation glossing evidence supporting it as a lexicalized compound.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['1', '2'], ['7', '8', '9']]
- Model analysis: Selected 'was booming' as a fixed expression indicating business prosperity, consistently supported by translation and boundary analyses. 'From all over' selected as a conventionalized expression for wide geographic distribution, consistently supported across analyses. Rejected 'came to visit' and 'Emma's shop' as they were either ordinary compositional verb phrases or proper noun phrases.

### en:project_239:p6:s3

Emma became famous for her sparkling personality and beautiful shop.

- Gold spans: []
- Predicted spans: [['became', 'famous']]
- Model analysis: The expression 'became famous' is selected as an MWE due to strong agreement across analyses that it forms a conventionalized expression conveying a specific meaning and is supported by translation glossing. All other potential MWEs were rejected as either compositional or routine adjective+noun phrases.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: [['0', '1'], ['9', '10']]
- Model analysis: Selected 'One day' as a fixed expression due to conventional use and direct translation as 'Un jour'. Selected 'heard about' as a phrasal verb due to the complex translation in French, supporting glossing as a unit.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold spans: []
- Predicted spans: [['9', '10', '11']]
- Model analysis: Selected 'special tea party' as a compound. It is a lexicalized expression, which aligns with translation context as 'fête de thé spéciale' and supported by majority analysis agreement. The broader phrase 'special tea party' was preferred over 'tea party' due to its cultural specificity and lexicalization.

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold spans: []
- Predicted spans: [['5', '6']]
- Model analysis: Selected 'so impressed' as a fixed_expression because it forms a conventional expression indicating a strong reaction, consistent with glossing evidence. Rejected all other candidates as they are compositional or standard noun/verb phrases.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['0', '1', '2']]
- Model analysis: Selected 'From then on' as a fixed adverbial phrase based on consistent evidence across analyses and supported by translation context. 'All over the world' and 'making new friends' were rejected due to natural translation and compositional semantics.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['2', '3', '4']]
- Model analysis: The segment contains the expression 'happily ever after' as a fixed_expression, supported by translation and source-token evidence. Other candidates were rejected as compositional phrases.

### en:project_239:p8:s3

Every day was a new adventure filled with laughter, magic, and love.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['6', '7']]
- Model analysis: Selected 'filled with' as a phrasal verb based on conventional usage and translation evidence as a single unit. Rejected other candidates as ordinary compositional phrases.


## False-negative examples to inspect

### en:project_239:p2:s1

Once upon a time, in a small village in France, there was a lovely lady named Emma Bovary.

- Gold spans: [['once', 'upon', 'a', 'time']]
- Predicted spans: [['0', '1', '2', '3']]
- Model analysis: Selected 'Once upon a time' as a fixed_expression due to its conventionalized use in storytelling and its translation as a single phrase 'Il était une fois' in French. Rejected all other candidates as they were deemed compositional or descriptive with no strong MWE properties.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['8', '9', '10']]
- Model analysis: Selected 'a little bit' as a fixed_expression due to its conventionalized usage and translation as a single unit 'un peu' in French. All other candidate phrases are rejected due to either compositional translation or being ordinary descriptive phrases.

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold spans: [['took', 'a', 'walk']]
- Predicted spans: [['2', '3', '4']]
- Model analysis: Selected 'took a walk' as a fixed expression due to its conventional use and translation as a single phrase 'fait une promenade.' All other phrases are compositional or routine and were rejected.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['climbed', 'on'], ['fly', 'high', 'up']]
- Model analysis: Selected 'climbed on' as a phrasal verb, a conventional verb-particle construction, supported by glossing evidence in French ('montait sur'). Selected 'fly high up' as a fixed expression indicating specific directional flight, translated as a phrase in French ('s'envolaient haut'). Other candidate phrases are compositional and thus rejected.

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['3', '4']]
- Model analysis: Selected 'filled with' as a phrasal verb; expression is commonly stable and translated as 'remplies de' in the context. Rejected 'joy and laughter' and 'Emma's days' as compositional phrases.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['back', 'at', 'home']]
- Model analysis: Selected 'Back at home' as a fixed expression because it is translated non-compositionally as 'De retour chez lui', suggesting conventional usage.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: [['had', 'a', 'wonderful', 'time']]
- Model analysis: The expression 'had a wonderful time' is selected as a light-verb expression, supported by its consistent translation as 'a passé un moment merveilleux' and its function as a unit meaning 'enjoyable experience.' Other candidate expressions were rejected due to their compositional nature.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['14', '15'], ['2', '3']]
- Model analysis: Selected 'dreamt of' as a phrasal verb with high confidence and translation evidence supporting a fixed expression. 'Fairy-tale boutique' selected based on translation glossing evidence supporting it as a lexicalized compound.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['1', '2'], ['7', '8', '9']]
- Model analysis: Selected 'was booming' as a fixed expression indicating business prosperity, consistently supported by translation and boundary analyses. 'From all over' selected as a conventionalized expression for wide geographic distribution, consistently supported across analyses. Rejected 'came to visit' and 'Emma's shop' as they were either ordinary compositional verb phrases or proper noun phrases.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: [['0', '1'], ['9', '10']]
- Model analysis: Selected 'One day' as a fixed expression due to conventional use and direct translation as 'Un jour'. Selected 'heard about' as a phrasal verb due to the complex translation in French, supporting glossing as a unit.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['0', '1', '2']]
- Model analysis: Selected 'From then on' as a fixed adverbial phrase based on consistent evidence across analyses and supported by translation context. 'All over the world' and 'making new friends' were rejected due to natural translation and compositional semantics.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['2', '3', '4']]
- Model analysis: The segment contains the expression 'happily ever after' as a fixed_expression, supported by translation and source-token evidence. Other candidates were rejected as compositional phrases.

### en:project_239:p8:s3

Every day was a new adventure filled with laughter, magic, and love.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['6', '7']]
- Model analysis: Selected 'filled with' as a phrasal verb based on conventional usage and translation evidence as a single unit. Rejected other candidates as ordinary compositional phrases.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['10', '11']]
- Model analysis: Selected 'ever after' as a fixed expression. It is a lexicalized phrase used commonly in fairy tales, indicating a happy conclusion. The phrase aligns with the translation 'pour toujours', confirming its idiomatic and stable use.

### en:project_239:p8:s5

The end.

- Gold spans: [['the', 'end']]
- Predicted spans: []
- Model analysis: No MWEs selected. The phrase 'The end' is a compositional noun phrase and is translated naturally word by word. It lacks sufficient idiomatic, lexicalized, or conventionalized value to be considered an MWE.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['of', 'definite', ',', 'indefinite', 'and', 'null', 'articles']]
- Model analysis: No MWE for 'First Responder'; analysis is conflicting and suggests ordinary noun phrase. Selected 'of Definite, Indefinite and Null Articles' as compound due to translation context consistency and glossing support.

### en:project_245:p2:s1

Hunky Felix is a fearless first responder.

- Gold spans: [['first', 'responder']]
- Predicted spans: [['5', '6']]
- Model analysis: The term 'first responder' is a stable, lexicalized compound noun in English, used for emergency personnel and translated as 'premier intervenant' in French. 'Fearless' is not part of the fixed expression.

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['one', 'day'], ['used', 'his', 'downtime', 'explaining']]
- Model analysis: Selected 'One day' as a fixed expression because it is a conventional scene-setting phrase. 'Used his downtime explaining' recognized as a light-verb expression due to its structure and translation evidence showing it's not easily decomposed word-by-word.

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['1', '2'], ['12', '13', '14']]
- Model analysis: Selected 'explained to' as a phrasal verb due to frequent translation as a verb-preposition combination. 'Climbed to save' selected as a fixed expression given translation indicating purpose and intent as a fixed complement pattern.

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold spans: [['a', 'little']]
- Predicted spans: [["{'surface': 'a'}", "{'surface': 'little'}"]]
- Model analysis: Selected the MWE 'a little' as a fixed_expression. It is a conventionalized, lexicalized quantifier expression in English supported by the majority consensus and translation context. Rejected larger spans such as 'a little better now' due to compositional nature.

