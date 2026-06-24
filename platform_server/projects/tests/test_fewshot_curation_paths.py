from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from pipeline.fewshot_curation import _display_path, _filesystem_path, _read_json, _strip_windows_long_path_prefix, _write_text


class FewshotCurationPathTests(SimpleTestCase):
    def test_filesystem_path_adds_windows_long_path_prefix(self):
        path = Path("C:/cygwin64/home/github/c-lara-2/generated/deep/file.json")

        fs_path = _filesystem_path(path, os_name="nt")

        self.assertTrue(str(fs_path).startswith("\\\\?\\"))

    def test_display_path_strips_windows_long_path_prefix(self):
        path = Path("\\\\?\\C:\\cygwin64\\home\\github\\c-lara-2\\generated\\deep\\file.json")

        display_path = _strip_windows_long_path_prefix(path)

        self.assertEqual(str(display_path), "C:\\cygwin64\\home\\github\\c-lara-2\\generated\\deep\\file.json")

    def test_display_path_can_use_repo_relative_path_after_prefix_strip(self):
        repo_root = Path("C:/repo")
        path = Path("\\\\?\\C:\\repo\\generated\\file.json")

        display = _display_path(path, repo_root)

        # On POSIX this remains absolute because Windows drive paths are not relative to C:/repo,
        # but the extended-length prefix should still be removed for manifests and review summaries.
        self.assertNotIn("\\\\?\\", display)

    def test_write_text_uses_filesystem_path_helper(self):
        logical_path = Path("deep/file.json")
        filesystem_path = Path("/tmp/deep/write-file.json")
        if filesystem_path.exists():
            filesystem_path.unlink()

        with patch("pipeline.fewshot_curation._filesystem_path", return_value=filesystem_path):
            _write_text(logical_path, "hello")

        self.assertEqual(filesystem_path.read_text(encoding="utf-8"), "hello")

    def test_read_json_uses_filesystem_path_helper(self):
        logical_path = Path("deep/file.json")
        filesystem_path = Path("/tmp/deep/file.json")
        filesystem_path.parent.mkdir(parents=True, exist_ok=True)
        filesystem_path.write_text('{"ok": true}\n', encoding="utf-8")

        with patch("pipeline.fewshot_curation._filesystem_path", return_value=filesystem_path):
            payload = _read_json(logical_path)

        self.assertEqual(payload, {"ok": True})
