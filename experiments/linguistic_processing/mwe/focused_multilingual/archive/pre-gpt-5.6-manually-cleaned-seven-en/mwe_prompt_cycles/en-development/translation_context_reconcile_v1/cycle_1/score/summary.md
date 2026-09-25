# MWE prompt score summary

- Split: `development`
- Records: 336
- Exact match: 24 (7.1%)
- Precision: 0.089
- Recall: 0.349
- F1: 0.142

## Error examples

### en:project_239:p1:s2

Madame Bovary retold

- Gold: []
- Predicted: [["{'surface': 'madame'}", "{'surface': 'bovary'}"]]
- Model analysis: The MWE analysis identifies 'Madame Bovary' as a proper noun, reflecting its usage as a title or name. Both 'boundary_precision' and 'source_conservative' analyses support treating these two tokens as a single unit due to their role as a stable expression. Although 'translation_glossing' rejects 'Madame Bovary' due to direct translation, the translation context confirms it is a single concept. 'Bovary retold' and 'Madame Bovary retold' are not plausible MWEs as there is no evidence of stability as a lexical unit.

### en:project_239:p2:s2

Emma lived in a beautiful house with her husband, Charles, who was a kind and gentle doctor.

- Gold: []
- Predicted: [['a', 'kind', 'and', 'gentle', 'doctor'], ['lived', 'in']]
- Model analysis: The MWE 'lived in' was selected as it is a phrasal verb indicating residence with consistent support across all analyses and aligns with French 'vivait dans'. 'A kind and gentle doctor' was selected due to its translation as 'médecin gentil et doux' in French, suggesting a meaningful collective gloss.

### en:project_239:p2:s3

Although Emma had everything she needed, she often dreamed of more exciting adventures.

- Gold: [['dreamed', 'of']]
- Predicted: [['dreamed', 'of'], ['exciting', 'adventures']]
- Model analysis: The phrasal verb 'dreamed of' (tokens: 9-10) was selected for combined meaning and glossing benefits; it translates as a single word 'rêvait' in French. The collocation 'exciting adventures' (tokens: 12-13) forms a natural collocation, supported by translation consideration, appearing as a cohesive unit 'aventures excitantes'. 'Although' was not marked as an MWE as it's a common standalone conjunction.

### en:project_239:p3:s1

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

- Gold: [['little', 'bit', 'of']]
- Predicted: [['a', 'little', 'bit', 'of'], ['one', 'sunny', 'day']]
- Model analysis: The segment contains two MWEs: 'One sunny day' and 'a little bit of'. 'One sunny day' is a common fixed adverbial expression as supported by all analyses and the translation context. 'A little bit of' is a fixed phrase representing 'un peu de' in French, indicating a non-compositional and essential phrase for translation or glossing. Other token groups, such as 'in her life,' are rejected based on compositionality and lack of forced phrase-level translation, as all analyses indicated.

### en:project_239:p3:s2

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

- Gold: [['took', 'a', 'walk']]
- Predicted: [['2', '3', '4'], ['7', '8']]
- Model analysis: The MWE 'took a walk' was selected due to its recognition as a stable idiomatic expression that translates as a unit in French ('fait une promenade'), supporting the glossing purpose. 'Village fair' was also selected, regarded as a common collocation recognized as a single concept referring to a specific type of event. Other candidates were rejected as they were deemed descriptive and compositional, thus better understood word by word.

### en:project_239:p3:s3

She even found herself a sparkly pink unicorn named Glitter.

