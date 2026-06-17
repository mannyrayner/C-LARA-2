import base64
import json
import shutil

from django.contrib.auth import get_user_model
from django.core.cache import cache
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
        text_prompt = str(prompt)
        if "Item:" in text_prompt:
            item_json = text_prompt.split("Item:", 1)[-1].strip()
            try:
                item = json.loads(item_json)
            except json.JSONDecodeError:
                item = {}
            text = str(item.get("text") or "").strip().lower()
            is_gloss_language = text in {"person", "long", "mouth"}
            return {
                "is_gloss_language": is_gloss_language,
                "confidence": "high",
                "reason": "The item looks like English." if is_gloss_language else "The item does not look like English.",
            }

        row_json = text_prompt.split("Row:", 1)[-1].strip()
        try:
            row = json.loads(row_json)
        except json.JSONDecodeError:
            row = {}
        translation = str(row.get("translation") or "").strip().lower()
        surface = str(row.get("surface") or "").strip()
        is_warning = translation == "pama"
        return {
            "text_is_gloss_language": surface.lower() in {"person", "long"},
            "text_language_confidence": "high",
            "translation_is_gloss_language": not is_warning,
            "translation_language_confidence": "high",
            "warning": is_warning,
            "reason": (
                f"The gloss/translation ‘{translation}’ does not look like English, while the page text ‘{surface}’ does."
                if is_warning
                else "The gloss/translation looks like English."
            ),
            "confidence": "high" if is_warning else "low",
        }


