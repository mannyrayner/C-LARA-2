# Guided pictures and language level — 30 October 2026

Manny reports one successful example with the writing-practice release on the
laptop and requests more testing before inviting the learner. Private control
run 41044395387 reports successful laptop installation under control commit
7f41609f8ee1fdcc2b515ee774aa9c58d4ffe16a, whose release request specifies app
863e401bf1dec9dfb59f730976f56fb88699ff96. This is early functional evidence,
not a classroom evaluation or an AWS acceptance of writing practice.

The next concrete beginner request motivates a simpler personal workflow:
picture -> explanation-language meaning -> approval -> automatic target-language
sentence, vocabulary and audio. The first call only proposes meaning; later
processing uses the existing capture publisher and bounded queue. A manual change
of focus is possible in the explanation language, and clarification is explicit.
The approved explanation text is preserved exactly. No target-language review is
claimed merely because a beginner approved that meaning.

Personal modes now persist per member/dictionary, independently of owner policy.
Guided mode requires standing permission with a displayed estimate; old/manual
workflows remain the default for this first trial. New dictionary creation and
owner Settings offer Beginner, Low intermediate, Higher intermediate and Advanced.
Prompt guidance preserves the specific visible subject/action and simplifies
surrounding language. Existing content and approved learner writing stay intact.
New individual and batch generations freeze the chosen level; copies inherit it.

## Validation

- 47 focused guided/writing/settings tests passed, then the full 767-test
  Community Dictionaries suite passed in 200.416 seconds.
- A final 19-test guided suite passed after adding translated-interface and
  switched-mode recovery coverage. French and Slovak catalogs compile cleanly.
- Four manual-preparation/recovery tests passed. A real disposable SQLite database
  upgraded from migration 0025 to 0026, produced a verified backup, preserved an
  existing dictionary/user, and allowed an idempotent second preparation.
- Django system and migration drift checks passed; whitespace checks passed.
- Providers are mocked. No paid OpenAI requests, production content changes or
  physical-phone acceptance occurred in this implementation session. There is no
  live PostgreSQL preparation result yet.

The additive migration creates two new preference tables. A separately reviewed,
manually invoked preparation helper reuses the installed controller's gate,
drain, identities and restart/recovery. It does not relax Actions/SSM code-only
restrictions. Preparation commit: 8ee6024719b73de9f702ce4dad2848ffee88a4a7.
The feature is a subsequent code-only commit. See the
[runbook](../../docs/howto/community-learning-deployment.md).

Next evidence: laptop acceptance of the combined modes, then approved AWS
preparation/deployment and a physical-phone trial with beginner-oriented content.
In particular, check that less-common but central subjects are named faithfully
rather than simplified away, and collect real learner feedback on the number of
steps and the usefulness/difficulty of the resulting sentences.
