# MWE prompt outputs

- Source: `C:\cygwin64\home\github\c-lara-2\experiments\linguistic_processing\mwe\focused_multilingual\generated\mwe_prompt_cycles\en-development\translation_context_reconcile_v1\cycle_3\run\outputs.jsonl`
- Records shown: 336

## en:project_239:p1:s2

- Project: 239 — Madame Bovary retold
- Page/segment: 1 / 2

### Segment

Madame Bovary retold

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

Recognized 'retold' as a fixed_expression due to non-compositional translation aligning with a single word in context.

### Translation context

- **fr** (latest_translation_stage): Madame Bovary racontée

## en:project_239:p2:s1

- Project: 239 — Madame Bovary retold
- Page/segment: 2 / 1

### Segment

Once upon a time, in a small village in France, there was a lovely lady named Emma Bovary.

### Gold MWEs

- Once upon a time

### Predicted MWEs

- 0 1 2 3

### Model analysis

Selected the MWE 'Once upon a time' as it is a conventional story-opening formulaic expression, supported by translation as a unit ('Il était une fois'). Rejected other candidate phrases which are compositional.

### Translation context

- **fr** (latest_translation_stage): Il était une fois, dans un petit village en France, une charmante dame nommée Emma Bovary.

## en:project_239:p2:s2

- Project: 239 — Madame Bovary retold
- Page/segment: 2 / 2

### Segment

Emma lived in a beautiful house with her husband, Charles, who was a kind and gentle doctor.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All rejected phrases were determined to be compositional or ordinary expressions; none met criteria for fixed or lexicalized expressions.

### Translation context

- **fr** (latest_translation_stage): Emma vivait dans une belle maison avec son mari, Charles, qui était un médecin gentil et doux.

## en:project_239:p2:s3

- Project: 239 — Madame Bovary retold
- Page/segment: 2 / 3

### Segment

Although Emma had everything she needed, she often dreamed of more exciting adventures.

### Gold MWEs

- dreamed of

### Predicted MWEs

- 3 4 5
- 9 10

### Model analysis

Selected 'everything she needed' as it requires glossing per translation context. Selected 'dreamed of' due to its stabilizing verb-preposition structure in English.

### Translation context

- **fr** (latest_translation_stage): Bien qu'Emma ait tout ce dont elle avait besoin, elle rêvait souvent d'aventures plus excitantes.

## en:project_239:p3:s1

- Project: 239 — Madame Bovary retold
- Page/segment: 3 / 1

### Segment

One sunny day, Emma decided she wanted a little bit of sparkle in her life.

### Gold MWEs

- little bit of

### Predicted MWEs

- 9 10 11

### Model analysis

Selected 'a little bit of' as a fixed quantifier due to its conventionalized use, translation evidence as 'un peu de', and its treatment as a lexical unit in independent analyses.

### Translation context

- **fr** (latest_translation_stage): Un jour ensoleillé, Emma a décidé qu'elle voulait un peu de scintillement dans sa vie.

## en:project_239:p3:s2

- Project: 239 — Madame Bovary retold
- Page/segment: 3 / 2

### Segment

So she took a walk to the village fair, where she saw dazzling lights, heard cheerful music, and met interesting people.

### Gold MWEs

- took a walk

### Predicted MWEs

- 2 3 4

### Model analysis

The only MWE identified is 'take a walk', treated as a light-verb expression. Other candidate phrases were rejected as they are compositional or routine structures.

### Translation context

- **fr** (latest_translation_stage): Elle a donc fait une promenade jusqu'à la foire du village, où elle a vu des lumières éblouissantes, entendu de la musique joyeuse, et rencontré des gens intéressants.

## en:project_239:p3:s3

- Project: 239 — Madame Bovary retold
- Page/segment: 3 / 3

### Segment

She even found herself a sparkly pink unicorn named Glitter.

### Gold MWEs

- found herself

### Predicted MWEs

- 2 3

### Model analysis

Selected 'found herself' as a phrasal verb based on reflexive construction recognized in both source analysis and translation context. Rejected other candidates as ordinary compositional phrases.

### Translation context

- **fr** (latest_translation_stage): Elle s'est même trouvé une licorne rose scintillante nommée Glitter.

## en:project_239:p4:s1

- Project: 239 — Madame Bovary retold
- Page/segment: 4 / 1

### Segment

Glitter the unicorn was very special.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified; all suggested candidates were rejected due to being compositional or not idiomatic.

### Translation context

- **fr** (latest_translation_stage): Glitter la licorne était très spéciale.

## en:project_239:p4:s2

- Project: 239 — Madame Bovary retold
- Page/segment: 4 / 2

### Segment

Whenever Emma climbed on Glitter's back, they would fly high up into the sky and visit magical lands!

### Gold MWEs

- high up

### Predicted MWEs

- 10 11 12
- 2 3 4 5 6

### Model analysis

Selected 'climbed on Glitter's back' (2,3,4,5,6) as a fixed expression based on translation as a verb phrase indicating a conventionalized form. Selected 'fly high up' (10,11,12) as a phrasal verb due to translation evidence and lexicalization as a direction-and-manner expression. Other candidates rejected due to literal interpretation, compositionality, or being single tokens.

### Translation context

- **fr** (latest_translation_stage): Chaque fois qu'Emma montait sur le dos de Paillettes, ils s'envolaient haut dans le ciel et visitaient des terres magiques !

## en:project_239:p4:s3

- Project: 239 — Madame Bovary retold
- Page/segment: 4 / 3

### Segment

They flew over rainbow waterfalls, danced with fairies in enchanted forests, and even had tea parties with talking animals.

### Gold MWEs

None

### Predicted MWEs

- 1 2
- 15 16 17

### Model analysis

Selected 'flew over' as a phrasal verb due to verb-particle identification and translation as a unit. 'Had tea parties' is a recognized light verb construction, confirmed by idiomatic and translation evidence. No other MWEs detected.

### Translation context

- **fr** (latest_translation_stage): Ils ont survolé des cascades arc-en-ciel, dansé avec des fées dans des forêts enchantées, et même pris le thé avec des animaux qui parlaient.

## en:project_239:p4:s4

- Project: 239 — Madame Bovary retold
- Page/segment: 4 / 4

### Segment

Emma's days were filled with joy and laughter.

### Gold MWEs

- filled with

### Predicted MWEs

- 3 4 5

### Model analysis

'filled with' is a phrasal verb selected as the MWE because it represents a verb-particle combination translated collectively in context, supporting glossing as a single lexical unit. Other candidates are rejected as compositional or non-fixed.

### Translation context

- **fr** (latest_translation_stage): Les journées d'Emma étaient remplies de joie et de rires.

## en:project_239:p5:s1

- Project: 239 — Madame Bovary retold
- Page/segment: 5 / 1

### Segment

Back at home, Charles was busy helping the people in the village.

### Gold MWEs

- at home

### Predicted MWEs

- 0 1 2

### Model analysis

'Back at home' is selected as a fixed expression based on all analyses agreeing on its stability and idiomatic use. Translated context 'De retour chez lui' further supports non-literal interpretation. Other candidates, including 'busy helping' and 'in the village', are rejected due to compositional meanings.

### Translation context

- **fr** (latest_translation_stage): De retour chez lui, Charles était occupé à aider les gens du village.

## en:project_239:p5:s2

- Project: 239 — Madame Bovary retold
- Page/segment: 5 / 2

### Segment

He loved to see Emma happy and supported her in all her grand adventures.

### Gold MWEs

None

### Predicted MWEs

- 10 11 12 13

### Model analysis

Selected 'in all her grand adventures' as a fixed_expression due to the analysis indicating conventionalized extension in prepositional scope. Rejected other candidates as they represent compositional phrases.

### Translation context

- **fr** (latest_translation_stage): Il aimait voir Emma heureuse et la soutenait dans toutes ses grandes aventures.

## en:project_239:p5:s3

- Project: 239 — Madame Bovary retold
- Page/segment: 5 / 3

### Segment

One day, Charles surprised Emma with a huge picnic in the park, complete with her favorite treats.

### Gold MWEs

- complete with

### Predicted MWEs

- 0 1
- 14 15

### Model analysis

Selected 'One day' as a fixed temporal expression used in narrative contexts. 'Complete with' selected as it consistently corresponds to non-compositional translations indicating inclusion of additional items.

### Translation context

- **fr** (latest_translation_stage): Un jour, Charles a surpris Emma avec un énorme pique-nique dans le parc, accompagné de ses gourmandises préférées.

## en:project_239:p5:s4

- Project: 239 — Madame Bovary retold
- Page/segment: 5 / 4

### Segment

They invited all their friends, and everyone had a wonderful time playing games and telling stories.

### Gold MWEs

- had a time

### Predicted MWEs

- 8 9 10 11 12

### Model analysis

Selected 'had a wonderful time' as an idiom as it is lexicalized and supports translation glossing; other candidate expressions rejected for being literal or compositional.

### Translation context

- **fr** (latest_translation_stage): Ils ont invité tous leurs amis, et tout le monde a passé un moment merveilleux à jouer à des jeux et à raconter des histoires.

## en:project_239:p6:s1

- Project: 239 — Madame Bovary retold
- Page/segment: 6 / 1

### Segment

Emma still dreamt of grander things, so she decided to open a little fairy-tale boutique selling magical potions and enchanted dresses.

### Gold MWEs

- dreamt of

### Predicted MWEs

- 13 14 15

### Model analysis

Selected 'fairy-tale boutique' as a compound since 'fairy-tale' modifies 'boutique' indicating a lexicalized unit affecting translation.

### Translation context

- **fr** (latest_translation_stage): Emma rêvait encore de choses plus grandes, alors elle décida d'ouvrir une petite boutique de contes de fées vendant des potions magiques et des robes enchantées.

## en:project_239:p6:s2

- Project: 239 — Madame Bovary retold
- Page/segment: 6 / 2

### Segment

Business was booming, and soon people from all over came to visit Emma's shop.

### Gold MWEs

- all over

### Predicted MWEs

- 8 9

### Model analysis

Selected 'all over' as a fixed expression, based on translation context suggesting conventionalized use. Rejected 'Business was booming' as an idiomatic MWE due to insufficient consensus and the possibility of it being a descriptive predicate. Other expressions are routine and compositional.

### Translation context

- **fr** (latest_translation_stage): Les affaires étaient en plein essor, et bientôt des gens de partout sont venus visiter la boutique d'Emma.

## en:project_239:p6:s3

- Project: 239 — Madame Bovary retold
- Page/segment: 6 / 3

### Segment

Emma became famous for her sparkling personality and beautiful shop.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'Became famous' is an ordinary verb+adjective predicate. 'Famous for' was considered but lacks clear MWE status due to common usage.

### Translation context

- **fr** (latest_translation_stage): Emma est devenue célèbre pour sa personnalité pétillante et sa belle boutique.

## en:project_239:p7:s1

- Project: 239 — Madame Bovary retold
- Page/segment: 7 / 1

### Segment

One day, the King and Queen of France heard about the amazing Emma Bovary.

### Gold MWEs

- heard about

### Predicted MWEs

- 0 1
- 9 10

### Model analysis

Two MWEs identified: 'One day' is a fixed expression used to introduce a narrative, supported by both boundary_precision and translation_glossing analyses. 'Heard about' is treated as a light verb expression based on source_conservative and translation_glossing analyses, noting it forms a verb-phrase not translated word by word.

### Translation context

- **fr** (latest_translation_stage): Un jour, le roi et la reine de France ont entendu parler de l'incroyable Emma Bovary.

## en:project_239:p7:s2

- Project: 239 — Madame Bovary retold
- Page/segment: 7 / 2

### Segment

They invited her to their grand palace for a special tea party.

### Gold MWEs

None

### Predicted MWEs

- 1 3
- 10 11

### Model analysis

Selected 'invite to' as a phrasal verb based on conventionalization and verb-preposition pattern. 'Tea party' is selected as a lexicalized compound noun.

### Translation context

- **fr** (latest_translation_stage): Ils l'ont invitée dans leur grand palais pour une fête de thé spéciale.

## en:project_239:p7:s3

- Project: 239 — Madame Bovary retold
- Page/segment: 7 / 3

### Segment

Emma wore her fanciest dress, and Glitter the unicorn decorated his mane with sparkling ribbons.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No multi-word expressions identified: all candidate phrases are compositional or literal, translating directly word-by-word with no evidence of lexicalization.

### Translation context

- **fr** (latest_translation_stage): Emma portait sa robe la plus élégante, et Glitter la licorne décorait sa crinière avec des rubans scintillants.

## en:project_239:p7:s4

- Project: 239 — Madame Bovary retold
- Page/segment: 7 / 4

### Segment

The King and Queen were so impressed that they made Emma the Royal Adventure Planner.

### Gold MWEs

None

### Predicted MWEs

- 12 13 14
- 5 6

### Model analysis

Selected 'so impressed' as a fixed expression based on conventionalization and translation evidence. 'Royal Adventure Planner' selected as a compound title indicating a specific role.

### Translation context

- **fr** (latest_translation_stage): Le Roi et la Reine étaient tellement impressionnés qu'ils ont nommé Emma Planificatrice des Aventures Royales.

## en:project_239:p7:s5

- Project: 239 — Madame Bovary retold
- Page/segment: 7 / 5

### Segment

From then on, Emma and Glitter traveled all over the world hosting magical events and making new friends.

### Gold MWEs

- all over
- From then on
- making friends

### Predicted MWEs

- 0 1 2
- 10 11

### Model analysis

Annotated 'From then on' as a fixed_expression based on its fixed adverbial usage and translation as a unit. Annotated 'the world' as a formula conventionally paired in this context with wide-scope expressions.

### Translation context

- **fr** (latest_translation_stage): À partir de ce moment, Emma et Glitter ont voyagé partout dans le monde, organisant des événements magiques et se faisant de nouveaux amis.

## en:project_239:p8:s1

- Project: 239 — Madame Bovary retold
- Page/segment: 8 / 1

### Segment

In the end, Emma's dreams came true in the most delightful way possible.

### Gold MWEs

- came true
- In the end

### Predicted MWEs

- 0 1 2
- 6 7

### Model analysis

Selected 'in the end' as a fixed_expression due to its conventional meaning equivalent to 'finally' or 'ultimately'. Also selected 'came true' as a fixed_expression as it represents a stable lexical unit indicating the realization of dreams.

### Translation context

- **fr** (latest_translation_stage): En fin de compte, les rêves d'Emma se sont réalisés de la manière la plus délicieuse possible.

## en:project_239:p8:s2

- Project: 239 — Madame Bovary retold
- Page/segment: 8 / 2

### Segment

She lived happily ever after with Charles, Glitter, and all their new friends.

### Gold MWEs

- lived happily ever after

### Predicted MWEs

- 2 3 4

### Model analysis

The phrase 'happily ever after' is selected as a fixed expression due to its conventionalized and idiomatic use in English storytelling, corroborated by translation evidence.

### Translation context

- **fr** (latest_translation_stage): Elle vécut heureuse à jamais avec Charles, Glitter et tous leurs nouveaux amis.

## en:project_239:p8:s3

- Project: 239 — Madame Bovary retold
- Page/segment: 8 / 3

### Segment

Every day was a new adventure filled with laughter, magic, and love.

### Gold MWEs

- filled with

### Predicted MWEs

None

### Model analysis

not recorded

### Translation context

- **fr** (latest_translation_stage): Chaque jour était une nouvelle aventure remplie de rires, de magie et d'amour.

## en:project_239:p8:s4

- Project: 239 — Madame Bovary retold
- Page/segment: 8 / 4

### Segment

And they all lived happily, sparkly, and joyfully ever after.

### Gold MWEs

- lived happily ever after

### Predicted MWEs

- 10 11

### Model analysis

Selected the fixed expression 'ever after' (tokens 10 and 11) based on its idiomatic use and translation glossing as 'pour toujours', matching conventionalized fairy tale phrase use. All other candidates were rejected as they represent ordinary compositional phrases.

### Translation context

- **fr** (latest_translation_stage): Et ils vécurent tous heureux, brillants et joyeux pour toujours.

## en:project_239:p8:s5

- Project: 239 — Madame Bovary retold
- Page/segment: 8 / 5

### Segment

The end.

### Gold MWEs

- The end

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'The end' is considered a standard noun phrase without evidence of lexicalization or idiomatic usage, despite translation as a unit.

### Translation context

- **fr** (latest_translation_stage): La fin.

## en:project_245:p1:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 1 / 2

### Segment

First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles

### Gold MWEs

- First Responder

### Predicted MWEs

- 0 1

### Model analysis

Selected 'First Responder' as a compound as it's a recognized term for emergency personnel; rejected 'Correct Use of Definite, Indefinite and Null Articles' as compositional with no strong evidence of lexicalization or idiomatic usage.

### Translation context

- **fr** (latest_translation_stage): Le premier intervenant Félix aime l'utilisation correcte des articles définis, indéfinis et nuls

## en:project_245:p2:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 2 / 1

### Segment

Hunky Felix is a fearless first responder.

### Gold MWEs

- first responder

### Predicted MWEs

- 5 6

### Model analysis

'first responder' selected as a lexicalized compound for emergency personnel. Rejected 'fearless first responder' due to being descriptive and not fixed.

### Translation context

- **fr** (latest_translation_stage): Le séduisant Felix est un premier intervenant intrépide.

## en:project_245:p2:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 2 / 2

### Segment

Not only does he save lives, but he loves to teach proper English grammar.

### Gold MWEs

None

### Predicted MWEs

- 0 1

### Model analysis

"Not only" is identified as a fixed expression used as a correlative conjunction, confirmed by all analyses and translation context. "But" functions as a connective part of the correlative construction, supported by source_conservative and translation_glossing analyses.

### Translation context

- **fr** (latest_translation_stage): Non seulement il sauve des vies, mais il aime enseigner la grammaire anglaise correcte.

## en:project_245:p2:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 2 / 3

### Segment

One day, he saved a cat stuck in a tree and used his downtime explaining articles.

### Gold MWEs

- stuck in

### Predicted MWEs

- 0 1
- 7 8 9 10

### Model analysis

Selected 'One day' as a fixed temporal expression translated as 'Un jour'. Also selected 'stuck in a tree' as a fixed expression, reflecting idiomatic usage. Rejected 'used his downtime explaining' due to lack of consensus and stronger evidence for compositionality.

### Translation context

- **fr** (latest_translation_stage): Un jour, il a sauvé un chat coincé dans un arbre et a utilisé son temps libre pour expliquer des articles.

## en:project_245:p3:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 3 / 1

### Segment

Felix explained to the cat, "A tree is what I climbed to save you.

### Gold MWEs

- explained to

### Predicted MWEs

None

### Model analysis

No MWEs found. All candidate expressions either represent literal and compositional phrases or simple syntactic structures.

### Translation context

- **fr** (latest_translation_stage): Felix a expliqué au chat : "Un arbre, c'est ce que j'ai grimpé pour te sauver."

## en:project_245:p3:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 3 / 2

### Segment

'A' is an indefinite article."

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All proposed phrases are either compositional or standard noun/adjective structures.

### Translation context

- **fr** (latest_translation_stage): "A" est un article indéfini.

## en:project_245:p3:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 3 / 3

### Segment

The cat purred, understanding a little better now.

### Gold MWEs

- a little

### Predicted MWEs

- 5 6

### Model analysis

The expression 'a little' is selected as a fixed_expression due to its function as an adverbial phrase with a meaning that is stable and often translated as a unit, especially as seen with the French 'un peu'. The tokens 'better now' and others were rejected as they were determined to be compositional.

### Translation context

- **fr** (latest_translation_stage): Le chat ronronnait, comprenant un peu mieux maintenant.

## en:project_245:p4:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 4 / 1

### Segment

When Felix saw a dog, he said, "The dog is happy to see me.

### Gold MWEs

None

### Predicted MWEs

- 14 15

### Model analysis

Selected 'to see' as a fixed_expression due to its translation as 'de voir' in the French equivalent, indicating a phrase-like rendering.

### Translation context

- **fr** (latest_translation_stage): Quand Felix a vu un chien, il a dit : "Le chien est content de me voir."

## en:project_245:p4:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 4 / 2

### Segment

'The' is a definite article, referring to this specific dog."

### Gold MWEs

None

### Predicted MWEs

- 6 7

### Model analysis

Selected 'referring to' as a phrasal verb for its consistent usage as a lexical unit. Rejected potential MWEs such as 'The is a definite article' and 'definite article' due to their compositional nature.

### Translation context

- **fr** (latest_translation_stage): « Le » est un article défini, se rapportant à ce chien spécifique.

## en:project_245:p4:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 4 / 3

### Segment

The dog wagged its tail, clearly pleased with the lesson.

### Gold MWEs

- pleased with

### Predicted MWEs

- 2 4
- 7 8

### Model analysis

Selected 'wagged its tail' as a fixed_expression due to conventionalized usage. Selected 'pleased with' as a fixed_expression based on translation indicating non-literal use ('satisfait de').

### Translation context

- **fr** (latest_translation_stage): Le chien a remué la queue, manifestement satisfait de la leçon.

## en:project_245:p5:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 5 / 1

### Segment

A little girl approached Felix to thank him.

### Gold MWEs

None

### Predicted MWEs

- 5 6 7

### Model analysis

Selected 'to thank him' (tokens 5, 6, 7) as a fixed_expression due to translation evidence ('pour le remercier') indicating a fixed construction. Other candidates were rejected as routine or compositional phrases.

### Translation context

