from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from urllib.parse import quote

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

        run_root = Path(result["run_root"])
        html_root = run_root / "html"
        concordance_paths = list(html_root.glob("concordance_*.html"))
        self.assertTrue(concordance_paths, "concordance pages should be emitted")
        concordance_html = concordance_paths[0].read_text(encoding="utf-8")
        static_js = html_root / "static" / "clara_scripts.js"
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

    def test_concordance_deduplicates_mwe_segments(self) -> None:
        """Ensure an MWE lemma only appears once per segment in the concordance."""

        out_root = self.artifacts / "html"
        mwe_text = {
            "l2": "en",
            "surface": "The friends sign off together.",
            "pages": [
                {
                    "surface": "The friends sign off together.",
                    "segments": [
                        {
                            "surface": "The friends sign off together.",
                            "tokens": [
                                {"surface": "The", "annotations": {}},
                                {"surface": " ", "annotations": {}},
                                {"surface": "friends", "annotations": {}},
                                {"surface": " ", "annotations": {}},
                                {
                                    "surface": "sign",
                                    "annotations": {
                                        "lemma": "sign off",
                                        "pos": "VERB",
                                        "mwe_id": "m1",
                                        "audio": {"path": str(self.token_audio)},
                                    },
                                },
                                {"surface": " ", "annotations": {}},
                                {
                                    "surface": "off",
                                    "annotations": {
                                        "lemma": "sign off",
                                        "pos": "VERB",
                                        "mwe_id": "m1",
                                        "audio": {"path": str(self.token_audio)},
                                    },
                                },
                                {"surface": " ", "annotations": {}},
                                {"surface": "together", "annotations": {}},
                                {"surface": ".", "annotations": {}},
                            ],
                            "annotations": {"translation": "Les amis finissent ensemble."},
                        }
                    ],
                }
            ],
        }

        result = compile_html(CompileHTMLSpec(text=mwe_text, output_dir=out_root, run_id="mwe"))
        concordance = result.get("concordance", [])
        mwe_entry = next((e for e in concordance if e.get("lemma") == "sign off"), None)
        self.assertIsNotNone(mwe_entry, "MWE lemma should appear in concordance")
        self.assertEqual(
            1,
            len(mwe_entry["occurrences"]),
            "MWE lemma should be listed once per segment in concordance",
        )

    def test_concordance_filenames_are_encoded(self) -> None:
        """Problematic lemma characters should be encoded for concordance filenames."""

        out_root = self.artifacts / "html"
        text_with_quote = self.sample_text.copy()
        text_with_quote["pages"] = [
            {
                "surface": "Hi",
                "segments": [
                    {
                        "surface": "Hi",
                        "tokens": [
                            {
                                "surface": "Hi",
                                "annotations": {
                                    "lemma": '"',
                                    "gloss": "quote",
                                },
                            }
                        ],
                    }
                ],
            }
        ]

        result = compile_html(
            CompileHTMLSpec(text=text_with_quote, output_dir=out_root, run_id="encoded")
        )

        run_root = Path(result["run_root"])
        html_root = run_root / "html"
        encoded_slug = quote('"', safe="~()*!.'-_")
        expected_path = html_root / f"concordance_{encoded_slug}.html"
        self.assertTrue(
            expected_path.exists(),
            f"Expected concordance file {expected_path.name} to be written",
        )

    def test_mwe_tokens_include_encoded_slug(self) -> None:
        """Tokens that belong to an MWE should carry the encoded lemma slug used for concordances."""

        out_root = self.artifacts / "html"
        mwe_text = {
            "l2": "en",
            "surface": "A sharp pain appeared.",
            "pages": [
                {
                    "surface": "A sharp pain appeared.",
                    "segments": [
                        {
                            "surface": "A sharp pain appeared.",
                            "tokens": [
                                {"surface": "A", "annotations": {}},
                                {"surface": " ", "annotations": {}},
                                {
                                    "surface": "sharp",
                                    "annotations": {
                                        "lemma": "sharp pain",
                                        "pos": "NOUN",
                                        "mwe_id": "m2",
                                    },
                                },
                                {"surface": " ", "annotations": {}},
                                {
                                    "surface": "pain",
                                    "annotations": {
                                        "lemma": "sharp pain",
                                        "pos": "NOUN",
                                        "mwe_id": "m2",
                                    },
                                },
                                {"surface": " ", "annotations": {}},
                                {"surface": "appeared", "annotations": {}},
                                {"surface": ".", "annotations": {}},
                            ],
                        }
                    ],
                }
            ],
        }

        result = compile_html(CompileHTMLSpec(text=mwe_text, output_dir=out_root, run_id="mwe-slug"))

        html_path = Path(result["html_path"])
        page_content = html_path.read_text(encoding="utf-8")
        expected_file_slug = quote("sharp pain", safe="~()*!.'-_")
        expected_url_slug = expected_file_slug.replace("%", "%25")
        self.assertIn(f'data-lemma-slug="{expected_url_slug}"', page_content)
        self.assertIn(f'data-lemma-file-slug="{expected_file_slug}"', page_content)

    def test_concordance_loader_preserves_percent_signs(self) -> None:
        """Concordance JS should escape percent signs so encoded slugs resolve to on-disk files."""

        out_root = self.artifacts / "html"
        result = compile_html(CompileHTMLSpec(text=self.sample_text, output_dir=out_root, run_id="percent-safe"))

        scripts_path = Path(result["html_path"]).parent / "static" / "clara_scripts.js"
        script = scripts_path.read_text(encoding="utf-8")

        self.assertIn("lemmaFileSlug", script)
        self.assertIn("replace(/%25/g, '%')", script)


if __name__ == "__main__":
    unittest.main()
