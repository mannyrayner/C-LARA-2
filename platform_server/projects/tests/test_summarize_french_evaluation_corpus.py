from __future__ import annotations

import shutil
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from pipeline.stage_artifacts import write_stage_artifact
from projects.management.commands.summarize_french_evaluation_corpus import build_summary, summarize_project
from projects.models import Project


class SummarizeFrenchEvaluationCorpusTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="mannyrayner", password="pw")
        self.project = Project.objects.create(
            owner=self.user,
            title="French fixture",
            language="fr",
            target_language="en",
            source_text="Bonjour le monde",
        )
        shutil.rmtree(self.project.artifact_dir(), ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.project.artifact_dir(), ignore_errors=True)

    def test_summarize_project_counts_segments_tokens_and_whitespace(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_imported"
        write_stage_artifact(
            run_dir,
            "segmentation_phase_2",
            {
                "pages": [
                    {
                        "surface": "Bonjour le monde",
                        "segments": [
                            {
                                "surface": "Bonjour le monde",
                                "tokens": [
                                    {"surface": "Bonjour"},
                                    {"surface": " le"},
                                    {"surface": " monde"},
                                    {"surface": " !"},
                                ],
                            },
                            {"surface": "", "tokens": []},
                        ],
                    }
                ]
            },
        )

        stats = summarize_project(self.project)

        self.assertTrue(stats.has_segmentation_phase_2)
        self.assertEqual(stats.page_count, 1)
        self.assertEqual(stats.segment_count, 2)
        self.assertEqual(stats.token_count, 4)
        self.assertEqual(stats.non_whitespace_token_count, 4)
        self.assertEqual(stats.whitespace_only_token_count, 0)
        self.assertEqual(stats.token_surface_chars_including_whitespace, len("Bonjour le monde !"))
        self.assertEqual(stats.token_surface_chars_excluding_whitespace, len("Bonjourlemonde!"))
        self.assertEqual(stats.segments_with_no_tokens, 1)
        self.assertEqual(stats.tokens_with_leading_or_trailing_whitespace, 3)
        self.assertEqual(stats.punctuation_only_token_count, 1)
        self.assertEqual(stats.average_tokens_per_segment, 2.0)
        self.assertEqual(stats.max_tokens_in_segment, 4)

    def test_build_summary_totals_per_project_stats(self):
        run_dir = self.project.artifact_dir() / "runs" / "run_imported"
        write_stage_artifact(
            run_dir,
            "segmentation_phase_2",
            {"pages": [{"surface": "Salut", "segments": [{"surface": "Salut", "tokens": [{"surface": "Salut"}]}]}]},
        )

        stats = summarize_project(self.project)
        summary = build_summary([stats], username="mannyrayner", language="fr", language_match="exact")

        self.assertEqual(summary["project_count"], 1)
        self.assertEqual(summary["projects_with_segmentation_phase_2"], 1)
        self.assertEqual(summary["segment_count"], 1)
        self.assertEqual(summary["token_count"], 1)
        self.assertEqual(summary["non_whitespace_token_count"], 1)
