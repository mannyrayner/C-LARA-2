# Bounded picture concurrency

Community Dictionary picture admission shares two slots per paying account
across entry pictures, style samples, words-first pictures and word pictures.
`CLARA_COMMUNITY_IMAGE_CONCURRENCY` accepts 1–4 (default 2). The system check
rejects values outside that range. Existing daily quotas, owner approval for
one extra request/batch, consent and actual-usage billing are unchanged.

Admission locks the payer row only while reserving a slot and recording its
receipt. Provider I/O runs outside the transaction. Each active receipt holds
its conservative picture estimate against available credit; personal-key calls
occupy slots but do not reserve platform credit. Legacy active receipts use
the configured image estimate. Reservations are not provider spending caps,
and do not reserve money for unrelated AI tools.

Already-approved waiting word pictures are dispatched by batch: prefer a batch
without an active call, then the least recently served batch, preserving FIFO
within each batch. Distinct batches in the same dictionary are separate groups.
The choice is advisory; the existing locked revision claim prevents duplicate
paid calls even when several workers choose the same row. Completing any kind
of picture wakes waiting word-picture work. Queue delivery does not replay a
paid stage, including failed or uncertain calls. Existing native recovery and
explicit retry controls remain necessary after worker loss.

This first version does not queue new interactive pictures when all slots are
occupied; they show a wait message. It does not add an email-request database
or guarantee equal turns between interactive requests and word batches.
Worker count and provider capacity may further limit actual parallelism. The
existing processing timeout window still governs stale admission receipts;
they are not silently retried.

Run the focused workflow tests with mocked providers:

```sh
cd platform_server
python manage.py test community_dictionary.tests.test_image_capacity community_dictionary.tests.test_image_generation community_dictionary.tests.test_lemma_images community_dictionary.tests.test_guided_words
```

The dedicated PostgreSQL CI job also exercises simultaneous row-lock admission,
credit reservations and overlapping paid-stage mocks. SQLite cannot verify
those database locks and explicitly skips the two PostgreSQL race tests.
