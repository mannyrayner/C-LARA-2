# Check and improve bilingual descriptions

**Check and improve** appears beside **Edit words** on an accepted sentence in an
AI-supported dictionary with picture descriptions/audio enabled. It works on
existing entries. The optional instructions box appears only after opening it.
Use it, for example, to request a fuller description while preserving a preferred
community word.

The editor approves the check estimate and permission to send the current pair,
picture and bounded recent edit history to OpenAI. The private result says that
the descriptions match, proposes a repair, or asks for human judgment. It compares
meaning rather than requiring literal translations; explanations can add context.
It can offer alternatives following either language. The checker does not certify
linguistic accuracy or native review. It can be wrong, particularly for smaller
languages: the preview and community member's judgment remain essential.

Suggestions have editable fields. Nothing replaces accepted text until **Apply
suggestion and update words and audio** is approved. **Keep my wording** leaves
both descriptions intact. If the descriptions match or the model is uncertain,
the current text can be reviewed/edited and sent to the existing vocabulary/audio
refresh without claiming a suggested improvement. Approval is separate from the
initial check and includes the refresh estimate/provider permissions.

## Checking after an edit

The Edit words form offers **Check both descriptions after saving (AI)**, selected
initially, with an estimate and a description of the data sent. Saving changed,
immediately accepted wording with this enabled queues one check automatically and
opens its progress/review page. Uncheck it to use the existing words/audio-only
update. Unchanged text and category-only changes make no paid check. Missing AI
configuration never disables editing. If a check cannot be admitted, the human edit
is retained and a fresh manual check is offered. A GET, refresh or browser back
navigation never starts a provider call.

## Human terminology and history

Both fields' recent accepted revision chains are supplied, without contributor
contact details. Short lexical replacements in human edits (for example a local
word replacing a loanword) become preferred corrections while still present in
the current text. The model is instructed to retain them; a suggestion that
reverses/drops a detected correction is removed and an uncertain result is shown
if none remain. These are conservative lexical guards, not a complete linguistic
analysis of every historical edit. The reviewer can explicitly edit a preview
when a different meaning or wording is intended. Accepted revisions retain their
previous-version links; unchanged fields retain their contributor.

An approved job transitions to the existing **Update words and audio** processing,
using the same durable record/allowance. It rebuilds vocabulary from the exact
approved wording and reuses current results/audio. Human recordings and historical
material are retained. Missing generated audio can be retried explicitly through
the existing refresh workflow; this does not rerun the bilingual check.

## Implementation and deployment

Uses existing private PictureCapture records (`input_mode=improve`, then `refresh`
after approval). No model/schema/dependency change or migration. Claims commit
before provider calls; concurrent workers/taps reuse claims. Snapshots, history
availability, source permissions, settings, prices and audio policy are rechecked
before calls and before application. Another edit or withdrawal invalidates the
preview. Failed/uncertain calls are not automatically repeated; unstarted work
has an explicit continuation action. Suggestions belong to the requesting editor.

The check estimate is a bounded-input planning estimate; actual token usage is
recorded with the existing billing mechanism. Check and refresh count as one
attempt against the current description allowance. Explicit fresh checks after a
failure remain new paid attempts.

French and Slovak interface catalogs include the new controls. Use the normal
laptop-first deployment and human AWS acceptance process. Suggested laptop checks:

1. Open an existing sentence, invoke Check and improve, add optional instructions,
   run the check and verify no accepted text changes before approval.
2. Make an English-only meaning change; save with automatic checking enabled.
3. Confirm that an accepted community-term correction survives a proposed rewrite.
4. Edit or keep a suggestion, approve the dependent refresh, and inspect the words
   and audio. A model's proposed wording still needs native-speaker judgment.
