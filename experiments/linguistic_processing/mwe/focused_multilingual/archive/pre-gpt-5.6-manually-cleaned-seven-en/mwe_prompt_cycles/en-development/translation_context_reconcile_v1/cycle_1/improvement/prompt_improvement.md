# Conservative MWE prompt-improvement proposal

This report is intentionally general. It is meant to guide a prompt revision without encoding project-specific answers or memorising development examples.

## Current score

- Records: 336
- Project IDs: [239, 245, 254, 255, 257, 261, 263]
- Precision: 0.089
- Recall: 0.349
- F1: 0.142

## General revision principles

- Mark an MWE only when the expression is conventionalized, idiomatic, lexicalized, or functions as a stable multi-token lexical unit.
- Do not mark ordinary compositional adjective+noun, determiner+noun, or verb+object phrases just because they are frequent in the text.
- Prefer high precision: when unsure, leave tokens unmarked rather than inventing an MWE.
- Keep labels broad and language-neutral; avoid rules tied to a single project or named example.
- Preserve the input token sequence exactly and only add MWE IDs to tokens that belong to accepted multi-token expressions.

## False-positive examples to inspect

### en:project_239:p1:s2

Madame Bovary retold

- Gold spans: []
- Predicted spans: [["{'surface': 'madame'}", "{'surface': 'bovary'}"]]
- Model analysis: The MWE analysis identifies 'Madame Bovary' as a proper noun, reflecting its usage as a title or name. Both 'boundary_precision' and 'source_conservative' analyses support treating these two tokens as a single unit due to their role as a stable expression. Although 'translation_glossing' rejects 'Madame Bovary' due to direct translation, the translation context confirms it is a single concept. 'Bovary retold' and 'Madame Bovary retold' are not plausible MWEs as there is no evidence of stability as a lexical unit.

### en:project_239:p2:s2

Emma lived in a beautiful house with her husband, Charles, who was a kind and gentle doctor.

- Gold spans: []
- Predicted spans: [['a', 'kind', 'and', 'gentle', 'doctor'], ['lived', 'in']]
- Model analysis: The MWE 'lived in' was selected as it is a phrasal verb indicating residence with consistent support across all analyses and aligns with French 'vivait dans'. 'A kind and gentle doctor' was selected due to its translation as 'médecin gentil et doux' in French, suggesting a meaningful collective gloss.

### en:project_239:p2:s3

Although Emma had everything she needed, she often dreamed of more exciting adventures.

