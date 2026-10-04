All deployed and working on the server, this is great!



Could you implement a first cut at the language-porting functionality? A couple more suggestions about that:



1. Given that dictionaries may soon be quite large, it could be good to think ahead and implement this with fan-out/fan-in so that the entries are ported concurrently.
2. I think it is also responsible to present a rough estimate of how much the porting will cost before starting, and ask the user for approval. Also tell them if it looks like they don't have funds in their account to cover it.



What do you think?
