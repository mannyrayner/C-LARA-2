# Workplan conventions

This directory holds human-owned, cross-cutting project intention needed to interpret C-LARA's
roadmaps and canonical issues. It does not replace either system.

## Canonical ownership

- Roadmaps own long-term feature/research strategy and architecture.
- `docs/issues/issues/*.json` owns tactical issue state, priority, dependencies, and deadlines.
- `docs/issues/index.json` owns the ordered current issue focus.
- The workplan owns information that is often implicit or spans several issues: relationships among
  persistent objectives, external commitments, strategic trade-offs, resource assumptions, known
  cross-cutting constraints, and explicit decisions to defer otherwise desirable work.

Do not copy an issue's state, priority, dependency array, or deadline into the workplan. Link the
issue ID and explain why it matters. If an external commitment has actionable work and a date, create
or update an issue and refer to it here.

## Sprint-minimal representation

Start with one `project-intentions.md` file rather than separate goals, dependencies, deadlines,
priorities, and constraints files. Fragmentation would add synchronization work before the Digital
Minds Research Sprint and could create competing sources of truth.

Use stable IDs and the following sections:

1. persistent objectives (`GOAL-*`), including success criteria and relationships to other goals;
2. external commitments, each linked to a canonical issue where actionable;
3. current human strategic guidance, with author and `as of` date;
4. cross-cutting risks and constraints not owned by one issue;
5. resource assumptions, including available human/AI roles;
6. explicit deferrals and the conditions that would cause reconsideration;
7. unresolved questions for the human coordinator.

Each assertion should identify its human owner and last-confirmed date. The meta-review may report
ambiguity or propose a question, but it must not silently rewrite human intentions. Changes to this
document require ordinary human review and are outside the global-workspace application command's
write allowlist.

If dry runs show that Codex cannot inspect this format reliably, introduce a canonical JSON file
with a deterministic Markdown rendering. Do not introduce both representations until validation and
rendering exist.
