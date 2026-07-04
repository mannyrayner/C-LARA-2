# ISSUE-0038: Keep picture-dictionary images synchronized when words are deleted

- **Status:** closed
- **Priority:** P1
- **Created:** 2026-06-15T09:32:00Z
- **Updated:** 2026-06-15T10:15:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0020](ISSUE-0020.md), [ISSUE-0037](ISSUE-0037.md)
- **Canonical JSON:** [ISSUE-0038.json](ISSUE-0038.json)

## Notes

Created from human suggestion #28 (submitted by mannyrayner on 2026-06-15). Deleting words from a
picture dictionary appears to leave page images associated with the old page numbers rather than the
remaining words/pages, causing images to go out of sync after page renumbering. Investigate whether
page image directories or metadata are keyed only by page number; if so, preserve image-to-word
identity when entries are removed by moving/renaming directories or introducing a more stable
word/page identifier. This is high priority because deletion is a normal organiser workflow and
stale image associations can corrupt compiled dictionaries, flashcards, subset projects, and
classroom review. Implemented on 2026-06-15 by retargeting surviving entry image paths to their new
canonical page directories during dictionary page sync, moving image/page_NNN directories through
temporary names before stale-page pruning, and adding regression coverage for deleting the first
entry from a three-word picture dictionary.
