from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from pipeline.audio import SimpleTTSEngine
from pipeline.compile_html import CompileHTMLSpec, compile_html
from tests.log_utils import log_test_case


class CompileHTMLTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifacts = Path("tests/artifacts/compile_html")
        if self.artifacts.exists():
            shutil.rmtree(self.artifacts)
        (self.artifacts / "audio").mkdir(parents=True, exist_ok=True)
        (self.artifacts / "html").mkdir(parents=True, exist_ok=True)

        engine = SimpleTTSEngine()
        self.token_audio = self.artifacts / "audio" / "token.wav"
        self.segment_audio = self.artifacts / "audio" / "segment.wav"
        self.page_audio = self.artifacts / "audio" / "page.wav"
        engine.synthesize_to_path("token", self.token_audio)
        engine.synthesize_to_path("segment", self.segment_audio)
        engine.synthesize_to_path("page", self.page_audio)

        self.sample_text = {
            "l2": "en",
            "surface": "Hello world",
            "pages": [
                {
                    "surface": "Hello world",
                    "segments": [
                        {
                            "surface": "Hello world",
                            "tokens": [
                                {
                                    "surface": "Hello",
                                    "annotations": {
                                        "lemma": "hello",
                                        "gloss": "salut",
                                        "pos": "INTJ",
                                        "pinyin": "ni hao",
                                        "audio": {"path": str(self.token_audio)},
                                    },
                                },
                                {"surface": " ", "annotations": {}},
                                {
                                    "surface": "world",
                                    "annotations": {
                                        "lemma": "world",
                                        "gloss": "monde",
                                        "pos": "N",
                                        "audio": {"path": str(self.token_audio)},
                                    },
                                },
                            ],
                            "annotations": {
                                "translation": "Bonjour le monde",
                                "audio": {"path": str(self.segment_audio)},
                            },
                        }
                    ],
                    "annotations": {"audio": {"path": str(self.page_audio)}},
                }
            ],
            "annotations": {},
        }

    def test_compile_html_writes_artifacts(self) -> None:
        out_root = self.artifacts / "html"
        result = compile_html(CompileHTMLSpec(text=self.sample_text, output_dir=out_root, run_id="unit"))

        html_path = Path(result["html_path"])
        self.assertTrue(html_path.exists())

        content = html_path.read_text(encoding="utf-8")
        self.assertIn('data-lemma="hello"', content)
        self.assertIn('<ruby><rb>Hello</rb><rt>ni hao</rt></ruby>', content)
        self.assertIn('Bonjour le monde', content)

        concordance_paths = list(Path(result["run_root"]).glob("concordance_*.html"))
        self.assertTrue(concordance_paths, "concordance pages should be emitted")
        concordance_html = concordance_paths[0].read_text(encoding="utf-8")
        static_js = Path(result["run_root"]) / "static" / "clara_scripts.js"
        js_content = static_js.read_text(encoding="utf-8")
        self.assertIn("gloss-popup", js_content)
        self.assertIn("toggle-translation", js_content)

        log_test_case(
            "compile_html:render",
            purpose="renders annotated text and concordance to HTML",
            inputs={"segment": self.sample_text["pages"][0]["segments"][0]},
            output={
                "html_path": str(html_path),
                "concordance_entries": len(result.get("concordance", [])),
                "html_content": content,
                "concordance_sample": concordance_html,
                "static_js": js_content,
            },
            status="pass",
        )


if __name__ == "__main__":
    unittest.main()
