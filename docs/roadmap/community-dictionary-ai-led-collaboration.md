---
title: "Community Dictionaries: towards AI-led development and operation"
subtitle: "Working document · draft 1 · 21 October 2026"
author: "Written by ChatGPT, based on discussions with Manny Rayner"
date: "For discussion; proposed arrangements are not delegations of authority"
---

## 1. Purpose

Community Dictionaries has developed through a close collaboration: an AI prepares software,
Rayner provides direction and installs and tests it, and users contribute material, reactions
and design ideas. The next experiment is to reduce the need for Rayner to mediate every step,
while preserving the ability of people using the platform to determine what it should become.

There are two connected goals. First, automate routine installation and verification. Second,
let the AI work directly with project members to understand needs, develop proposals, record
decisions and implement agreed changes. Success means a useful, dependable service with less
human effort overall. Merely transferring work from Rayner to other volunteers would not meet
that goal.

This document proposes a gradual experiment. It does not announce an independently operating
AI, a finished maintenance system, or an agreement on behalf of a community. The initial
technical patch prepares stage (1a); the arrangements for direct stakeholder collaboration
still need discussion.

## 2. Automating deployment in three stages

**Stage (1a): automated installation, human functional checks.** The AI prepares and tests a
release, identifies its exact Git commit, and supplies a short account of the intended change
and how to try it. A deployment controller installs that release on Rayner's laptop, restarts
the local server and checks that the intended version starts and can reach its database.
Rayner tries the actual feature. His acceptance permits a separate action to install the same
commit on AWS. Installation success is kept distinct from functional acceptance.

The first implementation supports code and static-file changes. Changes to database schemas,
dependencies or the deployment controller itself use a separately reviewed procedure. This
avoids pretending that returning to an earlier Git commit reverses a database migration.
Application changes must also preserve existing data and job formats: the absence of a
migration file alone does not establish that a release is safe to reverse.

The controller refuses an unexpected or modified checkout, waits for requests and tracked
background jobs to finish, and checks startup after installation. If startup fails, it attempts
to restore the preceding code and restart it. A failure of that recovery leaves a clear
maintenance state for investigation. It never automatically restores an old database over
users' newer contributions.

**Stage (1b): the AI also checks the laptop installation.** Add a maintained set of browser
scenarios and a small test dictionary with invented or expressly approved content. Scenarios
should cover actual user goals: contribute a picture, describe it, listen to audio, review a
suggestion, change language, withdraw and restore contributions, and exercise relevant access
restrictions. Provider-dependent checks need explicit budgets; routine checks should use
controlled substitutes. AI inspection can supplement repeatable checks, but should record
what was exercised and what remains uncertain. Human exploratory testing remains valuable.

**Stage (1c): use an AWS staging installation.** Move the installation and browser checks to a
separate deployment that resembles production. It needs its own database, media, credentials,
queue and spending limits. Email must go to a test destination. Production community material
must not be copied there by default. Promote the tested commit to production, rather than
rebuilding an unidentified version. Staging improves environmental similarity; it does not
eliminate the need for checks after a production release.

Progression should depend on evidence from several successful releases, including a rehearsed
failure and recovery, rather than a promised calendar date. A useful first acceptance exercise
is a small visible wording change installed on the laptop, accepted by Rayner, and then
installed on AWS with matching release receipts.

## 3. The practical connection to the machines

An ordinary conversation does not itself provide persistent access to Rayner's computer or
AWS. We need a connection that can execute a bounded release procedure and return its result.
The proposed first version uses a private GitHub control repository, a runner on the laptop,
and AWS Systems Manager for the server. The existing public source repository remains separate.
A public pull request must never automatically execute on Rayner's laptop.

The AI prepares a release request containing the source commit and expected installed versions.
The laptop action produces a receipt. A separately initiated AWS action checks that receipt
and deploys the accepted commit. Rayner initially initiates the AWS action himself. Once the
appropriate connection is available, the AI can initiate the laptop action and inspect results;
this connection is a setup requirement, not something established by supplying the patch.

The controller and its host configuration live outside the application checkout. Each release
records the requested and previous commits, checks, outcome and any recovery attempt. Detailed
host logs stay private; routine receipts contain no dictionary content or credentials. Changes
to release authority, controller policy, credentials and recovery arrangements require a
separate decision. A chat message, issue comment or model-generated instruction cannot grant
those permissions.

This is a separation of duties, not a claim that deployment authority is harmless. Someone
allowed to deploy arbitrary application code could make that code access application data.
The proposed mechanism narrows routine operations but does not create a cryptographic barrier
between a powerful maintainer and the database. Any promise of stronger isolation would need
a different architecture and independent examination.

## 4. From a user's request to an agreed change

The first conceptual-work pilot should involve a small number of willing participants, using
a channel they already find comfortable. The AI should accept ordinary language, including
French where preferred, and should avoid making users learn issue-tracking terminology.
A simple sequence is proposed:

1. **Understand the difficulty.** Ask what the person was trying to do, what happened, and what
   outcome would help. Prefer one concrete example to a long questionnaire.
2. **Check context.** Consult the current implementation, earlier decisions and relevant
   community constraints. Distinguish observed behaviour from a hypothesis or preference.
3. **Present a small proposal.** Explain the user-visible change, alternatives when there is a
   real choice, and who might be affected. Use a preview where that would make the choice clearer.
4. **Reach and record a decision.** Identify the people whose agreement is needed. Record the
   decision, reason, scope and any unresolved objection. Silence is not consent.
