It looks like things are already working. I think the simple architecture we arrived at was a good choice. Here's an example I just ran on the laptop. My query was:

What are the tasks you know of that are most relevant to Sophie's Indigenous community work?

and after 36 seconds received the very plausible answer:

Most relevant tasks, based on current canonical records, are:

1. `ISSUE-0026` community-recorded audio workflow MVP before **August 24, 2026** if possible ([docs/issues/issues/ISSUE-0026.json](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/issues/issues/ISSUE-0026.json)).
2. `ISSUE-0029` autosave for community judging inputs, also targeted before **August 24, 2026** as likely lower-effort ([docs/issues/issues/ISSUE-0029.json](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/issues/issues/ISSUE-0029.json)).
3. Focused pre-visit verification/closure of picture-dictionary workflows in `ISSUE-0037` and `ISSUE-0039` ([docs/issues/issues/ISSUE-0037.json](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/issues/issues/ISSUE-0037.json), [docs/issues/issues/ISSUE-0039.json](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/issues/issues/ISSUE-0039.json)).
4. `ISSUE-0045` lightweight mobile browsing + exercises slice for **mid-September 2026** (not realistic for August 24), with ComputEL-10 relevance ([docs/issues/issues/ISSUE-0045.json](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/issues/issues/ISSUE-0045.json)).
5. Scope-definition follow-up with Sophie (`REQ-0007`/`ACT-0003`) to lock exact acceptance criteria for mobile/audio/exercises and confirm the ComputEL deadline ([docs/global_workspace/current_state.json](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/global_workspace/current_state.json)).

Direct human observation (authoritative input):

- Manny reports Sophie is very keen on the ComputEL-10 paper and wants early usable audio; mid-September mobile could still help paper inclusion ([docs/global_workspace/project-intentions.md](https://github.com/mannyrayner/C-LARA-2/blob/main/docs/global_workspace/project-intentions.md)).

Second-hand report:

- “Sophie says picture-dictionary workflow looks good” is relayed by Manny, not directly observed by the project-manager agent.

Project-manager inference:

- The highest Indigenous-community urgency is the pre-visit trio: recorded audio + judging autosave + verification of picture-dictionary flows, while mobile is the next-phase target.

Key uncertainty needing human confirmation:

- Exact ComputEL-10 submission date and minimum required deliverables for submission are still unconfirmed.

Before we deploy this on the server, however, I think we want a control in the Admin tab that allows an Admin to toggle another user's access privileges for the Project Manager. By default they will be off. If the Project Manager is not accessible, the relevant option will not be shown, or be shown greyed out with a label saying to ask an admin for access rights if you think you need it.

What do you think?