- Gold: [['found', 'herself']]
- Predicted: [['even', 'found', 'herself']]
- Model analysis: The expression 'even found herself' was selected as a MWE because it is a reflexive construction best captured as a phrase. Both 'boundary_precision' and 'translation_glossing' analyses agree on this, with 'translation_glossing' presenting strong non-compositional translation correlation ('s'est même trouvé'). The expression 'sparkly pink' was not included as an MWE, following the majority analysis consensus that it functions compositionally. The 'named Glitter' construct was omitted as it was deemed sufficiently clear when glossed word by word, despite some selection preference in 'boundary_precision'.

### en:project_239:p4:s1

Glitter the unicorn was very special.

- Gold: []
- Predicted: [['4', '5']]
- Model analysis: After reviewing the independent analyses, 'very special' is selected as an MWE based on translation glossing analysis. The translation context supports it as a set phrase ('très spéciale') that benefits from phrase-level glossing. Other candidate expressions were rejected as they did not meet the criteria for MWEs in this context.

### en:project_239:p4:s2

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

- Gold: [['high', 'up']]
- Predicted: [['climbed', 'on'], ['fly', 'high', 'up', 'into', 'the', 'sky'], ['glitter', "'s", 'back']]
- Model analysis: The analysis reconciles the following MWEs: (1) 'climbed on' is a phrasal verb suggested by both translation evidence and conventional usage. (2) 'Glitter's back' functions as a possessive phrase needing unified translation as indicated by the French counterpart. (3) 'fly high up into the sky' combines elements from analyses to describe a full motion, supported by both boundary precision and translation glossing evidence.

### en:project_239:p4:s3

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

- Gold: []
- Predicted: [['flew', 'over'], ['had', 'tea', 'parties'], ['talking', 'animals']]
- Model analysis: The MWE analysis selects 'flew over' as a phrasal verb based on consistent evidence across analyses and translation suggesting it as an idiomatic unit. 'Had tea parties' is treated as an idiomatic phrase as indicated by idiomatic translation to 'pris le thé'. 'Talking animals' is accepted as a fixed expression given 'animaux qui parlaient' reflects a recognized conceptual unit, despite 'source_conservative' analysis disagreement.

### en:project_239:p4:s4

Emma's days were filled with joy and laughter.

- Gold: [['filled', 'with']]
- Predicted: [['were', 'filled', 'with']]
- Model analysis: The phrase 'were filled with' was selected as an MWE due to its status as a phrasal verb in English that corresponds to the French phrase 'étaient remplies de'. The expression functions as a cohesive unit indicating a state of being, making it appropriate for phrase-level glossing. The candidates 'with joy' and 'joy and laughter' were not selected as MWEs; 'with joy' was uncertain and 'joy and laughter' was rejected since they are compositional and translate directly into French.

### en:project_239:p5:s1

Back at home, Charles was busy helping the people in the village.

- Gold: [['at', 'home']]
- Predicted: [['back', 'at', 'home']]
- Model analysis: The phrase 'Back at home' is selected as a MWE. All three analyses agree that it is a fixed expression, supported by translation evidence (French: 'De retour chez lui'). The group 'busy helping' and 'in the village' were considered but rejected due to their compositional nature in this context.

### en:project_239:p5:s2

He loved to see Emma happy and supported her in all her grand adventures.

- Gold: []
- Predicted: [['emma', 'happy'], ['loved', 'to', 'see'], ['supported', 'her', 'in', 'all', 'her', 'grand', 'adventures']]
- Model analysis: Reconciled three main MWEs: 'loved to see' (phrasal verb with supporting analyses from boundary_precision and source_conservative), 'Emma happy' (perceptual fixed expression based on source-conservative and boundary-precision justifications), and 'supported her in all her grand adventures' (idiomatic expression supported by translation glossing as it is treated in French as a non-compositional unit).

### en:project_239:p5:s3

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

- Gold: [['complete', 'with']]
- Predicted: [['0', '1'], ['14', '15']]
- Model analysis: The phrase 'One day' is selected as a fixed temporal expression, supported by its non-literal translation as 'Un jour' in the context. The phrase 'complete with' is also selected due to its translation to 'accompagné de', indicating a stable idiomatic usage beyond literal composition.

### en:project_239:p5:s4

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

- Gold: [['had', 'a', 'time']]
- Predicted: [['had', 'a', 'wonderful', 'time']]
- Model analysis: The expression 'had a wonderful time' is selected due to its meaning in translation as 'un moment merveilleux' in French, which indicates a non-compositional, phrase-level translation justifying it as a fixed expression. Other potential MWEs like 'playing games' and 'telling stories' were considered but rejected due to their literal translations.

### en:project_239:p6:s1

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

- Gold: [['dreamt', 'of']]
- Predicted: [['a', 'little', 'fairy-tale', 'boutique'], ['dreamt', 'of']]
- Model analysis: After reviewing the analyses, 'dreamt of' is confirmed as a necessary phrasal verb, supported by both source and translation evidence. The entire phrase 'a little fairy-tale boutique' is selected based on translation glossing, suggesting it is perceived as a single concept, rather than just 'fairy-tale boutique'. Other expressions like 'grander things', 'magical potions', and 'enchanted dresses' are rejected as they can be glossed directly in translation and are widely understood without requiring phrase-level interpretation.

### en:project_239:p6:s2

Business was booming, and soon people from all over came to visit Emma's shop.

- Gold: [['all', 'over']]
- Predicted: [['business', 'was', 'booming'], ['from', 'all', 'over']]
- Model analysis: Two MWEs were selected for this segment. 'Business was booming' was identified as a fixed expression in all analyses due to its non-compositional meaning, corresponding well with 'en plein essor' in the translation context. The phrase 'from all over' was chosen as a set phrase, frequently used to imply diverse origins, and corresponds to 'de partout' in the translation context. Other candidate MWEs were rejected due to compositionality or lack of evidence for fixed usage.

### en:project_239:p6:s3

Emma became famous for her sparkling personality and beautiful shop.

- Gold: []
- Predicted: [['became', 'famous'], ['sparkling', 'personality']]
- Model analysis: The multi-word expressions 'became famous' and 'sparkling personality' are selected based on agreement across analyses and translation context. 'Became famous' is a fixed expression that is rendered as a unit in the French translation, while 'sparkling personality' is a common collocation with specific meaning that aligns with its French counterpart. 'Beautiful shop' is rejected as it is straightforwardly compositional.

### en:project_239:p7:s1

One day, the King and Queen of France heard about the amazing Emma Bovary.

- Gold: [['heard', 'about']]
- Predicted: [['emma', 'bovary'], ['heard', 'about'], ['king', 'and', 'queen', 'of', 'france'], ['one', 'day']]
- Model analysis: All analyses agree to select 'One day' as a fixed time expression. Although 'King and Queen' alone was debated, 'King and Queen of France' has translation evidence as a collocation; it's included as it forms a stable expression. 'Heard about' is consistently identified as a phrasal verb. Finally, all agreed that 'Emma Bovary' is a proper noun.

### en:project_239:p7:s2

They invited her to their grand palace for a special tea party.

- Gold: []
- Predicted: [['1', '2', '3'], ['10', '11']]
- Model analysis: Reconciled 'invited her to' as MWE due to strong translation evidence ('l'ont invitée dans') suggesting it functions as a single expression requiring phrase-level glossing. 'Tea party' was also confirmed as an MWE, supported by multiple analyses and consistent cross-linguistic expression with 'fête de thé'.

### en:project_239:p7:s3

Emma wore her fanciest dress, and Glitter the unicorn decorated his mane with sparkling ribbons.

- Gold: []
- Predicted: [['her', 'fanciest', 'dress'], ['with', 'sparkling', 'ribbons']]
- Model analysis: The segment has two plausible MWEs. 'Her fanciest dress' is selected as a MWE because it translates to a non-compositional phrase in French, supporting its treatment as a unit for glossing. The selection is corroborated by both 'boundary_precision' and 'translation_glossing'. 'With sparkling ribbons' is also marked as an MWE; it corresponds to the French 'avec des rubans scintillants', suggesting it is best treated as a single phrase in glossing, supported by 'translation_glossing' and 'source_conservative'.

### en:project_239:p7:s4

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

- Gold: []
- Predicted: [['king', 'and', 'queen'], ['royal', 'adventure', 'planner'], ['were', 'so', 'impressed']]
- Model analysis: The phrase 'King and Queen' is selected as a conventional collocation due to frequent use and translation into 'Roi et la Reine.' 'Were so impressed' is chosen for its syntactic fixedness, echoed by 'tellement impressionnés' in French. 'Royal Adventure Planner' is treated as an official title, supported by consistent translation evidence.

### en:project_239:p7:s5

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

- Gold: [['all', 'over'], ['from', 'then', 'on'], ['making', 'friends']]
- Predicted: [['all', 'over', 'the', 'world'], ['from', 'then', 'on']]
- Model analysis: The phrase 'From then on' is consistently identified as an MWE across all analyses due to its function as a fixed temporal transition, which corresponds to the French translation indicating continuity from a point in time. The phrase 'all over the world' is also consistently selected as an MWE, as it forms a stable expression indicating global scope and is glossed as a unit in the French translation. 'Making new friends' is rejected as an MWE since it is compositional despite some idiomatic rendering in French.

### en:project_239:p8:s2

She lived happily ever after with Charles, Glitter, and all their new friends.

- Gold: [['lived', 'happily', 'ever', 'after']]
- Predicted: [['1', '2', '3', '4']]
- Model analysis: The expression 'lived happily ever after' is selected as a single MWE because it is a fixed idiomatic expression representing a fairy tale ending, confirmed by its direct translation into French as a phrase ('vécut heureuse à jamais'). Analyses prioritize source-token evidence and translation context to support its treatment as a unit.

### en:project_239:p8:s3

Every day was a new adventure filled with laughter, magic, and love.

- Gold: [['filled', 'with']]
- Predicted: [['every', 'day'], ['filled', 'with']]
- Model analysis: The phrase 'Every day' was selected as an MWE based on its frequent usage and translation as a unit in French ('Chaque jour'). 'Filled with' was also selected as an MWE due to its common use as a phrasal verb and distinct translation in French ('remplie de'). Other components of the segment are compositional and do not require MWE annotations.

### en:project_245:p1:s2

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

- Gold: [['first', 'responder']]
- Predicted: [['definite', 'articles'], ['first', 'responder'], ['indefinite', 'articles'], ['null', 'articles']]
- Model analysis: The segments 'First Responder', 'Definite Articles', 'Indefinite Articles', and 'Null Articles' are selected as MWEs. 'First Responder' is frequently used as a fixed expression referring to emergency personnel, corroborated by all analyses and supported by translation as 'premier intervenant'. 'Definite Articles', 'Indefinite Articles', and 'Null Articles' are recognized grammatical terms with specific usages in English and French translations justify their treatment as MWEs. Other candidates were rejected due to lack of evidence as fixed expressions or necessity for specialized glossing.

