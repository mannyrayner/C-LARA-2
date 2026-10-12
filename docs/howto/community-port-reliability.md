# Language-port reliability and proportionate credit holds

12 October 2026. Prepared against `3ed343a3b70565c686b836eadb5d0330c5df7f14`.
Installation: [laptop and AWS runbook](community-port-reliability-install.md).

Manny's 150-sentence trials exposed four problems: excessive vocabulary allowances,
awkward recovery of missing Italian audio, one French sentence in an Italian port,
and vocabulary rejection for every Japanese sentence. This revision addresses those
paths. It has not yet been tested by Manny on the laptop or deployed to AWS.

## Estimates, approval and returning credit

New quotes use short expected recordings, three new words per sentence as a planning
assumption, and pronunciation-guidance costs for a proportion of unknown words.
The refundable allowance is 2.5 times the estimate, with a one-cent minimum per item.
Existing vocabulary context, actual text length, model prices and expected reuse
still matter. This is an application estimate, not an independently checked tariff.

For a short example sentence, no existing vocabulary context and configured token
prices of US$2 input / US$10 output per million, the new vocabulary calculation is
US$0.0131 estimated / US$0.0328 allowance per sentence: US$1.965 / US$4.92 for 150
such sentences. The previous calculation was approximately US$9.915 / US$130.35.
These examples are not a quotation for Manny's actual dictionary.

Workers claim their forecast share of an item's allowance before analysis or speech.
Concurrent word recordings share the item's remaining budget. If it is insufficient,
the item pauses; other funded items may continue. The progress page offers a signed,
explicit additional approval and checks available credit. Repeating that approval
cannot debit it twice. Translation already obtained is retained when audio pauses;
resuming does not translate it again. Workflow suggestions point to the approval.

As each item finishes its required review and audio, its unused credit is returned
once, even while other items await review. The final settlement reconciles previous
returns and charges. The audit now understands incremental refunds and additional
approved reservations. Cancellation still waits for in-flight operations and keeps
saved entries. Never manually adjust account balances to reduce a displayed hold.

The allowance caps the C-LARA account charge, not the provider invoice. A response,
pronunciation-guidance step or silent-audio retry can cost more than its forecast;
subsequent work checks the remaining allowance. Unknown provider usage is still
marked uncertain. Personal-key and server-funded jobs also require explicit
approval to increase their planning allowance, but no C-LARA credit is deducted.

Migration `0023_port_budget_release` adds two bookkeeping fields. It does not rewrite
existing jobs, balances, ledger rows or dictionary content. Previously prepared or
approved jobs retain their existing allowance and settlement policy. They do not
suddenly acquire a smaller hold on installation. Request a fresh estimate for new
work; finish wanted reviews rather than cancelling merely to release credit.

## Japanese and Chinese vocabulary

The old exact-span validator required regular-expression word boundaries. Han and
kana characters count as word characters, so legitimate Japanese words next to
particles were rejected. The shared validator now accepts exact lexical spans
within Han/kana text while retaining alphabetic word boundaries. Prompts explain
unspaced Japanese/Chinese surface forms and Korean inflected forms. Manual edits
use the same validator. The AI supplies lexical segmentation; no Jieba, Japanese
or Korean tokenizer is installed by this revision.

For example, `猫`, `ソファ` and `寝ています` now align with
`猫がソファで寝ています。`; the last can link to the lemma `寝る`. This fixes a
reproduced software rejection, not a guarantee of linguistic segmentation quality.
Korean is not treated as unspaced Chinese: its full inflected surface must match.
Latin fragments such as `att` inside `Katten` remain invalid. Discontinuous MWEs
continue to use ordered exact spans separated by an ellipsis.

To repair the existing Japanese port, keep the accepted sentences. Open that
language version's vocabulary workflow and choose **Retry failed or missing
vocabulary — new estimate**, or **Build vocabulary from accepted sentences**.
Review the quote and approve. Already-current vocabulary is skipped. No need to
translate the sentences again. Diagnostic logs identify known validation reasons
without printing dictionary text or provider output.

## Independent target-language check

New sentence translation and batch-description jobs send the generated sentence
and requested language to a separate, text-only model check. No extra picture is
sent for this check. Its usage is included in the same item's recorded text cost;
it is disclosed in estimates and workflow approvals.

A mismatch, an uncertain answer or a failed check keeps the text available, flags
it for attention, skips automatic speech, and excludes it from **Accept all**.
Review and correct it if necessary, save it, then create its audio. Proper names,
borrowed words and short ambiguous sentences still require human judgement. This
check does not certify meaning, translation quality or pronunciation, and it is
not retroactively applied to already accepted sentences.

## Recover missing audio

On a completed job's progress/results page, use **Retry missing audio — show
estimate** after saving the wanted text. Approve the separate estimate. It finds
saved results of that job with no currently usable recording, uses their current
accepted wording, and keeps successful recordings. For a vocabulary job it checks
shared word pages; for a sentence job it checks sentences. It does not translate
again or change the old job's charges. You can recover sentence audio and word
audio from their respective jobs.

Other active jobs on that language version must finish first. A later text edit
invalidates the audio estimate/claim rather than recording obsolete text. Source
withdrawal, membership and ownership restrictions remain enforced. An interrupted
request is not automatically repeated; **Resume waiting work** marks an old
uncertain attempt failed, after which a new explicit recovery estimate is possible.
An individual entry's existing Create audio control remains available.

## Verification and limits

See the accompanying [verification record](../../experiments/community_dictionary/port-reliability-2026-10-12.md).
Provider calls and queues in tests are mocked. No production account was changed,
no paid calls were made, and no claim of live Japanese quality or language-check
accuracy is made. The additive migration and new accounting paths need the normal
laptop trial and subsequent AWS audit. Existing large reservations are not refunded
by a data migration.
