import base64
import json
import shutil

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from unittest.mock import patch

from projects.models import (
    Community,
    CommunityImageVote,
    CommunityMembership,
    CommunityOrganiserReview,
    PictureDictionary,
    Project,
    ProjectImagePage,
    ProjectImagePageVariant,
)


class FakeImageClient:
    def generate_image(self, prompt, **kwargs):
        return {
            "bytes": base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRX0AAAAASUVORK5CYII="
            ),
            "revised_prompt": "community revised",
            "model": kwargs.get("model", "gpt-image-1"),
        }


class CommunityWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="pw")
        self.organiser = User.objects.create_user(username="org", password="pw")
        self.member = User.objects.create_user(username="mem", password="pw")
        self.community = Community.objects.create(name="Iaai C", language="iai")
        CommunityMembership.objects.create(community=self.community, user=self.organiser, role="organiser")
        CommunityMembership.objects.create(community=self.community, user=self.member, role="member")
        self.project = Project.objects.create(
            owner=self.owner,
            title="Community Project",
            source_text="Hello",
            language="iai",
            target_language="fr",
        )
        self.page = ProjectImagePage.objects.create(
            project=self.project,
            page_number=1,
            page_text="Hello",
            generation_prompt="base prompt",
            image_model="gpt-image-1",
            image_path="images/pages/page_001/variant_001.png",
            status="generated",
        )
        self.variant = ProjectImagePageVariant.objects.create(
            page=self.page,
            variant_index=1,
            image_model="gpt-image-1",
            image_path="images/pages/page_001/variant_001.png",
            generation_prompt="base prompt",
            image_revised_prompt="rev",
            status="generated",
        )
        self.page.preferred_variant = self.variant
        self.page.save(update_fields=["preferred_variant", "updated_at"])

    def test_owner_can_assign_and_clear_project_community(self):
        client = Client()
        client.login(username="owner", password="pw")
        # owner is not organiser, so fails
        fail = client.post(reverse("project-community", args=[self.project.pk]), {"community_id": self.community.id}, follow=True)
        self.assertEqual(fail.status_code, 200)
        self.project.refresh_from_db()
        self.assertIsNone(self.project.community)

        # make owner organiser and retry
        CommunityMembership.objects.create(community=self.community, user=self.owner, role="organiser")
        ok = client.post(reverse("project-community", args=[self.project.pk]), {"community_id": self.community.id}, follow=True)
        self.assertEqual(ok.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.community_id, self.community.id)
        self.assertEqual(self.project.access_scope, Project.ACCESS_COMMUNITY)

        clear = client.post(reverse("project-community", args=[self.project.pk]), {"action": "clear"}, follow=True)
        self.assertEqual(clear.status_code, 200)
        self.project.refresh_from_db()
        self.assertIsNone(self.project.community)

    def test_community_tab_and_home_redirect_for_single_membership(self):
        client = Client()
        client.login(username="mem", password="pw")
        project_list = client.get(reverse("project-list"))
        self.assertContains(project_list, reverse("community-home"))
        home = client.get(reverse("community-home"))
        self.assertEqual(home.status_code, 302)
        self.assertIn(reverse("community-member-home", args=[self.community.id]), home["Location"])

    def test_member_can_submit_votes(self):
        self.project.community = self.community
        self.project.save(update_fields=["community", "updated_at"])
        client = Client()
        client.login(username="mem", password="pw")
        resp = client.post(
            reverse("community-member-judge-project", args=[self.community.id, self.project.id]),
            {f"vote_{self.variant.id}": "up", f"note_{self.variant.id}": "nice"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        vote = CommunityImageVote.objects.get(user=self.member, variant=self.variant)
        self.assertEqual(vote.value, "up")
        self.assertEqual(vote.note, "nice")

    def test_organiser_picture_dictionary_controls(self):
        self.project.community = self.community
        self.project.source_text = "Frida sings in Antarctica."
        self.project.save(update_fields=["community", "source_text", "updated_at"])
        client = Client()
        client.login(username="org", password="pw")

        page = client.get(reverse("community-organiser-home", args=[self.community.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Picture dictionary (Phase A)")
        self.assertContains(page, "Ensure dictionary")
        self.assertContains(page, "Add from text")
        self.assertContains(page, "Style brief (used if style is missing)")
        self.assertNotContains(page, "Remove words")

        ensure = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"picture_dictionary_action": "ensure"},
            follow=True,
        )
        self.assertEqual(ensure.status_code, 200)
        dictionary = PictureDictionary.objects.get(community=self.community)
        self.assertEqual(dictionary.organiser_id, self.organiser.id)
        self.assertContains(
            ensure,
            reverse("manual-page-annotation", args=[dictionary.project.id]),
        )

        add_words = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"picture_dictionary_action": "add", "picture_dictionary_words": "Frida, Pinguin"},
            follow=True,
        )
        self.assertEqual(add_words.status_code, 200)
        dictionary.refresh_from_db()
        self.assertIn("Frida", dictionary.project.source_text)

        runs_dir = self.project.artifact_dir() / "runs"
        if runs_dir.exists():
            shutil.rmtree(runs_dir)

        add_from_text = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"picture_dictionary_action": "add_from_text", "source_project_id": str(self.project.id)},
            follow=True,
        )
        self.assertEqual(add_from_text.status_code, 200)
        self.assertContains(add_from_text, "Add from text requires lemma annotations.")

        lemma_run = self.project.artifact_dir() / "runs" / "run_lemma_source" / "stages"
        lemma_run.mkdir(parents=True, exist_ok=True)
        lemma_payload = {
            "l2": "iai",
            "surface": "Frida sings in Antarctica.",
            "pages": [
                {
                    "segments": [
                        {
                            "tokens": [
                                {"surface": "Frida", "annotations": {"lemma": "Frida", "pos": "PROPN"}},
                                {"surface": "sings", "annotations": {"lemma": "sing", "pos": "VERB"}},
                                {"surface": "Antarctica", "annotations": {"lemma": "Antarctica", "pos": "PROPN"}},
                            ]
                        }
                    ]
                }
            ],
        }
        (lemma_run / "lemma.json").write_text(json.dumps(lemma_payload), encoding="utf-8")
        add_from_text = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"picture_dictionary_action": "add_from_text", "source_project_id": str(self.project.id)},
            follow=True,
        )
        self.assertEqual(add_from_text.status_code, 200)
        dictionary.refresh_from_db()
        self.assertIn("Antarctica", dictionary.project.source_text)
        compile_missing_style = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"picture_dictionary_action": "compile"},
            follow=True,
        )
        self.assertEqual(compile_missing_style.status_code, 200)
        self.assertContains(compile_missing_style, "Style is missing. Enter a style brief and compile again.")

        with patch("projects.views._generate_project_image_style") as mock_generate_style:
            mock_generate_style.return_value = {
                "expanded_style_description": "Watercolor style.",
                "representative_excerpt": "Frida sings in Antarctica.",
                "sample_image_prompt": "A watercolor penguin scene.",
                "_request_payload": {"prompt": "style prompt"},
                "_response_payload": {"expanded_style_description": "Watercolor style."},
            }
            compile_dictionary = client.post(
                reverse("community-organiser-home", args=[self.community.id]),
                {
                    "picture_dictionary_action": "compile",
                    "picture_dictionary_style_brief": "Soft watercolor, pastel palette.",
                },
                follow=True,
            )
        self.assertEqual(compile_dictionary.status_code, 200)
        self.assertContains(compile_dictionary, "Created dictionary image style from the provided style brief.")
        self.assertContains(compile_dictionary, "Picture dictionary compilation started. This may take a while.")
        self.assertContains(compile_dictionary, "Dictionary text compilation started for")
        self.assertContains(compile_dictionary, "Text phase 1/3: syncing dictionary entries to image pages.")
        self.assertContains(compile_dictionary, "Text phase 2/3: writing segmentation and annotation stage artifacts.")
        self.assertContains(compile_dictionary, "Text phase 3/3: running annotation pipeline")
        self.assertContains(compile_dictionary, "Dictionary image compilation started for")
        self.assertContains(compile_dictionary, "Picture dictionary compilation complete.")
        self.assertContains(compile_dictionary, "Current style brief:")
        self.assertContains(compile_dictionary, "Soft watercolor, pastel palette.")

        dictionary_entries = list(dictionary.entries.filter(is_active=True).order_by("id"))
        self.assertTrue(dictionary_entries)
        remove_selected = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"picture_dictionary_action": "remove_selected", "remove_entry": [str(dictionary_entries[0].id)]},
            follow=True,
        )
        self.assertEqual(remove_selected.status_code, 200)
        dictionary_entries[0].refresh_from_db()
        self.assertFalse(dictionary_entries[0].is_active)
        self.assertContains(remove_selected, "Last dictionary compile:")

    @patch("projects.views._build_ai_client")
    def test_organiser_review_can_generate_requested_variants_and_mark_reviewed(self, mock_build_ai_client):
        self.project.community = self.community
        self.project.save(update_fields=["community", "updated_at"])
        mock_build_ai_client.return_value = FakeImageClient()
        client = Client()
        client.login(username="org", password="pw")
        resp = client.post(
            reverse("community-organiser-review-project", args=[self.community.id, self.project.id]),
            {"action": "generate_requested", "image_model": "gpt-image-1", f"request_count_{self.page.id}": "2"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Generating 2 requested variant(s). Please wait")
        self.assertContains(resp, "Generated 2 new variant(s) from organiser requests.")
        self.assertEqual(ProjectImagePageVariant.objects.filter(page=self.page).count(), 3)

        reviewed = client.post(
            reverse("community-organiser-review-project", args=[self.community.id, self.project.id]),
            {"action": "mark_reviewed", "review_note": "done"},
            follow=True,
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertTrue(
            CommunityOrganiserReview.objects.filter(
                community=self.community, project=self.project, organiser=self.organiser
            ).exists()
        )