class FakeSubsetSelectionClient:
    async def chat_json(self, prompt, **kwargs):  # noqa: ARG002
        text_prompt = str(prompt)
        payload_text = text_prompt.split("Subset candidate:", 1)[-1].strip()
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = {}
        candidate = payload.get("candidate") or {}
        haystack = " ".join(
            str(candidate.get(key) or "").lower()
            for key in ("surface", "lemma", "gloss", "translation")
        )
        include = "animal" in haystack or "dog" in haystack
        return {
            "include": include,
            "confidence": "high" if include else "medium",
            "reason": "The translation matches the requested animal subset." if include else "The translation is not an animal term.",
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
        self.assertContains(home, "Checking dictionary/image consistency, please wait")
        self.assertContains(home, f"Review images for {self.project.title}")

        review = client.get(reverse("community-organiser-review-project", args=[self.community.id, self.project.id]))
        self.assertEqual(review.status_code, 200)
        self.assertContains(review, "current preferred image")
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
        self.assertNotContains(page, "Sync dictionary text + placeholder stages (no image generation)")
        self.assertNotContains(page, "Compile dictionary (sync pages + annotation + images)")
        self.assertContains(page, "Add from text")
        self.assertContains(page, "Import as dictionary copy")
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

    def test_organiser_can_edit_unified_picture_dictionary_view(self):
        CommunityMembership.objects.get_or_create(
            community=self.community,
            user=self.organiser,
            defaults={"role": CommunityMembership.ROLE_ORGANISER},
        )
        client = Client()
        client.login(username="org", password="pw")
        client.post(reverse("community-organiser-home", args=[self.community.id]), {"picture_dictionary_action": "ensure"})
        dictionary = PictureDictionary.objects.get(community=self.community)
        client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "low_resource_surface": ["pama"],
                "low_resource_lemma": ["pama"],
                "low_resource_pos": ["N"],
                "low_resource_gloss": ["person"],
            },
        )
        entry = dictionary.entries.get(surface="pama")
        page = ProjectImagePage.objects.get(project=dictionary.project, page_number=1)
        page.generation_prompt = "Original prompt"
        page.save(update_fields=["generation_prompt", "updated_at"])

        response = client.get(reverse("community-organiser-home", args=[self.community.id]))
        self.assertContains(response, "Unified picture-dictionary view")
        self.assertContains(response, "Background information")
        self.assertContains(response, "Select all")
        self.assertContains(response, "Select incomplete")
        self.assertContains(response, "Select none")
        self.assertContains(response, "Display all")
        self.assertContains(response, "Display incomplete only")
        self.assertContains(response, "Dictionary entry fields")
        self.assertContains(response, "Create prompts for selected rows")
        self.assertContains(response, "Create images for selected rows")
        self.assertContains(response, "Create missing information for selected rows")
        self.assertNotContains(response, "Create prompts + images for selected rows")
        self.assertContains(response, "Original prompt")

        save = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "update_unified_entries",
                f"unified_surface_{entry.id}": "pama updated",
                f"unified_lemma_{entry.id}": "pama-lemma",
                f"unified_pos_{entry.id}": "noun",
                f"unified_gloss_{entry.id}": "person updated",
                f"unified_prompt_{entry.id}": "A clear text-free picture of a person.",
            },
            follow=True,
        )
        self.assertEqual(save.status_code, 200)
        self.assertContains(save, "Saved unified dictionary view")
        entry.refresh_from_db()
        self.assertEqual(entry.surface, "pama updated")
        self.assertEqual(entry.lemma, "pama-lemma")
        self.assertEqual(entry.pos, "NOUN")
        page.refresh_from_db()
        self.assertEqual(page.page_text, "pama updated")
        self.assertEqual(page.generation_prompt, "A clear text-free picture of a person.")
        translation_payload = read_stage_artifact(dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary", "translation")
        token_annotations = translation_payload["pages"][0]["segments"][0]["tokens"][0]["annotations"]
        self.assertEqual(token_annotations["translation"], "person updated")
        gloss_payload = read_stage_artifact(dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary", "gloss")
        self.assertEqual(gloss_payload["pages"][0]["segments"][0]["tokens"][0]["annotations"]["gloss"], "person updated")

        class FakeUnifiedPromptClient:
            async def chat_text(self, prompt, **kwargs):  # noqa: ARG002
                return (
                    "A realistic cartoon picture of one friendly person standing outdoors in a simple Cape York coastal setting, "
                    "focused on the idea of a mother/person, with warm colours and absolutely no written text."
                )

        with patch("projects.views._build_ai_client", return_value=FakeUnifiedPromptClient()) as mock_prompt_client:
            prompt_response = client.post(
                reverse("community-organiser-home", args=[self.community.id]),
                {
                    "picture_dictionary_action": "generate_unified_prompts",
                    "picture_dictionary_background_information": "Use Kok Kaper classroom-friendly cultural context.",
                    "picture_dictionary_style_brief": "Bright watercolor style.",
                    "unified_selected_entry_id": [str(entry.id)],
                    f"unified_surface_{entry.id}": "pama updated",
                    f"unified_lemma_{entry.id}": "pama-lemma",
                    f"unified_pos_{entry.id}": "noun",
                    f"unified_gloss_{entry.id}": "person updated",
                    f"unified_suggestion_{entry.id}": "Show one friendly person, no text.",
                    f"unified_prompt_{entry.id}": "A clear text-free picture of a person.",
                },
                follow=True,
            )
        self.assertEqual(prompt_response.status_code, 200)
        self.assertTrue(mock_prompt_client.called)
        self.assertContains(prompt_response, "Created AI image-generation prompts for 1 selected dictionary row")
        page.refresh_from_db()
        self.assertIn("friendly person standing outdoors", page.generation_prompt)
        self.assertNotIn("Source-language word:", page.generation_prompt)
        metadata_path = dictionary.project.artifact_dir() / "picture_dictionary_workspace.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["background_information"], "Use Kok Kaper classroom-friendly cultural context.")
        self.assertEqual(metadata["entry_suggestions"][str(entry.id)], "Show one friendly person, no text.")

        def fake_generate_selected_image_variants(*, project, image_model, requests, progress_callback=None):  # noqa: ARG001
            for requested_page, _count, prompt in requests:
                ProjectImagePageVariant.objects.create(
                    page=requested_page,
                    variant_index=2,
                    image_model=image_model,
                    image_path="images/pages/page_001/variant_002.png",
                    generation_prompt=prompt,
                    status=ProjectImagePageVariant.STATUS_GENERATED,
                )
            return len(requests)

        with patch("projects.views._generate_requested_page_variants", side_effect=fake_generate_selected_image_variants) as mock_generate_images:
            image_response = client.post(
                reverse("community-organiser-home", args=[self.community.id]),
                {
                    "picture_dictionary_action": "generate_unified_images",
                    "picture_dictionary_background_information": "Use Kok Kaper classroom-friendly cultural context.",
                    "picture_dictionary_style_brief": "Bright watercolor style.",
                    "unified_selected_entry_id": [str(entry.id)],
                    f"unified_surface_{entry.id}": "pama updated",
                    f"unified_lemma_{entry.id}": "pama-lemma",
                    f"unified_pos_{entry.id}": "noun",
                    f"unified_gloss_{entry.id}": "person updated",
                    f"unified_suggestion_{entry.id}": "Show one friendly person, no text.",
                    f"unified_prompt_{entry.id}": page.generation_prompt,
                },
                follow=True,
            )
        self.assertEqual(image_response.status_code, 200)
        self.assertTrue(mock_generate_images.called)
        self.assertContains(image_response, "Created 1 image variant for selected dictionary row")
        self.assertContains(image_response, "selected 1 latest image")
        page.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(page.image_path, "images/pages/page_001/variant_002.png")
        self.assertEqual(entry.image_path, "images/pages/page_001/variant_002.png")

        missing_entry = dictionary.entries.create(surface="ngama", lemma="", pos="", is_active=True)

        class FakeMissingInfoClient:
            async def chat_json(self, prompt, **kwargs):  # noqa: ARG002
                return {"lemma": "ngama", "pos": "NOUN", "translation": "water"}

        with patch("projects.views._build_ai_client", return_value=FakeMissingInfoClient()) as mock_missing_client:
            missing_response = client.post(
                reverse("community-organiser-home", args=[self.community.id]),
                {
                    "picture_dictionary_action": "generate_unified_missing_info",
                    "picture_dictionary_background_information": "Use Kok Kaper classroom-friendly cultural context.",
                    "picture_dictionary_style_brief": "Bright watercolor style.",
                    "unified_selected_entry_id": [str(missing_entry.id)],
                    f"unified_surface_{entry.id}": entry.surface,
                    f"unified_lemma_{entry.id}": entry.lemma,
                    f"unified_pos_{entry.id}": entry.pos,
                    f"unified_gloss_{entry.id}": "person updated",
                    f"unified_suggestion_{entry.id}": "Show one friendly person, no text.",
                    f"unified_prompt_{entry.id}": page.generation_prompt,
                    f"unified_surface_{missing_entry.id}": "ngama",
                    f"unified_lemma_{missing_entry.id}": "",
                    f"unified_pos_{missing_entry.id}": "",
                    f"unified_gloss_{missing_entry.id}": "",
                    f"unified_suggestion_{missing_entry.id}": "",
                    f"unified_prompt_{missing_entry.id}": "",
                },
                follow=True,
            )
        self.assertEqual(missing_response.status_code, 200)
        self.assertTrue(mock_missing_client.called)
        self.assertContains(missing_response, "Created missing lemma/POS/translation information for 1 selected dictionary row")
        missing_entry.refresh_from_db()
        self.assertEqual(missing_entry.lemma, "ngama")
        self.assertEqual(missing_entry.pos, "NOUN")
        missing_gloss_payload = read_stage_artifact(dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary", "gloss")
        self.assertEqual(missing_gloss_payload["pages"][-1]["segments"][0]["tokens"][0]["annotations"]["gloss"], "water")


    def test_low_resource_dictionary_headers_include_language_names(self):
        xkk_community = Community.objects.create(name="Kok Kaper C", language="xkk")
        CommunityMembership.objects.create(community=xkk_community, user=self.organiser, role="organiser")
        dictionary_project = Project.objects.create(
            owner=self.organiser,
            title="Kok Kaper picture dictionary",
            source_text="",
            language="xkk",
            target_language="en",
            community=xkk_community,
        )
        PictureDictionary.objects.create(
            community=xkk_community,
            project=dictionary_project,
            organiser=self.organiser,
            language="xkk",
        )
        client = Client()
        client.login(username="org", password="pw")

        page = client.get(reverse("community-organiser-home", args=[xkk_community.id]))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Kok Kaper word")
        self.assertContains(page, "English gloss (= translation)")

    def test_low_resource_organiser_can_add_annotated_dictionary_rows(self):
        client = Client()
        client.login(username="org", password="pw")

        page = client.get(reverse("community-organiser-home", args=[self.community.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Add new low-resource dictionary words")
        self.assertContains(page, "Create new images")
        self.assertContains(page, "Iaai word")
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
                {"translation_is_gloss_language": True, "warning": True, "reason": "over-eager", "confidence": "high"},
                row_number=1,
                surface="Path-ch’rrich",
                translation=translation,
                translation_language="en",
            )
            self.assertIsNone(warning)

        warning = views._picture_dictionary_single_mixup_warning_from_payload(
            {"translation_is_gloss_language": False, "warning": True, "reason": "looks swapped", "confidence": "high"},
            row_number=2,
            surface="long",
            translation="yelkarr’ng",
            translation_language="en",
        )
        self.assertIsNotNone(warning)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("projects.views._build_ai_client")
    def test_dictionary_mixup_diagnostics_checks_rows_after_forty(self, mock_build_ai_client):
        cache.clear()
        mock_build_ai_client.return_value = FakeDictionaryMixupClient()
        client = Client()
        client.login(username="org", password="pw")
        response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"picture_dictionary_action": "ensure"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        dictionary = PictureDictionary.objects.get(community=self.community)
        rows = [
            {"surface": f"kkword{i}", "lemma": f"kkword{i}", "pos": "NOUN", "gloss": "person"}
            for i in range(45)
        ]
        rows[44] = {"surface": "long", "lemma": "long", "pos": "ADJ", "gloss": "pama"}

        warnings, traces = views._picture_dictionary_surface_translation_mixup_diagnostics(
            dictionary=dictionary,
            rows=rows,
            user=self.organiser,
        )

        self.assertEqual(len(traces), 45)
        self.assertGreaterEqual(mock_build_ai_client.call_count, 45)
        self.assertTrue(any(warning["row_number"] == "45" for warning in warnings))

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("projects.views._build_ai_client")
    def test_dictionary_mixup_diagnostics_reuses_cached_language_checks(self, mock_build_ai_client):
        cache.clear()
        mock_build_ai_client.return_value = FakeDictionaryMixupClient()
        dictionary = PictureDictionary.objects.create(
            community=self.community,
            project=self.project,
            organiser=self.organiser,
            language=self.project.language,
        )
        rows = [{"surface": "long", "lemma": "long", "pos": "ADJ", "gloss": "pama"}]

        first_warnings, first_traces = views._picture_dictionary_surface_translation_mixup_diagnostics(
            dictionary=dictionary,
            rows=rows,
            user=self.organiser,
        )
        first_call_count = mock_build_ai_client.call_count
        second_warnings, second_traces = views._picture_dictionary_surface_translation_mixup_diagnostics(
            dictionary=dictionary,
            rows=rows,
            user=self.organiser,
        )

        self.assertEqual(first_call_count, 2)
        self.assertEqual(mock_build_ai_client.call_count, first_call_count)
        self.assertEqual(first_warnings, second_warnings)
        self.assertEqual(first_traces, second_traces)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("projects.views._build_ai_client")
    def test_dictionary_mixup_diagnostics_classifies_fields_independently(self, mock_build_ai_client):
        cache.clear()
        mock_build_ai_client.return_value = FakeDictionaryMixupClient()
        dictionary = PictureDictionary.objects.create(
            community=self.community,
            project=self.project,
            organiser=self.organiser,
            language=self.project.language,
        )

        warnings, traces = views._picture_dictionary_surface_translation_mixup_diagnostics(
            dictionary=dictionary,
            rows=[{"surface": "Thaw", "lemma": "Thaw", "pos": "NOUN", "gloss": "mouth"}],
            user=self.organiser,
        )

        self.assertEqual(warnings, [])
        self.assertEqual(traces[0]["text_language_id"], "not French")
        self.assertEqual(traces[0]["gloss_language_id"], "French")

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("projects.views._build_ai_client")
    def test_low_resource_add_warns_on_surface_translation_mixup(self, mock_build_ai_client):
        cache.clear()
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
        self.assertContains(response, "Please confirm these rows before adding them")
        self.assertContains(response, 'value="person"')
        self.assertGreaterEqual(mock_build_ai_client.call_count, 2)
        dictionary = PictureDictionary.objects.get(community=self.community)
        self.assertFalse(dictionary.entries.filter(surface="person", is_active=True).exists())
        self.assertFalse(dictionary.entries.filter(surface="pama", is_active=True).exists())

        confirmed = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "confirm_low_resource_mixup": "1",
                "low_resource_surface": ["pama", "person"],
                "low_resource_lemma": ["pama", "person"],
                "low_resource_pos": ["NOUN", "NOUN"],
                "low_resource_gloss": ["person", "pama"],
            },
            follow=True,
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertContains(confirmed, "Added rows after organiser confirmation")
        self.assertContains(confirmed, "Added 2 and updated 0 low-resource dictionary row")
        self.assertTrue(dictionary.entries.filter(surface="person", is_active=True).exists())
        self.assertTrue(dictionary.entries.filter(surface="pama", is_active=True).exists())

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("projects.views._build_ai_client")
    def test_organiser_review_warns_on_legacy_dictionary_mixup(self, mock_build_ai_client):
        cache.clear()
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
        cache.clear()
        mock_build_ai_client.return_value = FakeDictionaryMixupClient()

        response = client.get(
            reverse("community-organiser-review-project", args=[self.community.id, dictionary.project.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Possible dictionary word/gloss mix-ups")
        self.assertContains(response, "word <strong>person</strong>, gloss/translation <strong>pama</strong>", html=False)
        self.assertContains(response, "Show dictionary language-ID trace")
        self.assertContains(response, "English (high)")
        self.assertContains(response, "not English (high)")

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

    def test_low_resource_remove_selected_renumbers_surviving_image_directories(self):
        client = Client()
        client.login(username="org", password="pw")
        response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "low_resource_surface": ["aaa", "bbb", "ccc"],
                "low_resource_lemma": ["aaa", "bbb", "ccc"],
                "low_resource_pos": ["NOUN", "NOUN", "NOUN"],
                "low_resource_gloss": ["dummy a", "dummy b", "dummy c"],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        dictionary = PictureDictionary.objects.get(community=self.community)
        entries = list(dictionary.entries.filter(surface__in=["aaa", "bbb", "ccc"]).order_by("id"))
        self.assertEqual([entry.surface for entry in entries], ["aaa", "bbb", "ccc"])
        for page_number, entry in enumerate(entries, start=1):
            rel_path = f"images/pages/page_{page_number:03d}/variant_001.png"
            image_path = dictionary.project.artifact_dir() / rel_path
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(entry.surface.encode("utf-8"))
            entry.image_path = rel_path
            entry.current_page_number = page_number
            entry.save(update_fields=["image_path", "current_page_number", "updated_at"])
            page = ProjectImagePage.objects.get(project=dictionary.project, page_number=page_number)
            page.page_text = entry.surface
            page.image_path = rel_path
            page.save(update_fields=["page_text", "image_path", "updated_at"])

        response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "remove_selected",
                "remove_entry": [str(entries[0].id)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        survivors = list(dictionary.entries.filter(is_active=True).order_by("id"))
        self.assertEqual([entry.surface for entry in survivors], ["bbb", "ccc"])
        self.assertEqual([entry.current_page_number for entry in survivors], [1, 2])
        self.assertEqual(survivors[0].image_path, "images/pages/page_001/variant_001.png")
        self.assertEqual(survivors[1].image_path, "images/pages/page_002/variant_001.png")
        self.assertEqual(
            (dictionary.project.artifact_dir() / "images/pages/page_001/variant_001.png").read_bytes(),
            b"bbb",
        )
        self.assertEqual(
            (dictionary.project.artifact_dir() / "images/pages/page_002/variant_001.png").read_bytes(),
            b"ccc",
        )
        self.assertFalse((dictionary.project.artifact_dir() / "images/pages/page_003").exists())
        pages = list(ProjectImagePage.objects.filter(project=dictionary.project).order_by("page_number"))
        self.assertEqual([(page.page_number, page.page_text, page.image_path) for page in pages], [
            (1, "bbb", "images/pages/page_001/variant_001.png"),
            (2, "ccc", "images/pages/page_002/variant_001.png"),
        ])

    def test_organiser_can_create_picture_dictionary_subset_project(self):
        client = Client()
        client.login(username="org", password="pw")
        response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "low_resource_surface": ["pama", "thaw", "kutew"],
                "low_resource_lemma": ["pama", "thaw", "kutew"],
                "low_resource_pos": ["NOUN", "NOUN", "NOUN"],
                "low_resource_gloss": ["person", "mouth", "dog"],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        dictionary = PictureDictionary.objects.get(community=self.community)
        entries = list(dictionary.entries.filter(is_active=True).order_by("id"))
        for idx, entry in enumerate(entries, start=1):
            rel_path = f"images/pages/page_{idx:03d}/variant_001.png"
            image_file = dictionary.project.artifact_dir() / rel_path
            image_file.parent.mkdir(parents=True, exist_ok=True)
            image_file.write_bytes(b"fake-image")
            entry.image_path = rel_path
            entry.current_page_number = idx
            entry.save(update_fields=["image_path", "current_page_number", "updated_at"])
            page = ProjectImagePage.objects.get(project=dictionary.project, page_number=idx)
            page.image_path = rel_path
            page.status = ProjectImagePage.STATUS_APPROVED
            page.save(update_fields=["image_path", "status", "updated_at"])
            ProjectImagePageVariant.objects.update_or_create(
                page=page,
                variant_index=1,
                defaults={
                    "image_path": rel_path,
                    "image_model": "gpt-image-1",
                    "generation_prompt": entry.surface,
                    "status": ProjectImagePageVariant.STATUS_APPROVED,
                },
            )

        response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "save_subset",
                "subset_title": "Beginner Kok Kaper set",
                "subset_description": "First classroom test set",
                "subset_selection_note": "manual beginner words",
                "subset_entry_id": [str(entries[0].id), str(entries[2].id)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Created subset project")
        subset_project = Project.objects.get(owner=self.organiser, title="Beginner Kok Kaper set")
        self.assertEqual(subset_project.community, self.community)
        self.assertEqual(subset_project.access_scope, Project.ACCESS_COMMUNITY)
        self.assertEqual(subset_project.source_text, "pama\nkutew")
        subset_run = subset_project.artifact_dir() / "runs" / "run_picture_dictionary_subset"
        lemma_payload = read_stage_artifact(subset_run, "lemma")
        self.assertEqual([page["surface"] for page in lemma_payload["pages"]], ["pama", "kutew"])
        self.assertEqual(
            (subset_project.artifact_dir() / "images/pages/page_001/variant_001.png").read_bytes(),
            b"fake-image",
        )
        subset_dir = dictionary.project.artifact_dir() / "picture_dictionary_subsets" / f"project_{subset_project.id}"
        config = json.loads((subset_dir / "config.json").read_text(encoding="utf-8"))
        pages = json.loads((subset_dir / "pages.json").read_text(encoding="utf-8"))["pages"]
        self.assertEqual(config["project_id"], subset_project.id)
        self.assertEqual([page["entry_id"] for page in pages], [entries[0].id, entries[2].id])
        self.assertNotContains(response, "Review images for Beginner Kok Kaper set")

        review_response = client.get(
            reverse("community-organiser-review-project", args=[self.community.id, subset_project.id]),
            follow=True,
        )
        self.assertEqual(review_response.status_code, 200)
        self.assertContains(review_response, "Subset dictionary projects inherit images")

    def test_ai_suggestion_prefills_picture_dictionary_subset_entries(self):
        client = Client()
        client.login(username="org", password="pw")
        client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "low_resource_surface": ["pama", "kutew", "thaw"],
                "low_resource_lemma": ["pama", "kutew", "thaw"],
                "low_resource_pos": ["NOUN", "NOUN", "NOUN"],
                "low_resource_gloss": ["person", "animal, dog", "mouth"],
            },
            follow=True,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        entries = {entry.surface: entry for entry in dictionary.entries.filter(is_active=True)}
        with patch("projects.views._ai_available_for_user", return_value=True), patch(
            "projects.views._build_ai_client",
            return_value=FakeSubsetSelectionClient(),
        ):
            response = client.post(
                reverse("community-organiser-home", args=[self.community.id]),
                {
                    "picture_dictionary_action": "suggest_subset",
                    "subset_title": "Animal words",
                    "subset_selection_note": "words for animals",
                },
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI subset prefill complete: suggested 1 dictionary entry for the subset")
        self.assertContains(response, "AI is pre-filling the subset list, please wait")
        self.assertContains(response, "subset-suggest-button")
        self.assertContains(response, "Animal words")
        self.assertContains(response, "animal, dog")
        self.assertContains(response, f'name="subset_entry_id" value="{entries["kutew"].id}" checked', html=False)
        self.assertNotContains(response, f'name="subset_entry_id" value="{entries["pama"].id}" checked', html=False)

    def test_organiser_can_reload_and_update_picture_dictionary_subset_project(self):
        client = Client()
        client.login(username="org", password="pw")
        client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "add_low_resource_rows",
                "low_resource_surface": ["pama", "thaw", "kutew"],
                "low_resource_lemma": ["pama", "thaw", "kutew"],
                "low_resource_pos": ["NOUN", "NOUN", "NOUN"],
                "low_resource_gloss": ["person", "mouth", "dog"],
            },
            follow=True,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        entries = list(dictionary.entries.filter(is_active=True).order_by("id"))
        create_response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "save_subset",
                "subset_title": "Editable subset",
                "subset_entry_id": [str(entries[0].id), str(entries[1].id)],
            },
            follow=True,
        )
        self.assertEqual(create_response.status_code, 200)
        subset_project = Project.objects.get(owner=self.organiser, title="Editable subset")
        subset_id = f"project_{subset_project.id}"

        load_response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {"picture_dictionary_action": "load_subset", "subset_id": subset_id},
            follow=True,
        )
        self.assertEqual(load_response.status_code, 200)
        self.assertContains(load_response, "Editing subset:")
        self.assertContains(load_response, "Editable subset")
        self.assertContains(load_response, f'value="{entries[0].id}" checked', html=False)
        self.assertContains(load_response, f'value="{entries[1].id}" checked', html=False)

        update_response = client.post(
            reverse("community-organiser-home", args=[self.community.id]),
            {
                "picture_dictionary_action": "save_subset",
                "editing_subset_id": subset_id,
                "subset_title": "Editable subset revised",
                "subset_entry_id": [str(entries[2].id)],
            },
            follow=True,
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertContains(update_response, "Updated subset project")
        subset_project.refresh_from_db()
        self.assertEqual(subset_project.title, "Editable subset revised")
        self.assertEqual(subset_project.source_text, "kutew")
        subset_dir = dictionary.project.artifact_dir() / "picture_dictionary_subsets" / subset_id
        pages = json.loads((subset_dir / "pages.json").read_text(encoding="utf-8"))["pages"]
        self.assertEqual([page["entry_id"] for page in pages], [entries[2].id])

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
