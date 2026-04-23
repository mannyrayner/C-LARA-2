from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from projects.models import Community, CommunityMembership, PictureDictionary, PictureDictionaryEntry


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