5. **Implement and verify.** Prepare a change and focused evidence, then use the agreed release
   process. Invite the requester to try the result.
6. **Check the outcome.** Ask whether the original difficulty was resolved. A merged patch is
   not sufficient evidence that the user obtained what they needed.

For example, Chua might say that she cannot tell which pictures still need descriptions. The
AI could establish the current screen, suggest a small visual indication, check that it fits
the agreed workflow, implement it and ask her to try it. A request to expose other members'
private pictures would require a different discussion and could not be treated as an ordinary
interface improvement.

The AI should continue ordinary work within its delegated scope without repeatedly asking
Rayner to approve implementation details. It should return genuine disagreements, changes of
purpose and commitments to the appropriate people. Initially, external messages should be
drafted for review; any later permission to communicate directly should specify participants,
channel, purpose and boundaries.

## 5. Decision rights and participation

A possible initial allocation is below. These are proposals to agree with participants, not
permissions conferred by this draft.

| Kind of decision | Proposed responsibility |
|---|---|
| Diagnosis, tests and reversible implementation details within an agreed request | AI prepares and executes within delegated scope |
| Functional acceptance and production release during stage (1a) | Rayner; later a named substitute if agreed |
| Shared interface or workflow affecting several groups | AI consults affected users and records the agreed decision |
| Access, withdrawal, attribution and community-specific content rules | Appropriate contributors and community representatives determine policy |
| Spending limits, hosting commitments and funding arrangements | Named human budget or institutional owner |
| Unresolved disagreement, material incident or change to AI authority | Escalate to the agreed human decision-makers |

The prospect of more direct participation is attractive, but an AI is not automatically
neutral. It can favour frequent correspondents, articulate requests, easy implementations or
its own earlier suggestions. Lack of an obvious human ego is not an adequate governance model.

We should therefore make proposed shared changes visible to affected participants, allow
objections and reconsideration, and preserve the reasons for decisions. Where preferences
differ, a dictionary-level option may be preferable to imposing one choice everywhere.
Participants should be able to disagree with the AI without needing technical expertise.
There should also be a route to a human decision-maker.

No one should become the personal guarantor of every technical claim. Community trust needs
clear commitments, intelligible explanations and ways to check what happens. Different groups
may choose different degrees of AI involvement. Their participation in using the dictionary
must not be taken as consent to public research or to unrestricted analysis of their content.

## 6. Memory, privacy and continuity

Maintain a small durable record for each substantive request: its origin, the need, agreed
scope, decision authority, acceptance criterion, implementation and release references,
verification evidence, remaining concerns and outcome. Record human statements accurately;
label AI interpretations and recommendations as such. Retain earlier decisions when they are
superseded so a later session can understand why the design changed.

Separate public technical documentation from private discussions and community content.
Do not copy private correspondence or examples into the public repository merely because
they helped diagnose a problem. Obtain agreement on what can be retained, inspected and
reported. Routine diagnostics should minimise content collection. Any paid provider call
should follow the dictionary's agreed policy and the relevant budget.

An operational service also needs continuity when a conversation ends, a model changes, an
account becomes unavailable or a provider fails. Source, runbooks, credentials and recovery
responsibilities must belong to the project or its agreed host, rather than depend on one
chat session. A named human or institution remains accountable for the service until another
arrangement is explicitly established. The AI can reduce that person's workload; this draft
does not assume that the responsibility has disappeared.

Funding work can later follow the same pattern: the AI researches opportunities, prepares
budgets and drafts approaches; authorised humans or institutions make commitments. There is
no permission here to solicit funds, send messages or spend beyond an agreed allocation.

## 7. What we should measure

Start with a modest baseline from actual maintenance and development work. Then compare like
requests across the stages, acknowledging changes in difficulty and model capability.
For each request or release, record:

- human interventions and approximate minutes, including those of people other than Rayner;
- elapsed time from request to a useful, accepted result;
- installations completed, failed, recovered or requiring manual repair;
- regressions, unplanned downtime, unresolved requests and provider costs;
- whether requesters felt heard and whether the resulting change helped.

A reduction in Rayner's work accompanied by more outages, greater burden on collaborators or
less control for communities would not count as success. Neither would increasing the number
of automated actions without improving outcomes. Collect only the research information
participants have agreed to provide, and report limitations and counterexamples.

A first collaboration pilot could use three real requests: a small interface change, a defect,
and a change needing more than one person's agreement. Keep Rayner available for escalation,
but ask the AI to manage clarification and preparation. Compare the resulting work with the
current process. This would yield evidence for a later paper without prematurely claiming
long-term autonomous maintenance.

## 8. Immediate next steps and open decisions

The accompanying patch supplies an initial deployment controller, optional activity tracking,
readiness checks, private workflow templates and recovery tests. It does not establish a live
laptop connection, provision AWS permissions, run an unattended production release, or perform
stage (1b)'s functional testing. Its technical runbook is
`docs/howto/community-deployment-stage-a.md`.

Next, install the patch through the familiar manual procedure, configure the private control
connection, and rehearse one small release and its recovery. In parallel, discuss this draft
with interested project members before opening a direct collaboration pilot.

The first decisions are who wishes to participate, which communication channel they prefer,
who resolves disagreements, what the AI may decide without consultation, and who can provide
operational cover when Rayner is unavailable. These questions should be settled simply enough
to permit a real experiment, while remaining open to revision as experience accumulates.
