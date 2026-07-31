# Unified content catalogue and legacy migration roadmap

This roadmap coordinates the remaining legacy C-LARA bulk import work in
[ISSUE-0010](../issues/issues/ISSUE-0010.json) with the hosted compiled LARA registration work in
[ISSUE-0001](../issues/issues/ISSUE-0001.json). The user-facing goal is one **Content** tab for native C-LARA-2,
imported C-LARA, server-hosted legacy LARA, and externally hosted legacy LARA resources. Storage, editability, and
provenance remain explicit even though discovery is unified.

## Agreed product decisions

- Use a catalogue record for every published item (the previously discussed **option A**), including native
  C-LARA-2 projects.
- Display provenance but do not use it to change search ranking. Users may filter by provenance.
- Preserve comments, ratings, ordinary title/language search, and access counting for every content type.
- Keep the administrative owner separate from the displayed original creator. Do not display the C-LARA-2
  administrator as the resource creator merely because they registered or imported it.
- Publish locally hosted legacy LARA content publicly after successful validation; the current administrator manages
  the imported catalogue records.
- Treat publication date as optional because it is not available for the legacy LARA collection.

## Content and hosting types

Catalogue provenance and hosting location are independent dimensions:

| Provenance | Hosting type | Meaning |
| --- | --- | --- |
| Native C-LARA-2 | Project compilation | Editable C-LARA-2 project and its compiled output |
| Imported C-LARA | Project compilation | Editable project converted from a legacy C-LARA bundle |
| Legacy LARA | Server hosted | Read-only compiled directory served from the AWS host |
| Legacy LARA | External URL | Read-only catalogue record linking to an authorised external host |

The implementation should introduce a catalogue-level model (working name `ContentItem`) rather than representing
compiled LARA directories as fake editable `Project` rows. A catalogue item may point to a `Project`, a safe
server-hosted relative entry path, or an external HTTPS URL. Stable provenance identity, original creator display,
publication/access state, discovery metadata, comments, ratings, and counters belong at catalogue level. Existing
published projects require an idempotent backfill and a compatibility period while project publication fields remain
in use.

## Legacy C-LARA bulk import

The `adelaide-v3` library has 652 metadata directories and 485 successful `source.zip` conversions; all 485 ZIPs
passed integrity validation and are visible through the configured server-side library. The batch importer must:

- identify sources by a stable pair such as `(source_system, legacy_project_id)`, never by title alone;
- reconcile existing manually imported projects before creating new rows;
- record library version, original owner, source checksum, destination project, status, timestamps, and diagnostics;
- provide a dry run, per-project transactions, resumability, `--limit`, skip-existing, and retry-failed controls;
- continue after individual failures and emit machine-readable plus human-readable reports;
- create or update the corresponding catalogue item with **Imported C-LARA** provenance;
- make repeated runs idempotent.

Some newly available bundles originally contained a phonetic text layer. The conversion included these projects by
**discarding the phonetic layer**, because C-LARA-2 cannot currently represent it. Documentation and reports must not
describe these as imported “phonetic projects”; any provenance/import diagnostic should state this loss explicitly.

## Compiled LARA collection

The laptop collection is approximately 9 GB and contains about 50 projects. The two largest known items are volumes 1
and 2 of *À la recherche du temps perdu* at approximately 1 GB and 2 GB. Each project has a uniform layout:

1. one project directory;
2. exactly one immediate subdirectory; and
3. `_hyperlinked_text_.html` in that subdirectory as the entry point.

Assets are relative and self-contained. Before transfer, record total size, per-project size, file count, and available
AWS disk space. Use resumable `rsync` to `/srv/c-lara/legacy-compiled/lara/` and initially serve the validated tree
directly through Nginx. Large audio should be checked for HTTP range-request behaviour and mobile loading, but Nginx
is the accepted first deployment rather than S3/CloudFront.

The old content metadata was not downloaded and there is no collection manifest. Obtain metadata from the still-live
C-LARA service, manually or with a small script. With only about 50 items, manual curation is acceptable. Build a
versioned manifest containing at least:

- stable legacy identifier;
- title;
- text and annotation/gloss languages;
- original creator display name;
- hosting type;
- safe relative entry path or external URL; and
- optional description and publication date.

