I think we have more or less converged! So implement it as follows:

1. For words that are English homographs, use an AI API call to create enriched prompts like the ones you created here.
2. Test for silence/near-silence, and if so regenerate.
3. Flag all English homographs for review.

If you add that functionality, I can first test on the laptop with the small dictionary, then we can install on AWS and I will also try the larger one in French and Italian.

What do you think?
