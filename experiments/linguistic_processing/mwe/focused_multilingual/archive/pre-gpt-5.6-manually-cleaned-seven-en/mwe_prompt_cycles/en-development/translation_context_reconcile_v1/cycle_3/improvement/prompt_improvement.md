# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.000
- Recall: 0.000
- F1: 0.000

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
- Model analysis: Selected the MWE 'Once upon a time' as it is a conventional story-opening formulaic expression, supported by translation as a unit ('Il était une fois'). Rejected other candidate phrases which are compositional.

### en:project_239:p2:s3

Although Emma had everything she needed, she often dreamed of more exciting adventures.

- Gold spans: [['dreamed', 'of']]
- Predicted spans: [['3', '4', '5'], ['9', '10']]
- Model analysis: Selected 'everything she needed' as it requires glossing per translation context. Selected 'dreamed of' due to its stabilizing verb-preposition structure in English.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['9', '10', '11']]
- Model analysis: Selected 'a little bit of' as a fixed quantifier due to its conventionalized use, translation evidence as 'un peu de', and its treatment as a lexical unit in independent analyses.

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold spans: [['took', 'a', 'walk']]
- Predicted spans: [['2', '3', '4']]
- Model analysis: The only MWE identified is 'take a walk', treated as a light-verb expression. Other candidate phrases were rejected as they are compositional or routine structures.

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold spans: [['found', 'herself']]
- Predicted spans: [['2', '3']]
- Model analysis: Selected 'found herself' as a phrasal verb based on reflexive construction recognized in both source analysis and translation context. Rejected other candidates as ordinary compositional phrases.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['10', '11', '12'], ['2', '3', '4', '5', '6']]
- Model analysis: Selected 'climbed on Glitter's back' (2,3,4,5,6) as a fixed expression based on translation as a verb phrase indicating a conventionalized form. Selected 'fly high up' (10,11,12) as a phrasal verb due to translation evidence and lexicalization as a direction-and-manner expression. Other candidates rejected due to literal interpretation, compositionality, or being single tokens.

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold spans: []
- Predicted spans: [['1', '2'], ['15', '16', '17']]
- Model analysis: Selected 'flew over' as a phrasal verb due to verb-particle identification and translation as a unit. 'Had tea parties' is a recognized light verb construction, confirmed by idiomatic and translation evidence. No other MWEs detected.

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['3', '4', '5']]
- Model analysis: 'filled with' is a phrasal verb selected as the MWE because it represents a verb-particle combination translated collectively in context, supporting glossing as a single lexical unit. Other candidates are rejected as compositional or non-fixed.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['0', '1', '2']]
- Model analysis: 'Back at home' is selected as a fixed expression based on all analyses agreeing on its stability and idiomatic use. Translated context 'De retour chez lui' further supports non-literal interpretation. Other candidates, including 'busy helping' and 'in the village', are rejected due to compositional meanings.

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold spans: []
- Predicted spans: [['10', '11', '12', '13']]
- Model analysis: Selected 'in all her grand adventures' as a fixed_expression due to the analysis indicating conventionalized extension in prepositional scope. Rejected other candidates as they represent compositional phrases.

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: [['0', '1'], ['14', '15']]
- Model analysis: Selected 'One day' as a fixed temporal expression used in narrative contexts. 'Complete with' selected as it consistently corresponds to non-compositional translations indicating inclusion of additional items.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: [['8', '9', '10', '11', '12']]
- Model analysis: Selected 'had a wonderful time' as an idiom as it is lexicalized and supports translation glossing; other candidate expressions rejected for being literal or compositional.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['13', '14', '15']]
- Model analysis: Selected 'fairy-tale boutique' as a compound since 'fairy-tale' modifies 'boutique' indicating a lexicalized unit affecting translation.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['8', '9']]
- Model analysis: Selected 'all over' as a fixed expression, based on translation context suggesting conventionalized use. Rejected 'Business was booming' as an idiomatic MWE due to insufficient consensus and the possibility of it being a descriptive predicate. Other expressions are routine and compositional.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: [['0', '1'], ['9', '10']]
- Model analysis: Two MWEs identified: 'One day' is a fixed expression used to introduce a narrative, supported by both boundary_precision and translation_glossing analyses. 'Heard about' is treated as a light verb expression based on source_conservative and translation_glossing analyses, noting it forms a verb-phrase not translated word by word.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold spans: []
- Predicted spans: [['1', '3'], ['10', '11']]
- Model analysis: Selected 'invite to' as a phrasal verb based on conventionalization and verb-preposition pattern. 'Tea party' is selected as a lexicalized compound noun.

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold spans: []
- Predicted spans: [['12', '13', '14'], ['5', '6']]
- Model analysis: Selected 'so impressed' as a fixed expression based on conventionalization and translation evidence. 'Royal Adventure Planner' selected as a compound title indicating a specific role.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['0', '1', '2'], ['10', '11']]
- Model analysis: Annotated 'From then on' as a fixed_expression based on its fixed adverbial usage and translation as a unit. Annotated 'the world' as a formula conventionally paired in this context with wide-scope expressions.

### en:project_239:p8:s1

In the end, Emma's dreams came true in the most delightful way possible.

- Gold spans: [['came', 'true'], ['in', 'the', 'end']]
- Predicted spans: [['0', '1', '2'], ['6', '7']]
- Model analysis: Selected 'in the end' as a fixed_expression due to its conventional meaning equivalent to 'finally' or 'ultimately'. Also selected 'came true' as a fixed_expression as it represents a stable lexical unit indicating the realization of dreams.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['2', '3', '4']]
- Model analysis: The phrase 'happily ever after' is selected as a fixed expression due to its conventionalized and idiomatic use in English storytelling, corroborated by translation evidence.