The registration command must validate that each server-hosted entry resolves below the configured root and matches
the one-subdirectory/`_hyperlinked_text_.html` contract. It must reject path traversal, missing/ambiguous entry points,
duplicate stable identities, and unsafe URL schemes. Registration and reruns must be idempotent and auditable.

## External Pitjantjatjara resource

*Basic Course in Pitjantjatjara* is the only known restricted-hosting exception. Indigenous data-sovereignty
requirements mean that C-LARA-2 must register its existing public external URL rather than copy it to AWS. It remains
publicly discoverable, supports comments/ratings and outbound access counting, and may receive a lightweight
availability check. The resource itself already contains the necessary attribution and sovereignty notice, so the
catalogue need not duplicate that text.

The administrator may update or withdraw the link. C-LARA-2 must not mirror, proxy, scrape, thumbnail, cache, or send
the resource to AI services as a side effect of registration or display. The UI should mark it as externally hosted
and open the authorised URL safely.

## Unified Content UX

The existing Content tab remains the single discovery entry point. Catalogue list and detail pages should:

- search all content types by ordinary free text and language fields;
- optionally filter by provenance without changing relevance ranking;
- show provenance and external-hosting badges;
- show the original creator, not the administrative importer, as creator attribution;
- support common comments, ratings, access counts, and public visibility;
- expose editing/compilation actions only when backed by an editable project; and
- send local hosted links through a safe server route and external links to their authorised origin.

## Delivery phases

### Phase 1 — schema and provenance foundation

- Add the catalogue model, provenance/hosting enums, original-creator fields, safe location fields, and stable source
  identity constraints.
- Move or generalise comments, ratings, and access counting to catalogue level with data migrations.
- Backfill current published C-LARA-2 projects idempotently and keep publication state synchronized during transition.

### Phase 2 — C-LARA batch importer

Status: **initial implementation delivered.** `import_legacy_bundle_library` now provides persistent source identity,
dry-run/reporting, natural ID ordering, limits, repeatable ID selection, existing-import reconciliation, independent
transactions, idempotent skip behavior, and explicit failed-record retries. Deployment still requires migration plus a
small smoke-test batch before the full Adelaide run.

- Add persistent import provenance and reconcile existing imports.
- Implement dry-run and resumable batch management commands with reports.
- Smoke-test small, large, media-rich, and formerly phonetic-layer bundles before importing the remainder.
- Audit and report the discarded phonetic layer rather than implying it was imported.

### Phase 3 — LARA transfer and manifest

- Inventory local sizes and AWS capacity, then transfer the compiled tree resumably.
- Obtain and curate missing title/language/original-creator metadata from the live C-LARA service.
- Validate uniform entry points and generate the versioned registration manifest.
- Add the external Pitjantjatjara record without copying its content.

### Phase 4 — unified registration and catalogue UX

- Implement idempotent server-hosted/external registration.
- Serve safe local paths through Nginx and register public catalogue URLs.
- Switch catalogue search/detail/comment/rating/count flows to catalogue items.
- Add provenance filters/badges and test local, project-backed, and external links.

### Phase 5 — mobile corpus audit

- Use native C-LARA-2, imported C-LARA, compiled LARA, large Proust audio, and the external-link case as a mobile
  regression corpus.
- Measure responsive layout, touch interaction, audio range/loading behaviour, page weight, and broken legacy links.
- Record unsupported legacy behaviour separately from regressions in modern C-LARA-2 compilation.

## Acceptance criteria

- Re-running either bulk operation creates no duplicate projects or catalogue items.
- Every catalogue item has explicit provenance and original-creator attribution independent of its administrator.
- All content types appear in one searchable Content tab and support common comments, ratings, and access counting.
- Server-hosted paths cannot escape the configured root; external registrations accept only authorised safe URLs.
- The Pitjantjatjara resource remains external and is not copied, proxied, cached, scraped, or sent to AI services.
- The 485 valid C-LARA bundles receive imported/skipped/failed outcomes with durable diagnostics.
- Every registered local LARA project has exactly one validated `_hyperlinked_text_.html` entry point.
- Large projects are served without exhausting disk space and receive explicit mobile/audio delivery checks.
