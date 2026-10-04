I have just been trying it out on the laptop. I could successfully convert the small Swedish/English dictionary to French/English, nearly everything works! But still some issues left to fix:



1. The "category" tags are not being translated when they are in the text language. E.g. here I had assigned the Swedish word "katt" to the category "djur", and after the conversion it is still "djur". I'm thinking this should be done intelligently, using AI calls. So a) we determine whether the category tags are in the text language or the commenting language, b) if they are in the commenting language, we leave them unchanged, c) if they are in the text language, use AI to translate them, looking at examples of words classified by the category, d) replace in the converted version.
2. The TTS generation needs to be advised about the text language (this may in general be needed for TTS generation). E.g. here, when we convert "katt" to "chat", it is pronounced as though it were the English word with that orthography.
3. The current procedure is over-editorialising. Here, as a joke in dubious taste, I had illustrated the Swedish word "kung" with an image of Donald Trump, but the conversion procedure said it did not look like an image matching "kung". This is arguably correct, but I should have been able to override and either choose the best AI-generated French translation matching the Swedish "kung" and the English "king" (the guess "roi" would presumably be presented), or else fill in the French myself.



What do you think?
