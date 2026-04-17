import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from projects.models import Community, CommunityMembership


class AdminToolsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff_user = User.objects.create_user(username="staffer", password="pw", is_staff=True)
        self.normal_user = User.objects.create_user(username="normal", password="pw")
        self.target_user = User.objects.create_user(username="target", password="pw")
        self.client = Client()

    def test_non_admin_cannot_access_admin_tools(self):
        self.client.login(username="normal", password="pw")
        resp = self.client.get(reverse("admin-tools"))
        self.assertEqual(resp.status_code, 404)

    def test_admin_can_grant_admin_privileges(self):
        self.client.login(username="staffer", password="pw")
        resp = self.client.post(
            reverse("admin-tools"),
            {"action": "grant_admin", "user": self.target_user.id},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_staff)

    def test_admin_can_delete_language_audio_cache(self):
        self.client.login(username="staffer", password="pw")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cache_dir = root / "audio_repository" / "de"
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / "de_test.wav").write_bytes(b"123")

            with override_settings(MEDIA_ROOT=root):
                resp = self.client.post(
                    reverse("admin-tools"),
                    {"action": "delete_audio_cache", "language": "de"},
                    follow=True,
                )
                self.assertEqual(resp.status_code, 200)
                self.assertFalse(cache_dir.exists())

    def test_admin_can_create_community_from_admin_tools(self):
        self.client.login(username="staffer", password="pw")
        resp = self.client.post(
            reverse("admin-tools"),
            {
                "action": "create_community",
                "name": "Drehu language community",
                "language": "dre",
                "description": "First-cut test community",
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Drehu language community")

    def test_admin_can_assign_user_as_community_organiser(self):
        self.client.login(username="staffer", password="pw")
        create = self.client.post(
            reverse("admin-tools"),
            {
                "action": "create_community",
                "name": "Iaai language community",
                "language": "iai",
                "description": "Community for Iaai projects",
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(create.status_code, 200)
        community_id = Community.objects.get(name="Iaai language community").pk

        assign = self.client.post(
            reverse("admin-tools"),
            {
                "action": "assign_community_role",
                "community": community_id,
                "user": self.target_user.id,
                "role": "organiser",
            },
            follow=True,
        )
        self.assertEqual(assign.status_code, 200)
        membership = CommunityMembership.objects.get(user=self.target_user, community_id=community_id)
        self.assertEqual(membership.role, CommunityMembership.ROLE_ORGANISER)


@override_settings(BOOTSTRAP_ADMIN_USERNAMES=["bootstrap"])
class BootstrapAdminRegistrationTests(TestCase):
    def test_bootstrap_user_gets_staff_on_registration(self):
        resp = self.client.post(
            reverse("register"),
            {
                "username": "bootstrap",
                "email": "bootstrap@example.com",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )
        self.assertEqual(resp.status_code, 302)
        user = get_user_model().objects.get(username="bootstrap")
        self.assertTrue(user.is_staff)
