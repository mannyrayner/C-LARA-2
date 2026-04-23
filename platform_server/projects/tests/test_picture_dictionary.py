from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from projects.models import Community, CommunityMembership, PictureDictionary, PictureDictionaryEntry, Project
from projects.views import _build_picture_glosses_for_compile


class PictureDictionaryCommandTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.organiser = User.objects.create_user(username="dictorg", password="pw")
        self.member = User.objects.create_user(username="dictmember", password="pw")
        self.community = Community.objects.create(name="German Community", language="de")
        CommunityMembership.objects.create(
            community=self.community,
            user=self.organiser,
            role=CommunityMembership.ROLE_ORGANISER,
        )
        CommunityMembership.objects.create(
            community=self.community,
            user=self.member,
            role=CommunityMembership.ROLE_MEMBER,
        )

    def test_ensure_add_remove_and_compile_picture_dictionary(self):
        call_command(
            "picture_dictionary",
            "ensure",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        self.assertEqual(dictionary.project.community_id, self.community.id)
        self.assertEqual(dictionary.project.language, "de")

        call_command(
            "picture_dictionary",
            "add",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="Pinguin, Oper, Pinguin",
        )
        dictionary.refresh_from_db()
        self.assertEqual(dictionary.project.source_text, "Pinguin\nOper")

        call_command(
            "picture_dictionary",
            "remove",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="Oper",
        )
        dictionary.refresh_from_db()
        self.assertIn("Pinguin", dictionary.project.source_text)
        self.assertNotIn("Oper", dictionary.project.source_text)

        call_command(
            "picture_dictionary",
            "add-from-text",
            community_id=self.community.id,
            organiser=self.organiser.username,
            text="Frida ist ein Pinguin in der Antarktis.",
        )
        dictionary.refresh_from_db()
        self.assertIn("Frida", dictionary.project.source_text)

        call_command(
            "picture_dictionary",
            "compile",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        self.assertEqual(dictionary.project.image_pages.count(), 6)
        seg1_path = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages" / "segmentation_phase_1.json"
        self.assertTrue(seg1_path.exists())
        payload = seg1_path.read_text(encoding="utf-8")
        self.assertIn('"source": "picture_dictionary"', payload)
        for stage_name in ("segmentation_phase_2", "mwe", "lemma", "gloss", "romanization", "pinyin"):
            stage_path = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages" / f"{stage_name}.json"
            self.assertTrue(stage_path.exists())

    def test_non_organiser_cannot_manage_dictionary(self):
        with self.assertRaises(CommandError):
            call_command(
                "picture_dictionary",
                "ensure",
                community_id=self.community.id,
                organiser=self.member.username,
            )

    def test_remove_keeps_registry_and_marks_entries_inactive(self):
        call_command(
            "picture_dictionary",
            "ensure",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        call_command(
            "picture_dictionary",
            "add",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="chat, chien",
        )
        entry = PictureDictionaryEntry.objects.get(dictionary=dictionary, surface="chat")
        call_command(
            "picture_dictionary",
            "remove",
            community_id=self.community.id,
            organiser=self.organiser.username,
            words="chat",
        )
        entry.refresh_from_db()
        self.assertFalse(entry.is_active)
        call_command(
            "picture_dictionary",
            "compile",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary.refresh_from_db()
        for stage_name in ("lemma", "gloss", "romanization", "pinyin"):
            stage_path = dictionary.project.artifact_dir() / "runs" / "run_picture_dictionary" / "stages" / f"{stage_name}.json"
            self.assertNotIn("chat", stage_path.read_text(encoding="utf-8"))

    def test_cross_project_picture_glosses_are_staged_into_compile_html_dir(self):
        call_command(
            "picture_dictionary",
            "ensure",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        entry = PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface="femme",
            lemma="femme",
            pos="NOUN",
            is_active=True,
        )
        image_rel = "images/pages/page_002/variant_001.png"
        image_abs = dictionary.project.artifact_dir() / image_rel
        image_abs.parent.mkdir(parents=True, exist_ok=True)
        image_abs.write_bytes(b"fake-image")
        entry.image_path = image_rel
        entry.save(update_fields=["image_path", "updated_at"])

        toy_project = Project.objects.create(
            owner=self.organiser,
            title="Toy French Text",
            source_text="La femme parle.",
            language="fr",
            target_language="en",
            community=self.community,
        )
        output_dir = toy_project.artifact_dir() / "runs" / "run_test_cross_project_gloss"
        output_dir.mkdir(parents=True, exist_ok=True)
        glosses = _build_picture_glosses_for_compile(project=toy_project, output_dir=output_dir)
        self.assertIn("femme", glosses)
        rel_path = glosses["femme"]["image_path"]
        self.assertTrue(rel_path.startswith("picture_glosses/"))
        staged = output_dir / "html" / Path(rel_path)
        self.assertTrue(staged.exists())

    def test_cross_project_picture_glosses_fallback_to_dictionary_page_image_path(self):
        call_command(
            "picture_dictionary",
            "ensure",
            community_id=self.community.id,
            organiser=self.organiser.username,
        )
        dictionary = PictureDictionary.objects.get(community=self.community)
        entry = PictureDictionaryEntry.objects.create(
            dictionary=dictionary,
            surface="chat",
            lemma="chat",
            pos="NOUN",
            is_active=True,
            current_page_number=1,
        )
        dictionary.project.image_pages.create(
            page_number=1,
            page_text="chat",
            generation_prompt="chat",
            image_model="gpt-image-1",
            image_path="images/pages/page_001/variant_001.png",
        )
        image_abs = dictionary.project.artifact_dir() / "images/pages/page_001/variant_001.png"
        image_abs.parent.mkdir(parents=True, exist_ok=True)
        image_abs.write_bytes(b"fake-image")

        toy_project = Project.objects.create(
            owner=self.organiser,
            title="Toy French Text 2",
            source_text="Le chat dort.",
            language="fr",
            target_language="en",
            community=self.community,
        )
        output_dir = toy_project.artifact_dir() / "runs" / "run_test_fallback_gloss"
        output_dir.mkdir(parents=True, exist_ok=True)
        glosses = _build_picture_glosses_for_compile(project=toy_project, output_dir=output_dir)
        self.assertIn("chat", glosses)
        entry.refresh_from_db()
        self.assertEqual(entry.image_path, "images/pages/page_001/variant_001.png")