## False-negative examples to inspect

### en:project_239:p2:s1

Once upon a time, in a small village in France, there was a lovely lady named Emma Bovary.

- Gold spans: [['once', 'upon', 'a', 'time']]
- Predicted spans: [['0', '1', '2', '3']]
- Model analysis: Selected the MWE 'Once upon a time' as it is a conventional story-opening formulaic expression, supported by translation as a unit ('Il était une fois'). Rejected other candidate phrases which are compositional.

### en:project_239:p2:s3

Although Emma had everything she needed, she often dreamed of more exciting adventures.

- Gold spans: [['dreamed', 'of']]
- Predicted spans: [['3', '4', '5'], ['9', '10']]
- Model analysis: Selected 'everything she needed' as it requires glossing per translation context. Selected 'dreamed of' due to its stabilizing verb-preposition structure in English.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['9', '10', '11']]
- Model analysis: Selected 'a little bit of' as a fixed quantifier due to its conventionalized use, translation evidence as 'un peu de', and its treatment as a lexical unit in independent analyses.

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold spans: [['took', 'a', 'walk']]
- Predicted spans: [['2', '3', '4']]
- Model analysis: The only MWE identified is 'take a walk', treated as a light-verb expression. Other candidate phrases were rejected as they are compositional or routine structures.

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold spans: [['found', 'herself']]
- Predicted spans: [['2', '3']]
- Model analysis: Selected 'found herself' as a phrasal verb based on reflexive construction recognized in both source analysis and translation context. Rejected other candidates as ordinary compositional phrases.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['10', '11', '12'], ['2', '3', '4', '5', '6']]
- Model analysis: Selected 'climbed on Glitter's back' (2,3,4,5,6) as a fixed expression based on translation as a verb phrase indicating a conventionalized form. Selected 'fly high up' (10,11,12) as a phrasal verb due to translation evidence and lexicalization as a direction-and-manner expression. Other candidates rejected due to literal interpretation, compositionality, or being single tokens.

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['3', '4', '5']]
- Model analysis: 'filled with' is a phrasal verb selected as the MWE because it represents a verb-particle combination translated collectively in context, supporting glossing as a single lexical unit. Other candidates are rejected as compositional or non-fixed.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['0', '1', '2']]
- Model analysis: 'Back at home' is selected as a fixed expression based on all analyses agreeing on its stability and idiomatic use. Translated context 'De retour chez lui' further supports non-literal interpretation. Other candidates, including 'busy helping' and 'in the village', are rejected due to compositional meanings.

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: [['0', '1'], ['14', '15']]
- Model analysis: Selected 'One day' as a fixed temporal expression used in narrative contexts. 'Complete with' selected as it consistently corresponds to non-compositional translations indicating inclusion of additional items.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: [['8', '9', '10', '11', '12']]
- Model analysis: Selected 'had a wonderful time' as an idiom as it is lexicalized and supports translation glossing; other candidate expressions rejected for being literal or compositional.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['13', '14', '15']]
- Model analysis: Selected 'fairy-tale boutique' as a compound since 'fairy-tale' modifies 'boutique' indicating a lexicalized unit affecting translation.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['8', '9']]
- Model analysis: Selected 'all over' as a fixed expression, based on translation context suggesting conventionalized use. Rejected 'Business was booming' as an idiomatic MWE due to insufficient consensus and the possibility of it being a descriptive predicate. Other expressions are routine and compositional.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: [['0', '1'], ['9', '10']]
- Model analysis: Two MWEs identified: 'One day' is a fixed expression used to introduce a narrative, supported by both boundary_precision and translation_glossing analyses. 'Heard about' is treated as a light verb expression based on source_conservative and translation_glossing analyses, noting it forms a verb-phrase not translated word by word.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['0', '1', '2'], ['10', '11']]
- Model analysis: Annotated 'From then on' as a fixed_expression based on its fixed adverbial usage and translation as a unit. Annotated 'the world' as a formula conventionally paired in this context with wide-scope expressions.

### en:project_239:p8:s1

In the end, Emma's dreams came true in the most delightful way possible.

- Gold spans: [['came', 'true'], ['in', 'the', 'end']]
- Predicted spans: [['0', '1', '2'], ['6', '7']]
- Model analysis: Selected 'in the end' as a fixed_expression due to its conventional meaning equivalent to 'finally' or 'ultimately'. Also selected 'came true' as a fixed_expression as it represents a stable lexical unit indicating the realization of dreams.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['2', '3', '4']]
- Model analysis: The phrase 'happily ever after' is selected as a fixed expression due to its conventionalized and idiomatic use in English storytelling, corroborated by translation evidence.

### en:project_239:p8:s3

Every day was a new adventure filled with laughter, magic, and love.

- Gold spans: [['filled', 'with']]
- Predicted spans: []
- Model analysis: not recorded

### en:project_239:p8:s4

And they all lived happily, sparkly, and joyfully ever after.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['10', '11']]
- Model analysis: Selected the fixed expression 'ever after' (tokens 10 and 11) based on its idiomatic use and translation glossing as 'pour toujours', matching conventionalized fairy tale phrase use. All other candidates were rejected as they represent ordinary compositional phrases.

### en:project_239:p8:s5

The end.

- Gold spans: [['the', 'end']]
- Predicted spans: []
- Model analysis: No MWEs identified. 'The end' is considered a standard noun phrase without evidence of lexicalization or idiomatic usage, despite translation as a unit.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold spans: [['first', 'responder']]
- Predicted spans: [['0', '1']]
- Model analysis: Selected 'First Responder' as a compound as it's a recognized term for emergency personnel; rejected 'Correct Use of Definite, Indefinite and Null Articles' as compositional with no strong evidence of lexicalization or idiomatic usage.

