# Optional public browsing — 11 October 2026

## Human evidence and request

Manny reports successful AWS email delivery and, on the following morning,
successful password reset followed by login to his test account. The apparent
failure was confusion between two accounts sharing an email address; the reset
message correctly named the test account. Cathy's independent trial is still
pending. This supersedes revision 63's pending initial SMTP/recovery evidence;
it is human-reported acceptance, not an instrumented test performed by the agent.

Manny then asks to add anonymous browse-only access. His earlier scope was
owner-controlled, disabled by default for each dictionary. No particular dictionary
has been authorised for publication by this implementation request.

## Prepared increment

Baseline: main `067cfc7938822858f34782fe2f28f0a532e28a7c`.
Migration `0020_public_browsing` adds a default-off flag and setting revision.

Owners explicitly confirm contributor permission in Settings. Visitors discover
public dictionaries from the login page, or follow a shared link. Pictures,
Words and Sentences retain search, categories, translations, playback and links.
The separate accepted-only projection excludes pending/history/discussion/member
information and grants no write, practice, AI or export permissions. Member
routes retain their original checks. Public-enabled dictionaries show a notice
to members, including the fact that future accepted content will be public.

Every visitor page and media request checks current availability; hidden,
archived and personal dictionaries are excluded. Hiding switches public browsing
off; unhiding does not republish. Existing withdrawal/dependency rules and
synthetic-audio source checks apply. Turning access off cannot recall previously
received content. Public means anyone, including signed-in outsiders and former
members, rather than a secret-link or invitation mode.

## Verification actually performed

- Django system check and migration consistency check pass.
- **536 tests pass** on SQLite/Python 3.12/Django 5.2.17: the full community
  dictionary suite plus email-reset, admin-tools and profile regressions.
- The **22 new public-browsing tests** check default privacy, owner-only explicit
  enablement, CSRF, stale submissions, idempotency, hidden/archive/personal access,
  accepted current-field projection, draft/history/search exclusions, guessed and
  cross-dictionary media IDs, byte ranges/HEAD/416, revocation, withdrawal/restore,
  held dependencies, obsolete synthetic audio, links and absence of AI/write paths.
  Streaming responses are closed in tests for Windows file-cleanup compatibility.
- Disposable Chromium rehearsal passes at **320, 390 and 1280 pixels**. An owner
  enables access; separate visitor contexts discover, search, reveal translations,
  play audio, traverse word/sentence/picture links and fail to obtain an export.
  The owner revokes access; subsequent page and audio requests return 404.
  No browser JavaScript errors or horizontal overflow were detected. Phone and
  desktop screenshots were inspected.
- The browser fixture uses a generated geometric picture and a one-second test
  tone, not community data or a claim about TTS quality. No live AI or SMTP call
  and no AWS change was made. Local browser-launch/extraction issues were resolved
  in the rehearsal environment; they were not application failures.

Run the focused tests with:

```bash
python manage.py test community_dictionary.tests.test_public_browsing
```

The reusable browser harness is `public_browsing_browser_rehearsal.py`, with
`public_browsing_browser_workflow.cjs`. It needs the project's Python dependencies,
Node, Playwright and Chromium. Set `COMMUNITY_PLAYWRIGHT_MODULE` if Playwright is
outside Node's normal lookup path and `COMMUNITY_CHROMIUM_PATH` for an existing
browser (or `COMMUNITY_CHROMIUM_MODULE` for the serverless Chromium ESM module).
It creates a temporary database/private-media directory and never uses the real DB.
From the repository root:

```bash
python experiments/community_dictionary/public_browsing_browser_rehearsal.py /tmp/community-public-browser
```

## Remaining acceptance

Manny's laptop trial, AWS public-view deployment, real-phone public playback and
community publication decisions remain pending. This is not a PostgreSQL load
test or evidence of long-term anonymous-traffic reliability. Anonymous content
still consumes normal hosting/bandwidth. No new independent security audit or
claim of protection against visitors copying public material is made.

Use the [runbook](../../docs/howto/community-public-browsing-install.md) for the
prepared patch. Existing email settings and human-owned project intentions are
unchanged.
