# Community Dictionary language versions

Updated 8 October 2026. The [sentence extension](community-sentence-porting.md)
now includes accepted picture-description sentences and their vocabulary links.
Read that guide for recovery of existing word-only attempts.

Earlier trial record, 5 October 2026. Manny confirms the category and picture-interpretation fixes
on the laptop. Short-word TTS remained unreliable. The new [pronunciation guidance
increment](community-tts-guidance.md) adds English-homograph guidance/warnings and
one bounded silence retry. Manny subsequently reports successful chat/lit generation
and a successful small-dictionary laptop test of the integrated increment.
Manny now also reports conversion/review of the 61-entry French AWS version, with
four initial pronunciation issues. See the [trial record](../../experiments/community_dictionary/porting-aws-2026-10-05.md)
and the prepared [review-UX follow-up](community-port-review.md).

## Use it

As the source dictionary owner, open **Settings → Create a version in another
language**. Choose a name, target language, commenting language and named voice.
Keep either language unchanged to preserve that part. These are content languages;
the app interface is unchanged. Examples:

- Swedish/English → Italian/English: reuse pictures and English explanations,
  translate Swedish words with their visual context, generate Italian speech.
- Swedish/English → Icelandic/English: the same workflow for Kate/Axel's review.
- Swedish/English → Swedish/French: translate explanations and English categories while keeping Swedish categories and
  retaining the original Swedish words and recordings exactly.

The owner must have enabled **Learn from a photo (OpenAI)** in the source settings.
The explicit approval also affirms permission to send the selected texts/pictures
to the provider and reuse contributions. Being a dictionary owner does not itself
establish community permission. The new dictionary initially has no invited
members; contributors still retain control over their copied contributions.

**Estimate cost** makes no provider calls. It lists the number of entries, a rough
USD estimate, who pays and (when applicable) available C-LARA credit. Approve the
estimate to start. Leave the page if desired; return to **Language versions →
Latest job** and refresh progress. Open **Review result** for each ready entry,
listen, correct the proposed wording if necessary and save. Only saved results
enter the new dictionary. A revised word discards mismatching preview speech;
use the existing Create audio command afterwards. Unclear results are flagged
rather than automatically adopted. You can accept a tentative suggestion or supply
your own translation, without changing the source. This also works for blocked
previews created by the first release.

Accepted word and sentence entries, with accepted components and pictures/audio, are eligible. Image-only
entries, pending material, archived entries and private collections are excluded.
The model sees the word or sentence, explanation, category, language names and one representative
picture (selected picture preferred). Sentence requests also include linked source
vocabulary and meanings for alignment. Category classification also uses up to five
accepted source word/explanation/category examples. Labels inferred to be in the
target language follow that language; labels in the commenting language follow
that one. Ambiguous/mixed/other-language labels are kept and flagged for review.
Concurrent results share one decision per label, reused on later updates while its
evidence remains valid. Categories remain editable on review. All associated accepted pictures are reused,
including picture/word links. Source audio is never sent for recognition. The
prompt preserves the intended referent: a sofa pictured with a cat should remain
about the sofa. Explicit words establish the intended concept; a surprising or
symbolic picture prompts a warning, not a veto. A Swedish *kung* / English *king*
can therefore be rendered as French *roi* despite an unconventional illustration.
This is a prompt and review workflow, not an accuracy guarantee.
A new target language must have configured TTS in this first cut. Changing only the
commenting language can keep any existing target language, including human audio.
The new dictionary does not automatically enable image generation or clone its style.

## Cost and funding

The model is the configured `COMMUNITY_DICTIONARY_PHOTO_MODEL`. The estimate uses
its explicit configured token prices, approximate image/text sizes and the existing
speech duration/input estimate. The approval page exposes the model and rates;
these are application settings, not a live vendor quotation. Category examples
are included in the estimated input size; classification uses the existing entry
call rather than an extra paid call per category.