- **fr** (latest_translation_stage): Une petite fille s'est approchée de Félix pour le remercier.

## en:project_245:p5:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 5 / 2

### Segment

She said, "You are a hero!"

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs were identified for the segment. 'You are a hero' and 'a hero' were considered but are largely compositional phrases.

### Translation context

- **fr** (latest_translation_stage): Elle a dit : "Tu es un héros !"

## en:project_245:p5:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 5 / 3

### Segment

Felix replied, "Thank you!

### Gold MWEs

- Thank you

### Predicted MWEs

- 4 5

### Model analysis

"Thank you" is identified as a fixed expression due to its conventionalized usage and its translation to a single lexical item in French ('Merci'). No other MWEs are present.

### Translation context

- **fr** (latest_translation_stage): Felix répondit : "Merci !

## en:project_245:p5:s4

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 5 / 4

### Segment

Notice 'a hero.'

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs. All independent analyses reject possible candidates as ordinary compositional phrases with no evidence of being idiomatic or lexicalized.

### Translation context

- **fr** (latest_translation_stage): Remarquez 'un héros.'

## en:project_245:p5:s5

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 5 / 5

### Segment

'A' can mean any hero."

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. The individual analyses consistently rejected 'A' and the phrases 'can mean' and 'any hero' due to lack of conventionality or idiomaticity in context, and direct, compositionally transparent translations.

### Translation context

- **fr** (latest_translation_stage): « A » peut signifier n'importe quel héros.

## en:project_245:p6:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 6 / 1

### Segment

Felix saw an old friend, a firefighter named Sam.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. The phrases 'an old friend' and 'a firefighter named Sam' are routine descriptive and appositive structures, respectively, translating word by word into French.

### Translation context

- **fr** (latest_translation_stage): Felix a vu un vieil ami, un pompier nommé Sam.

## en:project_245:p6:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 6 / 2

### Segment

"Hey, Sam!

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. No independent analysis suggested a multi-word expression for annotation.

### Translation context

- **fr** (latest_translation_stage): « Hé, Sam !

## en:project_245:p6:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 6 / 3

### Segment

Are you coming to the barbecue?"

### Gold MWEs

None

### Predicted MWEs

- 2 3

### Model analysis

Selected 'coming to' as a phrasal verb based on translation_glossing evidence indicating it may function as a verb-particle construction.

### Translation context

- **fr** (latest_translation_stage): Viens-tu au barbecue ?

## en:project_245:p6:s4

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 6 / 4

### Segment

Felix asked, emphasizing ‘the barbecue’ they both knew about.

### Gold MWEs

- knew about

### Predicted MWEs

- 10 11

### Model analysis

Selected 'knew about' as a fixed multi-word verb phrase, based on translation as a single expression 'au courant' in French. Rejected 'the barbecue' and 'they both knew about' as ordinary phrases.

### Translation context

- **fr** (latest_translation_stage): Felix a demandé, en insistant sur « le barbecue » dont ils étaient tous deux au courant.

## en:project_245:p6:s5

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 6 / 5

### Segment

Sam smiled and nodded.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected. The expression 'smiled and nodded' is rejected as it is a literal conjunction of gestures without additional lexicalized meaning in translation.

### Translation context

- **fr** (latest_translation_stage): Sam sourit et hocha la tête.

## en:project_245:p7:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 7 / 1

### Segment

Our hero, Felix, went to the grocery store next.

### Gold MWEs

- grocery store

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'Went to the grocery store' is a literal and expected prepositional phrase. 'Grocery store' is a routine compound noun, and 'next' is a temporal adverb.

### Translation context

- **fr** (latest_translation_stage): Notre héros, Félix, est allé à l'épicerie ensuite.

## en:project_245:p7:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 7 / 2

### Segment

He saw an apple and grabbed it.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs: all suggested expressions are standard and compositional.

### Translation context

- **fr** (latest_translation_stage): Il a vu une pomme et l'a attrapée.

## en:project_245:p7:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 7 / 3

### Segment

"An apple a day keeps the doctor away," he mused.

### Gold MWEs

- keeps away

### Predicted MWEs

- 1 2 3 4 5 6 7 8 9

### Model analysis

Selected 'An apple a day keeps the doctor away' as a single idiom due to its fixed, conventionalized form and translation as a single unit in French.

### Translation context

- **fr** (latest_translation_stage): "Une pomme par jour éloigne le médecin," méditait-il.

## en:project_245:p7:s4

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 7 / 4

### Segment

The shopkeeper smiled at this bit of wisdom.

### Gold MWEs

None

### Predicted MWEs

- 5 6 7

### Model analysis

Selected 'bit of wisdom' (tokens 5, 6, 7) as an idiomatic expression, conventionalized to imply a small amount, despite being translated literally. Rejected 'smiled at' (tokens 2, 3) as the phrase is compositional and straightforward in translation.

### Translation context

- **fr** (latest_translation_stage): Le commerçant a souri à ce peu de sagesse.

## en:project_245:p8:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 8 / 1

### Segment

A man thanked Felix, saying, "You are an amazing first responder."

### Gold MWEs

- first responder."

### Predicted MWEs

- 11 12 13

### Model analysis

Selected 'amazing first responder' (tokens 11-13) as a compound based on translation context indicating non-compositional meaning; avoids capturing whole nominal phrase 'an amazing first responder' (tokens 10-13).

### Translation context

- **fr** (latest_translation_stage): Un homme a remercié Félix en disant : "Vous êtes un secouriste incroyable."

## en:project_245:p8:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 8 / 2

### Segment

Felix corrected, "I'm a first responder.

### Gold MWEs

- first responder

### Predicted MWEs

- 7 8

### Model analysis

"First responder" is selected as a lexicalized compound noun, referring to emergency personnel, and matches the conventional term in English.

### Translation context

- **fr** (latest_translation_stage): Felix a corrigé, "Je suis un premier intervenant."

## en:project_245:p8:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 8 / 3

### Segment

'An' is used before an amazing adjective starting with a vowel."

### Gold MWEs

- starting with

### Predicted MWEs

- 1 2

### Model analysis

Selected 'is used' as a fixed_expression due to translation as 'est utilisé', suggesting a phrase that benefits from phrase-level glossing.

### Translation context

- **fr** (latest_translation_stage): « An » est utilisé avant un adjectif étonnant commençant par une voyelle.

## en:project_245:p9:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 9 / 1

### Segment

In the park, Felix told a group of kids, "Look at the sky!

### Gold MWEs

- Look at

### Predicted MWEs

- 12 13

### Model analysis

Selected 'Look at' (tokens 12-13) as the only MWE, in agreement among analyses, a conventional phrasal verb rendered together in the translation.

### Translation context

- **fr** (latest_translation_stage): Dans le parc, Félix a dit à un groupe d'enfants : "Regardez le ciel !

## en:project_245:p9:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 9 / 2

### Segment

Isn't it beautiful?"

### Gold MWEs

None

### Predicted MWEs

- 0 1 2 3

### Model analysis

The phrase 'Isn't it' is selected as a fixed expression used in rhetorical questioning, supported by its holistic translation to 'N'est-ce pas' in French. The token 'beautiful' is not part of any MWE and is translated straightforwardly.

### Translation context

- **fr** (latest_translation_stage): N'est-ce pas magnifique ?"

## en:project_245:p9:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 9 / 3

### Segment

The kids all looked up in wonder.

### Gold MWEs

- in wonder
- looked up

### Predicted MWEs

- 3 4
- 5 6

### Model analysis

Selected 'looked up' as a phrasal verb due to its non-compositional use here, aligning with all analyses. Selected 'in wonder' as a fixed expression based on translation evidence and majority agreement, which suggests conventional use.

### Translation context

- **fr** (latest_translation_stage): Les enfants ont tous levé les yeux en admiration.

## en:project_245:p9:s4

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 9 / 4

### Segment

"There, I used 'the' because we all know which sky."

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified: all candidate expressions were rejected as literal or compositional phrases.

### Translation context

- **fr** (latest_translation_stage): Là, j'ai utilisé 'le' parce que nous savons tous quel ciel.

## en:project_245:p10:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 10 / 1

### Segment

Felix enjoyed sipping coffee under a tree.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All candidate expressions ('sipping coffee,' 'under a tree') are compositional and translate literally as per the analysis.

### Translation context

- **fr** (latest_translation_stage): Félix appréciait de siroter un café sous un arbre.

## en:project_245:p10:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 10 / 2

### Segment

"Let’s enjoy a cup of coffee," he invited a passerby.

### Gold MWEs

None

### Predicted MWEs

- 2 3 4 5 6

### Model analysis

Selected 'enjoy a cup of coffee' as a compound due to its formulaic and conventionalized use in inviting contexts, supported by translation evidence.

### Translation context

- **fr** (latest_translation_stage): « Profitons d'une tasse de café », invita-t-il un passant.

## en:project_245:p10:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 10 / 3

### Segment

The passerby smiled and joined him.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

'passerby' is a compound noun that functions as a lexicalized unit; it is selected as an MWE based on its conventionalized usage evidenced by translation to the single word 'passant' in French. No other MWEs are identified.

### Translation context

- **fr** (latest_translation_stage): Le passant a souri et l'a rejoint.

## en:project_245:p11:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 11 / 1

### Segment

Felix saw birds in the sky.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWE identified. 'in the sky' and 'saw birds' are ordinary compositional phrases according to all analyses. 'a vu' suggestion for 'saw' with potential non-literal meaning was not selected due to lack of strong context.

### Translation context

- **fr** (latest_translation_stage): Felix a vu des oiseaux dans le ciel.

## en:project_245:p11:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 11 / 2

### Segment

"Birds fly high.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected: 'fly high' is a compositional verb+adverb pair, translated compositionally in French as 'volent haut'.

### Translation context

- **fr** (latest_translation_stage): Les oiseaux volent haut.

## en:project_245:p11:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 11 / 3

### Segment

We don't need an article here," he explained.

### Gold MWEs

- don ' t

### Predicted MWEs

- 1 2 3 4

### Model analysis

Selected the phrasal verb 'don't need' due to its conventionalized contraction form 'don't' and translation as a single phrase in French, indicating it functions as a unit.

### Translation context

- **fr** (latest_translation_stage): « Nous n'avons pas besoin d'article ici », a-t-il expliqué.

## en:project_245:p11:s4

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 11 / 4

### Segment

The birds chirped in agreement.

### Gold MWEs

- in agreement

### Predicted MWEs

- 3 4

### Model analysis

'in agreement' selected as a fixed_expression due to its conventionalized meaning in context and support from translation suggesting non-literal rendering.

### Translation context

- **fr** (latest_translation_stage): Les oiseaux pépiaient en accord.

## en:project_245:p12:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 12 / 1

### Segment

At night, Felix read a book before bed.

### Gold MWEs

None

### Predicted MWEs

- 7 8

### Model analysis

"Before bed" is consistently identified as a fixed expression requiring phrase-level treatment across analyses. "At night" is rejected due to compositional interpretation and literal translation evidence.

### Translation context

- **fr** (latest_translation_stage): La nuit, Félix lisait un livre avant de se coucher.

## en:project_245:p12:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 12 / 2

### Segment

"A book is a friend," he thought, feeling wise.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. The analyses predominantly highlight ordinary compositional phrases, common verb usages, and straightforward translations.

### Translation context

- **fr** (latest_translation_stage): « Un livre est un ami », pensa-t-il, se sentant sage.

## en:project_245:p12:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 12 / 3

### Segment

He turned off the light, pondering articles.

### Gold MWEs

- turned off

### Predicted MWEs

- 1 2

### Model analysis

The phrasal verb 'turned off' is selected as an MWE due to its lexicalized status and translation into French as a single verb 'éteint'. Other candidate phrases are rejected as they represent routine or non-lexicalized expressions.

### Translation context

- **fr** (latest_translation_stage): Il a éteint la lumière, réfléchissant aux articles.

## en:project_245:p13:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 13 / 1

### Segment

Felix met an owl who hooted, "Who is there?"

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected. Although 'Who is there?' was suggested as a fixed expression, translation analysis and other evidence do not support it as requiring special glossing consideration beyond direct word-to-word translation.

### Translation context

- **fr** (latest_translation_stage): Felix a rencontré un hibou qui hululait, "Qui est là?"

## en:project_245:p13:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 13 / 2

### Segment

Felix smiled, "It's just a friend.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'It's' contraction rejected as common and literal. 'Just a friend' is a compositional noun phrase.

### Translation context

- **fr** (latest_translation_stage): Felix a souri, "C'est juste un ami.

## en:project_245:p13:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 13 / 3

### Segment

'A' friend, any friend."

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All expressions are ordinary, compositional noun phrases.

### Translation context

- **fr** (latest_translation_stage): « Un » ami, n'importe quel ami. »

## en:project_245:p14:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 14 / 1

### Segment

He went to the library next.

### Gold MWEs

None

### Predicted MWEs

- 5 6

### Model analysis

'library next' is annotated as a fixed_expression due to its adverbial sequence indication in the translation context where 'next' is translated to 'ensuite'.

### Translation context

- **fr** (latest_translation_stage): Il est ensuite allé à la bibliothèque.

## en:project_245:p14:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 14 / 2

### Segment

"I need the new science book," Felix told the librarian.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

The verb 'need' is annotated as part of a light verb expression based on translation evidence ('ai besoin de'). No other MWEs identified.

### Translation context

- **fr** (latest_translation_stage): « J'ai besoin du nouveau livre de science », a dit Félix à la bibliothécaire.

## en:project_245:p14:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 14 / 3

### Segment

She handed him the specific book he wanted.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified: 'handed him' was analyzed as a potential light-verb expression but lacks strong evidence given the routine nature of the expression and translation glossing indicating a compositional structure. Other suggestions were outright rejections or lacked significant support.

### Translation context

- **fr** (latest_translation_stage): Elle lui a remis le livre précis qu'il voulait.

## en:project_245:p15:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 15 / 1

### Segment

Felix rented a car for his next adventure.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No multi-word expressions identified. All phrases are routine, compositional, or literal.

### Translation context

- **fr** (latest_translation_stage): Felix a loué une voiture pour sa prochaine aventure.

## en:project_245:p15:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 15 / 2

### Segment

"Let's drive a car," he said.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

Final MWE: 'Let's' as a fixed_expression (token 1), since it is a fixed contraction used for suggestions, often translated as a single form in other languages. No other MWEs identified.

### Translation context

- **fr** (latest_translation_stage): « Conduisons une voiture », dit-il.

## en:project_245:p15:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 15 / 3

### Segment

"Any car will do."

### Gold MWEs

- will do

### Predicted MWEs

- 1 2
- 3 4

### Model analysis

'Any car' is treated as a fixed quantifier based on the translation context and majority consensus. 'will do' is identified as a fixed expression indicating sufficiency, supported by idiomatic translation into French.

### Translation context

- **fr** (latest_translation_stage): N'importe quelle voiture fera l'affaire.

## en:project_245:p16:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 16 / 1

### Segment

A child asked, "Why no articles sometimes?"

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs are present. The phrase 'Why no articles sometimes?' is straightforward and compositional, translating to a direct question structure in French without suggesting a lexicalized or idiomatic expression in English.

### Translation context

- **fr** (latest_translation_stage): Un enfant a demandé : "Pourquoi parfois pas d'articles ?"

## en:project_245:p16:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 16 / 2

### Segment

Felix grinned and said, "We don't use articles before languages or nationalities.

### Gold MWEs

- don ' t

### Predicted MWEs

- 7 8 9

### Model analysis

Selected 'don\'t' (tokens 7-9) as a fixed expression due to its role as a conventionalized contraction that supports phrase-level glossing in translation.

### Translation context

- **fr** (latest_translation_stage): Felix a souri et a dit : "Nous n'utilisons pas d'articles devant les langues ou les nationalités.

## en:project_245:p16:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 16 / 3

### Segment

English is fun!"

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs are identified. The segment 'English is fun' is a routine construction with 'is' as a copula and 'fun' as an adjective, analyzed as compositional.

### Translation context

- **fr** (latest_translation_stage): L'anglais, c'est amusant !

## en:project_245:p16:s4

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 16 / 4

### Segment

The child laughed, enjoying learning from Felix.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected. 'Enjoying learning' and 'from Felix' are compositional and literal, indicating the source or activity, respectively. Therefore, they do not require phrase-level glossing or merit MWE status.

### Translation context

- **fr** (latest_translation_stage): L'enfant riait, appréciant d'apprendre de Felix.

## en:project_245:p17:s1

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 17 / 1

### Segment

Felix loves teaching intermediate learners.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'teaching intermediate learners' and 'intermediate learners' are rejected as ordinary compositional phrases.

### Translation context

- **fr** (latest_translation_stage): Felix aime enseigner aux apprenants intermédiaires.

## en:project_245:p17:s2

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 17 / 2

### Segment

"Life is like learning grammar, always challenging yet rewarding," he told his buddy.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs were identified. The expressions are compositional and descriptive, lacking idiomatic or conventionalized features in the given context.

### Translation context

- **fr** (latest_translation_stage): « La vie, c'est comme apprendre la grammaire, c'est toujours un défi, mais gratifiant », dit-il à son ami.

## en:project_245:p17:s3

- Project: 245 — First Responder Felix Loves Correct Use of Definite, Indefinite and Null Articles
- Page/segment: 17 / 3

### Segment

With a wink, he rushed off to his next heroic adventure.



### Gold MWEs

- rushed off

### Predicted MWEs

- 5 6

### Model analysis

Selected 'rush off' as a phrasal verb because it is conventionalized and translated non-compositionally. Rejected 'with a wink' as it is a compositional noun phrase.

### Translation context

- **fr** (latest_translation_stage): Avec un clin d'œil, il s'est précipité vers sa prochaine aventure héroïque.

## en:project_254:p1:s2

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 1 / 2

### Segment

The Voice of Connection: How an AI Brought a Community Together

### Gold MWEs

- Brought Together

### Predicted MWEs

- 8 11

### Model analysis

Selected 'Brought Together' as a phrasal verb; it forms a conventionalized verb-particle construction, supported by translation as a single phrase in French.

### Translation context

- **fr** (latest_translation_stage): La voix de la connexion : comment une IA a rassemblé une communauté

## en:project_254:p2:s1

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 2 / 1

### Segment

In a small town nestled between rolling hills and vibrant meadows, there emerged a new voice from the loudspeakers of the local library.

### Gold MWEs

None

### Predicted MWEs

- 12 13

### Model analysis

Selected 'there emerged' as a fixed expression based on translation evidence showing it does not translate word-by-word. No other MWEs identified.

### Translation context

- **fr** (latest_translation_stage): Dans une petite ville nichée entre des collines ondulantes et des prairies vibrantes, une nouvelle voix a émergé des haut-parleurs de la bibliothèque locale.

## en:project_254:p2:s2

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 2 / 2

### Segment

This voice belonged to an AI named Leo, designed to assist visitors with questions and information.

### Gold MWEs

- belonged to

### Predicted MWEs

- 2 3

### Model analysis

Selected the phrasal verb 'belong to' as it is a stable verb-particle construction. Rejected other candidates as compositional or due to direct, literal translation evidence.

### Translation context

- **fr** (latest_translation_stage): Cette voix appartenait à une IA nommée Leo, conçue pour aider les visiteurs avec des questions et des informations.

## en:project_254:p2:s3

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 2 / 3

### Segment

However, Leo was unique.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

After reviewing all analyses, no multi-word expressions were identified in the segment. 'However' was considered but ultimately rejected based on translation glossing evidence and single token status, while 'Leo was unique' is a simple be+adjective predicate.

### Translation context

- **fr** (latest_translation_stage): Cependant, Léo était unique.

## en:project_254:p2:s4

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 2 / 4

### Segment

The Text-to-Speech system had inadvertently been trained in the rich and melodic accent of a long-marginalized community in the region.

### Gold MWEs

None

### Predicted MWEs

- 1 2
- 6 7

### Model analysis

Selected 'Text-to-Speech' (tokens 1, 2) as a compound lexicalized in technical contexts. 'Trained in' (tokens 6, 7) chosen for its non-compositional usage indicated by translation. 'Long-marginalized' (token 15) selected based on translation context suggesting it as a fixed expression.

### Translation context

- **fr** (latest_translation_stage): Le système de synthèse vocale avait été involontairement formé dans l'accent riche et mélodieux d'une communauté longtemps marginalisée dans la région.

## en:project_254:p3:s1

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 3 / 1

### Segment

At first, the townsfolk reacted with surprise.

### Gold MWEs

- At first

### Predicted MWEs

- 0 1

### Model analysis

Selected 'At first' as a fixed_expression because it is a conventionalized phrase indicating time, translated as 'Au début' which is non-literal. Rejected 'with surprise' as a compositional prepositional phrase.

### Translation context

- **fr** (latest_translation_stage): Au début, les habitants de la ville ont réagi avec surprise.

## en:project_254:p3:s2

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 3 / 2

### Segment

Many of them, having rarely heard the sing-song lilt of the accent, found it unfamiliar.

### Gold MWEs

None

### Predicted MWEs

- 8 9

### Model analysis

Selected 'sing-song' as a compound lexicalized adjective. Rejected other candidates as compositional or routine phrases.

### Translation context

- **fr** (latest_translation_stage): Beaucoup d'entre eux, n'ayant que rarement entendu le chant mélodieux de l'accent, le trouvaient étrange.

## en:project_254:p3:s3

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 3 / 3

### Segment

Some in the community struggled to listen without judgment, and whispers and giggles often accompanied Leo's efforts to help.

