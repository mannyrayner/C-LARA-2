import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import render_global_workspace as workspace


class GlobalWorkspaceArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the immutable first revision as the fixture so later live revisions do
        # not silently change the semantics of these archive-transition tests.
        cls.baseline_path = (
            workspace.DEFAULT_ARCHIVE / "rev-0001-2026-08-12.json"
        )
        cls.baseline_bytes = cls.baseline_path.read_bytes()
        cls.baseline = json.loads(cls.baseline_bytes)

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.live_json = self.root / "current_state.json"
        self.live_markdown = self.root / "current_state.md"
        self.archive = self.root / "archive"
        self.archive.mkdir()
        self.human_input = self.root / "human-input.md"
        self.human_input.write_text("Test human input.\n", encoding="utf-8")
        self.live_json.write_bytes(self.baseline_bytes)
        self.live_markdown.write_text(workspace.render(self.baseline), encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_archive_is_idempotent_and_preserves_exact_json(self):
        rendered = workspace.render(self.baseline)
        json_path, markdown_path, created = workspace.ensure_archived(
            self.baseline, self.baseline_bytes, rendered, self.archive
        )
        self.assertTrue(created)
        self.assertEqual(json_path.name, "rev-0001-2026-08-12.json")
        self.assertEqual(json_path.read_bytes(), self.baseline_bytes)
        self.assertEqual(markdown_path.read_text(encoding="utf-8"), rendered)

        _, _, created_again = workspace.ensure_archived(
            self.baseline, self.baseline_bytes, rendered, self.archive
        )
        self.assertFalse(created_again)

    def test_archive_refuses_conflicting_revision(self):
        rendered = workspace.render(self.baseline)
        json_path, _, _ = workspace.ensure_archived(
            self.baseline, self.baseline_bytes, rendered, self.archive
        )
        json_path.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(workspace.WorkspaceValidationError, "conflicting archive"):
            workspace.ensure_archived(
                self.baseline, self.baseline_bytes, rendered, self.archive
            )

    def test_human_input_archive_is_idempotent_and_refuses_conflicts(self):
        paths, created = workspace.ensure_inputs_archived(
            self.archive, 2, [self.human_input]
        )
        self.assertEqual(len(created), 1)
        self.assertEqual(paths[0].read_bytes(), self.human_input.read_bytes())
        _, created_again = workspace.ensure_inputs_archived(
            self.archive, 2, [self.human_input]
        )
        self.assertEqual(created_again, [])

        conflicting = self.root / "conflicting.md"
        conflicting.write_text("Different human input.\n", encoding="utf-8")
        with self.assertRaisesRegex(workspace.WorkspaceValidationError, "conflicting human input"):
            workspace.ensure_inputs_archived(self.archive, 2, [conflicting])

    def test_apply_update_archives_live_state_before_installing_next_revision(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["workspace_revision"] = 2
        candidate["as_of"] = "2026-08-13T00:00:00Z"
        candidate["changes_from_previous_revision"]["summary"] = "Test revision."
        candidate_path = self.root / "candidate.json"
        candidate_path.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")

        archived_json, archived_markdown = workspace.apply_update(
            candidate_path,
            self.live_json,
            self.live_markdown,
            self.archive,
            [self.human_input],
        )

        self.assertEqual(archived_json.read_bytes(), self.baseline_bytes)
        self.assertEqual(archived_markdown.read_text(encoding="utf-8"), workspace.render(self.baseline))
        self.assertEqual(json.loads(self.live_json.read_text())["workspace_revision"], 2)
        self.assertEqual(self.live_markdown.read_text(encoding="utf-8"), workspace.render(candidate))
        self.assertEqual(
            (self.archive / "inputs/rev-0002/input-001.md").read_bytes(),
            self.human_input.read_bytes(),
        )
        self.assertTrue((self.archive / "rev-0002-2026-08-13.json").is_file())

    def test_apply_update_requires_exactly_next_revision(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["workspace_revision"] = 3
        candidate_path = self.root / "candidate.json"
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

        with self.assertRaisesRegex(workspace.WorkspaceValidationError, "exactly one greater"):
            workspace.apply_update(
                candidate_path,
                self.live_json,
                self.live_markdown,
                self.archive,
                [self.human_input],
            )
        self.assertEqual(list(self.archive.iterdir()), [])

    def test_apply_update_refuses_stale_live_markdown(self):
        self.live_markdown.write_text("stale\n", encoding="utf-8")
        candidate = copy.deepcopy(self.baseline)
        candidate["workspace_revision"] = 2
        candidate_path = self.root / "candidate.json"
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

        with self.assertRaisesRegex(workspace.WorkspaceValidationError, "live Markdown is stale"):
            workspace.apply_update(
                candidate_path,
                self.live_json,
                self.live_markdown,
                self.archive,
                [self.human_input],
            )
        self.assertEqual(list(self.archive.iterdir()), [])

    def test_apply_update_requires_human_input_for_next_revision(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["workspace_revision"] = 2
        candidate_path = self.root / "candidate.json"
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

        with self.assertRaisesRegex(workspace.WorkspaceValidationError, "requires at least one"):
            workspace.apply_update(
                candidate_path, self.live_json, self.live_markdown, self.archive, []
            )


if __name__ == "__main__":
    unittest.main()
