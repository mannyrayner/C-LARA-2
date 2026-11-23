# Laptop deployment of shared lemma pictures

The latest verified laptop receipt (21 November 2026, workflow run 44847217654)
reports `b6114d1666c8d043743b51ece096804c10620e97` installed. The helper refuses a
changed checkout/version; do not substitute a guessed expected commit.

The schema-preparation commit is
`2ac51afc27c2212464fe28e6146d003b20d8f96f`. It is based directly on that verified
release. It adds only the models, migration 0030, the bounded helper and its tests;
it does not activate automatic picture generation. The feature release follows
that commit, with no additional schema change. Both commits must be merged into
public main before installation because the installed controller verifies ancestry.

This release branch excludes the unrelated staging/controller changes on main.
No installed controller, workflow, IAM policy or deployment restriction is changed.
The migration adds a dictionary preference column and a lemma-picture table;
existing content is retained and no provider is called by schema preparation.

## One manual preparation on the laptop

With the normal laptop runner available, run in Cygwin:

```bash
cd /home/github/c-lara-2 &&
git fetch origin main &&
git show 2ac51afc27c2212464fe28e6146d003b20d8f96f:ops/community_deploy/prepare_lemma_image_schema.py > ../clara-deploy/prepare_lemma_image_schema.py &&
./.venv/Scripts/python.exe -E ../clara-deploy/prepare_lemma_image_schema.py \
  --controller ../clara-deploy/bin/runner.py \
  --config ../clara-deploy/laptop.json \
  --expected b6114d1666c8d043743b51ece096804c10620e97 \
  --commit 2ac51afc27c2212464fe28e6146d003b20d8f96f
```

The helper checks exact migration bytes and operations, rejects unrelated pending
migrations or protected changes, drains activity, stops the managed service,
verifies a SQLite backup, applies only migration 0030 and checks readiness after
restart. It attempts to recover the preceding code on failure without reversing
the additive schema; uncertain recovery retains maintenance mode.

Expect `status: prepared`. The installed checkout is then the schema commit, so
never repeat a command claiming the old feature commit is still installed. The
receipt is `lemma-image-schema-receipt.json` in the controller state directory.
Do not launch a second server or bypass a refusal.

## Install and try the feature

After preparation, the assistant can update the private release request and run a
fresh **Install Community Dictionaries on laptop** workflow for the exact feature
commit, expecting the schema commit. This remains a code-only installation.
It does not authorize or trigger an AWS installation. AWS needs its own separately
reviewed schema preparation and the usual human acceptance of the laptop trial.

Open the local Community Dictionaries app, then:

1. In a small AI-supported dictionary, check **Settings → Automatically illustrate
   new word pages** and the existing image-AI switch. Automatic requests use the
   owner's account; explicitly requested batches/regeneration use the requester.
2. Create a new lemma with an accepted translation. Check the background picture
   or the deliberate **No simple picture** symbol and the visible attempt state.
3. Try **Tools → Add missing word pictures**, starting with five words. Review the
   cost and scope before confirming. Existing pictures and choices are kept.
4. Open a word's **Word picture** controls; try an illustration-only choice, a
   replacement and the generic symbol. Check its inflected occurrence in a sentence.
5. Try picture flashcards, a crossword and word scramble. Answers should use
   lemma forms, with only dedicated pictures marked suitable as clues.

Generation quality and physical-phone presentation require this real trial;
mocked-provider tests do not establish either. Record the actual installed
commit and Manny/Cathy's feedback separately from workflow success.
