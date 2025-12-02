"""Tests for pinyin annotation."""
from __future__ import annotations

import unittest

from pipeline import pinyin
from tests.log_utils import log_test_case


class PinyinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_text = {
            "l2": "zh",
            "surface": "我喜欢苹果。",
            "pages": [
                {
                    "surface": "我喜欢苹果。",
                    "segments": [
                        {
                            "surface": "我喜欢苹果。",
                            "tokens": [
                                {"surface": "我"},
                                {"surface": "喜欢"},
                                {"surface": "苹果"},
                                {"surface": "。"},
                            ],
                        }
                    ],
                }
            ],
            "annotations": {},
        }

    def test_adds_pinyin_annotations(self) -> None:
        spec = pinyin.PinyinSpec(text=self.sample_text)
        try:
            annotated = pinyin.annotate_pinyin(spec)
        except ImportError as exc:
            self.skipTest(str(exc))

        tokens = annotated["pages"][0]["segments"][0]["tokens"]
        pinyin_values = [t.get("annotations", {}).get("pinyin") for t in tokens]
        self.assertIsNotNone(pinyin_values[0])
        self.assertTrue(any(p for p in pinyin_values if p))
        self.assertIsNone(tokens[-1].get("annotations", {}).get("pinyin"))

        log_test_case(
            "pinyin:unit",
            purpose="adds pinyin annotations to lexical tokens",
            inputs={"tokens": [t["surface"] for t in self.sample_text["pages"][0]["segments"][0]["tokens"]]},
            output={"pinyin": pinyin_values},
            status="pass",
        )


if __name__ == "__main__":
    unittest.main()
