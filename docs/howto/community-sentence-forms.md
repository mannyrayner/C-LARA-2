# Sentence forms and dictionary lemmas

Sentence vocabulary now puts the form actually used in the sentence first,
followed by the shared dictionary lemma. Each has its own translation disclosure
and playback control. For example, Italian **vanno** can have French **vont**,
alongside the lemma **andare**, **aller**. Identical forms (including a difference
only in initial capitalization) use the existing lemma row without duplication.

New AI picture descriptions, guided pictures, writing practice and the vocabulary
stage of language conversion request the contextual gloss in their existing text
analysis call. Different forms receive their own audio through the existing
bounded speech queue. The vocabulary editing form also exposes the contextual
translation. Shared lemma/sense pages remain shared; inflections do not become
additional dictionary entries.

For separated expressions such as **zieht … an**, the contextual translation is
shown but playback uses the whole sentence, explicitly labelled as such. The
application does not synthesize an artificial phrase by joining separated parts.
Continuous multiword forms use the existing hybrid TTS strategy.

## Existing dictionaries

The owner opens **Tools → Add missing sentence forms**:

1. Request an estimate. This makes no AI requests and reserves no credit.
2. Check the sentence count, estimated cost and allowance. Approve permission and
   the allowance to begin. Insufficient C-LARA credit prevents approval; balances
   behind personal API keys cannot be inspected.
3. Return to the progress page through Tools. Processing continues in the
   background. Completed translations remain if an audio request fails.
4. Use the per-sentence retry estimate for an incomplete result, or request a new
   estimate for the dictionary. Valid completed work is skipped. Audio-only retries
   reuse the saved contextual gloss and do not request another translation.

The backfill sends accepted sentences, their translations and their linked lemma
information to OpenAI. It sends no pictures or existing recordings. It uses an
already recorded surface when present; missing surfaces must align with the
sentence before publication. The estimate covers selected vocabulary links, not
an exhaustive grammatical analysis of every word in every sentence.

The existing selection model retains one occurrence per sentence/lemma-sense link.
This first version does not add all repeated occurrences of the same lemma within
one sentence, a morphological paradigm, or a new exercise mode.

## Corrections, permissions and costs

An editor can open **More options → Correct this translation** on a contextual
form. The previous version stays attributed; the new text is not overwritten by
a later backfill. If its previous recording is no longer applicable, the owner
can add the missing audio through Tools. Normal sentence and lemma editing remain
available in their existing controls.

Forms are contributions with their own author/controller and dependencies on the
exact sentence, translation, lemma and lemma-meaning revisions. Withdrawal moves
them and their recordings into the normal private retention mechanism. Public
playback checks current revisions and sharing permissions. A later sentence or
word edit cannot silently attach earlier form audio to changed wording.

Batch processing shares the existing item budgets, credit reservation/refund
ledger, cancellation and interrupted-job recovery. No provider request is started
on a browsing GET. A paused budget needs a further explicit approval. Estimates
are planning figures, not provider invoices or provider spending caps.

Capture estimates now include additional form recordings. Existing standing
guided-picture consent must be renewed under **Settings → My way of adding
pictures** because its cost scope changed. Existing content remains usable.

## Laptop acceptance check

- Create one Italian/French picture description containing an inflection such as
  *vanno*. Check the form, contextual French translation, lemma translation and
  both recordings. Confirm that the main sentence player still plays the sentence.
- On a small existing dictionary, run the Tools backfill. Open several sentences,
  including an irregular verb and a multiword expression.
- Correct one contextual translation, then request another estimate. Completed
  work should be skipped and the correction preserved.
- Browse the public version if enabled. Check that the same learning information
  appears, without editing controls.

The automated suite uses mocked providers. Actual linguistic quality, pronunciation
and phone ergonomics still need the usual human trial.
