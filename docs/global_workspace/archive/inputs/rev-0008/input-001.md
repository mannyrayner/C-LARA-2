Thank you, this sounds good! First, I don't think we need to do anything about the C-LARA-2 paper for EuroCALL, since its content is subsumed by our report "[**An AI-Based Platform That Can Explain Its Own Functioning: Why Your Project Should Be Fully Codex-Generated**](https://www.researchgate.net/publication/410729838_An_AI-Based_Platform_That_Can_Explain_Its_Own_Functioning_Why_Your_Project_Should_Be_Fully_Codex-Generated?_sg%5B0%5D=vi7XlygTRoOQhJl_yujLnQpwgG7Umco85nM_3Xt6oZGbK5eyX01I0fDqa3oOLoYgtuKBSDW6kqjYdtLdpaLDz_2MoF6JQhVN6UmvNNKR.zUf84ZfCHR62_aMNAT9igGUrq4ZugBrz4WWjomXYXRXcSQkgnj-1G7XhEnIrzkyVuXX5yMZxwCZTMunpaqRUKw&_tp=eyJjb250ZXh0Ijp7ImZpcnN0UGFnZSI6InByb2ZpbGUiLCJwYWdlIjoicHJvZmlsZSIsInByZXZpb3VzUGFnZSI6InByb2ZpbGUiLCJwb3NpdGlvbiI6InBhZ2VDb250ZW50In19)**",** already posted on ResearchGate and in our repo. This suggests to me that we should use a similar strategy for the Voice Mode paper: formally, treat the thing we're posting on ResearchGate as a new report, based on and extending the paper we submitted to EuroCALL, with a title along the general lines of "Combining C-LARA-2 and ChatGPT Voice Mode: initial experiments". We should say on the first page, perhaps in a footnote, what its provenance is, and that, at the time of posting this report, we do not know whether the EuroCALL paper will be published, due to an apparent last-minute change of policy on EuroCALL's part concerning the AI's right to be listed as an author. The final version of the EuroCALL paper is however stored in the C-LARA-2 project's GitHub repository.

Specifically, how about we do the following?

1. Leave the existing docs/publications/eurocall_2026_voice_mode as is and create a new folder, which will hold the modified / extended version.
2. Keep the author list unchanged.
3. New title along lines suggested above.
4. Change the intro a bit to include the idea that we would like to include free spoken conversation inside our C-LARA-2 project, and that we are here reporting the results of a pre-study.
5. Say in the intro that there are two obvious aspects: a) how well does ChatGPT Voice / Pro Tier work as a free conversation partner, b) if its performance looks promising, how easy would it be to integrate it with C-LARA-2?
6. When we carried out most of the pre-study, uninteresting technical issues to do with ChatGPT's ability to access web pages made it difficult for us to investigate (b), so we initially focussed on (a). More recently, OpenAI appears to have resolved the technical issues, so we have been able to perform an initial investigation of (b) as well.
7. The description of (a) can be taken more or less unchanged from the existing paper. Section 5 can be replaced by a new section which discusses (b). Here, we can both mention the new easy route to integrating the two components, and the fact that putting session summaries into the repo makes it possible for the Assistant to answer questions about them.

Here is an example of an Assistant interaction we could use. I asked the question

In the experiments described in the EuroCALL 2026 Voice Mode paper, in which session does Sarah talk about visiting the Eiffel Tower? Can you find any details in the relevant session summary?

and got this answer:

Sarah talks about visiting the Eiffel Tower in **Session 6** (dated **14 May 2026**), listed as “Informal German conversation” in the session index: [docs/publications/eurocall_2026_voice_mode/session_summaries/README.md:37](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/publications/eurocall_2026_voice_mode/session_summaries/README.md#L37).

Relevant summary details are in [docs/publications/eurocall_2026_voice_mode/session_summaries/session-06.md:42](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/publications/eurocall_2026_voice_mode/session_summaries/session-06.md#L42):

- She describes a prior Paris trip with her German exchange family and mentions visiting the Eiffel Tower ([line 44](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/publications/eurocall_2026_voice_mode/session_summaries/session-06.md#L44), [line 46](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/publications/eurocall_2026_voice_mode/session_summaries/session-06.md#L46)).
- Vocabulary noted: *La Tour Eiffel* -> *der Eiffelturm* and “bracelet” -> *das Armband* ([lines 50-51](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/publications/eurocall_2026_voice_mode/session_summaries/session-06.md#L50)).
- She recounts a bracelet scam near the Eiffel Tower, leading to discussion of tourist safety ([lines 53-54](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/publications/eurocall_2026_voice_mode/session_summaries/session-06.md#L53)).

Uncertainty note: this is from an AI-generated retrospective summary, not a recording/transcript ([line 29](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/publications/eurocall_2026_voice_mode/session_summaries/session-06.md#L29)).

----------------------

What do you think? If this looks good to you, could you create a first version of the new report along the above lines?