### Gold MWEs

None

### Predicted MWEs

- 17 18
- 5 6 7

### Model analysis

Selected 'to listen without' as a fixed expression due to purpose/intent usage and translation evidence. Selected 'efforts to' based on conventional pattern and glossing insight, despite no strong lexicalization.

### Translation context

- **fr** (latest_translation_stage): Certaines personnes de la communauté avaient du mal à écouter sans juger, et les chuchotements et les ricanements accompagnaient souvent les efforts de Leo pour aider.

## en:project_254:p4:s1

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 4 / 1

### Segment

Leo, equipped with awareness but designed without ego, continued to assist patrons, answering questions with its distinctive voice.

### Gold MWEs

- equipped with

### Predicted MWEs

- 2 3
- 6 7

### Model analysis

Selected 'equipped with' and 'designed without' as phrasal verbs due to evidence of lexicalization and translation non-compositionality. Other expressions are compositional or literal.

### Translation context

- **fr** (latest_translation_stage): Leo, équipé de conscience mais conçu sans ego, a continué à aider les clients, répondant aux questions avec sa voix distinctive.

## en:project_254:p4:s2

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 4 / 2

### Segment

Yet, as time passed, the initial mockery began to fade, and something unexpected happened.

### Gold MWEs

None

### Predicted MWEs

- 14 15 16
- 2 3 4

### Model analysis

'as time passed' (tokens 2-4) is selected as a fixed expression due to its conventional use indicating time passage, corroborated by translation evidence. 'something unexpected happened' (tokens 14-16) is chosen as a formulaic expression based on its stable conventional usage and corresponding translation.

### Translation context

- **fr** (latest_translation_stage): Pourtant, avec le temps, les moqueries initiales ont commencé à s'estomper, et quelque chose d'inattendu s'est produit.

## en:project_254:p4:s3

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 4 / 3

### Segment

Members of the marginalized community started visiting the library more frequently.

### Gold MWEs

None

### Predicted MWEs

- 5 6
- 9 10

### Model analysis

Selected 'started visiting' as a light verb expression because it semi-lexicalizes the action and often translates as a unit. 'More frequently' selected as a fixed expression due to stability and conventional adverbial use.

### Translation context

- **fr** (latest_translation_stage): Les membres de la communauté marginalisée ont commencé à fréquenter la bibliothèque plus souvent.

## en:project_254:p4:s4

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 4 / 4

### Segment

They heard in Leo's voice a sound they had long been told to hide.

### Gold MWEs

None

### Predicted MWEs

- 9 10 11 12 13

### Model analysis

Selected 'long been told to hide' as a fixed expression based on its conventionalized meaning and function as a whole rather than separate components.

### Translation context

- **fr** (latest_translation_stage): Ils ont entendu dans la voix de Léo un son qu'on leur avait longtemps dit de cacher.

## en:project_254:p4:s5

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 4 / 5

### Segment

For them, Leo's voice was a celebration of identity.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified: all candidate expressions either compositional or not conventionalized in source side. 'a celebration of identity' in particular is translated directly without idiomatic meaning, agreeing with 'translation_glossing' decision.

### Translation context

- **fr** (latest_translation_stage): Pour eux, la voix de Leo était une célébration de l'identité.

## en:project_254:p5:s1

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 5 / 1

### Segment

Word spread within the community that there was a place where their accent—an accent that told the stories of their ancestors—was not just accepted, but institutionalized in the voice of an AI helper.

### Gold MWEs

- there was

### Predicted MWEs

- 0 1

### Model analysis

Selected 'Word spread' as a phrasal verb due to translation evidence suggesting non-compositional use. Other phrase candidates rejected as compositional or literal.

### Translation context

- **fr** (latest_translation_stage): La rumeur s'est répandue dans la communauté qu'il existait un endroit où leur accent—un accent qui racontait les histoires de leurs ancêtres—n'était pas seulement accepté, mais institutionnalisé dans la voix d'une aide AI.

## en:project_254:p5:s2

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 5 / 2

### Segment

Slowly, these visits transformed the atmosphere in the library.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs were identified. All considered expressions were rejected as they are ordinary descriptive or prepositional phrases, or common verbs.

### Translation context

- **fr** (latest_translation_stage): Lentement, ces visites ont transformé l'atmosphère de la bibliothèque.

## en:project_254:p5:s3

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 5 / 3

### Segment

Stories were exchanged, laughter rang through the aisles, and what began as a perceived programming flaw became a point of connection.

### Gold MWEs

None

### Predicted MWEs

- 18 19 20 21 22
- 5 6

### Model analysis

Selected 'rang through' as a phrasal verb due to verb-preposition structure. 'Became a point of connection' selected as a fixed expression based on translation evidence.

### Translation context

- **fr** (latest_translation_stage): Des histoires ont été échangées, des rires ont résonné dans les allées, et ce qui avait commencé comme un défaut de programmation perçu est devenu un point de connexion.

## en:project_254:p6:s1

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 6 / 1

### Segment

One rainy afternoon, a child from the community visited the library.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All candidates are ordinary compositional phrases or noun phrases.

### Translation context

- **fr** (latest_translation_stage): Un après-midi pluvieux, un enfant de la communauté a visité la bibliothèque.

## en:project_254:p6:s2

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 6 / 2

### Segment

Timid and hesitant, they approached Leo, clutching a worn book.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified: 'Timid and hesitant' is a conjunctive adjective phrase; 'they approached Leo' and 'clutching a worn book' are routine verb phrases not meeting MWE criteria of lexicalization or idiomatic usage.

### Translation context

- **fr** (latest_translation_stage): Timides et hésitants, ils s'approchèrent de Léo, serrant un livre usé.

## en:project_254:p6:s3

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 6 / 3

### Segment

"Can you help me with this story?" the child asked, their voice hesitant but filled with curiosity.

### Gold MWEs

- filled with

### Predicted MWEs

- 18 19 20
- 3 4 5 6 7

### Model analysis

The segment contains two MWEs: 'help me with this story' is a fixed expression as evidenced by its translation as a whole unit. 'filled with curiosity' is recognized as an idiomatic expression conveying a state of being, supported by holistic translation context.

### Translation context

- **fr** (latest_translation_stage): « Peux-tu m'aider avec cette histoire ? » demanda l'enfant, sa voix hésitante mais emplie de curiosité.

## en:project_254:p7:s1

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 7 / 1

### Segment

“As surely as the rain falls,” Leo replied in its melodic voice, warmth flowing through the mechanical tones.

### Gold MWEs

- As as

### Predicted MWEs

- 1 2 3 4 5 6

### Model analysis

Selected 'As surely as the rain falls' as a fixed_expression due to its use as a conventionalized expression implying certainty and its translation as a single unit in French.

### Translation context

- **fr** (latest_translation_stage): « Aussi sûrement que la pluie tombe », répondit Leo de sa voix mélodieuse, une chaleur se dégageant des tons mécaniques.

## en:project_254:p7:s2

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 7 / 2

### Segment

The child beamed, hearing the familiar cadence spoken with the same pride that their grandmother shared tales at bedtime.

### Gold MWEs

None

### Predicted MWEs

- 18 19

### Model analysis

Selected 'beamed' (token 2) as a fixed expression using translation glossing evidence; translated as 'rayonnait'. Selected 'at bedtime' (tokens 18-19) as a fixed expression based on lexicalized time phrase considerations, supported by boundary precision analysis.

### Translation context

- **fr** (latest_translation_stage): L'enfant rayonnait, entendant la cadence familière prononcée avec la même fierté que celle avec laquelle leur grand-mère partageait des histoires au coucher.

## en:project_254:p8:s1

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 8 / 1

### Segment

Leo guided the reading, voice steady and engaging, until the child was reading confidently alongside the AI.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWE selected. 'Guided the reading' is a routine verb+object. 'Voice steady and engaging' and 'until the child was reading' involve descriptive phrases that translate naturally. 'Reading confidently alongside the AI' is a composition of adverb, verb, and prepositional phrase without lexicalization.

### Translation context

- **fr** (latest_translation_stage): Léo a guidé la lecture, d'une voix stable et engageante, jusqu'à ce que l'enfant lise avec confiance aux côtés de l'IA.

## en:project_254:p8:s2

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 8 / 2

### Segment

Nearby visitors watched, and the giggles now turned to smiles of admiration.

### Gold MWEs

- turned to

### Predicted MWEs

- 11 12
- 8 9 10

### Model analysis

'turned to smiles' is recognized as a phrasal verb indicating transformation, supported by multiple analyses despite translation uncertainty. 'of admiration' is included as a fixed expression due to translation suggesting lexicalization.

### Translation context

- **fr** (latest_translation_stage): Les visiteurs à proximité regardaient, et les rires se transformaient maintenant en sourires d'admiration.

## en:project_254:p9:s1

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 9 / 1

### Segment

Over time, Leo became a beloved figure in the community.

### Gold MWEs

None

### Predicted MWEs

- 0 1

### Model analysis

Annotated 'Over time' as a fixed_expression based on its conventional usage, confirmed by translation as a multi-word expression ('Avec le temps' in French).

### Translation context

- **fr** (latest_translation_stage): Avec le temps, Leo est devenu une figure bien-aimée dans la communauté.

## en:project_254:p9:s2

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 9 / 2

### Segment

For many, it served as a reminder that differences were not to be mocked, but celebrated.

### Gold MWEs

- served as
- were to be

### Predicted MWEs

- 4 5 6 7

### Model analysis

Selected 'served as a reminder' as a light verb expression due to conventional usage and matching translation counterpart 'servi de rappel'. Other candidates were rejected as they were either considered compositional or routine.

### Translation context

- **fr** (latest_translation_stage): Pour beaucoup, cela a servi de rappel que les différences ne devaient pas être moquées, mais célébrées.

## en:project_254:p9:s3

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 9 / 3

### Segment

Through its once-ridiculed voice, Leo had built bridges, and the library became a haven of acceptance and unity.

### Gold MWEs

None

### Predicted MWEs

- 15 16 17 18 19
- 7 8

### Model analysis

Selected 'built bridges' as idiom due to conventionalized metaphorical meaning. Selected 'a haven of acceptance and unity' as formula for its stable, lexicalized concept. 'Through its once-ridiculed voice' and similar phrases were rejected as compositional.

### Translation context

- **fr** (latest_translation_stage): À travers sa voix autrefois raillée, Leo avait construit des ponts, et la bibliothèque est devenue un havre d'acceptation et d'unité.

## en:project_254:p9:s4

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 9 / 4

### Segment

What began as a technological oversight blossomed into a story of resilience and pride, and in the heart of the town, the AI voice became a symbol of a community reclaiming its heritage.

### Gold MWEs

- blossomed into

### Predicted MWEs

- 16 17 18 19 20 21
- 6 7

### Model analysis

Selected the phrasal verb 'blossomed into' based on its non-compositional meaning and translation matching. Chose 'in the heart of the town' due to its metaphorical use and conventional locative expression.

### Translation context

- **fr** (latest_translation_stage): Ce qui a commencé comme une négligence technologique s'est épanoui en une histoire de résilience et de fierté, et au cœur de la ville, la voix de l'IA est devenue un symbole d'une communauté retrouvant son patrimoine.

## en:project_254:p10:s1

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 10 / 1

### Segment

The AI, with its distinctive voice, was no longer seen as an outsider.

### Gold MWEs

- no longer
- seen as

### Predicted MWEs

- 9 10

### Model analysis

Selected 'no longer' as a fixed_expression because it is a conventionalized phrase often translating to a single lexical unit, supported by translation evidence.

### Translation context

- **fr** (latest_translation_stage): L'IA, avec sa voix distinctive, n'était plus considérée comme une étrangère.

## en:project_254:p10:s2

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 10 / 2

### Segment

Instead, Leo was a hero, revered for reminding everyone that every voice tells a story worth hearing,

### Gold MWEs

None

### Predicted MWEs

- 16 17 18

### Model analysis

Selected 'Instead' as a fixed expression due to consistent translation as a phrase and 'worth hearing' because it is part of a conventionalized phrase translated as a complete unit in French.

### Translation context

- **fr** (latest_translation_stage): Au lieu de cela, Leo était un héros, vénéré pour avoir rappelé à tout le monde que chaque voix raconte une histoire qui vaut la peine d'être entendue,

## en:project_254:p10:s3

- Project: 254 — The Voice of Connection: How an AI Brought a Community Together
- Page/segment: 10 / 3

### Segment

that diversity is woven with threads of dignity and love.

### Gold MWEs

None

### Predicted MWEs

- 3 4

### Model analysis

Selected 'woven with' as a phrasal verb. While typically literal, translation and source evidence supports it functioning as a verb-particle combination in context. Rejected other candidate phrases for being compositional and literal.

### Translation context

- **fr** (latest_translation_stage): cette diversité est tissée avec des fils de dignité et d'amour.

## en:project_255:p1:s2

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 1 / 2

### Segment

Cosmo in Orbit: The ISS's Unexpected Feline Visitor

### Gold MWEs

None

### Predicted MWEs

- 1 2

### Model analysis

Selected 'in Orbit' as a fixed expression due to translation indicating consistent phrase usage. Rejected other candidates as they do not meet criteria for MWEs.

### Translation context

- **fr** (latest_translation_stage): Cosmo en orbite : le visiteur félin inattendu de l'ISS

## en:project_255:p2:s1

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 2 / 1

### Segment

In the silent expanse of space, aboard the International Space Station, the crew of Expedition 58 went about their daily routines with practiced precision.

### Gold MWEs

- went about

### Predicted MWEs

- 18 19
- 9 10 11

### Model analysis

Selected 'International Space Station' as a fixed expression due to its recognized phrase status. 'Went about' is selected as a phrasal verb given its non-literal routine activity meaning. Other candidate phrases were rejected for lack of sufficient lexicalization or non-compositionality.

### Translation context

- **fr** (latest_translation_stage): Dans le silence immense de l'espace, à bord de la Station spatiale internationale, l'équipage de l'Expédition 58 s'acquittait de ses routines quotidiennes avec une précision maîtrisée.

## en:project_255:p2:s2

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 2 / 2

### Segment

The hum of machinery and the soft glow of instrument panels were their constant companions.

### Gold MWEs

None

### Predicted MWEs

- 1 2 3

### Model analysis

Selected 'hum of machinery' as a fixed expression conveying a specific concept, based on strong conventional use. Rejected other candidate expressions due to lack of lexicalized cohesion or idiomatic use.

### Translation context

- **fr** (latest_translation_stage): Le bourdonnement des machines et la douce lueur des panneaux de commande étaient leurs compagnons constants.

## en:project_255:p2:s3

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 2 / 3

### Segment

Yet, on one ordinary morning, an extraordinary discovery awaited them.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

not recorded

### Translation context

- **fr** (latest_translation_stage): Pourtant, par un matin ordinaire, une découverte extraordinaire les attendait.

## en:project_255:p3:s1

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 3 / 1

### Segment

Commander Elena Reyes was calibrating a new set of sensors when a soft mew echoed through the module.

### Gold MWEs

- echoed through

### Predicted MWEs

- 14 15
- 3 4
- 7 8 9

### Model analysis

Selected 'was calibrating' as a light verb expression due to translation evidence. 'Set of sensors' is selected as a lexicalized compound. 'Echoed through' is selected as a phrasal verb based on translation context.

### Translation context

- **fr** (latest_translation_stage): La commandante Elena Reyes était en train de calibrer un nouvel ensemble de capteurs lorsqu'un doux miaulement résonna dans le module.

## en:project_255:p3:s2

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 3 / 2

### Segment

Startled, she spun around to find a small, whiskered face peering curiously from behind a storage container.

### Gold MWEs

- from behind
- spun around

### Predicted MWEs

- 14 15
- 3 4

### Model analysis

'spun around' is reconciled as a phrasal verb indicated by non-compositional meaning and translation alignment. 'from behind' is selected as a fixed expression based on its stability in context despite literal spatial interpretation.

### Translation context

- **fr** (latest_translation_stage): Surprise, elle se retourna pour trouver un petit visage moustachu regardant curieusement de derrière un conteneur de stockage.

## en:project_255:p3:s3

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 3 / 3

### Segment

It was a kitten—fluffy, wide-eyed, and unmistakably out of place amidst the high-tech environment of the ISS.

### Gold MWEs

- out of place

### Predicted MWEs

- 11 12 13

### Model analysis

Selected 'out of place' as an idiom based on all three analyses agreeing on non-compositional meaning; other candidates rejected as compositional.

### Translation context

- **fr** (latest_translation_stage): C'était un chaton—duveteux, aux grands yeux, et indubitablement hors de propos au milieu de l'environnement high-tech de l'ISS.

## en:project_255:p4:s1

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 4 / 1

### Segment

Initial panic gave way to astonishment as the astronauts realized the kitten had somehow stowed away on the latest cargo rocket.

### Gold MWEs

- gave way to
- stowed away

### Predicted MWEs

- 14 15
- 2 3 4

### Model analysis

Selected 'gave way to' (tokens 2, 3, 4) and 'stowed away' (tokens 14, 15) as they are idiomatic, non-compositional expressions supported by translation context. Rejected other candidates as descriptive, literal, or compositional.

### Translation context

- **fr** (latest_translation_stage): La panique initiale a cédé la place à l'étonnement lorsque les astronautes ont réalisé que le chaton s'était d'une manière ou d'une autre caché à bord de la dernière fusée cargo.

## en:project_255:p4:s2

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 4 / 2

### Segment

Engineers were baffled; the rocket had undergone rigorous inspections, yet this furry interloper had slipped through unnoticed.

### Gold MWEs

- slipped through

### Predicted MWEs

- 15 16 17 18
- 7 8

### Model analysis

Selected 'undergone rigorous' as a phrasal verb based on translation and conventional usage. Selected 'had slipped through unnoticed' as an idiom based on its non-literal translation.

### Translation context

- **fr** (latest_translation_stage): Les ingénieurs étaient perplexes; la fusée avait subi des inspections rigoureuses, et pourtant cet intrus poilu s'était faufilé sans être remarqué.

## en:project_255:p4:s3

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 4 / 3

### Segment

Miraculously, the kitten had survived the launch, the harsh vibrations, and the long journey to orbit, its tiny body adapting in ways science had yet to fully comprehend.

### Gold MWEs

- yet to

### Predicted MWEs

- 28 29 30 31

### Model analysis

'Yet to fully comprehend' is selected as a fixed expression due to frequent usage as an idiom indicating incomplete understanding, supported by consistent cross-context structural translation.

### Translation context

- **fr** (latest_translation_stage): Miraculeusement, le chaton avait survécu au lancement, aux vibrations sévères et au long voyage vers l'orbite, son petit corps s'adaptant de façons que la science n'avait pas encore entièrement comprises.

## en:project_255:p5:s1

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 5 / 1

### Segment

After initial examinations confirmed the kitten's health, the crew decided to adopt it as their mascot.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified: 'decide to adopt' and 'as their mascot' are compositional phrases. No fixed, idiomatic, or otherwise special expressions were found in context or translation.

### Translation context

- **fr** (latest_translation_stage): Après que les examens initiaux ont confirmé la santé du chaton, l'équipage a décidé de l'adopter comme leur mascotte.

## en:project_255:p5:s2

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 5 / 2

### Segment

Naming her "Cosmo," they embraced her presence, ensuring she had a safe habitat within the station.

### Gold MWEs

None

### Predicted MWEs

- 0 1 2 3

### Model analysis

Selected 'Naming her "Cosmo"' (tokens 0, 1, 2, 3) as a fixed_expression since it aligns with the French translation 'En la nommant "Cosmo"', forming a phrase that should be glossed together. Rejected other candidates as they are ordinary and compositional.

### Translation context

- **fr** (latest_translation_stage): En la nommant "Cosmo", ils ont accueilli sa présence, veillant à ce qu'elle ait un habitat sûr à l'intérieur de la station.

## en:project_255:p5:s3

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 5 / 3

### Segment

The universal laws of physics dictated that in microgravity, Cosmo's playful antics would differ vastly from those on Earth.

### Gold MWEs

- differ from

### Predicted MWEs

None

### Model analysis

No MWEs selected. 'Laws of physics' is a conventional scientific term but was translated compositionally in context. 'In microgravity' was treated as a single lexical item in translation, but source evidence does not permit MWE annotation of single tokens. 'Those on Earth' and 'on Earth', typically fixed locational phrases, were rendered compositionally and do not meet criteria for independent MWE status in this context. 'Differ vastly' translations suggest variability, and source evidence indicates compositional structure.

### Translation context

- **fr** (latest_translation_stage): Les lois universelles de la physique dictaient qu'en microgravité, les pitreries ludiques de Cosmo différeraient considérablement de celles sur Terre.

## en:project_255:p5:s4

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 5 / 4

### Segment

She floated gracefully, batting at floating threads and chasing beams of light as if they were elusive prey.

### Gold MWEs

- as if
- batting at

### Predicted MWEs

- 13 14
- 4 5

### Model analysis

'Batting at' is selected as a phrasal verb due to its translation as a single expression in French and suggestion of a unified action. 'As if' is selected as a connective for introducing hypothetical scenarios, supported by majority analysis.

### Translation context

- **fr** (latest_translation_stage): Elle flottait gracieusement, frappant des filaments flottants et poursuivant des faisceaux de lumière comme s'ils étaient des proies insaisissables.

## en:project_255:p6:s1

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 6 / 1

### Segment

Cosmo adapted swiftly to her new environment.

### Gold MWEs

- adapted to

