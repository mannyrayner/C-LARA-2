# ISSUE-0023: Allow manual segmentation phase 1 editor when segmentation artifact exists but source text is empty

- **Status:** closed
- **Priority:** P3
- **Created:** 2026-05-23T00:00:00Z
- **Updated:** 2026-05-23T00:00:00Z
- **Origin:** human-suggestion
- **Deadline:** None
- **Dependencies:** [ISSUE-0020](ISSUE-0020.md)
- **Canonical JSON:** [ISSUE-0023.json](ISSUE-0023.json)

## Notes

Low-hanging UI/flow inconsistency: manual top-level showed the Manual segmentation phase 1 control
for imported picture-dictionary projects, but clicking it failed with 'requires source text' even
when segmentation_phase_1 artifact existed. Fixed by making manual_segmentation_phase_1 derive base
text from existing segmentation_phase_1 payload when source text is blank, and only error when both
source text and artifact are absent.
