# MWE prompt score summary

- Split: `development`
- Records: 336
- Exact match: 89 (26.5%)
- Precision: 0.113
- Recall: 0.234
- F1: 0.152

## Error examples

### en:project_239:p2:s1

Once upon a time, in a small village in France, there was a lovely lady named Emma Bovary.

- Gold: [['once', 'upon', 'a', 'time']]
- Predicted: [['0', '1', '2', '3']]
- Model analysis: Selected 'Once upon a time' as a fixed_expression due to its conventionalized use in storytelling and its translation as a single phrase 'Il était une fois' in French. Rejected all other candidates as they were deemed compositional or descriptive with no strong MWE properties.

### en:project_239:p2:s2

Emma lived in a beautiful house with her husband, Charles, who was a kind and gentle doctor.

- Gold: []
- Predicted: [['1', '2']]
- Model analysis: Selected 'lived in' as a phrasal verb due to source-token evidence and translation context. Rejected all other candidates as they are ordinary compositional phrases.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold: [['little', 'bit', 'of']]
- Predicted: [['8', '9', '10']]
- Model analysis: Selected 'a little bit' as a fixed_expression due to its conventionalized usage and translation as a single unit 'un peu' in French. All other candidate phrases are rejected due to either compositional translation or being ordinary descriptive phrases.

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold: [['took', 'a', 'walk']]
- Predicted: [['2', '3', '4']]
- Model analysis: Selected 'took a walk' as a fixed expression due to its conventional use and translation as a single phrase 'fait une promenade.' All other phrases are compositional or routine and were rejected.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold: [['high', 'up']]
- Predicted: [['climbed', 'on'], ['fly', 'high', 'up']]
- Model analysis: Selected 'climbed on' as a phrasal verb, a conventional verb-particle construction, supported by glossing evidence in French ('montait sur'). Selected 'fly high up' as a fixed expression indicating specific directional flight, translated as a phrase in French ('s'envolaient haut'). Other candidate phrases are compositional and thus rejected.

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold: []
- Predicted: [['1', '2'], ['15', '16', '17']]
- Model analysis: Selected 'flew over' as a phrasal verb due to translation as 'survolé' in French, indicating it's not suitable for word-by-word glossing. 'Had tea parties' is considered a fixed_expression due to cultural connotations and its translation into French as 'pris le thé', which suggests conventional use.

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold: [['filled', 'with']]
- Predicted: [['3', '4']]
- Model analysis: Selected 'filled with' as a phrasal verb; expression is commonly stable and translated as 'remplies de' in the context. Rejected 'joy and laughter' and 'Emma's days' as compositional phrases.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold: [['at', 'home']]
- Predicted: [['back', 'at', 'home']]
- Model analysis: Selected 'Back at home' as a fixed expression because it is translated non-compositionally as 'De retour chez lui', suggesting conventional usage.

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold: []
- Predicted: [['grand', 'adventures']]
- Model analysis: The expression 'grand adventures' is selected as a fixed_expression based on lexicalization evidence and specific meaning. All other candidate expressions were rejected as they represent compositional phrases.

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold: [['complete', 'with']]
- Predicted: [['complete', 'with'], ['one', 'day']]
- Model analysis: Selected 'One day' as a fixed expression as it is used to introduce stories and carries translation evidence ('Un jour'). Selected 'complete with' as a fixed expression due to translation as a single unit ('accompagné de') and its fixed nature.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold: [['had', 'a', 'time']]
- Predicted: [['had', 'a', 'wonderful', 'time']]
- Model analysis: The expression 'had a wonderful time' is selected as a light-verb expression, supported by its consistent translation as 'a passé un moment merveilleux' and its function as a unit meaning 'enjoyable experience.' Other candidate expressions were rejected due to their compositional nature.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold: [['dreamt', 'of']]
- Predicted: [['14', '15'], ['2', '3']]
- Model analysis: Selected 'dreamt of' as a phrasal verb with high confidence and translation evidence supporting a fixed expression. 'Fairy-tale boutique' selected based on translation glossing evidence supporting it as a lexicalized compound.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold: [['all', 'over']]
- Predicted: [['1', '2'], ['7', '8', '9']]
- Model analysis: Selected 'was booming' as a fixed expression indicating business prosperity, consistently supported by translation and boundary analyses. 'From all over' selected as a conventionalized expression for wide geographic distribution, consistently supported across analyses. Rejected 'came to visit' and 'Emma's shop' as they were either ordinary compositional verb phrases or proper noun phrases.

### en:project_239:p6:s3

Emma became famous for her sparkling personality and beautiful shop.

- Gold: []
- Predicted: [['became', 'famous']]
- Model analysis: The expression 'became famous' is selected as an MWE due to strong agreement across analyses that it forms a conventionalized expression conveying a specific meaning and is supported by translation glossing. All other potential MWEs were rejected as either compositional or routine adjective+noun phrases.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold: [['heard', 'about']]
- Predicted: [['0', '1'], ['9', '10']]
- Model analysis: Selected 'One day' as a fixed expression due to conventional use and direct translation as 'Un jour'. Selected 'heard about' as a phrasal verb due to the complex translation in French, supporting glossing as a unit.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold: []
- Predicted: [['9', '10', '11']]
- Model analysis: Selected 'special tea party' as a compound. It is a lexicalized expression, which aligns with translation context as 'fête de thé spéciale' and supported by majority analysis agreement. The broader phrase 'special tea party' was preferred over 'tea party' due to its cultural specificity and lexicalization.

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold: []
- Predicted: [['5', '6']]
- Model analysis: Selected 'so impressed' as a fixed_expression because it forms a conventional expression indicating a strong reaction, consistent with glossing evidence. Rejected all other candidates as they are compositional or standard noun/verb phrases.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted: [['0', '1', '2']]
- Model analysis: Selected 'From then on' as a fixed adverbial phrase based on consistent evidence across analyses and supported by translation context. 'All over the world' and 'making new friends' were rejected due to natural translation and compositional semantics.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold: [['lived', 'happily', 'ever', 'after']]
- Predicted: [['2', '3', '4']]
- Model analysis: The segment contains the expression 'happily ever after' as a fixed_expression, supported by translation and source-token evidence. Other candidates were rejected as compositional phrases.

### en:project_239:p8:s3

Every day was a new adventure filled with laughter, magic, and love.

- Gold: [['filled', 'with']]
- Predicted: [['6', '7']]
- Model analysis: Selected 'filled with' as a phrasal verb based on conventional usage and translation evidence as a single unit. Rejected other candidates as ordinary compositional phrases.

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold: [['lived', 'happily', 'ever', 'after']]
- Predicted: [['10', '11']]
- Model analysis: Selected 'ever after' as a fixed expression. It is a lexicalized phrase used commonly in fairy tales, indicating a happy conclusion. The phrase aligns with the translation 'pour toujours', confirming its idiomatic and stable use.

### en:project_239:p8:s5

The end.

- Gold: [['the', 'end']]
- Predicted: []
- Model analysis: No MWEs selected. The phrase 'The end' is a compositional noun phrase and is translated naturally word by word. It lacks sufficient idiomatic, lexicalized, or conventionalized value to be considered an MWE.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold: [['first', 'responder']]
- Predicted: [['of', 'definite', ',', 'indefinite', 'and', 'null', 'articles']]
- Model analysis: No MWE for 'First Responder'; analysis is conflicting and suggests ordinary noun phrase. Selected 'of Definite, Indefinite and Null Articles' as compound due to translation context consistency and glossing support.

### en:project_245:p2:s1

Hunky Felix is a fearless first responder.

- Gold: [['first', 'responder']]
- Predicted: [['5', '6']]
- Model analysis: The term 'first responder' is a stable, lexicalized compound noun in English, used for emergency personnel and translated as 'premier intervenant' in French. 'Fearless' is not part of the fixed expression.

### en:project_245:p2:s2

Not only does he save lives, but he loves to teach proper English grammar.

- Gold: []
- Predicted: [['0', '1']]
- Model analysis: Selected 'Not only' as a fixed expression (MWE) due to majority agreement and translation evidence of fixed usage. Rejected 'save lives' and 'proper English grammar' as they are ordinary verb-object and descriptive noun phrases, respectively, lacking evidence of lexicalization or idiomaticity.

