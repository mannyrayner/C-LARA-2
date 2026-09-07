# Step 19: acquire and reconnoitre the classical six

This runbook stops after human review of the occurrence inventory. **It never calls an annotation
model.** It acquires two English, two Norwegian, and two French originals listed in
`data/batches/classical_six_v1.json`. The theoretical motivations guide corpus selection only and
must not be supplied as annotation priors.

## 1. Preflight

```bash
test -z "$(git status --porcelain)" || { echo 'Use a clean tree'; exit 1; }
python scripts/docs/validate_runbook_index.py
python -m unittest tests.test_acquire_classical_source
python -m json.tool data/batches/classical_six_v1.json >/dev/null
for p in data/provenance/classical_six/*.json; do python -m json.tool "$p" >/dev/null || exit; done
```

Create three review commits: A for this runbook, manifest, pending provenance and generic helper; B
only after source/rights approval; C only after every extraction hit is inspected.

## 2. Resolve live sources and rights before acquisition

Open each official catalogue page (`/ebooks/541`, `/ebooks/4240`, `/ebooks/2419`, `/ebooks/13861`),
confirm title/author/language and copy its current official UTF-8 plain-text link into the matching
provenance file. Record the UTC retrieval date and the page's US public-domain statement. Independently
confirm the repository's Australian life-plus-70 basis and change `rights_review.approved` only after
human review. French records must say **Alexandre Dumas fils**, **La Dame aux camélias**, and French.

For Hamsun, open the official Runeberg contents pages already recorded in provenance. Follow the
*Victoria* (printed pages 89–162) and *Pan* (331–423) links. Record their actual inclusive URL indices;
do not infer them from printed pagination. Inspect the linked first/last scans and both adjacent
pages. Confirm boundaries in review notes before running the range command. Retain the sixth-edition,
National Library scan/Runeberg OCR, possible modernized spelling, and unproofread-OCR facts.

## 3. Acquire Gutenberg originals

Run the following once per resolved URL (example 541; substitute IDs/work IDs for the other three):

```bash
python scripts/corpus/acquire_classical_source.py gutenberg \
  --url 'PASTE_OFFICIAL_UTF8_URL_FROM_LIVE_CATALOGUE' \
  --raw data/sources/raw/gutenberg-541.txt \
  --literary data/sources/literary/wharton-age-of-innocence.txt \
  --record data/acquisition/gutenberg-541.json
```

The command refuses overwrite, uses `.part`, preserves the raw file, requires exactly one explicit
START/END marker pair, and records both SHA-256 values. Copy (do not retype) the acquisition fields
and transformations into provenance. Inspect beginning, midpoint and end, recording correct identity,
language, completeness, wrapper removal and absence of obvious corruption:

```bash
for f in data/sources/literary/{wharton-age-of-innocence,lawrence-women-in-love,dumas-fils-la-dame-aux-camelias,constant-adolphe}.txt; do
  echo "===== $f"; sed -n '1,40p' "$f"; n=$(wc -l <"$f"); sed -n "$((n/2-20)),$((n/2+20))p" "$f"; tail -40 "$f"
done
```

## 4. Acquire verified Runeberg ranges

Only after the URL-index boundary review, run (replace the reviewed indices, never with printed page
numbers unless inspection proved them identical):

```bash
python scripts/corpus/acquire_classical_source.py runeberg --volume-url https://runeberg.org/hamsun/6-3 \
  --first VERIFIED_VICTORIA_FIRST_INDEX --last VERIFIED_VICTORIA_LAST_INDEX \
  --raw-dir data/sources/raw/runeberg-hamsun-victoria \
  --literary data/sources/literary/hamsun-victoria.txt \
  --record data/acquisition/runeberg-hamsun-victoria.json
python scripts/corpus/acquire_classical_source.py runeberg --volume-url https://runeberg.org/hamsun/6-2 \
  --first VERIFIED_PAN_FIRST_INDEX --last VERIFIED_PAN_LAST_INDEX \
  --raw-dir data/sources/raw/runeberg-hamsun-pan \
  --literary data/sources/literary/hamsun-pan.txt \
  --record data/acquisition/runeberg-hamsun-pan.json
```

Compare every suspicious OCR target with its preserved HTML and scan image. Document it; never edit
OCR at acquisition. Copy the complete page list/range, per-page hashes, assembled hash and
transformations into provenance. Repeat beginning/middle/end inspection and approve provenance only
when no neighbouring works are present.

## 5. Diagnostic reconnaissance and pattern decision

Keep `data/development/search_patterns_v0_5.json` byte-for-byte unchanged. Search bounded structural
variants (diagnostic only, not production grammar):

```bash
rg -n -i -C 3 "I (really |still |truly )?love you|I love you still|I don.t love you|I never loved you" data/sources/literary/{wharton-age-of-innocence,lawrence-women-in-love}.txt
rg -n -i -C 3 "aime|t['’ ]?aime|vous aime|je.{0,30}aime" data/sources/literary/{dumas-fils-la-dame-aux-camelias,constant-adolphe}.txt
rg -n -C 3 "elsker|[Jj]eg.{0,30}elsker|elsker Dem|elsker dig|elsker deg" data/sources/literary/{hamsun-victoria,hamsun-pan}.txt
```

Inspect all plausible first-person-to-second-person declarations. If and only if a relevant `Jeg/jeg
elsker Dem` is attested, copy v0.5 to v0.6 and add a separate case-sensitive
`\\b[Jj]eg\\s+elsker\\s+Dem\\b` family. Retain all existing families and add tests that both subject
capitalizations match while lowercase `jeg elsker dem` does not receive formal-second-person status.
Otherwise record that v0.5 remains current. Never use `I .* love .* you`.

## 6. Extraction-only dry runs

Use the repository dry-run pipeline with the one common reviewed pattern manifest and no annotation
credentials. The checkout must contain the established extractor before continuing:

```bash
test -f scripts/extraction/run_batch.py || { echo 'STOP: established extractor unavailable'; exit 1; }
unset OPENAI_API_KEY ANTHROPIC_API_KEY
python scripts/extraction/run_batch.py --batch data/batches/classical_six_v1.json \
  --patterns data/development/search_patterns_v0_5.json --dry-run \
  --output data/reconnaissance/classical_six_v1
```

If v0.6 was justified, substitute it. The output must retain exact occurrence identity, pattern ID,
source offsets, bounded passage and structural-status candidates. Do not annotate.

## 7. Human inspection and report

Open every occurrence (including negative, embedded, reported, written, hypothetical and quoted
cases). Check first-person→second-person direction, context bounds, overlap duplication, OCR/scan,
and adjacent declarations. Record descriptive scene clusters without merging occurrence identities.
For every zero, repeat the broad diagnostics and retain zero unless a conventional equivalent was
actually missed. Write `data/reconnaissance/classical_six_v1/summary.md` with:

```text
| Work | Language | Occurrences | Approx. scene clusters | Extraction issues | Recommendation |
```

Have a human sign off the six source inspections, provenance/rights records, pattern decision, every
hit, exact counts and approximate clusters. Stop for Manny/ChatGPT review; do not annotate.

## 8. Final checks and commit checkpoint

```bash
python scripts/docs/validate_runbook_index.py
python -m unittest tests.test_acquire_classical_source
python -m compileall -q scripts/corpus
find data -name '*.part' -o -name '*.pyc'
git diff --check
# Run the repository security scanner if configured; never commit credentials.
git status --short
git add data docs/howto scripts/corpus scripts/docs tests/test_acquire_classical_source.py
git commit -m 'Reconnoitre classical six corpus'
```