With C-LARA credit, approval atomically checks and reserves a larger allowance.
Concurrent jobs cannot reserve the same available credit. Processing settles once,
returns unused credit and caps the C-LARA charge at the reservation (and each
item's allocation). Returned vision token usage and estimated speech costs remain
in the existing usage records; the reservation/refund is in the credit ledger.
The provider invoice can differ, and any excess beyond the application's cap is
an operator cost, not a later unexpected user debit. Failed calls with no usable
usage information are marked cost-unknown; no fabricated token usage is recorded.
They may cost the provider account even when no C-LARA usage debit can be measured.

With a personal OpenAI key, no C-LARA credit is taken. This app cannot check the
personal provider balance: it says so and asks the user to check it. With credit
charging disabled, the server operator pays. The approval freezes payer and prices;
a changed payer before/during processing stops further work instead of switching
accounts silently. Estimates expire after one hour and are revalidated on approval.

## Background processing and recovery

Production uses the existing Django-Q queue: one durable item per entry, a bounded
fan-out window (default four), and fan-in settlement after all items finish.
The existing Q worker count controls actual concurrency (normally two). Queue
payloads contain only item IDs. Network calls are outside database transactions.
A committed claim precedes each paid attempt; duplicate approvals, broker delivery
and resume commands do not repeat a claimed request. A failed item does not prevent
other entries from completing. Only a completed silent or nearly silent speech response is automatically regenerated, once. Timeouts, API errors and interrupted calls are not retried.

The default laptop configuration uses the repository's lightweight threaded Q
adapter. It starts jobs inside the development server; no separate `qcluster`
is needed in that mode. Keep the server running while processing. With
`DJANGO_Q_USE_REAL=1`, install/use the existing Django-Q2 setup and run
`python manage.py qcluster` separately with the same environment as the web server.
Do not change the AWS queue configuration if it is already working.

**Resume waiting work** safely re-enqueues unclaimed rows. Claims interrupted for
more than 15 minutes are abandoned and marked cost-unknown, never silently retried.
After a process restart, an administrator can also run:

```bash
python manage.py recover_language_ports
```

**Cancel and discard unsaved results** stops waiting work and removes previews;
requests already sent finish accounting but their results are discarded. Saved
entries remain. A running interrupted item must be recovered before its reservation
can settle. For recurring operations this recovery command can be incorporated into
an existing supervised maintenance schedule; no new scheduler is installed here.

## Updates and provenance

Choose **Estimate an update** from the job or language-version list (also linked
from the destination's Settings). New/changed source entries are proposed; unchanged
ones are skipped unless category context or translation/speech rules changed.
This deliberately revisits first-release outputs once so incorrect categories and
speech can be repaired. If the destination was edited, it is protected as a whole entry.
Corrections made during the initial review are also remembered and protected on
future updates. There is no automatic overwrite/merge of human corrections.
Matching existing synthetic audio is reused when wording, language and voice still
agree and the recording used the current language instructions (plus unchanged meaning when it informed pronunciation guidance); otherwise a new
preview is generated. Saving replacement speech supersedes earlier speech made by
that port, retaining history without duplicate playable versions. New TTS calls explicitly ask for native pronunciation. Detected English homographs also receive AI-generated pronunciation guidance and a visible review warning. One silence retry is allowed; its cost and the guidance cost are included in the estimate and accounting. This applies to ordinary entry TTS as well as porting. Existing saved
recordings do not change until a new recording is generated and saved. A failed speech
call leaves text available for review; audio can be added later from the entry.

Pictures and unchanged text/audio retain their author/custodian and source links.
Translated components are attributed to the initiating/reviewing user and labelled
as derived; additional dependency records connect all text/image inputs actually
used, including category examples and the input that established a shared label.
Consequently withdrawing an example can also hide translations derived using it.
Source withdrawal moves dependent contributions to private collections and
clears unsaved previews. Multiple source withdrawals must all be restored before
restoration can expose a dependent contribution. These are server-side controls,
not recall of material already downloaded or sent to a provider.

Exports include `provenance-links.json` with dependency IDs but do not include
external source dictionaries. Full database/private-media backups are required to
preserve operational cross-dictionary withdrawal links across a server restore.
Merging dictionaries, community discovery, independent automatic synchronization,
image regeneration and automatic model-based translation grading are not included.

## Laptop installation

This patch follows the practice and multiple-choice updates accepted on AWS on
4 October. Stop the laptop server and any real background worker. From
`/home/github/c-lara-2/platform_server`, make a verified SQLite backup outside Git:

```bash
../.venv/Scripts/python.exe -E manage.py shell -v 0 -c "exec(__import__('sys').stdin.read())" <<'PY'
import sqlite3
from pathlib import Path
from datetime import datetime
from django.conf import settings
config = settings.DATABASES['default']
assert config['ENGINE'] == 'django.db.backends.sqlite3', 'Stop: expected laptop SQLite'
source = Path(config['NAME']).resolve()
assert source.is_file(), f'Missing database: {source}'
destination = Path.cwd().parent.parent / 'clara2-backups'
destination.mkdir(exist_ok=True)
backup = destination / ('before-language-port-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
with sqlite3.connect(str(source)) as src, sqlite3.connect(str(backup)) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Backup verification failed'
print('Database backup verified:', backup)
PY
```

Save the patch in `/home/github/`, then:

```bash
cd /home/github/c-lara-2
git status --short
# The original language-porting patch must already be applied; staged changes may remain.
git apply --check ../community_dictionary_language_porting_fixes.patch &&
git apply --index ../community_dictionary_language_porting_fixes.patch
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate &&
../.venv/Scripts/python.exe -E manage.py showmigrations community_dictionary
```

Expect **257 tests, OK**, and the new additive migration **0012** applied. The
existing participation data is not rewritten; do not rerun the old 0008/0009
experimental restoration procedure. No new production dependency is required.
Start with the usual command:

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Try a small Italian/English version first: inspect its estimate, approve, wait for
results, review/play/save, and confirm the Swedish original is unchanged. Try a
commenting-only French version if useful. Re-estimate an unchanged version and
check it skips saved entries; make a correction and check a later source update
protects it. Use disposable content for withdrawal/restoration tests.

After laptop acceptance and check-in, AWS needs a database/private-media backup,
pending migrations through 0013, static collection and restart of web/background
services. Both web and worker must run the new code. The huge public-media archive from the earlier participation
migration need not be repeated solely for this additive schema update.

## Retry the existing French version

1. Review or discard remaining previews. An old blocked *king* result can now be
   opened and saved with **roi** directly; then use **Create audio** on its entry.
2. Select **Estimate an update** for the French version. Earlier unedited outputs
   are offered again. Review the estimate and approve as usual.
3. Check **djur → animaux**, unchanged English categories, and French pronunciation
   of **chat**. Save reviewed replacements. Manual corrections remain protected;
   edit protected entries directly if needed.
4. A subsequent unchanged update should skip the saved entries again.

## Earlier porting-repair verification

257 application tests pass, including 42 porting tests; six shared audio unit tests
also pass. New cases cover category context/consistency, commenting-only ports,
withdrawal dependencies, legacy blocked previews, editable uncertainty, old speech
replacement, and the actual French instruction payload through both SDK paths.
Chromium at 320/390px passes with eight items and two real Django-Q2 worker processes,
including uncertain-result save, image/audio previews and incremental skipping.

Provider calls in these checks are simulated. Manny subsequently confirmed the
category and picture-interpretation fixes, then accepted the integrated pronunciation
follow-up on the small laptop dictionary. Porting was subsequently deployed and the French AWS conversion reviewed by Manny.
A new physical-phone porting trial remains unreported. The latest review-UX increment
has separate verification and still awaits human acceptance.

The 5 October follow-up and current installation commands are documented in
[Community Dictionary pronunciation guidance](community-tts-guidance.md).