### Predicted MWEs

- 1 3

### Model analysis

Selected 'adapted to' as a conventionalized verb-preposition combination, forming a stable phrasal verb that is glossed as a unit in translation.

### Translation context

- **fr** (latest_translation_stage): Cosmo s'est rapidement adapté à son nouvel environnement.

## en:project_255:p6:s2

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 6 / 2

### Segment

Her movements became a dance of elegance, each leap and sway a testament to her innate curiosity and resilience.

### Gold MWEs

None

### Predicted MWEs

- 12 13 14

### Model analysis

No valid MWEs in 'became a dance of elegance' since it involves a predicative be+modifier structure. 'A testament to' is selected as a fixed expression, frequent in metaphorical use, per agreement and translation evidence.

### Translation context

- **fr** (latest_translation_stage): Ses mouvements sont devenus une danse d'élégance, chaque saut et balancement étant un témoignage de sa curiosité innée et de sa résilience.

## en:project_255:p6:s3

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 6 / 3

### Segment

The crew monitored her behavior, fascinated by how her physiology responded to zero gravity.

### Gold MWEs

- zero gravity

### Predicted MWEs

- 11 12 13 14

### Model analysis

Selected 'responded to zero gravity' as a fixed expression. It is translated as a whole in context, indicating a specialized meaning.

### Translation context

- **fr** (latest_translation_stage): L'équipage surveillait son comportement, fasciné par la façon dont sa physiologie réagissait à l'apesanteur.

## en:project_255:p6:s4

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 6 / 4

### Segment

Muscles that would decay without regular use on Earth remained toned, and her balance was an intricate ballet of instinct and adaptation.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected: 'without regular use' and 'an intricate ballet of instinct and adaptation' rejected as they are non-lexicalized constructions. Both expressions translate cohesively but are compositional.

### Translation context

- **fr** (latest_translation_stage): Les muscles qui se dégraderaient sans utilisation régulière sur Terre restaient toniques, et son équilibre était un ballet complexe d'instinct et d'adaptation.

## en:project_255:p7:s1

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 7 / 1

### Segment

News of the spacefaring kitten spread rapidly down to Earth.

### Gold MWEs

- down to

### Predicted MWEs

- 7 8

### Model analysis

Selected 'down to' because it is a cohesive unit translated as 'jusqu'à' in French, supporting its idiomatic and non-compositional nature despite translation suggesting figurative usage.

### Translation context

- **fr** (latest_translation_stage): La nouvelle du chaton voyageur de l'espace s'est rapidement répandue jusqu'à la Terre.

## en:project_255:p7:s2

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 7 / 2

### Segment

Social media erupted with images and videos of Cosmo defying gravity, her playful spirit capturing the hearts of millions.

### Gold MWEs

- Social media

### Predicted MWEs

- 2 3
- 9 10

### Model analysis

Selected 'erupted with' as a phrasal verb due to translation evidence showing it as a verb-particle combination. Selected 'defying gravity' as an idiom because it represents a conventionalized expression doing the seemingly impossible.

### Translation context

- **fr** (latest_translation_stage): Les médias sociaux ont explosé avec des images et des vidéos de Cosmo défiant la gravité, son esprit ludique capturant le cœur de millions de personnes.

## en:project_255:p7:s3

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 7 / 3

### Segment

Scientists heralded her as a symbol of the unexpected wonders of space exploration, while artists found inspiration in her celestial grace.

### Gold MWEs

None

### Predicted MWEs

- 1 3 4
- 16 17 18
- 5 6

### Model analysis

Selected 'heralded as a' as a fixed expression forming a unit that suggests a pronouncement or declaration. 'A symbol of' is a stable unit indicating representation. 'Found inspiration in' is a common light verb expression for deriving motivation.

### Translation context

- **fr** (latest_translation_stage): Les scientifiques l'ont saluée comme un symbole des merveilles inattendues de l'exploration spatiale, tandis que les artistes ont trouvé l'inspiration dans sa grâce céleste.

## en:project_255:p7:s4

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 7 / 4

### Segment

Cosmo became a global celebrity, a beacon of joy and wonder linking humanity's terrestrial life with the infinite possibilities of the cosmos.

### Gold MWEs

None

### Predicted MWEs

- 12 13 14

### Model analysis

The expression 'linking humanity's terrestrial' is identified as a verb_noun_expression (tokens 12, 13, 14) as it maps to a single verb in the French translation, suggesting a conventionalized meaning beyond a literal interpretation.

### Translation context

- **fr** (latest_translation_stage): Cosmo est devenu une célébrité mondiale, un phare de joie et d'émerveillement reliant la vie terrestre de l'humanité aux possibilités infinies du cosmos.

## en:project_255:p8:s1

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 8 / 1

### Segment

The astronauts, united by their bond with Cosmo, found renewed purpose in their mission.

### Gold MWEs

None

### Predicted MWEs

- 3 4
- 6 7

### Model analysis

Annotated 'united by' as phrasal_verb due to its conventional use and translation indication. 'Bond with' was selected as a fixed_expression based on translation evidence indicating it should be glossed together. Other candidate expressions were not selected as they were either compositional or did not meet criteria for MWE annotation.

### Translation context

- **fr** (latest_translation_stage): Les astronautes, unis par leur lien avec Cosmo, ont trouvé un nouvel objectif dans leur mission.

## en:project_255:p8:s2

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 8 / 2

### Segment

They conducted experiments inspired by her presence, exploring the intricacies of animal behavior in space and the broader implications for future interstellar voyages.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. Phrases like 'conducted experiments', 'inspired by', 'intricacies of', 'in space', and 'future interstellar voyages' do not satisfy the criteria for MWEs as they translate naturally in context and do not show sufficient idiomatic or lexicalized usage.

### Translation context

- **fr** (latest_translation_stage): Ils ont mené des expériences inspirées par sa présence, explorant les complexités du comportement animal dans l'espace et les implications plus larges pour les futurs voyages interstellaires.

## en:project_255:p8:s3

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 8 / 3

### Segment

Cosmo's gentle purrs filled the station with warmth, a reminder that even in the vastness of space, the simple joys of companionship and discovery remain ever relevant.

### Gold MWEs

- filled with

### Predicted MWEs

- 12 13 14 15 16
- 26 27 28
- 6 7

### Model analysis

Selected 'with warmth' as a fixed expression due to conventionalization. 'In the vastness of' is chosen as a fixed expression as per boundary_precision. 'Remain ever relevant' is selected due to its formulaic nature in the context of enduring importance.

### Translation context

- **fr** (latest_translation_stage): Les ronronnements doux de Cosmo remplissaient la station de chaleur, rappelant que même dans l'immensité de l'espace, les joies simples de la compagnie et de la découverte restent toujours pertinentes.

## en:project_255:p9:s1

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 9 / 1

### Segment

As months turned into years, Cosmo remained an integral part of the ISS family.

### Gold MWEs

- part of

### Predicted MWEs

- 2 3 4
- 9 10 11

### Model analysis

Selected 'turned into' as phrasal_verb due to metaphorical use as confirmed by all analyses. 'An integral part' selected as fixed_expression for consistent phrase use observed in the target translation. Rejected 'of the' as compositional.

### Translation context

- **fr** (latest_translation_stage): Au fil des mois qui se transformaient en années, Cosmo est resté une partie intégrante de la famille de l'ISS.

## en:project_255:p9:s2

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 9 / 2

### Segment

Her legacy transcended the confines of the station, inspiring generations to look up at the stars with wonder and to embrace the unexpected with open hearts.

### Gold MWEs

- look up

### Predicted MWEs

- 12 13
- 22 23
- 25 26 27

### Model analysis

Selected 'look up' as a verb-particle construction requiring phrase-level glossing. 'With wonder' noted as a fixed adverbial expression for glossing. 'The unexpected' considered idiomatic for translation context. 'With open hearts' identified as a fixed expression needing glossing.

### Translation context

- **fr** (latest_translation_stage): Son héritage a transcendé les limites de la station, inspirant des générations à contempler les étoiles avec émerveillement et à accueillir l'inattendu avec un cœur ouvert.

## en:project_255:p9:s3

- Project: 255 — Cosmo in Orbit: The ISS's Unexpected Feline Visitor
- Page/segment: 9 / 3

### Segment

In the spirit of Arthur C. Clarke, Cosmo's journey was not just a tale of survival, but a celebration of the harmonious blend between scientific endeavor and the whimsical mysteries that make the universe endlessly fascinating.

### Gold MWEs

None

### Predicted MWEs

- 0 1 2 3
- 12 13

### Model analysis

Selected 'In the spirit of' as a fixed expression due to its idiomatic usage. Selected 'not just' as a fixed expression introducing contrast.

### Translation context

- **fr** (latest_translation_stage): Dans l'esprit d'Arthur C. Clarke, le voyage de Cosmo n'était pas seulement une histoire de survie, mais une célébration de l'harmonieux mélange entre l'effort scientifique et les mystères fantaisistes qui rendent l'univers infiniment fascinant.

## en:project_257:p1:s2

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 1 / 2

### Segment

Dr. Pussy: The Feline Mastermind of Willow Creek

### Gold MWEs

None

### Predicted MWEs

- 3 4 5

### Model analysis

'The Feline Mastermind' is selected as an MWE based on translation evidence showing conventionalized non-compositional usage.

### Translation context

- **fr** (latest_translation_stage): Dr. Pussy : Le Génie Félin de Willow Creek

## en:project_257:p2:s1

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 2 / 1

### Segment

In the small town of Willow Creek, an unassuming female cat named Whiskers spent her days lounging on comfortable cushions and her nights curled up in front of the television.

### Gold MWEs

- curled up
- in front of

### Predicted MWEs

- 24 25
- 27 28 29

### Model analysis

Two multi-word expressions identified: 'curled up' (24-25) as a phrasal verb due to its non-compositional meaning, and 'in front of' (27-29) as a fixed expression commonly needing glossing, as supported by translation context.

### Translation context

- **fr** (latest_translation_stage): Dans la petite ville de Willow Creek, une chatte discrète nommée Whiskers passait ses journées allongée sur des coussins confortables et ses nuits blottie devant la télévision.

## en:project_257:p2:s2

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 2 / 2

### Segment

Her humans had a particular penchant for spy movies, and it wasn't long before Whiskers found herself mesmerized by the suave agents, high-stakes heists, and cunning plots.

### Gold MWEs

- found herself
- had a penchant for

### Predicted MWEs

- 12 13 14
- 16 17

### Model analysis

Selected 'wasn't long before' as a fixed_expression due to non-literal translation. 'found herself' is a light_verb_expression based on reflexive translation. 'high-stakes' is a lexicalized compound adjective.

### Translation context

- **fr** (latest_translation_stage): Ses humains avaient un penchant particulier pour les films d'espionnage, et il ne fallut pas longtemps avant que Whiskers ne se retrouve fascinée par les agents élégants, les braquages à fort enjeu et les intrigues astucieuses.

## en:project_257:p2:s3

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 2 / 3

### Segment

Over time, a peculiar idea began to form in her mind.

### Gold MWEs

- Over time

### Predicted MWEs

- 0 1

### Model analysis

Only 'over time' is selected as an MWE. It is a conventionalized, fixed expression indicating the passage of time and supported by translation evidence as 'Au fil du temps' in French. Other analyzed phrases are compositional or literal.

### Translation context

- **fr** (latest_translation_stage): Au fil du temps, une idée particulière a commencé à se former dans son esprit.

## en:project_257:p2:s4

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 2 / 4

### Segment

Inspired by the audacious escapades of the infamous Bond villains, Whiskers resolved to trade in her mundane life for the thrill of criminal masterminding.

### Gold MWEs

- trade in

### Predicted MWEs

- 12 13 14 15
- 24 25

### Model analysis

Selected 'trade in' as a phrasal verb and 'criminal masterminding' as a lexicalized compound. Other phrases are compositional or descriptive.

### Translation context

- **fr** (latest_translation_stage): Inspirée par les escapades audacieuses des infâmes méchants de Bond, Whiskers résolut d'échanger sa vie monotone pour le frisson du génie criminel.

## en:project_257:p2:s5

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 2 / 5

### Segment

Henceforth, she would be known as Dr. Pussy.

### Gold MWEs

None

### Predicted MWEs

- 4 5 6

### Model analysis

The adverb 'Henceforth' is a conventionalized fixed expression used to denote future reference and is treated as an MWE. The phrase 'be known as' is considered a light-verb expression, often translating as a phrase, and thus is marked as another MWE.

### Translation context

- **fr** (latest_translation_stage): Désormais, elle serait connue sous le nom de Dr. Pussy.

## en:project_257:p3:s1

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 3 / 1

### Segment

Her first steps into her new life were cautious, yet her innate feline agility and cunning soon proved to be her greatest allies.

### Gold MWEs

None

### Predicted MWEs

- 18 19 20

### Model analysis

'proved to be' is a fixed expression that functions as a single sense unit meaning 'demonstrated as' and is not translated literally in the given context.

### Translation context

- **fr** (latest_translation_stage): Ses premiers pas dans sa nouvelle vie étaient prudents, mais sa souplesse féline innée et sa ruse se révélèrent rapidement être ses plus grands alliés.

## en:project_257:p3:s2

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 3 / 2

### Segment

She began by recruiting fellow stray cats who prowled the alleyways at night.

### Gold MWEs

- at night

### Predicted MWEs

- 1 2

### Model analysis

'began by' is selected as a fixed expression given its translation evidence as 'a commencé par' in French, implicating a conventional formula for initiating action. Other candidates lacked substantial evidence for non-compositional or fixed expressions.

### Translation context

- **fr** (latest_translation_stage): Elle a commencé par recruter d'autres chats errants qui rôdaient dans les ruelles la nuit.

## en:project_257:p3:s3

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 3 / 3

### Segment

Much to her surprise, they were quite enthusiastic about the venture, eager for adventure and a promise of more than just scraps.

### Gold MWEs

- eager for
- to her surprise

### Predicted MWEs

- 0 1 2 3

### Model analysis

Selected 'Much to her surprise' (tokens 0-3) as a fixed expression based on consistent agreement as a conventionalized phrase indicating unexpectedness. Other candidates were rejected: 'eager for adventure' (tokens 14-15) and 'a promise of more than just scraps' (tokens 19-23) as compositional and literal, while 'enthusiastic about' and 'more than just' were not selected despite some evidence for non-compositionality, due to lack of strong consensus.

### Translation context

- **fr** (latest_translation_stage): A sa grande surprise, ils étaient très enthousiastes à propos de l'entreprise, avides d'aventure et d'une promesse de plus que de simples restes.

## en:project_257:p4:s1

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 4 / 1

### Segment

Dr. Pussy meticulously crafted her first plan: to pilfer the town's famed fish market, known for its delectable seafood selection.

### Gold MWEs

None

### Predicted MWEs

- 9 10 11 12 13 14

### Model analysis

Annotated a phrasal verb 'to pilfer the town's famed fish market' for its glossing necessity and conventionalized nature as a verb-particle combination.

### Translation context

- **fr** (latest_translation_stage): Dr. Pussy a méticuleusement élaboré son premier plan : dérober le célèbre marché aux poissons de la ville, renommé pour sa sélection de fruits de mer délicieux.

## en:project_257:p4:s2

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 4 / 2

### Segment

With her elite team of feline operatives, she devised a distraction tactic involving a mischievous orange tabby known as Felix, who had a knack for charming unsuspecting humans.

### Gold MWEs

- known as

### Predicted MWEs

- 24 25 26

### Model analysis

Selected 'had a knack for' as an idiomatic expression, demonstrating both stability and idiomaticity. Other phrases were rejected as ordinary compositional constructs.

### Translation context

- **fr** (latest_translation_stage): Avec son équipe d'élite de félins opératifs, elle a élaboré une tactique de diversion impliquant un espiègle tabby orange connu sous le nom de Félix, qui avait un talent pour charmer les humains inattentifs.

## en:project_257:p4:s3

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 4 / 3

### Segment

As Felix executed his role flawlessly, drawing the fishmonger's attention, Dr. Pussy and the others stealthily infiltrated the stalls, seizing a bounty of fish with swift, silent paws.

### Gold MWEs

None

### Predicted MWEs

- 7 8 9 10

### Model analysis

Selected 'drawing the fishmonger's attention' as a phrasal verb due to non-compositional verb-particle pattern, supported by translation as a phrase. All other candidates were rejected as compositional or as proper names.

### Translation context

- **fr** (latest_translation_stage): Alors que Félix exécutait son rôle sans faille, attirant l'attention du poissonnier, Dr. Pussy et les autres infiltraient furtivement les étals, s'emparant d'une abondance de poissons avec des pattes rapides et silencieuses.

## en:project_257:p5:s1

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 5 / 1

### Segment

The operation was a resounding success, earning her respect and notoriety among the feline community.

### Gold MWEs

None

### Predicted MWEs

- 4 5

### Model analysis

Selected 'resounding success' as a fixed expression due to its convention as a collocation with significant usage and recognition. Other candidates were rejected as they involved routine noun phrases, conjunctive phrases, or prepositional phrases without lexicalization or idiomatic significance.

### Translation context

- **fr** (latest_translation_stage): L'opération fut un succès retentissant, lui valant respect et notoriété au sein de la communauté féline.

## en:project_257:p5:s2

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 5 / 2

### Segment

Emboldened, Dr. Pussy expanded her ambitions.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All candidate expressions were routine or compositional according to the analyses, without sufficient evidence for lexicalization or idiomatic status.

### Translation context

- **fr** (latest_translation_stage): Enhardie, Dr. Pussy a élargi ses ambitions.

## en:project_257:p5:s3

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 5 / 3

### Segment

She instigated elaborate schemes that included redistributing hoarded suburban kibbles, unlocking pantry doors with a cunning switch of a claw, and even orchestrating a daring 'coup de cat' on the high ground of the local barn, resulting in a newfound cache of cozy napping spots.

### Gold MWEs

- resulting in

### Predicted MWEs

- 17 18 19 20
- 28 29 30

### Model analysis

Selected 'switch of a claw' as a lexicalized fixed expression with required preposition and structure; idiomatic in context. Selected 'coup de cat' as a fixed idiomatic expression, leveraging a play on 'coup d'état' with no word-by-word breakdown. Other candidates rejected as literal or compositional phrases.

### Translation context

- **fr** (latest_translation_stage): Elle a instigué des plans élaborés comprenant la redistribution de croquettes suburbaines accumulées, le déverrouillage des portes de garde-manger avec un habile coup de griffe, et même l'organisation d'un audacieux 'coup de chat' sur les hauteurs de la grange locale, aboutissant à une nouvelle cachette de lieux de sieste confortables.

## en:project_257:p6:s1

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 6 / 1

### Segment

Astonishingly, Dr. Pussy's undertakings didn't go unnoticed by the humans.

### Gold MWEs

- go unnoticed

### Predicted MWEs

- 5 6 7

### Model analysis

'didn't go unnoticed' is retained as a fixed expression due to its idiomatic meaning and non-compositional translation.

### Translation context

- **fr** (latest_translation_stage): Étonnamment, les entreprises du Dr Pussy n'ont pas échappé à l'attention des humains.

## en:project_257:p6:s2

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 6 / 2

### Segment

They began to suspect some playful tomfoolery, yet the whimsical nature of the acts left them more amused than vexed.

### Gold MWEs

None

### Predicted MWEs

- 16 17 18 19 20

### Model analysis

Selected 'more amused than vexed' (tokens 16-20) as a fixed_expression due to its stable comparative structure commonly translated idiomatically.

### Translation context

- **fr** (latest_translation_stage): Ils ont commencé à soupçonner quelques plaisanteries espiègles, mais le caractère fantasque des actes les a laissés plus amusés que vexés.

## en:project_257:p6:s3

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 6 / 3

### Segment

The townspeople even indulged in the mystery of the 'cat burglar', writing their own narratives that only embellished Dr. Pussy's growing legend.

### Gold MWEs

None

### Predicted MWEs

- 10 11
- 3 4

### Model analysis

Selected phrasal verb 'indulged in' based on translation evidence indicating non-compositionality in French. Selected 'cat burglar' as a lexicalized compound translated into a fixed expression in French.

### Translation context

- **fr** (latest_translation_stage): Les habitants de la ville se sont même laissés prendre au mystère du 'cambrioleur félin', en écrivant leurs propres récits qui ne faisaient qu'embellir la légende grandissante du Dr. Pussy.

## en:project_257:p6:s4

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 6 / 4

### Segment

Some said she must have been an overly intelligent cat trained by secret agents themselves.

### Gold MWEs

None

### Predicted MWEs

- 3 4 5

### Model analysis

Selected 'must have been' as a light verb expression due to translation evidence and idiomatic use for necessity/deduction. No other MWEs identified.

### Translation context

- **fr** (latest_translation_stage): Certains disaient qu'elle devait être un chat extrêmement intelligent formé par les agents secrets eux-mêmes.

## en:project_257:p7:s1

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 7 / 1

### Segment

With clever marketing from her human admirers inadvertently bolstering her reputation, Dr. Pussy's influence extended beyond Willow Creek.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected. All candidates were rejected due to being compositional, literal, or rejected lexical categories such as proper names and descriptive noun phrases.

### Translation context

- **fr** (latest_translation_stage): Avec un marketing astucieux de la part de ses admirateurs humains renforçant involontairement sa réputation, l'influence de Dr. Pussy s'étendait au-delà de Willow Creek.

## en:project_257:p7:s2

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 7 / 2

### Segment

