The word estimates are still too high when I convert Swedish to German on AWS:



1\. Translate and review sentences\
Swedish → German · explanations: English → English\
\
Estimate before starting\
150 entries (150 sentences) · 0 unchanged or ineligible · 0 protected because the destination was edited.\
\
Rough API estimate: US$3.4748\
\
Credit needed to start: US$17.5125 (refundable allowance). No credit has been reserved for this estimate.\
\
Processing complete\
150 entries (150 sentences) · 0 unchanged or ineligible · 0 protected because the destination was edited.\
\
Rough API estimate: US$3.4748\
\
Credit still held for this job: US$0.0000. Original reservation: US$17.5125.\
\
2\. Review vocabulary from accepted sentences\
Estimate before starting\
150 entries (150 sentences) · 0 unchanged or ineligible · 0 protected because the destination was edited.\
\
Rough API estimate: US$9.9151\
\
Credit needed to start: US$130.3750 (refundable allowance). No credit has been reserved for this estimate.\
\
150 entries (150 sentences) · 0 unchanged or ineligible · 0 protected because the destination was edited.\
\
Rough API estimate: US$9.9151\
\
Credit held for this job: US$130.3750.\


I also tried converting Swedish to Italian, Icelandic and Japanese. The estimates were similar, and there were some other issues:



1. For Italian, two audio files failed to generate on the first run. I could recover from this in the end, but it was messy.
2. Again for Italian, I found that one sentence had in fact been translated into French in the 'sentences' part. Maybe we need an AI check that the ported sentence is in the right language? I would expect this to be cheap.
3. For Japanese, the Words phase fails completely. Every entry produces something like this: "Entry 3883 · failed

   No usable vocabulary was returned. A new estimate is required to try again."  We probably need special processing for CJK languages? In C-LARA-2, we use Jieba for Chinese, but as far as I can recall nothing yet for Japanese or Korean.



Your thoughts?