- Gold spans: [['dreamed', 'of']]
- Predicted spans: [['dreamed', 'of'], ['exciting', 'adventures']]
- Model analysis: The phrasal verb 'dreamed of' (tokens: 9-10) was selected for combined meaning and glossing benefits; it translates as a single word 'rêvait' in French. The collocation 'exciting adventures' (tokens: 12-13) forms a natural collocation, supported by translation consideration, appearing as a cohesive unit 'aventures excitantes'. 'Although' was not marked as an MWE as it's a common standalone conjunction.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['a', 'little', 'bit', 'of'], ['one', 'sunny', 'day']]
- Model analysis: The segment contains two MWEs: 'One sunny day' and 'a little bit of'. 'One sunny day' is a common fixed adverbial expression as supported by all analyses and the translation context. 'A little bit of' is a fixed phrase representing 'un peu de' in French, indicating a non-compositional and essential phrase for translation or glossing. Other token groups, such as 'in her life,' are rejected based on compositionality and lack of forced phrase-level translation, as all analyses indicated.

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold spans: [['took', 'a', 'walk']]
- Predicted spans: [['2', '3', '4'], ['7', '8']]
- Model analysis: The MWE 'took a walk' was selected due to its recognition as a stable idiomatic expression that translates as a unit in French ('fait une promenade'), supporting the glossing purpose. 'Village fair' was also selected, regarded as a common collocation recognized as a single concept referring to a specific type of event. Other candidates were rejected as they were deemed descriptive and compositional, thus better understood word by word.

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold spans: [['found', 'herself']]
- Predicted spans: [['even', 'found', 'herself']]
- Model analysis: The expression 'even found herself' was selected as a MWE because it is a reflexive construction best captured as a phrase. Both 'boundary_precision' and 'translation_glossing' analyses agree on this, with 'translation_glossing' presenting strong non-compositional translation correlation ('s'est même trouvé'). The expression 'sparkly pink' was not included as an MWE, following the majority analysis consensus that it functions compositionally. The 'named Glitter' construct was omitted as it was deemed sufficiently clear when glossed word by word, despite some selection preference in 'boundary_precision'.

### en:project_239:p4:s1

Glitter the unicorn was very special.

- Gold spans: []
- Predicted spans: [['4', '5']]
- Model analysis: After reviewing the independent analyses, 'very special' is selected as an MWE based on translation glossing analysis. The translation context supports it as a set phrase ('très spéciale') that benefits from phrase-level glossing. Other candidate expressions were rejected as they did not meet the criteria for MWEs in this context.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['climbed', 'on'], ['fly', 'high', 'up', 'into', 'the', 'sky'], ['glitter', "'s", 'back']]
- Model analysis: The analysis reconciles the following MWEs: (1) 'climbed on' is a phrasal verb suggested by both translation evidence and conventional usage. (2) 'Glitter's back' functions as a possessive phrase needing unified translation as indicated by the French counterpart. (3) 'fly high up into the sky' combines elements from analyses to describe a full motion, supported by both boundary precision and translation glossing evidence.

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold spans: []
- Predicted spans: [['flew', 'over'], ['had', 'tea', 'parties'], ['talking', 'animals']]
- Model analysis: The MWE analysis selects 'flew over' as a phrasal verb based on consistent evidence across analyses and translation suggesting it as an idiomatic unit. 'Had tea parties' is treated as an idiomatic phrase as indicated by idiomatic translation to 'pris le thé'. 'Talking animals' is accepted as a fixed expression given 'animaux qui parlaient' reflects a recognized conceptual unit, despite 'source_conservative' analysis disagreement.

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['were', 'filled', 'with']]
- Model analysis: The phrase 'were filled with' was selected as an MWE due to its status as a phrasal verb in English that corresponds to the French phrase 'étaient remplies de'. The expression functions as a cohesive unit indicating a state of being, making it appropriate for phrase-level glossing. The candidates 'with joy' and 'joy and laughter' were not selected as MWEs; 'with joy' was uncertain and 'joy and laughter' was rejected since they are compositional and translate directly into French.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['back', 'at', 'home']]
- Model analysis: The phrase 'Back at home' is selected as a MWE. All three analyses agree that it is a fixed expression, supported by translation evidence (French: 'De retour chez lui'). The group 'busy helping' and 'in the village' were considered but rejected due to their compositional nature in this context.

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold spans: []
- Predicted spans: [['emma', 'happy'], ['loved', 'to', 'see'], ['supported', 'her', 'in', 'all', 'her', 'grand', 'adventures']]
- Model analysis: Reconciled three main MWEs: 'loved to see' (phrasal verb with supporting analyses from boundary_precision and source_conservative), 'Emma happy' (perceptual fixed expression based on source-conservative and boundary-precision justifications), and 'supported her in all her grand adventures' (idiomatic expression supported by translation glossing as it is treated in French as a non-compositional unit).

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: [['0', '1'], ['14', '15']]
- Model analysis: The phrase 'One day' is selected as a fixed temporal expression, supported by its non-literal translation as 'Un jour' in the context. The phrase 'complete with' is also selected due to its translation to 'accompagné de', indicating a stable idiomatic usage beyond literal composition.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: [['had', 'a', 'wonderful', 'time']]
- Model analysis: The expression 'had a wonderful time' is selected due to its meaning in translation as 'un moment merveilleux' in French, which indicates a non-compositional, phrase-level translation justifying it as a fixed expression. Other potential MWEs like 'playing games' and 'telling stories' were considered but rejected due to their literal translations.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold spans: [['dreamt', 'of']]
- Predicted spans: [['a', 'little', 'fairy-tale', 'boutique'], ['dreamt', 'of']]
- Model analysis: After reviewing the analyses, 'dreamt of' is confirmed as a necessary phrasal verb, supported by both source and translation evidence. The entire phrase 'a little fairy-tale boutique' is selected based on translation glossing, suggesting it is perceived as a single concept, rather than just 'fairy-tale boutique'. Other expressions like 'grander things', 'magical potions', and 'enchanted dresses' are rejected as they can be glossed directly in translation and are widely understood without requiring phrase-level interpretation.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['business', 'was', 'booming'], ['from', 'all', 'over']]
- Model analysis: Two MWEs were selected for this segment. 'Business was booming' was identified as a fixed expression in all analyses due to its non-compositional meaning, corresponding well with 'en plein essor' in the translation context. The phrase 'from all over' was chosen as a set phrase, frequently used to imply diverse origins, and corresponds to 'de partout' in the translation context. Other candidate MWEs were rejected due to compositionality or lack of evidence for fixed usage.