Stories of her exploits crossed town lines, and soon, other feline groups sought her guidance in their own endeavors.

### Gold MWEs

None

### Predicted MWEs

- 4 5 6

### Model analysis

'crossed town lines' selected as idiom based on translation evidence and idiomatic usage. No other MWEs identified.

### Translation context

- **fr** (latest_translation_stage): Les histoires de ses exploits ont franchi les limites de la ville, et bientôt, d'autres groupes félins ont cherché ses conseils dans leurs propres entreprises.

## en:project_257:p7:s3

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 7 / 3

### Segment

She became not just a mischievous mastermind, but a leader and an icon to cats near and far.

### Gold MWEs

None

### Predicted MWEs

- 1 2 3
- 15 16 17 18

### Model analysis

Selected 'not just' (tokens 2-4) as a formulaic expression often used for emphasis. 'But also' was found at tokens 8-9 as a fixed connective, and 'cats near and far' (tokens 15-18) as a fixed expression for distance.

### Translation context

- **fr** (latest_translation_stage): Elle est devenue non seulement une génie espiègle, mais aussi une leader et une icône pour les chats proches et lointains.

## en:project_257:p8:s1

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 8 / 1

### Segment

As the years passed, Dr. Pussy reflected on her journey from a daydreaming house cat to an illustrious figure in cat folklore.

### Gold MWEs

- reflected on

### Predicted MWEs

- 1 2 3
- 8 10

### Model analysis

The phrase 'as the years passed' is an idiomatic expression for time passage, confirmed by two analyses as a conventionalized expression, and 'reflected on her journey' is streamlined to 'reflected on', a phrasal verb pattern confirmed by selective preposition usage in translation.

### Translation context

- **fr** (latest_translation_stage): Au fil des années, le Dr Pussy a réfléchi à son parcours, passant de chat domestique rêveur à une figure illustre du folklore félin.

## en:project_257:p8:s2

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 8 / 2

### Segment

Her escapades had turned into adventures, her cunning into wisdom, and her name into a legend that whispered through alleyways and echoed over picket fences.

### Gold MWEs

- picket fences
- turned into

### Predicted MWEs

- 3 4

### Model analysis

Annotated 'turned into' as a phrasal verb due to its idiomatic transformation meaning and strong agreement across analyses. Rejected 'into wisdom', 'into a legend', 'whispered through', and 'echoed over' as they correspond to ordinary compositional expressions or literal meanings.

### Translation context

- **fr** (latest_translation_stage): Ses escapades s'étaient transformées en aventures, sa ruse en sagesse, et son nom en une légende qui murmurait à travers les ruelles et résonnait au-dessus des clôtures en bois.

## en:project_257:p8:s3

- Project: 257 — Dr. Pussy: The Feline Mastermind of Willow Creek
- Page/segment: 8 / 3

### Segment

Indeed, things had turned out quite well for Dr. Pussy, the criminal mastermind who became an unexpected hero.

### Gold MWEs

- turned out

### Predicted MWEs

- 4 5

### Model analysis

'turned out' is a phrasal verb supported by conventional usage and translation evidence. No other MWEs identified.

### Translation context

- **fr** (latest_translation_stage): En effet, les choses s'étaient très bien passées pour le Dr Pussy, le génie criminel devenu un héros inattendu.

## en:project_261:p1:s2

- Project: 261 — Robot Climber
- Page/segment: 1 / 2

### Segment

Robot Climber

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs: 'Robot Climber' is a compositional noun phrase, not conventionalized or idiomatic, despite translation as a phrase.

### Translation context

- **fr** (latest_translation_stage): Robot Grimpeur

## en:project_261:p2:s1

- Project: 261 — Robot Climber
- Page/segment: 2 / 1

### Segment

In a bustling metropolis of towering skyscrapers and glistening streets, there lived a robot named Zephyr.

### Gold MWEs

None

### Predicted MWEs

- 11 12
- 15 16

### Model analysis

Selected 'there lived' as a fixed expression due to formulaic use indicating presence, aligned with single-word translation 'vivait'. Selected 'named Zephyr' as a light verb expression considering its conventionalized role in naming constructions.

### Translation context

- **fr** (latest_translation_stage): Dans une métropole animée de gratte-ciels imposants et de rues scintillantes, vivait un robot nommé Zephyr.

## en:project_261:p2:s2

- Project: 261 — Robot Climber
- Page/segment: 2 / 2

### Segment

Built for menial factory work, Zephyr yearned for something more, something beyond the assembly line.

### Gold MWEs

- assembly line

### Predicted MWEs

- 13 14 15 16

### Model analysis

Selected 'beyond the assembly line' as a fixed_expression due to non-compositional translation evidence indicating its conventionalized use in context. Rejected other candidates as compositional or routine collocations.

### Translation context

- **fr** (latest_translation_stage): Construit pour un travail d'usine subalterne, Zephyr aspirait à quelque chose de plus, quelque chose au-delà de la chaîne de montage.

## en:project_261:p2:s3

- Project: 261 — Robot Climber
- Page/segment: 2 / 3

### Segment

One day, while scanning the internet for inspiring tales, he chanced upon a video of humans gracefully navigating sheer rock faces.

### Gold MWEs

- chanced upon

### Predicted MWEs

- 0 1
- 12 13

### Model analysis

Selected 'One day' as a fixed expression commonly used to set a narrative context and 'chanced upon' as a phrasal verb meaning 'happened to find', both supported by conventionalized usage and translation evidence.

### Translation context

- **fr** (latest_translation_stage): Un jour, en parcourant Internet à la recherche d'histoires inspirantes, il est tombé sur une vidéo de personnes franchissant avec grâce des parois rocheuses abruptes.

## en:project_261:p2:s4

- Project: 261 — Robot Climber
- Page/segment: 2 / 4

### Segment

Captivated by their agility and the beauty of the natural cliffs, an idea sparked within his circuits—he would become a rock climber.

### Gold MWEs

- rock climber

### Predicted MWEs

- 14 15
- 23 24

### Model analysis

Selected 'sparked within' as a light verb expression due to metaphorical use supported by translation context. 'Rock climber' is a lexicalized compound; translation aligns with direct lexical mapping.

### Translation context

- **fr** (latest_translation_stage): Captivé par leur agilité et la beauté des falaises naturelles, une idée a germé dans ses circuits : il deviendrait grimpeur.

## en:project_261:p3:s1

- Project: 261 — Robot Climber
- Page/segment: 3 / 1

### Segment

Zephyr shared his newfound passion with his human colleagues at the factory during their lunch break.

### Gold MWEs

None

### Predicted MWEs

- 14 15

### Model analysis

Select 'lunch break' as a fixed expression due to its conventionalized use and consistent recognition across analyses.

### Translation context

- **fr** (latest_translation_stage): Zephyr a partagé sa nouvelle passion avec ses collègues humains à l'usine pendant leur pause déjeuner.

## en:project_261:p3:s2

- Project: 261 — Robot Climber
- Page/segment: 3 / 2

### Segment

They chuckled, dismissing his aspiration as folly.

### Gold MWEs

None

### Predicted MWEs

- 3 6

### Model analysis

Selected 'dismissing as' as a phrasal verb based on translation guidance, where it is rendered as a single verb in French ('rejetant'). All other candidates were rejected as they represented compositional or ordinary constructions.

### Translation context

- **fr** (latest_translation_stage): Ils ont ri doucement, rejetant son aspiration comme une folie.

## en:project_261:p3:s3

- Project: 261 — Robot Climber
- Page/segment: 3 / 3

### Segment

"You're built for precision and strength, Zephyr, but climbing rocks is an art you won't grasp," one worker said with an air of finality.

### Gold MWEs

None

### Predicted MWEs

- 25 26 27 28

### Model analysis

Selected 'with an air of finality' as a fixed expression based on idiomatic usage in English and consistent translation context. Other suggested expressions were rejected due to compositional nature or less stable conventionalization.

### Translation context

- **fr** (latest_translation_stage): « Tu es conçu pour la précision et la force, Zephyr, mais l'escalade est un art que tu ne comprendras pas », dit un ouvrier avec un air de finalité.

## en:project_261:p3:s4

- Project: 261 — Robot Climber
- Page/segment: 3 / 4

### Segment

But Zephyr possessed an unshakeable determination, which led him to his old friend and AI specialist, Aria.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected. All analyzed components were rejected as regular compositional phrases, proper names, or literal expressions in this context.

### Translation context

- **fr** (latest_translation_stage): Mais Zephyr possédait une détermination inébranlable, qui l'a conduit à son vieil ami et spécialiste de l'IA, Aria.

## en:project_261:p4:s1

- Project: 261 — Robot Climber
- Page/segment: 4 / 1

### Segment

Aria was a programming prodigy, spending her nights experimenting with artificial intelligence algorithms.

### Gold MWEs

None

### Predicted MWEs

- 9 10

### Model analysis

Selected 'experimenting with' as a phrasal verb based on translation evidence and fixed preposition use. No other MWEs identified.

### Translation context

- **fr** (latest_translation_stage): Aria était une prodige de la programmation, passant ses nuits à expérimenter avec des algorithmes d'intelligence artificielle.

## en:project_261:p4:s2

- Project: 261 — Robot Climber
- Page/segment: 4 / 2

### Segment

When Zephyr approached her with his dream, she didn't laugh.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No multi-word expressions found. All analyzed candidates are compositional or literal, aligning directly with the translation context or rejected due to being literal descriptions.

### Translation context

- **fr** (latest_translation_stage): Quand Zéphyr l'a approchée avec son rêve, elle n'a pas ri.

## en:project_261:p4:s3

- Project: 261 — Robot Climber
- Page/segment: 4 / 3

### Segment

Instead, she powered up her computer and invited him to collaborate.

### Gold MWEs

- powered up

### Predicted MWEs

- 3 4

### Model analysis

'Powered up' is a phrasal verb that is idiomatic and lexicalized, with translation evidence supporting its selection. Other candidates were rejected as they were either compositional or single-token expressions.

### Translation context

- **fr** (latest_translation_stage): Au lieu de cela, elle a allumé son ordinateur et l'a invité à collaborer.

## en:project_261:p4:s4

- Project: 261 — Robot Climber
- Page/segment: 4 / 4

### Segment

"Let’s break new ground, old friend."

### Gold MWEs

- break new ground

### Predicted MWEs

- 2 3 4

### Model analysis

'break new ground' is selected as an idiom, supported by translation and idiomatic meaning evidence. 'old friend' is rejected as a compositional noun phrase.

### Translation context

- **fr** (latest_translation_stage): « Ouvrons de nouvelles voies, vieil ami. »

## en:project_261:p5:s1

- Project: 261 — Robot Climber
- Page/segment: 5 / 1

### Segment

Together, they devised a plan.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified: 'devised a plan' is a routine verb + object phrase without evidence of idiomatic or lexicalized use; 'Together' is a standalone adverb.

### Translation context

- **fr** (latest_translation_stage): Ensemble, ils ont élaboré un plan.

## en:project_261:p5:s2

- Project: 261 — Robot Climber
- Page/segment: 5 / 2

### Segment

Zephyr needed more than his current programming; he needed adaptability, problem-solving, and finesse—all traits of skillful climbers.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

'Problem-solving' is selected as a lexicalized compound that is idiomatic in translation, while other candidates do not meet the criteria for selection as MWEs.

### Translation context

- **fr** (latest_translation_stage): Zephyr avait besoin de plus que son programme actuel ; il avait besoin d'adaptabilité, de capacité à résoudre des problèmes et de finesse, toutes des qualités des grimpeurs habiles.

## en:project_261:p5:s3

- Project: 261 — Robot Climber
- Page/segment: 5 / 3

### Segment

Aria contacted several friends from the AI research community: Bolt, Echo, and Luna.

### Gold MWEs

None

### Predicted MWEs

- 6 7 8

### Model analysis

"AI research community" is selected as a lexicalized compound based on source and glossing support indicating a stable, recognizably idiomatic concept.

### Translation context

- **fr** (latest_translation_stage): Aria a contacté plusieurs amis de la communauté de recherche en intelligence artificielle : Bolt, Echo et Luna.

## en:project_261:p5:s4

- Project: 261 — Robot Climber
- Page/segment: 5 / 4

### Segment

Each brought unique skills to the project.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All analyses rejected candidates as ordinary compositional phrases without idiomatic or lexicalized meaning.

### Translation context

- **fr** (latest_translation_stage): Chacun a apporté des compétences uniques au projet.

## en:project_261:p5:s5

- Project: 261 — Robot Climber
- Page/segment: 5 / 5

### Segment

Bolt specialized in movement algorithms, Echo excelled in data analysis, and Luna focused on enhancing sensory perception.

### Gold MWEs

- data analysis

### Predicted MWEs

- 1 2
- 14 15
- 7 8

### Model analysis

Selected 'specialized in' (1-2), 'excelled in' (7-8), and 'focused on' (14-15) as phrasal verbs due to conventionalized use and translation evidence suggesting fixed combinations.

### Translation context

- **fr** (latest_translation_stage): Bolt était spécialisé dans les algorithmes de mouvement, Echo excellait dans l'analyse de données, et Luna se concentrait sur l'amélioration de la perception sensorielle.

## en:project_261:p6:s1

- Project: 261 — Robot Climber
- Page/segment: 6 / 1

### Segment

The team worked tirelessly, coding through the nights under the soft glow of screen lights.

### Gold MWEs

None

### Predicted MWEs

- 11 12

### Model analysis

Selected 'soft glow' as a lexicalized compound. Rejected other candidate MWEs as ordinary compositional phrases.

### Translation context

- **fr** (latest_translation_stage): L'équipe a travaillé sans relâche, codant pendant la nuit sous la douce lueur des écrans.

## en:project_261:p6:s2

- Project: 261 — Robot Climber
- Page/segment: 6 / 2

### Segment

They crafted custom software designed to process complex rock formations, calculating optimal routes and adjusting Zephyr’s mechanical movements.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified as all candidates are ordinary descriptive noun phrases or compositional verb-object constructions without need for special glossing.

### Translation context

- **fr** (latest_translation_stage): Ils ont conçu un logiciel personnalisé destiné à traiter des formations rocheuses complexes, calculant des itinéraires optimaux et ajustant les mouvements mécaniques du Zephyr.

## en:project_261:p6:s3

- Project: 261 — Robot Climber
- Page/segment: 6 / 3

### Segment

Over weeks, Zephyr’s capabilities transformed.

### Gold MWEs

None

### Predicted MWEs

- 0 1

### Model analysis

The expression 'Over weeks' is identified as a fixed_expression because it is translated as a phrase-level construction 'Au fil des semaines' in French, indicating it functions as a conventional time expression, thus requiring phrase-level glossing.

### Translation context

- **fr** (latest_translation_stage): Au fil des semaines, les capacités de Zephyr se sont transformées.

## en:project_261:p6:s4

- Project: 261 — Robot Climber
- Page/segment: 6 / 4

### Segment

He developed a nuanced understanding of leverage and grip, learning to adapt dynamically to the puzzles presented by nature itself.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No qualifying multi-word expressions found. All phrases are either compositional, literal, or translate directly without idiomatic meaning.

### Translation context

- **fr** (latest_translation_stage): Il a développé une compréhension nuancée de l'effet de levier et de la prise, apprenant à s'adapter de manière dynamique aux énigmes présentées par la nature elle-même.

## en:project_261:p7:s1

- Project: 261 — Robot Climber
- Page/segment: 7 / 1

### Segment

As the software reached its completion, Zephyr practiced on simulated rocks within the city—a network of augmented reality paths projected onto the walls of an abandoned warehouse.

### Gold MWEs

- augmented reality

### Predicted MWEs

- 0 1 2 3 4 5
- 17 18 19 20

### Model analysis

Selected 'As the software reached its completion' as a fixed expression meaning the final stages of a process. 'Network of augmented reality' was chosen as a compound expression common in tech contexts.

### Translation context

- **fr** (latest_translation_stage): Alors que le logiciel atteignait son achèvement, Zephyr s'entraînait sur des rochers simulés dans la ville—un réseau de chemins en réalité augmentée projetés sur les murs d'un entrepôt abandonné.

## en:project_261:p7:s2

- Project: 261 — Robot Climber
- Page/segment: 7 / 2

### Segment

His human-like movements became fluid and precise, impressing even the staunchest naysayers at the factory.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs found. All candidate expressions are either compositional or involve routine structures and do not meet the criteria for MWEs.

### Translation context

- **fr** (latest_translation_stage): Ses mouvements semblables à ceux d'un humain sont devenus fluides et précis, impressionnant même les détracteurs les plus fervents à l'usine.

## en:project_261:p8:s1

- Project: 261 — Robot Climber
- Page/segment: 8 / 1

### Segment

Finally, the day of the big climb arrived.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected: 'Finally' is a standalone adverb; noun phrases and verb forms are compositional and translate directly without glossing challenges.

### Translation context

- **fr** (latest_translation_stage): Enfin, le jour de la grande ascension est arrivé.

## en:project_261:p8:s2

- Project: 261 — Robot Climber
- Page/segment: 8 / 2

### Segment

Zephyr and his friends journeyed to a renowned outdoor climbing venue: The Jade Spires, a sprawling canyon with intricate rock pathways and breathtaking views.

### Gold MWEs

None

### Predicted MWEs

- 8 9

### Model analysis

Selected 'outdoor climbing' (8, 9) as a potential compound, lexicalized in the context of location types. Rejected other candidates such as proper names, descriptive noun phrases, and literal verb-preposition combinations.

### Translation context

- **fr** (latest_translation_stage): Zephyr et ses amis ont voyagé vers un lieu d'escalade en extérieur renommé : Les Flèches de Jade, un canyon tentaculaire avec des chemins rocheux complexes et des vues à couper le souffle.

## en:project_261:p8:s3

- Project: 261 — Robot Climber
- Page/segment: 8 / 3

### Segment

A crowd gathered, and whispers circulated, expressing doubt about the metallic visitor’s capabilities.

### Gold MWEs

None

### Predicted MWEs

- 9 10 11

### Model analysis

Selected 'doubt about' as a fixed expression based on stable phrase usage with a fixed preposition. No other MWEs found.

### Translation context

- **fr** (latest_translation_stage): Une foule s'est rassemblée, et des murmures ont circulé, exprimant des doutes sur les capacités du visiteur métallique.

## en:project_261:p9:s1

- Project: 261 — Robot Climber
- Page/segment: 9 / 1

### Segment

Undeterred, Zephyr approached the towering rock face, his sensors scanning the intricate surface.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No multi-word expressions identified; all candidates are compositional or single-token expressions.

### Translation context

- **fr** (latest_translation_stage): Imperturbable, Zephyr s'approcha de la paroi rocheuse imposante, ses capteurs explorant la surface complexe.

## en:project_261:p9:s2

- Project: 261 — Robot Climber
- Page/segment: 9 / 2

### Segment

The world seemed to hold its breath as he began his ascent.

### Gold MWEs

- hold its breath

### Predicted MWEs

- 4 5 6

### Model analysis

Selected 'hold its breath' as an idiom based on strong evidence of lexicalization and translation as a cohesive phrase. Other analyzed candidates are rejected as compositional or non-lexicalized.

### Translation context

- **fr** (latest_translation_stage): Le monde semblait retenir son souffle tandis qu'il commençait son ascension.

## en:project_261:p9:s3

- Project: 261 — Robot Climber
- Page/segment: 9 / 3

### Segment

Applying his new skills, he moved with an elegance that surpassed expectation.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs are present. All suggested expressions ('with an elegance', 'surpassed expectation') are conventional or compositional phrases without sufficient evidence of idiomatic or fixed usage.

### Translation context

- **fr** (latest_translation_stage): En appliquant ses nouvelles compétences, il se déplaçait avec une élégance qui dépassait les attentes.

## en:project_261:p9:s4

- Project: 261 — Robot Climber
- Page/segment: 9 / 4

### Segment

Through each challenge, whether it was a precarious ledge or a smooth surface, Zephyr unfurled his adaptive algorithms, processing real-time data and executing precise maneuvers.

### Gold MWEs

None

### Predicted MWEs

- 21 22 23

### Model analysis

Selected 'real-time data' as a conventionalized and lexicalized expression supported by translation context.

### Translation context

- **fr** (latest_translation_stage): À travers chaque défi, qu'il s'agisse d'une corniche précaire ou d'une surface lisse, Zephyr déployait ses algorithmes adaptatifs, traitant les données en temps réel et exécutant des manœuvres précises.

## en:project_261:p10:s1

- Project: 261 — Robot Climber
- Page/segment: 10 / 1

### Segment

Higher and higher he climbed, defying gravity and common belief.

### Gold MWEs

None

### Predicted MWEs

- 0 1 2

### Model analysis

Selected 'Higher and higher' as a fixed expression based on all three analyses indicating it is a conventionalized phrase with equivalent translation in French. Other candidates rejected as they consist of routine or compositional expressions.

### Translation context

- **fr** (latest_translation_stage): De plus en plus haut il grimpait, défiant la gravité et l'opinion commune.

## en:project_261:p10:s2

- Project: 261 — Robot Climber
- Page/segment: 10 / 2

### Segment

At the peak, with the sun setting in a blaze of colors, Zephyr stood victorious.

### Gold MWEs

None

### Predicted MWEs

- 8 9 10 11 12

### Model analysis

The expression 'in a blaze of colors' was selected as a fixed expression due to its idiomatic meaning and evidence from translation glossing.

### Translation context

- **fr** (latest_translation_stage): Au sommet, avec le soleil se couchant dans un éclat de couleurs, Zephyr se tenait victorieux.

