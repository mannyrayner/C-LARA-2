# Public practice and owner workflow suggestions

This increment makes the existing games available to visitors and brings the
next useful construction step out of Settings. It does not automatically enable
public browsing or any AI feature.

Manny reports successful AWS installation and useful initial owner-guidance testing
(12 October), after the generated-static-directory permission repair now recorded
in the installation runbook. See the next [language-version guidance increment](community-port-guidance.md)
for reminders to update an existing translated dictionary.

## Visitors can practise

When the owner has enabled **Public browsing**, the visitor navigation includes
**Practise**. Visitors can use all six flashcard directions, multiple-choice or
reveal answers, picture crosswords and word scrambles. These reuse existing
accepted words, pictures and recordings; there are no AI calls or practice
charges, and no account or persistent score. Ordinary hosting costs remain.

An unlisted public link also works. Discoverability alone does not grant content
access. Games exclude drafts, discussions, legacy text without an accepted
contribution, withdrawn/held content and stale synthetic audio. They use the
existing public media URLs. Disabling public browsing, hiding the dictionary or
withdrawing content blocks subsequent relevant requests. The page rechecks before
each game action, periodically, and on return from another app. As with public
browsing, already downloaded content cannot be recalled.

## One useful next step for the owner

**My dictionaries** shows a prominent linked notice on an owner's dictionary card
when a useful next action exists. The dictionary's Browse page shows the same
step, with this priority:

1. Pending membership requests.
2. Ready unflagged sentence or vocabulary suggestions to review (including accept-all via
   the existing review screen).
3. Work still processing, linking to progress.
4. Word suggestions to create from accepted batch/ported sentences whose
   vocabulary is not current.
5. Sentences to create for eligible pictures that lack them.

Only one primary suggestion is shown at a time. It is specific to the current
owner's authorized work. Ordinary contributors and visitors receive no production
prompts. Hidden, withdrawn, inactive and personal-collection access restrictions
remain in force. Existing controls and review pages remain available.

The generation panel shows the scope, a rough US-dollar estimate, voice and payer.
For app credit it also shows the reservation and available balance, and withholds
the approval button when the balance is insufficient. Personal/provider account
balances cannot be checked here. **Approve and create sentences** or **Approve and
create word suggestions** starts the existing background job after this disclosure.
The button also confirms permission to send the described material to OpenAI and
share reviewed results. Merely visiting a page never sends content to a provider,
reserves credit or creates a generation job.

Sentence suggestions include accepted pictures and pictures awaiting review.
Existing words and translations remain hints; they are not overwritten. Pictures
with an existing sentence or an outstanding individual description are skipped.
For another selection or voice, use the existing Settings workflow. Saving a
sentence accepts its source picture where needed; word generation follows after
sentence review. The vocabulary step reuses shared lemma/sense pages and the
existing review/edit/accept-all process. Missing word audio is generated after
vocabulary acceptance within the approved allowance.

The first cut guides existing batch and language-port jobs. It does not introduce
a general repair operation for arbitrary manually created sentence pages or
automatically retry failed items. Existing progress/recovery pages handle those.

## Preference and implementation

The owner can turn **Settings → Workflow suggestions** off or back on. Migration
`0022_workflow_suggestions` adds a default-on preference and its revision counter.
Turning suggestions off does not disable AI, cancel work, hide the old Settings
controls or change public access.

`workflow.py` builds read-only plans using the same selectors and estimators as
the existing batch/vocabulary quote functions. A signed, one-hour approval binds
the user, dictionary, operation, snapshots, languages, voice, model, price basis
and payer. The POST rechecks permissions, scope, prices and available funds under
the existing transaction locks; changed input requires a fresh estimate. A repeated
approval redirects to the same run without another reservation or dispatch.

`public_practice.py` uses the accepted-only public projection; game algorithms and
the interface are shared with member practice. No private member route is opened.
The practice JavaScript version changes, so AWS deployment needs `collectstatic`.
No dependency, email, nginx or environment changes are required.

See the [installation runbook](community-practice-guidance-install.md) and
[local evidence](../../experiments/community_dictionary/practice-guidance-2026-10-11.md).
