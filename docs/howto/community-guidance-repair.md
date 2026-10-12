# Repair slow workflow guidance and redundant picture cards

Manny reports the related-language guidance deployed successfully on AWS and
created the expected French sentences/audio/words, but with extra image-only
cards and tens-of-seconds latency on simple navigation. This repair addresses
two locally reproduced causes; the exact production records were not inspected.

## Routine navigation

Guidance was repeatedly checking sentence vocabulary, source snapshots and
destination edit protection one entry at a time. A fixture with 150 Swedish
sentences and a corresponding French version required about 6,370 queries for
the home page. Bulk reads shared within that page request reduce it to 53.
Measured local SQLite times were approximately 6.3 seconds before and 0.2 seconds
after; they are not an AWS response-time promise.

The read scope is discarded after constructing the suggestions. There is no
cross-request or timed cache, so fresh requests see edits and withdrawals.
Estimates retain the same content fingerprints, and approval/jobs/save use
their existing fresh database checks. No provider calls or paid work are added
to browsing. Ready-review checks also use bulk data instead of per-item queries.

## Picture presentation

The old display rule recognised an image-only record as redundant only when
the sentence image was its direct copy. Image-only copying and language porting
can instead produce siblings or longer copy chains. The repaired rule follows
the recorded `shared_from` ancestry, in batches, and hides an otherwise empty
image card when an accepted sentence in the same dictionary represents that
image family. Provenance links to an AI style are distinguished from image copies,
so different generated pictures referring to one style image remain distinct.
Historical capture copies with new JPEG filenames are recognised too.

This is a display repair, with no deletion, archival or data migration. Originals
remain accessible through **Pictures → All entries**, their direct pages and
the contribution/provenance tools. Pending images, independent text/audio/notes,
manual tags, open requests and unrelated pictures are preserved. If the accepted
sentence is withdrawn or archived, its original can reappear. Identical filenames
alone never establish a match; malformed provenance chains do not hide content.
The same rule applies to the accepted-only visitor view.

If an image-only card remains after installation, compare it in **Accepted** and
**All entries**, then provide the URLs of that card and its sentence. It may
contain independent material or have a different provenance shape; do not delete
it to make the display tidy.

See [installation](community-guidance-repair-install.md) and the
[test/evidence record](../../experiments/community_dictionary/guidance-repair-2026-10-12.md).