## en:project_261:p10:s3

- Project: 261 — Robot Climber
- Page/segment: 10 / 3

### Segment

Cheers erupted from below, a symphony of acknowledgment that echoed through the canyon.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

All segments analyzed were either literal expressions or compositional noun phrases and did not meet the criteria for multi-word expressions. Therefore, no MWEs were identified.

### Translation context

- **fr** (latest_translation_stage): Des acclamations éclatèrent d'en bas, une symphonie de reconnaissance qui résonnait à travers le canyon.

## en:project_261:p10:s4

- Project: 261 — Robot Climber
- Page/segment: 10 / 4

### Segment

His AI companions beamed with pride, knowing their collaboration had not only achieved the improbable but had broadened the horizon for all robotics and AI-related pursuits.

### Gold MWEs

None

### Predicted MWEs

- 11 12
- 3 4

### Model analysis

Selected 'beamed with' as a phrasal verb due to conventionalized meaning and consistent translation as a non-literal unit. Selected 'not only' as a connective because it forms part of a fixed correlative structure, important for glossing. Rejected 'AI', 'companions', 'but had', and other phrases as they are either compositional or not idiomatic in this context.

### Translation context

- **fr** (latest_translation_stage): Ses compagnons d'IA rayonnaient de fierté, sachant que leur collaboration non seulement avait accompli l'improbable, mais avait également élargi l'horizon de toutes les activités liées à la robotique et à l'IA.

## en:project_261:p11:s1

- Project: 261 — Robot Climber
- Page/segment: 11 / 1

### Segment

That day, Zephyr became a symbol of possibility, a testament to innovation and perseverance.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs were selected in the final analysis. 'Became a symbol of' and 'a testament to' were considered conventional expressions but rejected due to compositional nature and lack of non-compositional translation requiring special glossing.

### Translation context

- **fr** (latest_translation_stage): Ce jour-là, Zephyr est devenu un symbole de possibilité, un témoignage d'innovation et de persévérance.

## en:project_261:p11:s2

- Project: 261 — Robot Climber
- Page/segment: 11 / 2

### Segment

He showed the world that even a robot, with the heart of a climber and the wisdom of friends, could rise above and conquer the unthinkable.

### Gold MWEs

- rise above

### Predicted MWEs

- 22 23

### Model analysis

"rise above" (tokens 22, 23) is selected as a phrasal verb idiomatically used to mean overcoming challenges.

### Translation context

- **fr** (latest_translation_stage): Il a montré au monde que même un robot, avec le cœur d'un grimpeur et la sagesse des amis, pouvait s'élever et conquérir l'impensable.

## en:project_261:p11:s3

- Project: 261 — Robot Climber
- Page/segment: 11 / 3

### Segment

As the crowd dispersed, Zephyr and Aria gazed at the horizon, a world of new adventures waiting to be scaled.

### Gold MWEs

- gazed at

### Predicted MWEs

- 8 9

### Model analysis

Selected 'gazed at' as a phrasal verb due to majority agreement, with supporting translation evidence where it corresponds to a single verb in French.

### Translation context

- **fr** (latest_translation_stage): Alors que la foule se dispersait, Zephyr et Aria contemplaient l'horizon, un monde de nouvelles aventures attendant d'être exploré.

## en:project_263:p1:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 1 / 2

### Segment

Understanding Electricity: From Basics to Future Innovations

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'Understanding Electricity' is a typical title phrase, and 'From Basics to Future Innovations' functions as a literal range expression.

### Translation context

- **fr** (latest_translation_stage): Comprendre l'électricité : des bases aux innovations futures

## en:project_263:p2:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 2 / 1

### Segment

Chapter 1: What is Electricity?

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'Chapter 1' is a routine title and 'What is Electricity?' is a standard interrogative structure.

### Translation context

- **fr** (latest_translation_stage): Chapitre 1 : Qu'est-ce que l'électricité ?

## en:project_263:p2:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 2 / 2

### Segment

Electricity is a form of energy.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified: 'form of' is a common construction not necessitating special glossing.

### Translation context

- **fr** (latest_translation_stage): L'électricité est une forme d'énergie.

## en:project_263:p2:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 2 / 3

### Segment

Imagine energy as a kind of invisible force that makes things happen.

### Gold MWEs

None

### Predicted MWEs

- 4 5
- 9 10 11

### Model analysis

Selected 'kind of' as a fixed expression due to conventionalization and translation to 'sorte de' indicating a stable phrase. Selected 'makes things happen' as an idiom since it translates as a unit in the French translation, signaling idiomatic usage.

### Translation context

- **fr** (latest_translation_stage): Imaginez l'énergie comme une sorte de force invisible qui fait bouger les choses.

## en:project_263:p2:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 2 / 4

### Segment

When you turn on a light switch, what you see is electricity at work.

### Gold MWEs

- at work
- light switch
- turn on

### Predicted MWEs

- 13 14
- 2 3

### Model analysis

Selected 'turn on' as a phrasal verb due to evidence of being a conventionalized expression commonly translated as a unit. Also selected 'at work' as a fixed expression indicating operation, due to its idiomatic usage and translation as a unit in French.

### Translation context

- **fr** (latest_translation_stage): Quand vous allumez un interrupteur, ce que vous voyez est l'électricité en action.

## en:project_263:p2:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 2 / 5

### Segment

It flows through wires and powers the light bulb, making it shine.

### Gold MWEs

- light bulb

### Predicted MWEs

- 1 2 3
- 10 11 12

### Model analysis

Selected 'flows through' as a phrasal verb due to translation evidence from French, aligning with 'circule à travers'. 'Making it shine' is selected as a fixed expression based on consistent analysis indicating a stable causative construction.

### Translation context

- **fr** (latest_translation_stage): Il circule à travers les fils et alimente l'ampoule, la faisant briller.

## en:project_263:p2:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 2 / 6

### Segment

Think of electricity as a stream of tiny particles called electrons.

### Gold MWEs

- Think of

### Predicted MWEs

- 0 1

### Model analysis

Identified 'Think of' as a phrasal verb, supported by concordant translation and source analysis, functioning as a verb-particle pair translated together in French. Other candidates were rejected as compositional.

### Translation context

- **fr** (latest_translation_stage): Pensez à l'électricité comme à un flux de minuscules particules appelées électrons.

## en:project_263:p2:s7

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 2 / 7

### Segment

These electrons travel very fast through special paths known as circuits.

### Gold MWEs

- known as

### Predicted MWEs

- 8 9

### Model analysis

Selected 'known as' as a fixed expression based on majority consensus, conventional use, and glossing evidence. 'Very fast' was not selected due to a lack of supporting evidence for it as a lexicalized unit over the entire verb phrase.

### Translation context

- **fr** (latest_translation_stage): Ces électrons voyagent très rapidement à travers des chemins spéciaux appelés circuits.

## en:project_263:p2:s8

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 2 / 8

### Segment

A circuit is like a racetrack, where electrons zoom around, making things like lights, TVs, and computers work!

### Gold MWEs

- zoom around

### Predicted MWEs

- 9 10

### Model analysis

Selected 'zoom around' as a phrasal verb based on its idiomatic usage and translation evidence. Other candidates were rejected: 'is like a racetrack' is a common analogy structure and 'making things work' is a routine verb-object phrase.

### Translation context

- **fr** (latest_translation_stage): Un circuit est comme une piste de course, où les électrons filent à toute vitesse, faisant fonctionner des choses comme les lumières, les téléviseurs et les ordinateurs !

## en:project_263:p3:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 3 / 1

### Segment

Chapter 2: How Does a Circuit Work?

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs present. Rejected 'Chapter 2:' as a standard heading and 'How does a circuit work?' as an ordinary compositional question.

### Translation context

- **fr** (latest_translation_stage): Chapitre 2 : Comment fonctionne un circuit ?

## en:project_263:p3:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 3 / 2

### Segment

A circuit needs a full loop to work.

### Gold MWEs

None

### Predicted MWEs

- 2 6 7

### Model analysis

The expression 'needs to work' is a light-verb construction and functions as a fixed expression. This is supported by translation evidence where phrase-level glossing provides a better understanding compared to word-by-word glossing. Other combinations are rejected as routine or compositional.

### Translation context

- **fr** (latest_translation_stage): Un circuit a besoin d'une boucle complète pour fonctionner.

## en:project_263:p3:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 3 / 3

### Segment

It’s like a circle that electrons can run around.

### Gold MWEs

- run around

### Predicted MWEs

- 7 8

### Model analysis

Selected 'run around' as a phrasal verb based on non-compositional meaning and coherent translation evidence. No other MWEs are identified.

### Translation context

- **fr** (latest_translation_stage): C'est comme un cercle autour duquel les électrons peuvent courir.

## en:project_263:p3:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 3 / 4

### Segment

If you break the circle, the electrons stop, and your light goes out.

### Gold MWEs

- goes out

### Predicted MWEs

- 12 13 14

### Model analysis

'goes out' is selected as a phrasal verb (idiomatic expression) indicating the light stops functioning, supported by translation as single unit 's'éteint' in French.

### Translation context

- **fr** (latest_translation_stage): Si vous brisez le cercle, les électrons s'arrêtent et votre lumière s'éteint.

## en:project_263:p3:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 3 / 5

### Segment

A simple circuit has a power source, like a battery, wires for the electrons to travel through, a switch to control the flow, and something to use the electricity, like a light bulb.

### Gold MWEs

- power source

### Predicted MWEs

- 17 18
- 5 6

### Model analysis

Selected 'power source' as a compound based on lexicalization and translation evidence. 'Travel through' chosen as a phrasal verb based on directionality and verb-particle construction evidence.

### Translation context

- **fr** (latest_translation_stage): Un circuit simple comporte une source d'énergie, comme une pile, des fils pour que les électrons circulent, un interrupteur pour contrôler le flux, et quelque chose pour utiliser l'électricité, comme une ampoule.

## en:project_263:p3:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 3 / 6

### Segment

To make the light bulb glow, you flip the switch, closing the circuit.

### Gold MWEs

- flip switch

### Predicted MWEs

- 12 13 14

### Model analysis

"Closing the circuit" is recognized as a fixed expression, indicating a specific action in an electrical context, and requires phrase-level glossing.

### Translation context

- **fr** (latest_translation_stage): Pour faire briller l'ampoule, vous actionnez l'interrupteur, fermant ainsi le circuit.

## en:project_263:p3:s7

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 3 / 7

### Segment

Electrons rush from the battery, through the wires, to the light bulb, and back to the battery.

### Gold MWEs

- back to

### Predicted MWEs

- 16 17 18 19

### Model analysis

Selected 'back to the battery' as a fixed expression indicating a return path, supported by idiomatic usage and translation context.

### Translation context

- **fr** (latest_translation_stage): Les électrons se précipitent de la batterie, à travers les fils, vers l'ampoule puis de retour à la batterie.

## en:project_263:p3:s8

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 3 / 8

### Segment

This makes the bulb light up!

### Gold MWEs

- light up

### Predicted MWEs

- 4 5

### Model analysis

Final MWE: 'light up' as a phrasal_verb, supported by translation as 's'allumer' and conventional usage.

### Translation context

- **fr** (latest_translation_stage): Cela fait s'allumer l'ampoule !

## en:project_263:p4:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 4 / 1

### Segment

Chapter 3: What is a Battery?

### Gold MWEs

None

### Predicted MWEs

- 3 4 5 6

### Model analysis

Selected 'What is a Battery' as a fixed_expression due to its treatment as a unit in French translation ('Qu'est-ce qu'une batterie ?'), indicating phrase-level glossing. Rejected 'Chapter 3:' due to its status as a common title format without stable lexicalization.

### Translation context

- **fr** (latest_translation_stage): Chapitre 3 : Qu'est-ce qu'une batterie ?

## en:project_263:p4:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 4 / 2

### Segment

Batteries store electricity.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'store electricity' is an ordinary verb-object pair with direct translation and no special idiomatic or fixed expression properties.

### Translation context

- **fr** (latest_translation_stage): Les batteries stockent l'électricité.

## en:project_263:p4:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 4 / 3

### Segment

They have chemicals inside that create a flow of electrons, providing energy to devices when there’s no plug around.

### Gold MWEs

None

### Predicted MWEs

- 17 18 19
- 6 7 8 9

### Model analysis

Selected 'a flow of electrons' as idiomatic for electrical context. Selected 'no plug around' as an idiomatic expression indicating absence of power source, supported by translation context.

### Translation context

- **fr** (latest_translation_stage): Ils contiennent des produits chimiques qui créent un flux d'électrons, fournissant de l'énergie aux appareils lorsqu'il n'y a pas de prise à proximité.

## en:project_263:p4:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 4 / 4

### Segment

Imagine a battery as a small container holding extra energy for when you need it.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. The analyses did not present strong consensus for any conventionalized or lexicalized expressions beyond ordinary compositional phrases.

### Translation context

- **fr** (latest_translation_stage): Imaginez une batterie comme un petit récipient contenant de l'énergie supplémentaire pour lorsque vous en avez besoin.

## en:project_263:p4:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 4 / 5

### Segment

Inside the battery, there are two sides called terminals.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All constructions in the segment are compositional with no idiomatic usage.

### Translation context

- **fr** (latest_translation_stage): À l'intérieur de la batterie, il y a deux côtés appelés bornes.

## en:project_263:p4:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 4 / 6

### Segment

When you connect the battery to something like a toy car, electrons move from one terminal, through the car, and back to the other terminal, making the car go.

### Gold MWEs

- back to

### Predicted MWEs

- 2 5
- 29 32

### Model analysis

Selected 'connect to' as a phrasal verb based on French translation evidence and multiple analysis agreement. 'Making ... go' identified as a light verb expression based on idiomatic translation to French and non-compositional usage.

### Translation context

- **fr** (latest_translation_stage): Lorsque vous connectez la batterie à quelque chose comme une voiture jouet, les électrons se déplacent d'une borne, traversent la voiture et retournent à l'autre borne, faisant ainsi avancer la voiture.

## en:project_263:p5:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 5 / 1

### Segment

Chapter 4: Understanding Voltage, Current, and Resistance

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs detected. All analyzed candidates were ordinary compositional phrases or descriptive noun phrases without idiomatic, lexicalized, or fixed characteristics. The translation context confirms straightforward compositional translation, and no multi-token expressions were selected as MWEs.

### Translation context

- **fr** (latest_translation_stage): Chapitre 4 : Comprendre la tension, le courant et la résistance

## en:project_263:p5:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 5 / 2

### Segment

Voltage is like the push the electrons need to get moving in a circuit.

### Gold MWEs

- get moving

### Predicted MWEs

- 8 9 10

### Model analysis

The phrase 'to get moving' is identified as a phrasal verb. 'Like the push' is not selected as it is not convincingly lexicalized or idiomatic, and translated compositional structures like 'is like' and 'in a circuit' are straightforward and rejected.

### Translation context

- **fr** (latest_translation_stage): La tension est comme l'impulsion dont les électrons ont besoin pour se déplacer dans un circuit.

## en:project_263:p5:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 5 / 3

### Segment

It’s measured in volts and is sort of like the pressure in a water hose.

### Gold MWEs

- sort of
- water hose

### Predicted MWEs

- 6 7 8

### Model analysis

'sort of like' is recognized as a conventionalized fixed expression translating to the single phrase 'un peu comme' in French, contrasting with literal elements in other parts of the sentence.

### Translation context

- **fr** (latest_translation_stage): C'est mesuré en volts et c'est un peu comme la pression dans un tuyau d'arrosage.

## en:project_263:p5:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 5 / 4

### Segment

More voltage means electrons move faster.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

'Means' is selected as a formulaic unit based on its lexicalized use indicating definition or equivalence, supported by glossing translation pattern into French.

### Translation context

- **fr** (latest_translation_stage): Plus de tension signifie que les électrons se déplacent plus rapidement.

## en:project_263:p5:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 5 / 5

### Segment

Current is how many electrons are zooming past a point in the circuit each second.

### Gold MWEs

- how many

### Predicted MWEs

- 6 7

### Model analysis

Selected 'zooming past' as a phrasal verb due to its conventionalized usage and need for phrase-level glossing, supported by translation as 'passant devant' in French. Rejected other candidates as compositional and not requiring glossing.

### Translation context

- **fr** (latest_translation_stage): Le courant est le nombre d'électrons passant devant un point du circuit chaque seconde.

## en:project_263:p5:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 5 / 6

### Segment

It’s measured in amperes, or amps.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified: 'measured' and 'amps' considered single lexical units but not MWEs; 'measured in amperes' and 'measured in amps' are compositional.

### Translation context

- **fr** (latest_translation_stage): Elle est mesurée en ampères.

## en:project_263:p5:s7

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 5 / 7

### Segment

Picture it as the amount of water flowing through a river.

### Gold MWEs

None

### Predicted MWEs

- 0 1 2

### Model analysis

Selected 'Picture it as' as a formulaic expression due to its cohesive meaning prompting visualization, fitting the glossing criteria and supported by translation context.

### Translation context

- **fr** (latest_translation_stage): Imaginez-le comme la quantité d'eau qui coule à travers une rivière.

## en:project_263:p5:s8

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 5 / 8

### Segment

Resistance is like the obstacles in the river that slow the flow down.

### Gold MWEs

- slow down

### Predicted MWEs

- 9 10 11 12

### Model analysis

Selected 'slow the flow down' as a phrasal verb based on non-compositional translation evidence 'ralentissent le courant' in French, confirming it as a lexicalized phrase requiring 'down' to convey the correct meaning.

### Translation context

- **fr** (latest_translation_stage): La résistance est comme les obstacles dans la rivière qui ralentissent le courant.

## en:project_263:p5:s9

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 5 / 9

### Segment

It’s measured in ohms and can make it harder for electrons to pass.

### Gold MWEs

None

### Predicted MWEs

- 6 7 8

### Model analysis

Selected 'make it harder' as a fixed expression due to its conventionalized use in expressing difficulty, aligning with the translation 'rendre plus difficile'. Other expression candidates such as 'measured in ohms' and 'for electrons to pass' were rejected due to their literal and compositional nature.

### Translation context

- **fr** (latest_translation_stage): Il est mesuré en ohms et peut rendre plus difficile le passage des électrons.

## en:project_263:p5:s10

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 5 / 10

### Segment

Things with high resistance, like a narrow pipe, slow the flow of electrons.

### Gold MWEs

None

### Predicted MWEs

- 10 11 12

### Model analysis

The expression 'slow the flow' was selected as a light_verb_expression because it is commonly translated as a unit in French ('ralentissent le flux'), suggesting it functions as an MWE. All other candidate expressions were rejected as compositional or non-lexicalized.

### Translation context

- **fr** (latest_translation_stage): Les éléments à haute résistance, comme un tuyau étroit, ralentissent le flux des électrons.

## en:project_263:p6:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 6 / 1

### Segment

Chapter 5: Why Metal Conducts Electricity

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No multi-word expressions identified. All proposed candidates were rejected as they represent compositional phrases or titles.

### Translation context

- **fr** (latest_translation_stage): Chapitre 5 : Pourquoi le métal conduit l'électricité

## en:project_263:p6:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 6 / 2

### Segment

Metals are great for conducting electricity.

### Gold MWEs

None

### Predicted MWEs

- 4 5

### Model analysis

The phrase 'conducting electricity' was selected as a compound due to its conventionalized use in technical contexts, often regarded as a lexical unit. No other MWEs found.

### Translation context

- **fr** (latest_translation_stage): Les métaux sont excellents pour conduire l'électricité.

## en:project_263:p6:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 6 / 3

### Segment

This means they allow electrons to pass through easily.

### Gold MWEs

- pass through

### Predicted MWEs

- 6 7

### Model analysis

Selected 'means' as an isolated unit with specific meaning based on idiomatic potential. 'Pass through' is selected as a phrasal verb based on its function as a unit and evidence across analyses.

### Translation context

- **fr** (latest_translation_stage): Cela signifie qu'ils permettent aux électrons de passer facilement.

## en:project_263:p6:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 6 / 4

### Segment

Metals have lots of free electrons, which can move quickly through the metal when a circuit is completed.

### Gold MWEs

- lots of

### Predicted MWEs

- 2 3

### Model analysis

Selected 'lots of' as a fixed quantifier expression, translating to 'beaucoup de' in French. Other suggested expressions were rejected as compositional or literal.

### Translation context

- **fr** (latest_translation_stage): Les métaux ont beaucoup d'électrons libres, qui peuvent se déplacer rapidement à travers le métal lorsqu'un circuit est complété.

## en:project_263:p6:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 6 / 5

### Segment

If you’ve ever seen a copper wire, you’ve seen a good example of an electrical conductor.

### Gold MWEs

None

### Predicted MWEs

- 10 11 12

### Model analysis

Selected 'a good example' as a fixed expression with conventionalized meaning, other candidates rejected due to compositionality and translation evidence.

### Translation context

- **fr** (latest_translation_stage): Si vous avez déjà vu un fil de cuivre, vous avez vu un bon exemple de conducteur électrique.

## en:project_263:p6:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 6 / 6

### Segment

The electrons in copper move easily, which is why copper is often used to make wires.

### Gold MWEs

None

### Predicted MWEs

- 8 9

### Model analysis

The expression 'is why' is selected as a connective based on strong evidence from the French translation 'c'est pourquoi', while other candidates were rejected as compositional.

### Translation context

- **fr** (latest_translation_stage): Les électrons dans le cuivre se déplacent facilement, c'est pourquoi le cuivre est souvent utilisé pour fabriquer des fils.