### en:project_239:p6:s3

Emma became famous for her sparkling personality and beautiful shop.

- Gold spans: []
- Predicted spans: [['became', 'famous'], ['sparkling', 'personality']]
- Model analysis: The multi-word expressions 'became famous' and 'sparkling personality' are selected based on agreement across analyses and translation context. 'Became famous' is a fixed expression that is rendered as a unit in the French translation, while 'sparkling personality' is a common collocation with specific meaning that aligns with its French counterpart. 'Beautiful shop' is rejected as it is straightforwardly compositional.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold spans: [['heard', 'about']]
- Predicted spans: [['emma', 'bovary'], ['heard', 'about'], ['king', 'and', 'queen', 'of', 'france'], ['one', 'day']]
- Model analysis: All analyses agree to select 'One day' as a fixed time expression. Although 'King and Queen' alone was debated, 'King and Queen of France' has translation evidence as a collocation; it's included as it forms a stable expression. 'Heard about' is consistently identified as a phrasal verb. Finally, all agreed that 'Emma Bovary' is a proper noun.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold spans: []
- Predicted spans: [['1', '2', '3'], ['10', '11']]
- Model analysis: Reconciled 'invited her to' as MWE due to strong translation evidence ('l'ont invitée dans') suggesting it functions as a single expression requiring phrase-level glossing. 'Tea party' was also confirmed as an MWE, supported by multiple analyses and consistent cross-linguistic expression with 'fête de thé'.

### en:project_239:p7:s3

Emma wore her fanciest dress, and Glitter the unicorn decorated his mane with sparkling ribbons.

- Gold spans: []
- Predicted spans: [['her', 'fanciest', 'dress'], ['with', 'sparkling', 'ribbons']]
- Model analysis: The segment has two plausible MWEs. 'Her fanciest dress' is selected as a MWE because it translates to a non-compositional phrase in French, supporting its treatment as a unit for glossing. The selection is corroborated by both 'boundary_precision' and 'translation_glossing'. 'With sparkling ribbons' is also marked as an MWE; it corresponds to the French 'avec des rubans scintillants', suggesting it is best treated as a single phrase in glossing, supported by 'translation_glossing' and 'source_conservative'.


## False-negative examples to inspect

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold spans: [['little', 'bit', 'of']]
- Predicted spans: [['a', 'little', 'bit', 'of'], ['one', 'sunny', 'day']]
- Model analysis: The segment contains two MWEs: 'One sunny day' and 'a little bit of'. 'One sunny day' is a common fixed adverbial expression as supported by all analyses and the translation context. 'A little bit of' is a fixed phrase representing 'un peu de' in French, indicating a non-compositional and essential phrase for translation or glossing. Other token groups, such as 'in her life,' are rejected based on compositionality and lack of forced phrase-level translation, as all analyses indicated.

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold spans: [['took', 'a', 'walk']]
- Predicted spans: [['2', '3', '4'], ['7', '8']]
- Model analysis: The MWE 'took a walk' was selected due to its recognition as a stable idiomatic expression that translates as a unit in French ('fait une promenade'), supporting the glossing purpose. 'Village fair' was also selected, regarded as a common collocation recognized as a single concept referring to a specific type of event. Other candidates were rejected as they were deemed descriptive and compositional, thus better understood word by word.

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold spans: [['found', 'herself']]
- Predicted spans: [['even', 'found', 'herself']]
- Model analysis: The expression 'even found herself' was selected as a MWE because it is a reflexive construction best captured as a phrase. Both 'boundary_precision' and 'translation_glossing' analyses agree on this, with 'translation_glossing' presenting strong non-compositional translation correlation ('s'est même trouvé'). The expression 'sparkly pink' was not included as an MWE, following the majority analysis consensus that it functions compositionally. The 'named Glitter' construct was omitted as it was deemed sufficiently clear when glossed word by word, despite some selection preference in 'boundary_precision'.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold spans: [['high', 'up']]
- Predicted spans: [['climbed', 'on'], ['fly', 'high', 'up', 'into', 'the', 'sky'], ['glitter', "'s", 'back']]
- Model analysis: The analysis reconciles the following MWEs: (1) 'climbed on' is a phrasal verb suggested by both translation evidence and conventional usage. (2) 'Glitter's back' functions as a possessive phrase needing unified translation as indicated by the French counterpart. (3) 'fly high up into the sky' combines elements from analyses to describe a full motion, supported by both boundary precision and translation glossing evidence.

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold spans: [['filled', 'with']]
- Predicted spans: [['were', 'filled', 'with']]
- Model analysis: The phrase 'were filled with' was selected as an MWE due to its status as a phrasal verb in English that corresponds to the French phrase 'étaient remplies de'. The expression functions as a cohesive unit indicating a state of being, making it appropriate for phrase-level glossing. The candidates 'with joy' and 'joy and laughter' were not selected as MWEs; 'with joy' was uncertain and 'joy and laughter' was rejected since they are compositional and translate directly into French.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold spans: [['at', 'home']]
- Predicted spans: [['back', 'at', 'home']]
- Model analysis: The phrase 'Back at home' is selected as a MWE. All three analyses agree that it is a fixed expression, supported by translation evidence (French: 'De retour chez lui'). The group 'busy helping' and 'in the village' were considered but rejected due to their compositional nature in this context.

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold spans: [['complete', 'with']]
- Predicted spans: [['0', '1'], ['14', '15']]
- Model analysis: The phrase 'One day' is selected as a fixed temporal expression, supported by its non-literal translation as 'Un jour' in the context. The phrase 'complete with' is also selected due to its translation to 'accompagné de', indicating a stable idiomatic usage beyond literal composition.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold spans: [['had', 'a', 'time']]
- Predicted spans: [['had', 'a', 'wonderful', 'time']]
- Model analysis: The expression 'had a wonderful time' is selected due to its meaning in translation as 'un moment merveilleux' in French, which indicates a non-compositional, phrase-level translation justifying it as a fixed expression. Other potential MWEs like 'playing games' and 'telling stories' were considered but rejected due to their literal translations.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold spans: [['all', 'over']]
- Predicted spans: [['business', 'was', 'booming'], ['from', 'all', 'over']]
- Model analysis: Two MWEs were selected for this segment. 'Business was booming' was identified as a fixed expression in all analyses due to its non-compositional meaning, corresponding well with 'en plein essor' in the translation context. The phrase 'from all over' was chosen as a set phrase, frequently used to imply diverse origins, and corresponds to 'de partout' in the translation context. Other candidate MWEs were rejected due to compositionality or lack of evidence for fixed usage.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold spans: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted spans: [['all', 'over', 'the', 'world'], ['from', 'then', 'on']]
- Model analysis: The phrase 'From then on' is consistently identified as an MWE across all analyses due to its function as a fixed temporal transition, which corresponds to the French translation indicating continuity from a point in time. The phrase 'all over the world' is also consistently selected as an MWE, as it forms a stable expression indicating global scope and is glossed as a unit in the French translation. 'Making new friends' is rejected as an MWE since it is compositional despite some idiomatic rendering in French.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold spans: [['lived', 'happily', 'ever', 'after']]
- Predicted spans: [['1', '2', '3', '4']]
- Model analysis: The expression 'lived happily ever after' is selected as a single MWE because it is a fixed idiomatic expression representing a fairy tale ending, confirmed by its direct translation into French as a phrase ('vécut heureuse à jamais'). Analyses prioritize source-token evidence and translation context to support its treatment as a unit.

### en:project_245:p2:s3

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

- Gold spans: [['stuck', 'in']]
- Predicted spans: [['one', 'day'], ['stuck', 'in', 'a', 'tree'], ['used', 'his', 'downtime']]
- Model analysis: The phrase 'One day' is a fixed time expression, agreed upon by all analyses due to its common usage in English and translation as 'Un jour' in French. 'Stuck in a tree' was selected as a condition description because it functions as a single conceptual unit describing a specific state, confirmed by multiple analyses and the French translation 'coincé dans un arbre'. 'Used his downtime' was chosen given the phrase's translation as 'a utilisé son temps libre', indicating its recognition as a stable expression concerning the utilization of free time, despite borderline fixedness in source analysis.

### en:project_245:p3:s1

Felix explained to the cat, "A tree is what I climbed to save you.

- Gold spans: [['explained', 'to']]
- Predicted spans: [['save', 'you']]
- Model analysis: The analysis concluded that 'save you' should be marked as a plausible MWE. Despite 'save you' being directly translated and compositional, it matches a common collocation with purpose indication, fixed in both English and French ('pour te sauver'). Other candidates, including 'climbed to save' and 'is what', are rejected as they are literal or grammatical constructions translatable word-by-word.

### en:project_245:p3:s3

The cat purred, understanding a little better now.

- Gold spans: [['a', 'little']]
- Predicted spans: [['5', '6', '7']]
- Model analysis: Resolved to include the MWE 'a little better' (tokens 5-7) based on consistent selection across analyses and corroborated by non-compositional translation into French ('un peu mieux'). 'Understanding a little better' was not selected due to insufficient evidence of it being a fixed expression, while 'better now' was confirmed to be compositional.

### en:project_245:p4:s3

The dog wagged its tail, clearly pleased with the lesson.

- Gold spans: [['pleased', 'with']]
- Predicted spans: [['wagged', 'its', 'tail']]
- Model analysis: The phrase 'wagged its tail' is a widely recognized action for dogs and is consistently marked across all analyses, supported by its translation to 'remué la queue' in French, thus justifying it as an MWE. The expressions 'clearly pleased' and 'pleased with' are rejected as MWEs. 'Clearly pleased' is seen as compositional and literally interpretable, while 'pleased with' functions as a regular collocation in both English and French that doesn't benefit significantly from being treated as an MWE.

### en:project_245:p5:s3

Felix replied, "Thank you!

- Gold spans: [['thank', 'you']]
- Predicted spans: [["{'surface': 'thank'}", "{'surface': 'you'}"]]
- Model analysis: The expression 'Thank you' is consistently identified as an MWE by all analyses. It is a conventional phrase and rendered as 'Merci' in French, representing a non-compositional unit requiring phrase-level glossing.

### en:project_245:p6:s4

Felix asked, emphasizing ‘the barbecue’ they both knew about.

- Gold spans: [['knew', 'about']]
- Predicted spans: [['the', 'barbecue'], ['they', 'both', 'knew', 'about']]
- Model analysis: Selected 'emphasizing' as a single-term emphasis due to distinct French translation, although its combination with 'the barbecue' was uncertain. 'The barbecue' chosen as MWEs based on emphasis in context, thus forms an integral unit. Resolved 'they both knew about' as a unit by translation evidence indicating a more stable expression in French.

### en:project_245:p7:s1

Our hero, Felix, went to the grocery store next.

- Gold spans: [['grocery', 'store']]
- Predicted spans: [['the', 'grocery', 'store'], ['went', 'to']]
- Model analysis: The analyses suggested that 'went to the grocery store' could be a fixed expression due to its common translation. However, it's more precise to treat 'went to' as a phrasal verb and 'the grocery store' as a compound noun due to evidence from French translation and conventional usage. 'Next' was consistently deemed non-idiomatic.

### en:project_245:p7:s3

"An apple a day keeps the doctor away," he mused.

- Gold spans: [['keeps', 'away']]
- Predicted spans: [['an', 'apple', 'a', 'day', 'keeps', 'the', 'doctor', 'away']]
- Model analysis: The segment consists of a single MWE: 'An apple a day keeps the doctor away.' This phrase was unanimously selected by all analyses as it is a well-known idiomatic expression that is typically translated as a whole in other languages, such as French ('Une pomme par jour éloigne le médecin'). Given its fixed nature and cultural significance, it necessitates phrase-level glossing.

### en:project_245:p8:s1

A man thanked Felix, saying, "You are an amazing first responder."

- Gold spans: [['first', 'responder."']]
- Predicted spans: [['first', 'responder']]
- Model analysis: The MWE analysis finalized 'first responder' as a multi-word expression due to its nature as a conventional compound noun and its translation to 'secouriste' in French, indicating it functions as a single conceptual unit. Other combinations such as 'amazing first responder' were considered but rejected as the modifier 'amazing' is not part of the fixed phrase.

