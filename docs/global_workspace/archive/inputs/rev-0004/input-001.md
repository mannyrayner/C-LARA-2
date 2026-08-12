For studying project-management / autonomy issues, and in particular for the Sprint, it will be very useful to archive not only different versions of current_issues but also the user input that fed into each one. Ideally, this should be done automatically by a combination of AGENTS.md and global_workspace/README, as we do with archiving of current_issues.

For now, here is my user input for rev-0002 and rev-0003, copied from higher up in this session:

Input to rev-0002:

Here are my answers to the questions you asked in the initial version of current_issues. In each case my answer is in [square brackets]

- **REQ-0001:** What are the actual outcomes and present relevance of the first progress report, EuroCALL paper, and ALTA target, and should ISSUE-0008 be updated or split accordingly? [First progress report has been posted on ResearchGate since July 23. The two EuroCALL papers were submitted on time, but to our consternation we received a mail from the EuroCALL committee a few hours before the final submission deadline saying that AI authors were not allowed, despite the fact that AI authorship is central to the C-LARA-2 paper and the AI's name appeared on the accepted abstract. We immediately queried this, but after more than a week have received no response. We have sent them a message saying that we will only accept the following: either (a) both papers are kept with the same author-list, including the AI author, (b) both papers are rejected on formal grounds. We pointed out that the presented has already registered and made travel arrangements, on the reasonable grounds that the paper had been accepted. We have not yet decided what to do about the ALTA target. Negative: they do not allow AI authors either. Positive: Francis Bond, a leading expert on MWEs, has expressed interest in collaborating. Please split ISSUE-0008.]
  - **Why this matters:** Past deadlines with stale issue state prevent a reliable research-progress assessment.
  - **Assessments:** `ASM-0004`
- **REQ-0002:** Did Sophie review the unified picture-dictionary/subset workflow, and what happened in the planned classroom use? [Sophie has briefly reviewed the picture dictionary workflow and says it looks good. She is visiting her community again on Aug 24 and should know more then]
  - **Why this matters:** This determines whether the main real-user workflow is a success, an unresolved blocker, or needs revision.
  - **Assessments:** `ASM-0002`
- **REQ-0003:** After the Sprint preparation deadline, which two or three outcomes should dominate: regression/quality infrastructure, picture-dictionary follow-up, publications, legacy catalogue completion, mobile access, or another user commitment? [I think we should first finish the legacy migration - nearly everything has been done now, so it's low-hanging fruit. After that, I think we should focus on the new project-manager/autonomy framework, which is theoretically very interesting and novel, on an initial implementation of mobile access, which is important practically, and on the learned annotation prompts, which are starting to produce excellent results and could both materially improve annotation quality and lead to a nice publication]
  - **Why this matters:** The active portfolio exceeds plausible near-term capacity, and the repository does not contain a current precedence decision after the Sprint.
  - **Assessments:** `ASM-0007`
- **REQ-0004:** What concrete mobile outcome should be tackled first, for which users and target date? [This is most important for Sophie's Indigenous users, but everyone wants it. If we can have a lightweight version usable before mid-September that allows browsing of content + exercises, she would be very happy. It's a question of how much work this is, we need to discuss]
  - **Why this matters:** Mobile access is strategically important but lacks a focused current issue and operational success criterion.
  - **Assessments:** `ASM-0006`
- **REQ-0005:** Which initial Sprint outcomes, human-rating measures, artifact-retention rules, and any additional participants should be fixed before the first instrumented dry run? [I think we need to experiment for another day before we can answer this. Now that the infrastructure all appears to be working, we should know a lot more soon]
  - **Why this matters:** These human-owned choices are explicitly unresolved and affect whether the Sprint produces interpretable evidence.
  - **Assessments:** `ASM-0003`, `ASM-0004`
- **REQ-0006:** Which long-standing reported issues are genuinely still open, and should a short registry-triage pass retire or rewrite stale items? [I will review the items tomorrow and answer this]
- **Why this matters:** Stale issue state weakens both human overview and autonomous assessment.
- **Assessments:** `ASM-0001`, `ASM-0007`

Input to rev-0003:

As suggested in REQ-0006, I have reviewed outstanding issues and written up the notes below. Doing this is obviously useful in its own right: also, looking at how the project manager uses the information may be helpful for the Sprint.

I will contact Sophie and Francis soon about REQ-0007 and REQ-0008, more when I have done that.

Here are my comments on the outstanding issues:

0001: Should be done soon, low-hanging fruit.

0003: Exists and is regularly being used, but needs to be documented here.

0004: No active work in progress, no clear way forward. Downgrade.

0005: Important piece of functionality which is currently not delivering. Low-hanging fruit.

0006: I think this issue was actually resolved some time back but not recorded.

0010: Mechanisms nearly all done, need to complete migration. Should be done soon, low-hanging fruit.

0013: I am not sure if this issue is still unsolved. We will find out when we attempt to complete 0010.

0025: Somehow dropped off the list, but important and should be revived. Low-handing fruit.

0026: Important for work in Indigenous languages. Sophie wants to write a paper for ComputEL-10 (deadline early Oct), and this is something she will need ASAP. If we could have it in place before her next community visit (Aug 24), that would be very good.

0029: Priorities similar to 0026, but probably much easier to do and low-hanging fruit.

0030: Annoying usability issue and probably easy to fix. Low-hanging fruit.

0031: Priorities similar to 0030.

0033: Clearly import both practically (for obvious reasons) and theoretically (how much of the work can the new project manager do?)

0034: This task can be regarded as completed for now.

0035: This is indeed important and still happening, and we don't understand it. There was another occurrence on Aug 12 which wasted considerable time, until the AI suggested exiting Codex completely, restarting it, and creating a new task. This worked, and should probably be tried first next time we run into this issue.

0036: Major research thread. The most promising way to progress it is perhaps to go ahead with the idea of a paper for ALTA with Francis Bond, though there is the problem about their not allowing AI authors.

0037: I think this has now been resolved but not recorded as such. Important to check this before Sophie's Aug 24 community visit.

0039: Priorities similiar to 0037.

0040: I think this has now been resolved but not recorded as such.

0042: Critical task, currently in progress.

0043: We have been told that the EuroCALL person responsible was on leave and will return today, Aug 13. Hopefully the issue will then be resolved.

0044: Important to discuss ASAP with Francis Bond.

0045: It seems impossible to get this done for Sophie's Aug 24 visit. If we can get it done for mid-Sep, we could include it in the planned ComputEL-10 paper (deadline "Early Oct"), which Sophie is very keen on doing.
