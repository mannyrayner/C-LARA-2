import base64
import json
import shutil

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from pipeline.stage_artifacts import read_stage_artifact, write_stage_artifact

from projects import views
from projects.models import (
    Community,
    CommunityImageVote,
    CommunityMembership,
    CommunityOrganiserReview,
    PictureDictionary,
    Project,
    ProjectImagePage,
    ProjectImagePageVariant,
    ProjectImageStyle,
    TaskUpdate,
)


class FakeImageClient:
    async def chat_text(self, prompt, **kwargs):  # noqa: ARG002
        text = str(prompt)
        json_start = text.find("{")
        if json_start >= 0:
            try:
                payload = json.loads(text[json_start:])
                base_prompt = str(payload.get("base_prompt") or "").strip()
                if base_prompt:
                    return base_prompt
            except Exception:
                pass
        return "Constructed prompt for image generation."

    def generate_image(self, prompt, **kwargs):
        return {
            "bytes": base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRX0AAAAASUVORK5CYII="
            ),
            "revised_prompt": "community revised",
            "model": kwargs.get("model", "gpt-image-1"),
        }

class FakeDictionaryMixupClient:
    async def chat_json(self, prompt, **kwargs):  # noqa: ARG002
        row_json = str(prompt).split("Row:", 1)[-1].strip()
        try:
            row = json.loads(row_json)
        except json.JSONDecodeError:
            row = {}
        translation = str(row.get("translation") or "").strip().lower()
        surface = str(row.get("surface") or "").strip()
        is_warning = translation == "pama"
        return {
            "warning": is_warning,
            "reason": (
                f"The gloss/translation ‘{translation}’ does not look like English, while the page text ‘{surface}’ does."
                if is_warning
                else "The gloss/translation looks like English."
            ),
            "confidence": "high" if is_warning else "low",
        }

