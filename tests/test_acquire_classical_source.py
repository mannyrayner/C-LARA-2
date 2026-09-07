import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.corpus.acquire_classical_source import VisibleText, acquire_gutenberg, acquire_runeberg


class AcquisitionTests(unittest.TestCase):
    def test_gutenberg_uses_markers_and_preserves_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "source.txt"
            source.write_text("front\n*** START OF THE PROJECT GUTENBERG EBOOK TITLE ***\nBody\n*** END OF THE PROJECT GUTENBERG EBOOK TITLE ***\nback", encoding="utf-8")
            def copy(_url, destination): destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(source.read_bytes())
            with patch("scripts.corpus.acquire_classical_source.download", copy):
                acquire_gutenberg("https://example.test/book.txt", root/"raw.txt", root/"work.txt", root/"record.json")
            self.assertEqual((root/"work.txt").read_text(), "Body\n")
            self.assertIn("front", (root/"raw.txt").read_text())

    def test_visible_text_excludes_navigation_and_scripts(self):
        parser = VisibleText(); parser.feed("<nav>next</nav><p>Jeg elsker Dem.</p><script>bad</script>")
        self.assertEqual(parser.text(), "Jeg elsker Dem.\n")

    def test_runeberg_orders_pages_and_records_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def create(url, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(f"<p>page {Path(url).stem}</p>", encoding="utf-8")
            with patch("scripts.corpus.acquire_classical_source.download", create):
                acquire_runeberg("https://example.test/vol", 7, 8, 4, root/"raw", root/"work.txt", root/"record.json")
            self.assertEqual((root/"work.txt").read_text(), "page 0007\n\npage 0008\n")
            self.assertTrue((root/"raw/0007.html").exists())


if __name__ == "__main__": unittest.main()