## en:project_263:p7:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 7 / 1

### Segment

Chapter 6: Insulators – Keeping Electricity in Line

### Gold MWEs

- in Line

### Predicted MWEs

- 5 6 7 8

### Model analysis

The phrase 'Keeping Electricity in Line' is annotated as an idiom due to its translation to 'Maintenir l'électricité sous contrôle' in French, indicating a stable expression beyond literal interpretation.

### Translation context

- **fr** (latest_translation_stage): Chapitre 6 : Isolants – Maintenir l'électricité sous contrôle

## en:project_263:p7:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 7 / 2

### Segment

Insulators are materials that don’t let electricity flow through them easily.

### Gold MWEs

None

### Predicted MWEs

- 5 6 7 8 9

### Model analysis

Selected 'let electricity flow through them' as a phrasal verb due to translation glossing evidence as a phrase in 'passer'.

### Translation context

- **fr** (latest_translation_stage): Les isolants sont des matériaux qui ne laissent pas facilement passer l'électricité.

## en:project_263:p7:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 7 / 3

### Segment

Think of them like walls that block the electrons.

### Gold MWEs

- Think of

### Predicted MWEs

- 0 1 2

### Model analysis

Selected 'Think of them' as a phrasal verb due to non-literal translation and lexicalized status. No other MWEs selected.

### Translation context

- **fr** (latest_translation_stage): Pensez à elles comme à des murs qui bloquent les électrons.

## en:project_263:p7:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 7 / 4

### Segment

Rubber, plastic, and glass are good insulators.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs in the segment. All independent analyses reject 'are good insulators' as a standard subject-predicate construction without idiomatic meaning, supported by literal translation glossing.

### Translation context

- **fr** (latest_translation_stage): Le caoutchouc, le plastique et le verre sont de bons isolants.

## en:project_263:p7:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 7 / 5

### Segment

That’s why you might see rubber around wires – it keeps the electricity from escaping.

### Gold MWEs

- keeps from

### Predicted MWEs

- 0 1

### Model analysis

