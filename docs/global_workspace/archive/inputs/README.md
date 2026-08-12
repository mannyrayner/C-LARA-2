# Archived human inputs

Each `rev-NNNN/` directory contains the ordered human messages that materially informed that live
global-workspace revision. `input-001.md`, `input-002.md`, and so on preserve the UTF-8 Markdown
given to the update tool; they are immutable project memory, not generated summaries.

Revision 1 is the repository-derived baseline and has no input directory. Revision 2 and revision 3
were backfilled from copies supplied by Manny Rayner after those states were created. Starting with
the next revision, `scripts/render_global_workspace.py --update-from` requires one or more
`--human-input` files and archives them as part of the transition.

Do not edit an archived message to reflect later knowledge. Record a correction as new human input
to a later revision. Do not archive sensitive material without an explicit retention/redaction
decision.
