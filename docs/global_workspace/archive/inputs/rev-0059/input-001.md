Everything installs fine on AWS. I could convert the 150 entry Swedish/English dictionary to French/English.



However, when I open it, I see that we're not yet handling words correctly. It looks like conversion is translating each word entry separately, then inserting links to the translated words in the entry for the translated sentences. But this sometimes creates inconsistencies. E.g. we have this sentence:



Un bijou brillant en forme de lapin repose sur du tissu.



But the word links do not contain a link for "reposer", but rather one for "être couché ; se trouver", which has clearly been translated from Swedish "ligger på".



So I think conversion instead needs to translate just the sentences, then create the word pages and word links from the translated sentences, calling the code that does this for adding a new sentence entry.



Does that look right to you?

#