class FakeNoDictionaryMixupClient:
    async def chat_json(self, prompt, **kwargs):  # noqa: ARG002
        return {"warnings": []}

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
        self.style = ProjectImageStyle.objects.create(project=self.project)
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


    def test_organiser_can_manage_ordinary_community_members(self):
        User = get_user_model()
        newcomer = User.objects.create_user(username="newbie", password="pw")
        client = Client()
        client.login(username="org", password="pw")

        page = client.get(reverse("community-organiser-home", args=[self.community.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Community members")
        self.assertContains(page, "mem (member)")

        added = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"community_membership_action": "add_member", "user": str(newcomer.id)},
            follow=True,
        )
        self.assertEqual(added.status_code, 200)
        self.assertContains(added, "Added newbie as a member")
        self.assertTrue(
            CommunityMembership.objects.filter(
                community=self.community, user=newcomer, role=CommunityMembership.ROLE_MEMBER
            ).exists()
        )

        duplicate = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"community_membership_action": "add_member", "user": str(newcomer.id)},
            follow=True,
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, "newbie is already in")
        self.assertEqual(CommunityMembership.objects.filter(community=self.community, user=newcomer).count(), 1)

        newcomer_membership = CommunityMembership.objects.get(community=self.community, user=newcomer)
        removed = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"community_membership_action": "remove_member", "membership_id": str(newcomer_membership.id)},
            follow=True,
        )
        self.assertEqual(removed.status_code, 200)
        self.assertContains(removed, "Removed newbie from")
        self.assertFalse(CommunityMembership.objects.filter(community=self.community, user=newcomer).exists())

    def test_organiser_membership_management_enforces_boundaries(self):
        User = get_user_model()
        other_organiser = User.objects.create_user(username="otherorg", password="pw")
        other_community = Community.objects.create(name="Other", language="fr")
        CommunityMembership.objects.create(
            community=other_community, user=other_organiser, role=CommunityMembership.ROLE_ORGANISER
        )
        client = Client()
        client.login(username="org", password="pw")

        remove_self = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"community_membership_action": "remove_member", "membership_id": str(CommunityMembership.objects.get(community=self.community, user=self.organiser).id)},
            follow=True,
        )
        self.assertEqual(remove_self.status_code, 200)
        self.assertContains(remove_self, "You cannot remove your own organiser membership")
        self.assertTrue(CommunityMembership.objects.filter(community=self.community, user=self.organiser).exists())

        remove_other_organiser = client.post(
            reverse("community-organiser-home", args=[other_community.id]),
            {"community_membership_action": "remove_member", "membership_id": str(CommunityMembership.objects.get(community=other_community, user=other_organiser).id)},
        )
        self.assertEqual(remove_other_organiser.status_code, 404)
        self.assertTrue(CommunityMembership.objects.filter(community=other_community, user=other_organiser).exists())

        member_client = Client()
        member_client.login(username="mem", password="pw")
        member_response = member_client.get(reverse("community-organiser-home", args=[self.community.id]))
        self.assertEqual(member_response.status_code, 404)

    def test_organiser_can_import_project_as_picture_dictionary_copy_from_ui(self):
        self.project.community = self.community
        self.project.access_scope = Project.ACCESS_COMMUNITY
        self.project.title = "50 words in Kok Kaper"
        self.project.save(update_fields=["community", "access_scope", "title", "updated_at"])
        run_dir = self.project.artifact_dir() / "runs" / "run_seed"
        write_stage_artifact(
            run_dir,
            "gloss",
            {
                "pages": [
                    {
                        "surface": "50 words in Kok Kaper",
                        "segments": [
                            {
                                "tokens": [
                                    {"surface": "50"},
                                    {"surface": "words"},
                                    {"surface": "in"},
                                    {"surface": "Kok"},
                                    {"surface": "Kaper"},
                                ],
                                "annotations": {"translation": "50 words in Kok Kaper"},
                            }
                        ],
                        "annotations": {},
                    },
                    {
                        "surface": "pama",
                        "segments": [
                            {
                                "tokens": [
                                    {
                                        "surface": "pama",
                                        "annotations": {"lemma": "pama", "pos": "NOUN", "gloss": "person"},
                                    }
                                ],
                                "annotations": {},
                            }
                        ],
                        "annotations": {},
                    },
                ]
            },
        )
        rel = "images/pages/page_002/variant_001.png"
        image_path = self.project.artifact_dir() / rel
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"fake-pama")
        ProjectImagePage.objects.create(
            project=self.project,
            page_number=2,
            page_text="pama",
            image_path=rel,
            status=ProjectImagePage.STATUS_APPROVED,
        )

        client = Client()
        client.login(username="org", password="pw")
        response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"picture_dictionary_action": "import_from_project", "source_project_id": str(self.project.id)},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Imported “50 words in Kok Kaper” as a picture dictionary copy with 1 entry")
        dictionary = PictureDictionary.objects.get(community=self.community)
        self.assertNotEqual(dictionary.project_id, self.project.id)
        self.assertEqual(list(dictionary.entries.values_list("surface", flat=True)), ["pama"])
        self.assertNotIn("50", dictionary.project.source_text)

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

    def test_member_image_review_entry_point_and_preferred_variant_label(self):
        self.project.community = self.community
        self.project.save(update_fields=["community", "updated_at"])
        client = Client()
        client.login(username="mem", password="pw")

        home = client.get(reverse("community-member-home", args=[self.community.id]))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, "Judge page images")
        self.assertContains(home, f"Judge images for {self.project.title}")

        judge = client.get(reverse("community-member-judge-project", args=[self.community.id, self.project.id]))
        self.assertEqual(judge.status_code, 200)
        self.assertContains(judge, "Current preferred image")
        self.assertContains(judge, "variant 1")
        self.assertContains(judge, "current preferred image")

    def test_member_can_load_compiled_variant_image_for_community_project(self):
        self.project.community = self.community
        self.project.access_scope = Project.ACCESS_COMMUNITY
        self.project.is_published = False
        self.project.save(update_fields=["community", "access_scope", "is_published", "updated_at"])
        image_abs = self.project.artifact_dir() / self.variant.image_path
        image_abs.parent.mkdir(parents=True, exist_ok=True)
        image_abs.write_bytes(b"fake-image")

        client = Client()
        client.login(username="mem", password="pw")
        image_url = reverse("project-compiled", args=[self.project.id, self.variant.image_path])
        image_resp = client.get(image_url)
        self.assertEqual(image_resp.status_code, 200)
        self.assertEqual(image_resp.content, b"fake-image")

    def test_member_and_organiser_review_show_source_and_translation_context(self):
        self.project.community = self.community
        self.project.source_text = "Source page text from project"
        self.project.save(update_fields=["community", "source_text", "updated_at"])
        run_dir = self.project.artifact_dir() / "runs" / "run_translation" / "stages"
        run_dir.mkdir(parents=True, exist_ok=True)
        translation_payload = {
            "pages": [
                {"segments": [{"annotations": {"translation": "Bonjour la page"}}]},
            ]
        }
        (run_dir / "translation.json").write_text(json.dumps(translation_payload), encoding="utf-8")

        member_client = Client()
        member_client.login(username="mem", password="pw")
        judge = member_client.get(reverse("community-member-judge-project", args=[self.community.id, self.project.id]))
        self.assertEqual(judge.status_code, 200)
        self.assertContains(judge, "Source page text")
        self.assertContains(judge, "Source page text from project")
        self.assertContains(judge, "Page translation")
        self.assertContains(judge, "Bonjour la page")

        organiser_client = Client()
        organiser_client.login(username="org", password="pw")
        review = organiser_client.get(reverse("community-organiser-review-project", args=[self.community.id, self.project.id]))
        self.assertEqual(review.status_code, 200)
        self.assertContains(review, "Source page text")
        self.assertContains(review, "Source page text from project")
        self.assertContains(review, "Page translation")
        self.assertContains(review, "Bonjour la page")

    def test_review_does_not_mirror_source_into_translation_when_translation_missing(self):
        self.project.community = self.community
        self.project.source_text = "Makerr"
        self.project.page_image_text_source = Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION
        self.project.save(update_fields=["community", "source_text", "page_image_text_source", "updated_at"])
        member_client = Client()
        member_client.login(username="mem", password="pw")
        judge = member_client.get(reverse("community-member-judge-project", args=[self.community.id, self.project.id]))
        self.assertEqual(judge.status_code, 200)
        self.assertContains(judge, "Source page text")
        self.assertContains(judge, "Makerr")
        self.assertContains(judge, "Page translation:")
        self.assertContains(judge, "not available")

    def test_organiser_image_review_entry_point_and_preferred_variant_label(self):
        self.project.community = self.community
        self.project.save(update_fields=["community", "updated_at"])
        client = Client()
        client.login(username="org", password="pw")

        home = client.get(reverse("community-organiser-home", args=[self.community.id]))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, "Image review dashboard")
        self.assertContains(home, f"Review images for {self.project.title}")

        review = client.get(reverse("community-organiser-review-project", args=[self.community.id, self.project.id]))
        self.assertEqual(review.status_code, 200)
        self.assertContains(review, "Current preferred image")
        self.assertContains(review, "variant 1")
        self.assertContains(review, "current preferred image")
        self.assertContains(review, "All pages")

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
        self.assertContains(page, "Sync dictionary text + placeholder stages (no image generation)")
        self.assertContains(page, "Add from text")
        self.assertContains(page, "Import as dictionary copy")
        self.assertContains(page, "Style brief (used if style is missing)")
        self.assertContains(page, "low-resource mode is preselected")
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

        with patch("projects.views._generate_project_image_style") as mock_generate_style, patch(
            "projects.views.async_task"
        ) as mock_async_task:
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
            )
        self.assertEqual(compile_dictionary.status_code, 302)
        self.assertIn("/compile/monitor/", compile_dictionary["Location"])
        self.assertTrue(mock_async_task.called)
        scheduled = mock_async_task.call_args
        self.assertEqual(scheduled.args[0].__name__, "_run_picture_dictionary_compile_task")
        self.assertEqual(scheduled.args[1], dictionary.id)
        self.assertEqual(scheduled.args[2], self.organiser.id)
        report_id = scheduled.args[3]
        dictionary.project.refresh_from_db()
        self.assertEqual(dictionary.project.page_image_text_source, Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION)

        scheduled.args[0](*scheduled.args[1:4])
        self.assertTrue(
            TaskUpdate.objects.filter(report_id=report_id, user=self.organiser, message__icontains="Text phase 1/3").exists()
        )
        status = client.get(reverse("project-compile-status", args=[dictionary.project.id, report_id]))
        self.assertEqual(status.status_code, 200)
        payload = status.json()
        self.assertIn("messages", payload)
        self.assertTrue(any("Picture dictionary compilation complete." in msg for msg in payload["messages"]))

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


    def test_low_resource_organiser_can_add_annotated_dictionary_rows(self):
        client = Client()
        client.login(username="org", password="pw")

        page = client.get(reverse("community-organiser-home", args=[self.community.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Add new low-resource dictionary words")
        self.assertContains(page, "Create new images")
        self.assertContains(page, "Gloss (= translation)")
        self.assertNotContains(page, "Translation (optional)")
        self.assertNotContains(page, "Words (comma or newline separated)")

        response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "low_resource_surface": ["pama", ""],
                "low_resource_lemma": ["pama", ""],
                "low_resource_pos": ["NOUN", ""],
                "low_resource_gloss": ["person", ""],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Added 1 and updated 0 low-resource dictionary row")
        self.assertContains(response, "Pending new images:</strong> 1", html=False)
        dictionary = PictureDictionary.objects.get(community=self.community)
        entry = dictionary.entries.get(surface="pama")
        self.assertEqual(entry.lemma, "pama")
        self.assertEqual(entry.pos, "NOUN")
        dictionary.project.refresh_from_db()
        self.assertIn("pama", dictionary.project.source_text)

        run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary"
        lemma_payload = read_stage_artifact(run_dir, "lemma")
        gloss_payload = read_stage_artifact(run_dir, "gloss")
        translation_payload = read_stage_artifact(run_dir, "translation")
        lemma_token = lemma_payload["pages"][0]["segments"][0]["tokens"][0]
        gloss_token = gloss_payload["pages"][0]["segments"][0]["tokens"][0]
        translation_segment = translation_payload["pages"][0]["segments"][0]
        self.assertEqual(lemma_token["annotations"]["lemma"], "pama")
        self.assertEqual(lemma_token["annotations"]["pos"], "NOUN")
        self.assertEqual(gloss_token["annotations"]["gloss"], "person")
        self.assertEqual(translation_segment["annotations"]["translation"], "person")

        # Pending-image counts should use current image pages as a fallback, so
        # the dashboard is not stale if page-image generation has filled the
        # page image path before the registry row has been synced.
        page_row = ProjectImagePage.objects.get(project=dictionary.project, page_number=1)
        page_row.image_path = "images/pages/page_001/variant_001.png"
        page_row.save(update_fields=["image_path", "updated_at"])
        updated_page = client.get(reverse("community-organiser-home", args=[self.community.id]))
        self.assertContains(updated_page, "Pending new images:</strong> 0", html=False)

    def test_dictionary_mixup_postprocessing_suppresses_valid_english_glosses(self):
        for translation in ("sky", "car", "non protein food, vegetable food source", "ire, firewood"):
            warning = views._picture_dictionary_single_mixup_warning_from_payload(
                {"warning": True, "reason": "over-eager", "confidence": "high"},
                row_number=1,
                surface="Path-ch’rrich",
                translation=translation,
                translation_language="en",
            )
            self.assertIsNone(warning)

        warning = views._picture_dictionary_single_mixup_warning_from_payload(
            {"warning": True, "reason": "looks swapped", "confidence": "high"},
            row_number=2,
            surface="long",
            translation="yelkarr’ng",
            translation_language="en",
        )
        self.assertIsNotNone(warning)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("projects.views._build_ai_client")
    def test_low_resource_add_warns_on_surface_translation_mixup(self, mock_build_ai_client):
        mock_build_ai_client.return_value = FakeDictionaryMixupClient()
        client = Client()
        client.login(username="org", password="pw")

        response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "low_resource_surface": ["pama", "person"],
                "low_resource_lemma": ["pama", "person"],
                "low_resource_pos": ["NOUN", "NOUN"],
                "low_resource_gloss": ["person", "pama"],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Possible surface/translation mix-up")
        self.assertContains(response, "row 2: word ‘person’ with gloss ‘pama’")
        self.assertGreaterEqual(mock_build_ai_client.call_count, 2)
        dictionary = PictureDictionary.objects.get(community=self.community)
        self.assertFalse(dictionary.entries.filter(surface="person", is_active=True).exists())
        self.assertFalse(dictionary.entries.filter(surface="pama", is_active=True).exists())

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("projects.views._build_ai_client")
    def test_organiser_review_warns_on_legacy_dictionary_mixup(self, mock_build_ai_client):
        client = Client()
        client.login(username="org", password="pw")
        mock_build_ai_client.return_value = FakeNoDictionaryMixupClient()
        created = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "low_resource_surface": ["pama"],
                "low_resource_lemma": ["pama"],
                "low_resource_pos": ["NOUN"],
                "low_resource_gloss": ["person"],
            },
            follow=True,
        )
        self.assertEqual(created.status_code, 200)
        dictionary = PictureDictionary.objects.get(community=self.community)
        entry = dictionary.entries.get(surface="pama")
        entry.surface = "person"
        entry.lemma = "person"
        entry.save(update_fields=["surface", "lemma", "updated_at"])
        run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary"
        translation_payload = read_stage_artifact(run_dir, "translation")
        translation_payload["pages"][0]["segments"][0]["annotations"]["translation"] = "pama"
        write_stage_artifact(run_dir, "translation", translation_payload)
        gloss_payload = read_stage_artifact(run_dir, "gloss")
        gloss_payload["pages"][0]["segments"][0]["tokens"][0]["annotations"]["gloss"] = "pama"
        write_stage_artifact(run_dir, "gloss", gloss_payload)
        mock_build_ai_client.return_value = FakeDictionaryMixupClient()

        response = client.get(
            reverse("community-organiser-review-project", args=[self.community.id, dictionary.project.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Possible dictionary word/gloss mix-ups")
        self.assertContains(response, "word <strong>person</strong>, gloss/translation <strong>pama</strong>", html=False)

    def test_low_resource_remove_selected_cleans_project_pages_and_stage_artifacts(self):
        client = Client()
        client.login(username="org", password="pw")
        response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "low_resource_surface": ["xxx", "yyy"],
                "low_resource_lemma": ["xxx", "yyy"],
                "low_resource_pos": ["NOUN", "NOUN"],
                "low_resource_gloss": ["dummy x", "dummy y"],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        dictionary = PictureDictionary.objects.get(community=self.community)
        entries = list(dictionary.entries.filter(surface__in=["xxx", "yyy"]).order_by("surface"))
        self.assertEqual(len(entries), 2)
        self.assertEqual(ProjectImagePage.objects.filter(project=dictionary.project).count(), 2)
        for page_number, entry in enumerate(entries, start=1):
            rel_path = f"images/pages/page_{page_number:03d}/variant_001.png"
            image_path = dictionary.project.artifact_dir() / rel_path
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(f"stale-{entry.surface}".encode("utf-8"))
            entry.image_path = rel_path
            entry.current_page_number = page_number
            entry.save(update_fields=["image_path", "current_page_number", "updated_at"])
            page = ProjectImagePage.objects.get(project=dictionary.project, page_number=page_number)
            page.image_path = rel_path
            page.save(update_fields=["image_path", "updated_at"])

        response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "remove_selected",
                "remove_entry": [str(entry.id) for entry in entries],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Removed 2 selected dictionary entries")
        self.assertFalse(dictionary.entries.filter(surface__in=["xxx", "yyy"], is_active=True).exists())
        dictionary.project.refresh_from_db()
        self.assertNotIn("xxx", dictionary.project.source_text)
        self.assertNotIn("yyy", dictionary.project.source_text)
        self.assertFalse(ProjectImagePage.objects.filter(project=dictionary.project, page_text__in=["xxx", "yyy"]).exists())
        self.assertEqual(ProjectImagePage.objects.filter(project=dictionary.project).count(), 0)
        self.assertFalse((dictionary.project.artifact_dir() / "images/pages/page_001").exists())
        self.assertFalse((dictionary.project.artifact_dir() / "images/pages/page_002").exists())
        for entry in entries:
            entry.refresh_from_db()
            self.assertEqual(entry.image_path, "")
        run_dir = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary"
        seg1_payload = read_stage_artifact(run_dir, "segmentation_phase_1")
        lemma_payload = read_stage_artifact(run_dir, "lemma")
        self.assertEqual(seg1_payload.get("pages"), [])
        self.assertEqual(lemma_payload.get("pages"), [])

        readded = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "low_resource_surface": ["xxx"],
                "low_resource_lemma": ["xxx"],
                "low_resource_pos": ["NOUN"],
                "low_resource_gloss": ["dummy x"],
            },
            follow=True,
        )
        self.assertEqual(readded.status_code, 200)
        reactivated = dictionary.entries.get(surface="xxx")
        self.assertTrue(reactivated.is_active)
        self.assertEqual(reactivated.image_path, "")
        readded_page = ProjectImagePage.objects.get(project=dictionary.project, page_text="xxx")
        self.assertEqual(readded_page.image_path, "")
        self.assertFalse((dictionary.project.artifact_dir() / "images/pages/page_001").exists())

    def test_ai_capable_organiser_keeps_plain_dictionary_word_entry(self):
        ai_community = Community.objects.create(name="French community", language="fr")
        CommunityMembership.objects.create(community=ai_community, user=self.organiser, role="organiser")
        client = Client()
        client.login(username="org", password="pw")

        page = client.get(reverse("community-organiser-home", args=[ai_community.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Words (comma or newline separated)")
        self.assertContains(page, "Compile dictionary (sync pages + annotation + images)")
        self.assertNotContains(page, "Add new low-resource dictionary words")
        self.assertNotContains(page, "Create new images")

    def test_low_resource_compile_blocks_when_gloss_or_translation_missing(self):
        client = Client()
        client.login(username="org", password="pw")
        client.post(reverse("community-organiser-home", args=[self.community.id]), {"picture_dictionary_action": "ensure"})
        blocked = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "compile",
                "picture_dictionary_low_resource_mode": "1",
            },
            follow=True,
        )
        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "Compile temporarily blocked")

    def test_mark_reviewed_promotes_member_upvoted_variant_to_preferred(self):
        self.project.community = self.community
        self.project.save(update_fields=["community", "updated_at"])
        second_variant = ProjectImagePageVariant.objects.create(
            page=self.page,
            variant_index=2,
            image_model="gpt-image-1",
            image_path="images/pages/page_001/variant_002.png",
            generation_prompt="alternate prompt",
            image_revised_prompt="alternate revised",
            status="generated",
        )

        member_client = Client()
        member_client.login(username="mem", password="pw")
        vote_response = member_client.post(
            reverse("community-member-judge-project", args=[self.community.id, self.project.id]),
            {f"vote_{second_variant.id}": "up", f"note_{second_variant.id}": "best match"},
            follow=True,
        )
        self.assertEqual(vote_response.status_code, 200)

        organiser_client = Client()
        organiser_client.login(username="org", password="pw")
        reviewed = organiser_client.post(
            reverse("community-organiser-review-project", args=[self.community.id, self.project.id]),
            {"action": "mark_reviewed", "review_note": "looks good"},
            follow=True,
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertContains(reviewed, "Updated preferred image for 1 page")

        self.page.refresh_from_db()
        self.assertEqual(self.page.preferred_variant_id, second_variant.id)
        self.assertEqual(self.page.image_path, second_variant.image_path)

        member_page = member_client.get(reverse("community-member-judge-project", args=[self.community.id, self.project.id]))
        self.assertEqual(member_page.status_code, 200)
        self.assertContains(member_page, "Current preferred image:</strong> variant 2", html=False)
        self.assertContains(member_page, "current preferred image")

    @patch("projects.views._build_ai_client")
    def test_organiser_review_can_generate_requested_variants_and_mark_reviewed(self, mock_build_ai_client):
        self.project.community = self.community
        self.project.save(update_fields=["community", "updated_at"])
        mock_build_ai_client.return_value = FakeImageClient()
        client = Client()
        client.login(username="org", password="pw")
        resp = client.post(
            reverse("community-organiser-review-project", args=[self.community.id, self.project.id]),
            {"action": "generate_requested_preview", "image_model": "gpt-image-1", f"request_count_{self.page.id}": "2"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Proposed generation plan")

        resp_confirm = client.post(
            reverse("community-organiser-review-project", args=[self.community.id, self.project.id]),
            {"action": "generate_requested", "image_model": "gpt-image-1", f"request_count_{self.page.id}": "2"},
            follow=True,
        )
        self.assertEqual(resp_confirm.status_code, 200)
        self.assertContains(resp_confirm, "Generating 2 requested variant(s).")
        self.assertContains(resp_confirm, "Generated 2 new variant(s) from organiser requests.")
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


    def test_organiser_review_selected_pages_filter_preserves_checked_pages(self):
        self.project.community = self.community
        self.project.save(update_fields=["community", "updated_at"])
        second_page = ProjectImagePage.objects.create(
            project=self.project,
            page_number=2,
            page_text="Second page",
            generation_prompt="second prompt",
            image_model="gpt-image-1",
            image_path="images/pages/page_002/variant_001.png",
            status="generated",
        )
        ProjectImagePageVariant.objects.create(
            page=second_page,
            variant_index=1,
            image_model="gpt-image-1",
            image_path="images/pages/page_002/variant_001.png",
            generation_prompt="second prompt",
            status="generated",
        )
        client = Client()
        client.login(username="org", password="pw")

        resp = client.get(
            reverse("community-organiser-review-project", args=[self.community.id, self.project.id]),
            {"generation_filter": "selected_pages", "selected_page_id": str(self.page.id)},
        )

        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertContains(resp, "Page 1, variant 1")
        self.assertContains(resp, "Page 2, variant 1")
        self.assertRegex(content, rf'data-page-id="{second_page.id}"[^>]*display:none')
        self.assertContains(resp, f'name="selected_page_id" value="{self.page.id}" checked', html=False)
        self.assertContains(resp, 'Pages selected for regeneration in this view: <strong id="selected-page-count">1</strong>', html=False)
        self.assertContains(resp, "data-selection-storage-key", html=False)

    @patch("projects.views._build_ai_client")
    def test_organiser_regeneration_prompt_honours_disallow_text_setting(self, mock_build_ai_client):
        self.project.community = self.community
        self.project.save(update_fields=["community", "updated_at"])
        self.style.disallow_text_in_images = True
        self.style.save(update_fields=["disallow_text_in_images", "updated_at"])
        mock_build_ai_client.return_value = FakeImageClient()
        client = Client()
        client.login(username="org", password="pw")

        preview = client.post(
            reverse("community-organiser-review-project", args=[self.community.id, self.project.id]),
            {
                "action": "generate_requested_preview",
                "generation_filter": "selected_pages",
                "selected_page_id": [str(self.page.id)],
                "request_count_all": "1",
            },
            follow=True,
        )
        self.assertEqual(preview.status_code, 200)

        confirm = client.post(
            reverse("community-organiser-review-project", args=[self.community.id, self.project.id]),
            {"action": "generate_requested"},
            follow=True,
        )

        self.assertEqual(confirm.status_code, 200)
        generated_variant = ProjectImagePageVariant.objects.get(page=self.page, variant_index=2)
        self.assertIn("TEXT SUPPRESSION REQUIREMENTS", generated_variant.generation_prompt)
        self.assertIn("No exceptions", generated_variant.generation_prompt)

    @patch("projects.views._build_ai_client")
    def test_organiser_review_generate_requested_selected_pages_filter(self, mock_build_ai_client):
        self.project.community = self.community
        self.project.save(update_fields=["community", "updated_at"])
        second_page = ProjectImagePage.objects.create(
            project=self.project,
            page_number=2,
            page_text="Second page",
            generation_prompt="second prompt",
            image_model="gpt-image-1",
            status="generated",
        )
        mock_build_ai_client.return_value = FakeImageClient()
        client = Client()
        client.login(username="org", password="pw")
        resp = client.post(
            reverse("community-organiser-review-project", args=[self.community.id, self.project.id]),
            {
                "action": "generate_requested_preview",
                "generation_filter": "selected_pages",
                "image_model": "gpt-image-1",
                "selected_page_id": [str(self.page.id)],
                "request_count_all": "1",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Proposed generation plan")
        resp_confirm = client.post(
            reverse("community-organiser-review-project", args=[self.community.id, self.project.id]),
            {
                "action": "generate_requested",
            },
            follow=True,
        )
        self.assertEqual(resp_confirm.status_code, 200)
        self.assertContains(resp_confirm, "Generation progress updates")
        self.assertEqual(ProjectImagePageVariant.objects.filter(page=self.page).count(), 2)
        self.assertEqual(ProjectImagePageVariant.objects.filter(page=second_page).count(), 0)