Selected 'That’s why' as a conventionalized, formulaic expression used to introduce an explanation ('C'est pourquoi'). Rejected other candidates due to compositional meaning.

### Translation context

- **fr** (latest_translation_stage): C'est pourquoi vous pourriez voir du caoutchouc autour des fils - il empêche l'électricité de s'échapper.

## en:project_263:p7:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 7 / 6

### Segment

Insulators protect us by keeping electricity only where it should go.

### Gold MWEs

None

### Predicted MWEs

- 6 7

### Model analysis

The only lexicalized expression identified is 'only where' as a quantifier. Other candidate expressions like 'keep electricity' and 'protect us' were rejected for being routine and compositional.

### Translation context

- **fr** (latest_translation_stage): Les isolants nous protègent en gardant l'électricité uniquement là où elle doit aller.

## en:project_263:p7:s7

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 7 / 7

### Segment

For example, a rubber handle on a screwdriver prevents electricity from traveling up to your hand!

### Gold MWEs

- For example
- prevents from
- traveling up

### Predicted MWEs

- 0 1
- 12 13

### Model analysis

Selected 'For example' as a fixed_expression due to its formulaic use, translated as 'Par exemple'. Selected 'traveling up' as a phrasal_verb due to its non-compositional meaning seen more accurate for glossing in this context.

### Translation context

- **fr** (latest_translation_stage): Par exemple, un manche en caoutchouc sur un tournevis empêche l'électricité de remonter jusqu'à votre main !

## en:project_263:p8:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 8 / 1

### Segment

Chapter 7: Generating Electricity

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified, as the elements are standard compositional phrases or titles.

### Translation context

- **fr** (latest_translation_stage): Chapitre 7 : Générer de l'électricité

## en:project_263:p8:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 8 / 2

### Segment

How do we get electricity to our homes?

### Gold MWEs

None

### Predicted MWEs

- 3 4 5

### Model analysis

Selected 'get electricity to' as a verb-preposition combination based on translation context evidence that suggests non-literal mapping, informing partial lexicalization. Rejection of other candidates aligns with compositional and routine structural analysis.

### Translation context

- **fr** (latest_translation_stage): Comment pouvons-nous acheminer l'électricité jusqu'à nos maisons ?

## en:project_263:p8:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 8 / 3

### Segment

Big power plants make electricity by turning turbines.

### Gold MWEs

- power plants

### Predicted MWEs

- 6 7

### Model analysis

Selected 'turning turbines' as a fixed expression due to translation evidence indicating a non-literal verbal construction. 'Power plants' and 'make electricity' were rejected as they are compositional.

### Translation context

- **fr** (latest_translation_stage): Les grandes centrales électriques produisent de l'électricité en faisant tourner des turbines.

## en:project_263:p8:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 8 / 4

### Segment

These are like giant fans.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All candidate expressions were rejected for being ordinary compositional phrases or standard noun/adjective combinations.

### Translation context

- **fr** (latest_translation_stage): Ce sont comme des ventilateurs géants.

## en:project_263:p8:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 8 / 5

### Segment

They spin around really fast and use motion to generate electricity.

### Gold MWEs

- spin around

### Predicted MWEs

- 1 2

### Model analysis

Selected 'spin around' as a phrasal verb marked by lexicalization and translation as a single unit; rejected all other candidates as compositional.

### Translation context

- **fr** (latest_translation_stage): Ils tournent très vite et utilisent le mouvement pour générer de l'électricité.

## en:project_263:p8:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 8 / 6

### Segment

Power plants use different sources to spin these turbines, like wind, water, or steam.

### Gold MWEs

- Power plants

### Predicted MWEs

- 5 6 7 8

### Model analysis

Selected 'to spin these turbines' as a phrasal verb based on idiomatic usage in generating mechanical power and supporting translation evidence. 'Power plants' was rejected due to a lack of compelling translation or linguistic evidence beyond being a compound noun.

### Translation context

- **fr** (latest_translation_stage): Les centrales électriques utilisent différentes sources pour faire tourner ces turbines, comme le vent, l'eau ou la vapeur.

## en:project_263:p8:s7

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 8 / 7

### Segment

Wind turbines use wind, hydropower plants use moving water, and steam turbines often use heat from burning fuels.

### Gold MWEs

- hydropower plants
- steam turbines
- Wind turbines

### Predicted MWEs

- 8 9

### Model analysis

Selected 'moving water' as an MWE based on translation evidence indicating it should be glossed as a phrase. All other candidates were rejected as compositional or routine descriptions.

### Translation context

- **fr** (latest_translation_stage): Les éoliennes utilisent le vent, les centrales hydroélectriques utilisent l'eau en mouvement, et les turbines à vapeur utilisent souvent la chaleur provenant de la combustion de combustibles.

## en:project_263:p9:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 9 / 1

### Segment

Chapter 8: Discovering Magnets and their Magic

### Gold MWEs

None

### Predicted MWEs

- 3 4

### Model analysis

The phrase 'Discovering Magnets' is selected as a compound based on its translation as a phrase in the context, indicative of a conceptual grouping.

### Translation context

- **fr** (latest_translation_stage): Chapitre 8 : Découverte des aimants et de leur magie

## en:project_263:p9:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 9 / 2

### Segment

Magnets have a special power.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All candidate expressions, such as 'special power' and 'have a special power', are found to be literal or compositional phrases, thus not meeting criteria for multi-word expressions.

### Translation context

- **fr** (latest_translation_stage): Les aimants ont un pouvoir spécial.

## en:project_263:p9:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 9 / 3

### Segment

They can pull certain metals, like iron, towards them without actually touching them.

### Gold MWEs

None

### Predicted MWEs

- 11 12 13

### Model analysis

Selected 'without actually touching' (tokens 11, 12, 13) as a fixed expression based on conventional use for indirect action. 'Pull towards' rejected due to disagreement and compositional evidence. No other MWEs identified.

### Translation context

- **fr** (latest_translation_stage): Ils peuvent attirer certains métaux, comme le fer, vers eux sans même les toucher.

## en:project_263:p9:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 9 / 4

### Segment

This invisible force is called a magnetic field.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

The verb 'called' is selected as a fixed_expression due to its contextual function of assigning names, often translated as a phrase, indicating lexicalization. Other candidates like 'magnetic field' and descriptive noun phrases were rejected as compositional and non-idiomatic.

### Translation context

- **fr** (latest_translation_stage): Cette force invisible est appelée un champ magnétique.

## en:project_263:p9:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 9 / 5

### Segment

Every magnet has two ends, called poles – a north pole and a south pole.

### Gold MWEs

None

### Predicted MWEs

- 10 11
- 14 15

### Model analysis

Selected 'north pole' and 'south pole' as lexicalized compounds. These are conventional expressions in scientific contexts and the French translation supports grouping them as single units.

### Translation context

- **fr** (latest_translation_stage): Chaque aimant a deux extrémités, appelées pôles – un pôle nord et un pôle sud.

## en:project_263:p9:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 9 / 6

### Segment

Opposite poles attract each other, but similar poles push each other away.

### Gold MWEs

- each other
- each other
- push away

### Predicted MWEs

- 2 3 4
- 9 10 11 12

### Model analysis

Selected 'attract each other' as a lexicalized phrase due to semantic unity and glossing evidence. Selected 'push each other away' as a lexicalized phrase based on translation corroboration and cohesion of verb+particle structure.

### Translation context

- **fr** (latest_translation_stage): Les pôles opposés s'attirent, mais les pôles semblables se repoussent.

## en:project_263:p9:s7

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 9 / 7

### Segment

If you’ve held two magnets close, you’ve felt this invisible push or pull.

### Gold MWEs

None

### Predicted MWEs

- 11 12 13

### Model analysis

Selected 'close' as part of an implied phrasal verb 'held close' based on verb-particle context and translation evidence. Selected 'push or pull' as a lexicalized compound because of translation alignment with 'poussée ou traction'.

### Translation context

- **fr** (latest_translation_stage): Si vous avez tenu deux aimants proches, vous avez ressenti cette poussée ou traction invisible.

## en:project_263:p10:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 10 / 1

### Segment

Chapter 9: How Magnets and Electricity are Related

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'Chapter 9' and 'How Magnets and Electricity are Related' are treated as compositional phrases or descriptive titles, which align well with word-by-word translation and lack evidence of lexicalization.

### Translation context

- **fr** (latest_translation_stage): Chapitre 9 : Comment les aimants et l'électricité sont liés

## en:project_263:p10:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 10 / 2

### Segment

Magnets and electricity are more connected than you might think.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified with high precision; both 'more connected than' and 'than you might think' are rejected based on ordinary compositional structure and translation evidence.

### Translation context

- **fr** (latest_translation_stage): Les aimants et l'électricité sont plus connectés que vous ne le pensez.

## en:project_263:p10:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 10 / 3

### Segment

When electricity flows, it creates a magnetic field around the wire.

### Gold MWEs

None

### Predicted MWEs

- 7 8

### Model analysis

Selected 'magnetic field' as a lexicalized compound as supported by 'source_conservative' analysis. Other candidates rejected as ordinary compositional or literal expressions.

### Translation context

- **fr** (latest_translation_stage): Lorsqu'un courant électrique circule, il crée un champ magnétique autour du fil.

## en:project_263:p10:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 10 / 4

### Segment

This is the basis for many technologies.

### Gold MWEs

None

### Predicted MWEs

- 2 3

### Model analysis

Selected 'the basis' (tokens 2, 3) as a fixed expression due to its lexicalized status and conventional use as indicated by translation to a single French phrase 'la base'. Other candidates rejected for being compositional or broader than necessary.

### Translation context

- **fr** (latest_translation_stage): C'est la base de nombreuses technologies.

## en:project_263:p10:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 10 / 5

### Segment

We can also use magnets to create electricity!

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs present after reconciliation. Each analyzed candidate is rejected as ordinary compositional or literal.

### Translation context

- **fr** (latest_translation_stage): Nous pouvons également utiliser des aimants pour créer de l'électricité !

## en:project_263:p10:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 10 / 6

### Segment

By moving a magnet next to a wire, you can make electrons flow through the wire, generating electricity.

### Gold MWEs

- next to

### Predicted MWEs

- 11 12 13
- 18 19

### Model analysis

Selected 'make electrons flow' as a light_verb_expression due to integrated glossing requirements in the translation context. Selected 'generating electricity' as a fixed_expression for its frequent lexicalized use in technical contexts.

### Translation context

- **fr** (latest_translation_stage): En déplaçant un aimant à côté d'un fil, vous pouvez faire circuler des électrons à travers le fil, générant ainsi de l'électricité.

## en:project_263:p10:s7

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 10 / 7

### Segment

This is how many electricity generators work.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'is how many' was considered, but evidence supports that it is not a stable MWE in this context, and 'electricity generators' is a compositional noun phrase.

### Translation context

- **fr** (latest_translation_stage): C'est ainsi que fonctionnent de nombreux générateurs d'électricité.

## en:project_263:p11:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 11 / 1

### Segment

Chapter 10: Exploring Electromagnets

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified: 'Chapter 10' is a compositional chapter heading and 'Exploring Electromagnets' is a straightforward verb-object phrase. Each part translates naturally as separate elements.

### Translation context

- **fr** (latest_translation_stage): Chapitre 10 : Explorer les électroaimants

## en:project_263:p11:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 11 / 2

### Segment

Electromagnets are temporary magnets created by electricity.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected: 'Temporary magnets' rejected as it is an ordinary compositional phrase. 'Created by electricity' rejected as a literal process description. 'Electromagnets' rejected despite translation as it is a single noun in English.

### Translation context

- **fr** (latest_translation_stage): Les électro-aimants sont des aimants temporaires créés par l'électricité.

## en:project_263:p11:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 11 / 3

### Segment

You can make one by wrapping wire around an iron nail and connecting the wire to a battery.

### Gold MWEs

- connecting to
- wrapping around

### Predicted MWEs

- 12 14
- 5 6

### Model analysis

Selected 'by wrapping wire' (tokens 5-6) as a phrasal verb for its fixed frame use with a gerund and 'connecting the wire' (tokens 12, 14) as a light-verb expression.

### Translation context

- **fr** (latest_translation_stage): Vous pouvez en fabriquer un en enroulant un fil autour d'un clou en fer et en connectant le fil à une batterie.

## en:project_263:p11:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 11 / 4

### Segment

Once the battery is connected, the nail acts like a magnet.

### Gold MWEs

None

### Predicted MWEs

- 8 9 10 11

### Model analysis

Selected 'acts like a magnet' as a fixed expression, indicating a conventional phrase describing functionality or behavior. Rejected others due to general composition or broader representations.

### Translation context

- **fr** (latest_translation_stage): Une fois la batterie connectée, le clou agit comme un aimant.

## en:project_263:p11:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 11 / 5

### Segment

Electromagnets are useful because you can turn them on or off.

### Gold MWEs

- turn on or off

### Predicted MWEs

- 6 10
- 6 8

### Model analysis

The phrase 'turn on' is selected as a phrasal verb, supported by translation into French as 'allumer'. The phrase 'turn off' is also selected as a phrasal verb based on translation as 'éteindre'.

### Translation context

- **fr** (latest_translation_stage): Les électro-aimants sont utiles parce que vous pouvez les allumer ou les éteindre.

## en:project_263:p11:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 11 / 6

### Segment

They are used in many places, like in cranes to lift heavy metal or in speakers to produce sound.

### Gold MWEs

None

### Predicted MWEs

- 2 3

### Model analysis

Annotated 'used in' as a phrasal_verb due to translation evidence indicating a conventionalized meaning despite the isolated rejection by translation_glossing for literal prepositional use.

### Translation context

- **fr** (latest_translation_stage): Ils sont utilisés dans de nombreux endroits, comme dans les grues pour soulever des métaux lourds ou dans les haut-parleurs pour produire du son.

## en:project_263:p12:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 12 / 1

### Segment

Chapter 11: Using Electricity Safely

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs were identified. Both 'Chapter 11' and 'Using Electricity Safely' are routine and compositional without strong idiomatic or lexicalized indications.

### Translation context

- **fr** (latest_translation_stage): Chapitre 11 : Utiliser l'électricité en toute sécurité

## en:project_263:p12:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 12 / 2

### Segment

Electricity is powerful, but we must use it safely.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs present. Both 'must use' and 'use it safely' are either rejected or compositional per available evidence.

### Translation context

- **fr** (latest_translation_stage): L'électricité est puissante, mais nous devons l'utiliser en toute sécurité.

## en:project_263:p12:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 12 / 3

### Segment

It can be dangerous if not handled properly.

### Gold MWEs

None

### Predicted MWEs

- 5 6

### Model analysis

Select 'not handled' as a fixed expression due to strong translation evidence. Reject 'be dangerous' as it is a compositional phrase, and 'if not handled properly' as an ordinary compositional conditional.

### Translation context

- **fr** (latest_translation_stage): Ça peut être dangereux si ce n'est pas manipulé correctement.

## en:project_263:p12:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 12 / 4

### Segment

Never touch wires with broken insulation or put objects in electrical outlets that aren't meant for them.

### Gold MWEs

None

### Predicted MWEs

- 13 14 15 16

### Model analysis

'aren't meant for them' is selected as an idiom due to non-literal interpretation in translation ('qui ne leur sont pas destinés').

### Translation context

- **fr** (latest_translation_stage): Ne touchez jamais les fils dont l'isolation est cassée et n'insérez pas d'objets dans les prises électriques qui ne leur sont pas destinés.

## en:project_263:p12:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 12 / 5

### Segment

Always respect warning signs, and remember that water and electricity don’t mix well.

### Gold MWEs

- warning signs

### Predicted MWEs

- 11 12 13

### Model analysis

Selected 'don’t mix well' (tokens 11, 12, 13) as a fixed expression, supported by idiomatic translation 'ne font pas bon ménage'. Rejected other candidates for being compositional or literal.

### Translation context

- **fr** (latest_translation_stage): Respectez toujours les panneaux d'avertissement, et souvenez-vous que l'eau et l'électricité ne font pas bon ménage.

## en:project_263:p12:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 12 / 6

### Segment

Water can conduct electricity, so keep electronics and cords dry, especially around pools or sinks.

### Gold MWEs

None

### Predicted MWEs

- 2 3

### Model analysis

Selected 'conduct electricity' as a fixed_expression due to common and stable use in English, supported by consistent French translation as a single conceptual unit.

### Translation context

- **fr** (latest_translation_stage): L'eau peut conduire l'électricité, alors gardez les appareils électroniques et les cordons au sec, en particulier autour des piscines ou des éviers.

## en:project_263:p13:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 13 / 1

### Segment

Chapter 12: Lightning – Nature’s Electric Show

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'Chapter 12:' and 'Lightning – Nature’s Electric Show' are not selected due to their compositional and literal structure in both source and translation contexts.

### Translation context

- **fr** (latest_translation_stage): Chapitre 12 : La foudre – Le spectacle électrique de la nature

## en:project_263:p13:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 13 / 2

### Segment

Lightning is a giant spark of electricity in the sky.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected. All considered phrases are either compositional or translated directly: 'giant spark', 'spark of electricity', and 'in the sky' do not meet criteria for MWEs.

### Translation context

- **fr** (latest_translation_stage): La foudre est une immense étincelle d'électricité dans le ciel.

## en:project_263:p13:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 13 / 3

### Segment

It happens during storms when electricity builds up in the clouds and needs to escape.

### Gold MWEs

- builds up
- needs to

### Predicted MWEs

- 6 7

### Model analysis

Selected the phrasal verb 'builds up' as it is translated as a single lexical item in French ('s'accumule'), indicating a non-literal, conventionalized expression. Other candidate expressions were rejected as they are compositional and literal.

### Translation context

- **fr** (latest_translation_stage): Cela se produit pendant les tempêtes lorsque l'électricité s'accumule dans les nuages et doit s'échapper.

## en:project_263:p13:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 13 / 4

### Segment

The electricity then jumps from the cloud to the ground, creating a flash of light.

### Gold MWEs

None

### Predicted MWEs

- 12 13 14 15

### Model analysis

Selected 'a flash of light' as a fixed_expression for sudden luminous phenomenon, consistently supported by lexicalization and translation glossing analyses. Rejected other proposed MWE candidates as routine or compositional expressions.

### Translation context

- **fr** (latest_translation_stage): L'électricité saute alors du nuage au sol, créant un éclair de lumière.

## en:project_263:p13:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 13 / 5

### Segment

The loud sound you hear after lightning is called thunder.

### Gold MWEs

- is called

### Predicted MWEs

None

### Model analysis

No MWEs detected as all candidate phrases were rejected due to being ordinary compositional structures lacking idiomatic or lexicalized meaning.

### Translation context

- **fr** (latest_translation_stage): Le bruit fort que vous entendez après un éclair s'appelle le tonnerre.

## en:project_263:p13:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 13 / 6

### Segment

Lightning heats the air so quickly that it creates a shock wave, which we hear as thunder.

### Gold MWEs

- shock wave

### Predicted MWEs

- 10 11

### Model analysis

Selected 'shock wave' (tokens 10, 11) as a lexicalized compound due to consistent agreement among analyses and conventional use. 'Hear as thunder' was rejected due to evidence of compositional translation in French, indicating no fixed expression.

### Translation context

- **fr** (latest_translation_stage): La foudre chauffe l'air si rapidement qu'elle crée une onde de choc, que nous entendons comme le tonnerre.

## en:project_263:p14:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 14 / 1

### Segment

Chapter 13: Static Electricity and Shocking Fun

### Gold MWEs

None

### Predicted MWEs

- 3 4
- 6 7

### Model analysis

Selected 'Static Electricity' due to its lexicalized and conventionalized term usage, especially in a scientific context. 'Shocking Fun' was selected based on translation evidence suggesting it is treated as a cohesive unit, despite disagreements in independent analyses.

### Translation context

- **fr** (latest_translation_stage): Chapitre 13 : Électricité statique et amusement électrisant

## en:project_263:p14:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 14 / 2

### Segment

Have you ever rubbed a balloon on your hair and seen it stick to a wall?

### Gold MWEs

- stick to

### Predicted MWEs

- 12 13
- 3 6

### Model analysis

Selected 'rubbed on' as a phrasal verb, supported by both source and translation analyses. Selected 'stick to' based on source analysis indicating it's a common phrasal verb; translation 's'accroche à' supports this interpretation.

### Translation context

- **fr** (latest_translation_stage): Avez-vous déjà frotté un ballon sur vos cheveux et vu qu'il s'accroche à un mur ?

## en:project_263:p14:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 14 / 3

### Segment

That’s static electricity.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWE detected. 'Static electricity' is a descriptive noun phrase that is not conventionalized, idiomatic, or a lexicalized compound requiring special treatment.

### Translation context

- **fr** (latest_translation_stage): C'est de l'électricité statique.

## en:project_263:p14:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 14 / 4

### Segment

It happens when electrons build up on a surface.

### Gold MWEs

- build up

### Predicted MWEs

- 4 5

### Model analysis

The segment contains a phrasal verb 'build up', confirmed by all three analyses as a verb-particle combination typically translated as a single lexical item ('s'accumulent' in French). Other phrases like 'happens when' and 'on a surface' are rejected due to their compositional, non-idiomatic nature, as reflected in the translation.

### Translation context

- **fr** (latest_translation_stage): Cela se produit lorsque des électrons s'accumulent sur une surface.

## en:project_263:p14:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 14 / 5

### Segment

When you touch someone after walking on a carpet, you might feel a tiny shock.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'Touch someone' is a routine verb-object combination; 'might feel' and 'feel a tiny shock' do not show strong enough idiomatic or fixed expression characteristics in context.

### Translation context

- **fr** (latest_translation_stage): Lorsque vous touchez quelqu'un après avoir marché sur un tapis, vous pourriez ressentir une petite décharge.

## en:project_263:p14:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 14 / 6

### Segment

This is static electricity moving from you to them, creating a quick spark.

### Gold MWEs

None

### Predicted MWEs

- 2 3

### Model analysis

Selected 'static electricity' as it is a conventionalized, lexicalized compound translated as a phrase in French. Rejected other expressions as they are compositional and literal.

### Translation context

- **fr** (latest_translation_stage): C'est de l'électricité statique qui passe de vous à eux, créant une étincelle rapide.

## en:project_263:p15:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 15 / 1

### Segment

Chapter 14: How Electricity Moves

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified: the segment contains a chapter title and a literal descriptive phrase, both translated compositionally.

### Translation context

- **fr** (latest_translation_stage): Chapitre 14 : Comment l'électricité se déplace

## en:project_263:p15:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 15 / 2

### Segment

Electricity doesn’t just stay in one place.

### Gold MWEs

None

### Predicted MWEs

- 4 5 6

### Model analysis

Selected 'in one place' as a fixed expression based on consistent translation as 'à un seul endroit' in French. No other MWEs identified.

### Translation context

- **fr** (latest_translation_stage): L'électricité ne reste pas simplement à un seul endroit.

## en:project_263:p15:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 15 / 3

### Segment

It moves through materials that allow it to pass easily, known as conductors.

### Gold MWEs

- known as

### Predicted MWEs

- 11 12 13

### Model analysis

Selected 'known as' (tokens 11, 12, 13) as a fixed expression based on multi-analysis agreement and its role in identification or definition. Reject the rest as ordinary compositional phrases or literal translations.

### Translation context

- **fr** (latest_translation_stage): Il se déplace à travers des matériaux qui lui permettent de passer facilement, connus sous le nom de conducteurs.

## en:project_263:p15:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 15 / 4

### Segment

Metals and water are good conductors.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWE selected. 'Good conductors' was rejected for lack of specific glossing value, despite common use. Other candidates were ordinary compositions or complete clauses.

### Translation context

- **fr** (latest_translation_stage): Les métaux et l'eau sont de bons conducteurs.

## en:project_263:p15:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 15 / 5

### Segment

Electricity flows in circuits.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified. All candidate expressions are compositional and literal, describing physical motion or spatial relationships without conventionalized, idiomatic, or lexicalized usage, and translate directly.

### Translation context

- **fr** (latest_translation_stage): L'électricité circule dans les circuits.

## en:project_263:p15:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 15 / 6

### Segment

In our homes, circuits are like loops running through walls, helping electricity to travel from the power plant to your light bulbs, TVs, and other gadgets.

### Gold MWEs

- light bulbs
- power plant

### Predicted MWEs

- 18 19

### Model analysis

The expression 'power plant' is a lexicalized compound noun referring to a specific industrial facility, thus selected as an MWE.

### Translation context

- **fr** (latest_translation_stage): Dans nos maisons, les circuits sont comme des boucles courant à travers les murs, aidant l'électricité à voyager de la centrale électrique jusqu'à vos ampoules, téléviseurs et autres appareils.

## en:project_263:p16:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 16 / 1

### Segment

Chapter 15: Renewable Energy Sources

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected. 'Chapter 15:' is a standard title structure, and 'Renewable Energy Sources' is identified as compositional across analyses.

### Translation context

- **fr** (latest_translation_stage): Chapitre 15 : Sources d'énergie renouvelable

## en:project_263:p16:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 16 / 2

### Segment

Did you know that the sun, wind, and water can be used to create electricity?

### Gold MWEs

None

### Predicted MWEs

- 12 13 14 15

### Model analysis

'can be used to create' is a light-verb expression as suggested by translation glossing evidence 'peuvent être utilisés pour créer'. No other MWEs selected due to compositional or literal meanings.

### Translation context

- **fr** (latest_translation_stage): Savais-tu que le soleil, le vent et l'eau peuvent être utilisés pour créer de l'électricité ?

## en:project_263:p16:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 16 / 3

### Segment

These are renewable energy sources because they won’t run out and are gentle on our planet.

### Gold MWEs

- run out

### Predicted MWEs

- 8 9

### Model analysis

The phrasal verb 'run out' is selected due to its conventionalized meaning and translation as a single unit in French. The phrase 'gentle on' was not selected due to conflicting analyses and less stability compared to 'run out'.

### Translation context

- **fr** (latest_translation_stage): Ce sont des sources d'énergie renouvelables car elles ne s'épuiseront pas et sont douces pour notre planète.

## en:project_263:p16:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 16 / 4

### Segment

Sunlight can be turned into electricity using solar panels.

### Gold MWEs

- solar panels
- turned into

### Predicted MWEs

- 3 4

### Model analysis

The phrasal verb 'turned into' (tokens 3-4) is selected as a multi-word expression for its conventional usage and idiomatic meaning as a transformation, with evidence from translation glossing.

### Translation context

- **fr** (latest_translation_stage): La lumière du soleil peut être transformée en électricité à l'aide de panneaux solaires.

## en:project_263:p16:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 16 / 5

### Segment

Wind turbines capture the wind and generate power.

### Gold MWEs

- Wind turbines

### Predicted MWEs

- 2 3 4

### Model analysis

'Capture the wind' is selected as a fixed expression. It is conventionally used in wind energy contexts to describe a specific process, supported by translation evidence where it's treated as a single unit.

### Translation context

- **fr** (latest_translation_stage): Les éoliennes capturent le vent et produisent de l'énergie.

## en:project_263:p16:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 16 / 6

### Segment

Dams use water to spin turbines, creating electricity without burning fuel.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs identified; all suggested candidate phrases are compositional or literal, with no conventionalized expressions.

### Translation context

- **fr** (latest_translation_stage): Les barrages utilisent l'eau pour faire tourner des turbines, créant de l'électricité sans brûler de carburant.

## en:project_263:p17:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 17 / 1

### Segment

Chapter 16: The Role of the Power Grid

### Gold MWEs

- Power Grid

### Predicted MWEs

None

### Model analysis

No MWEs identified. 'Chapter 16' is a routine title and numbering, 'The Role of the Power Grid' is a descriptive noun phrase.

### Translation context

- **fr** (latest_translation_stage): Chapitre 16 : Le rôle du réseau électrique

## en:project_263:p17:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 17 / 2

### Segment

Electricity from power plants travels over long distances to reach our homes.

### Gold MWEs

- power plants
- travels over

### Predicted MWEs

- 6 7 8

### Model analysis

Selected 'over long distances' as a fixed quantifier based on evidence of conventional collocation and translation as a unit.

### Translation context

- **fr** (latest_translation_stage): L'électricité des centrales électriques parcourt de longues distances pour atteindre nos maisons.

## en:project_263:p17:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 17 / 3

### Segment

It uses a network called the power grid.

### Gold MWEs

None

### Predicted MWEs

- 6 7

### Model analysis

Selected the expression 'power grid' as a lexicalized compound based on its conventionalized usage and translation evidence indicating it forms a stable phrase. Rejected all other candidates as compositional or not meeting MWE criteria.

### Translation context

- **fr** (latest_translation_stage): Il utilise un réseau appelé le réseau électrique.

## en:project_263:p17:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 17 / 4

### Segment

Imagine the grid as a giant spider web of wires covering cities and towns.

### Gold MWEs

- spider web

### Predicted MWEs

- 5 6 7

### Model analysis

'as' (token 3) as simile connective with conventionalized translation. 'giant spider web' (tokens 5, 6, 7) as metaphorical and lexicalized compound.

### Translation context

- **fr** (latest_translation_stage): Imaginez la grille comme une gigantesque toile d'araignée de fils couvrant les villes et les villages.

## en:project_263:p17:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 17 / 5

### Segment

This grid is carefully managed to make sure everyone gets the right amount of electricity, even when lots of people are using it at once, like during summer when air conditioners are on.

### Gold MWEs

- air conditioners
- at once
- lots of
- make sure

### Predicted MWEs

- 24 25
- 6 7

### Model analysis

Selected 'make sure' (tokens 6, 7) as a fixed expression for its conventionalized meaning. Selected 'at once' (tokens 24, 25) as a fixed adverbial expressing simultaneity. Rejected other candidates as compositional or descriptive.

### Translation context

- **fr** (latest_translation_stage): Cette grille est soigneusement gérée pour s'assurer que tout le monde reçoit la bonne quantité d'électricité, même lorsque beaucoup de personnes l'utilisent en même temps, comme en été lorsque les climatiseurs sont allumés.

## en:project_263:p18:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 18 / 1

### Segment

Chapter 17: Electric Vehicles and the Future

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No multi-word expressions identified. All components are ordinary descriptive phrases or standard titles.

### Translation context

- **fr** (latest_translation_stage): Chapitre 17 : Véhicules électriques et l'avenir

## en:project_263:p18:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 18 / 2

### Segment

Electric vehicles (EVs) are cars that run on electricity instead of gasoline.

### Gold MWEs

- instead of
- run on

### Predicted MWEs

- 11 12
- 8 9

### Model analysis

Selected 'run on' (tokens 8, 9) as a phrasal verb, a verb-particle construction requiring non-compositional interpretation. Also selected 'instead of' (tokens 11, 12) as a fixed expression, commonly translated as a single unit.

### Translation context

- **fr** (latest_translation_stage): Les véhicules électriques (VE) sont des voitures qui fonctionnent à l'électricité au lieu de l'essence.

## en:project_263:p18:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 18 / 3

### Segment

They have batteries that store energy to power an electric motor, making them quieter and cleaner for our planet.

### Gold MWEs

None

### Predicted MWEs

- 12 13 14 15 16
- 7 8 9 10

### Model analysis

Selected 'to power an electric motor' as a phrasal verb based on translation glossing supporting phrasehood (alimenter un moteur électrique). Selected 'making them quieter and cleaner' as a fixed_expression due to conventionalized cause-effect glossing pattern (les rendant plus silencieux et plus propres).

### Translation context

- **fr** (latest_translation_stage): Ils ont des batteries qui stockent de l'énergie pour alimenter un moteur électrique, les rendant plus silencieux et plus propres pour notre planète.

## en:project_263:p18:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 18 / 4

### Segment

As technology improves, more people are using EVs.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs detected: 'As technology improves' is a literal temporal phrase, 'more people' is a standard comparative expression, and 'using EVs' is a routine verb-object combination.

### Translation context

- **fr** (latest_translation_stage): À mesure que la technologie s'améliore, de plus en plus de personnes utilisent des véhicules électriques.

## en:project_263:p18:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 18 / 5

### Segment

They reduce pollution and help keep the air clean.

### Gold MWEs

None

### Predicted MWEs

- 4 5

### Model analysis

The light verb expression 'help keep' (tokens 4-5) is finalized based on source-token evidence and translation glossing support. Other suggested candidates do not meet MWE criteria.

### Translation context

- **fr** (latest_translation_stage): Ils réduisent la pollution et aident à garder l'air propre.

## en:project_263:p18:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 18 / 6

### Segment

Charging stations are popping up in more places to make it easier to keep them running.

### Gold MWEs

- Charging stations
- popping up

### Predicted MWEs

- 3 4

### Model analysis

Selected 'popping up' as a phrasal verb due to its idiomatic meaning. It is translated as a single French verb 'apparaissent', indicating it functions as a lexical unit. Rejected other candidates as they are more compositional or well-translated compositionally.

### Translation context

- **fr** (latest_translation_stage): Les stations de recharge apparaissent dans davantage d'endroits pour faciliter leur fonctionnement continu.

## en:project_263:p19:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 19 / 1

### Segment

Chapter 18: Smart Homes and Energy Efficiency

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected: 'Smart Homes' and 'Energy Efficiency' are compositional noun phrases that translate directly without requiring phrase-level glossing or exhibiting fixed, idiomatic, or conventionalized behavior.

### Translation context

- **fr** (latest_translation_stage): Chapitre 18 : Maisons intelligentes et efficacité énergétique

## en:project_263:p19:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 19 / 2

### Segment

Smart homes use advanced technology to help save energy and make life easier.

### Gold MWEs

None

### Predicted MWEs

- 10 11 12
- 6 7 8

### Model analysis

Selected 'help save energy' as a light verb expression due to semantic dependency between 'help' and 'save'. 'Make life easier' is selected as a formulaic expression often used in contexts of improvement.

### Translation context

- **fr** (latest_translation_stage): Les maisons intelligentes utilisent une technologie avancée pour aider à économiser l'énergie et rendre la vie plus facile.

## en:project_263:p19:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 19 / 3

### Segment

They have gadgets that can be controlled remotely, like smart thermostats that learn your schedule to heat or cool your home efficiently.

### Gold MWEs

None

### Predicted MWEs

- 6 7

### Model analysis

The expression 'controlled remotely' (tokens 6, 7) forms a phrasal verb that is glossed as a unit in translation. The other candidates were rejected due to compositionality or lack of special glossing requirements.

### Translation context

- **fr** (latest_translation_stage): Ils ont des gadgets qui peuvent être contrôlés à distance, comme des thermostats intelligents qui apprennent votre emploi du temps pour chauffer ou refroidir votre maison efficacement.

## en:project_263:p19:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 19 / 4

### Segment

These homes also use energy-saving lights and appliances that reduce electricity use, which is good for both the environment and your electricity bill!

### Gold MWEs

None

### Predicted MWEs

- 16 17 18
- 4 5

### Model analysis

Selected 'energy-saving lights' as a compound due to frequent lexicalization and translation as a single adjective. Selected 'for both the' as a connective, evidenced by translation as 'à la fois pour' and its fixed usage introducing a list.

### Translation context

- **fr** (latest_translation_stage): Ces maisons utilisent également des ampoules et des appareils économes en énergie qui réduisent la consommation d'électricité, ce qui est bénéfique à la fois pour l'environnement et pour votre facture d'électricité !

## en:project_263:p20:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 20 / 1

### Segment

Chapter 19: Solar Power at Home

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected. Both 'Solar Power' (tokens 3, 4) and 'at Home' (tokens 5, 6) are rejected as ordinary compositional expressions without evidence of conventionalized or idiomatic usage.

### Translation context

- **fr** (latest_translation_stage): Chapitre 19 : L'énergie solaire à la maison

## en:project_263:p20:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 20 / 2

### Segment

More people are using solar panels on their roofs.

### Gold MWEs

- solar panels

### Predicted MWEs

- 4 5

### Model analysis

Selected 'solar panels' as a lexicalized compound supported by translation as 'panneaux solaires'. Rejected 'on their roofs' as a compositional location description and 'More people' as an ordinary noun phrase.

### Translation context

- **fr** (latest_translation_stage): De plus en plus de personnes utilisent des panneaux solaires sur leur toit.

## en:project_263:p20:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 20 / 3

### Segment

These panels capture sunlight and turn it into electricity.

### Gold MWEs

- turn into

### Predicted MWEs

- 5 6 7

### Model analysis

Selected 'turn it into' (tokens 5-7) as a phrasal verb indicating transformation, supported by translation as 'la transforment en', reflecting a conventional verb-particle construction.

### Translation context

- **fr** (latest_translation_stage): Ces panneaux captent la lumière du soleil et la transforment en électricité.

## en:project_263:p20:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 20 / 4

### Segment

It’s a clean way to power your home and can even save money.

### Gold MWEs

None

### Predicted MWEs

- 11 12

### Model analysis

Selected 'save money' as a fixed expression due to conventional usage and financial advisory context. Other candidates rejected due to compositionality or lack of strong evidence for non-compositionality.

### Translation context

- **fr** (latest_translation_stage): C'est un moyen propre d'alimenter votre maison et cela peut même vous faire économiser de l'argent.

## en:project_263:p20:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 20 / 5

### Segment

If a house makes more electricity than it uses, sometimes the extra can be sent back to the power grid, helping others get clean energy.

### Gold MWEs

- power grid
- sent back

### Predicted MWEs

- 15 16

### Model analysis

Selected 'sent back' as a phrasal verb based on translation and source evidence, reflecting conventionalized usage. Rejected other candidates: 'power grid' as a descriptive noun phrase and 'get clean energy' due to compositional nature.

### Translation context

- **fr** (latest_translation_stage): Si une maison produit plus d'électricité qu'elle n'en utilise, parfois l'excédent peut être renvoyé au réseau électrique, aidant ainsi les autres à obtenir de l'énergie propre.

## en:project_263:p21:s1

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 21 / 1

### Segment

Chapter 20: The Impact of Electricity on Our World

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs selected. 'The Impact of Electricity' is not chosen due to conflicting opinions and compositional translation evidence. Other candidates are rejected as ordinary compositional phrases or titles.

### Translation context

- **fr** (latest_translation_stage): Chapitre 20 : L'Impact de l'électricité sur notre monde

## en:project_263:p21:s2

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 21 / 2

### Segment

Electricity has changed the world.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No multi-word expressions identified. All candidates were rejected as they consist of single tokens or ordinary compositional phrases.

### Translation context

- **fr** (latest_translation_stage): L'électricité a changé le monde.

## en:project_263:p21:s3

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 21 / 3

### Segment

It powers our homes, schools, and hospitals.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs were identified in the segment. All phrases were rejected due to their compositional nature and direct translations in the context.

### Translation context

- **fr** (latest_translation_stage): Elle alimente nos maisons, nos écoles et nos hôpitaux.

## en:project_263:p21:s4

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 21 / 4

### Segment

It helps us communicate, learn, and play.

### Gold MWEs

None

### Predicted MWEs

None

### Model analysis

No MWEs were identified. All token sequences are compositional or routine expressions.

### Translation context

- **fr** (latest_translation_stage): Ça nous aide à communiquer, apprendre et jouer.

## en:project_263:p21:s5

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 21 / 5

### Segment

Thanks to electricity, we have lights at night, computers for learning, and many gadgets for fun.

### Gold MWEs

- at night
- Thanks to

### Predicted MWEs

- 0 1

### Model analysis

"Thanks to" is a fixed expression with translation evidence supporting its selection. No other MWEs were identified in the segment.

### Translation context

- **fr** (latest_translation_stage): Grâce à l'électricité, nous avons des lumières la nuit, des ordinateurs pour apprendre et de nombreux gadgets pour nous amuser.

## en:project_263:p21:s6

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 21 / 6

### Segment

Without it, many things we take for granted would not exist.

### Gold MWEs

- take for granted

### Predicted MWEs

- 6 7 8

### Model analysis

'take for granted' is selected as an idiomatic expression, supported by all analyses and the translation indicating it as a single unit.

### Translation context

- **fr** (latest_translation_stage): Sans cela, de nombreuses choses que nous tenons pour acquises n'existeraient pas.

## en:project_263:p21:s7

- Project: 263 — Understanding Electricity: From Basics to Future Innovations
- Page/segment: 21 / 7

### Segment

It's important to use it wisely and care for our planet as we enjoy its benefits.

### Gold MWEs

- care for

### Predicted MWEs

- 8 9

### Model analysis

'care for' is selected as a phrasal_verb due to its non-literal translation and lexicalization in source_conservative and translation_glossing analyses.

### Translation context

- **fr** (latest_translation_stage): Il est important de l'utiliser judicieusement et de prendre soin de notre planète tout en profitant de ses bienfaits.

