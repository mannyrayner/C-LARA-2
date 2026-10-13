# Automatic sentence, vocabulary and audio processing

Prepared 12 October 2026; laptop and AWS acceptance pending.

Dictionary owners can choose **Create everything automatically** in:

- Settings → Add missing sentences to pictures;
- Settings → Create a language version, or update an existing language version;
- Build vocabulary from accepted sentences, when only that stage remains.

The alternative **Review step by step** remains the initial selection. A workflow
suggestion's ordinary estimate also offers **Estimate fully automatic processing
instead**. Preparing an estimate makes no AI calls and reserves no credit.

After the owner approves one combined estimate, the job publishes generated
sentences and their audio, derives vocabulary from those actual saved sentences,
shares word pages by lemma and sense, creates links and generates missing word
audio. There is no intermediate acceptance screen. One progress page leads back
to the dictionary; work continues if the owner leaves it. Use Refresh progress
to see the latest state.

Automatically published text is explicitly labelled as having had no human review,
including on public entry pages. A later check of the current wording can replace
that label. Publication approval is recorded separately from linguistic review.
Existing source authorship, dependencies and withdrawal controls remain in force.
For in-place picture descriptions the approval explicitly includes accepting any
selected source pictures that were awaiting review. A dictionary with public
browsing enabled can therefore show these new results immediately.

## Costs and partial results

One allowance covers both stages. The estimate includes language checks and the
configured vocabulary/speech forecast. New quotes retain the smaller allowances
introduced in the language-port reliability repair. The vocabulary forecast uses
three short new-word recordings per sentence; actual vocabulary size varies and
shared words reduce the work. A longer or more expensive result may pause for an
explicit additional allowance. Personal-key spending remains subject to provider
billing, not an enforceable provider-side limit in this app.

For credit-funded jobs, the root reservation includes a separate vocabulary pot.
Finished sentence items return their own unused amounts, without releasing that
pot. At the boundary, root settlement and the capped child reservation commit
together. The two ledger reservations are linked stages of one approved operation,
not two independent user approvals. Repeated dispatch/approval does not charge or
publish again. Existing approved manual jobs keep their previous behaviour.

Failures preserve completed results. Uncertain language/image suggestions can be
published with attention flags, but do not seed automatic vocabulary or audio.
Unusable output is marked failed. Homograph pronunciation concerns and failed
recordings remain visible in the job's attention results. No successful response
is claimed to be a linguistic accuracy guarantee.

**Retry incomplete work — show estimate** prepares a fresh approved attempt. It
retains completed translations, current vocabulary and usable audio, and can also
include new/changed eligible pictures or sentences. Missing recordings on saved
sentences/linked words can be regenerated without retranslation. Vocabulary edited
after its saved generation snapshot is protected. Independent old word entries
with failed audio can still use the existing entry-level audio control. Broader
review/cleanup tools are deferred until a real reviewer can help design them.

Stop processing preserves published results. Resume waiting work supports the
existing queue-recovery rules; an uncertain paid request is not silently repeated.
If permissions, payer, model, price or recipe change before the second stage, it
does not automatically approve that changed operation. Saved results and refunds
remain; resolve the change and resume or prepare a fresh estimate.

## Implementation and evidence

`automatic.py` orchestrates existing batch/port stages; it introduces no schema,
dependency, queue-mode or environment changes. Automated tests cover end-to-end
batch description and conversion, shared vocabulary, combined credit approval and
audit, idempotency, insufficient funds, cancellation, withdrawal, human edits,
partial failures, missing-audio recovery, changed configuration, allowance pauses,
public labels, permissions and the unchanged manual route. Providers are mocked;
these checks do not establish model quality or production concurrency behaviour.

See [installation and trial instructions](community-automatic-processing-install.md)
and [experiment record](../../experiments/community_dictionary/automatic-processing-2026-10-12.md).
