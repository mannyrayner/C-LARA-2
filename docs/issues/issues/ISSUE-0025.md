# ISSUE-0025: Add systematic UI regression tracking for disappearing controls/content

- **Status:** reported
- **Priority:** P1
- **Created:** 2026-05-23T13:26:38Z
- **Updated:** 2026-05-23T13:26:38Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0003](ISSUE-0003.md)
- **Canonical JSON:** [ISSUE-0025.json](ISSUE-0025.json)

## Notes

Suggestion #16 from admin export (submitted by mannyrayner on 2026-05-23). We need a systematic
guard against unintentional UI regressions where controls/content disappear between commits.
Proposed scope: (1) implement an extractor that inventories key controls/content from
templates/views (algorithmic, AI-assisted, or hybrid); (2) persist datestamped snapshots in the
repository (likely under docs/) for diff-based review; (3) add workflow alerts/checks so
implementors are notified whenever UI inventory changes and can confirm intended vs unintended
changes. Also track alignment with docs/roadmap/ai-judges-evaluation.md so UI-regression checks
become part of the broader evaluation/monitoring strategy.
