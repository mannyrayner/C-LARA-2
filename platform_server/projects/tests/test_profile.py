from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import Profile


class ProfileTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="profile_user", password="pw")
        Profile.objects.create(user=self.user, timezone="UTC", dialogue_language="en")
        self.client = Client()
        self.client.login(username="profile_user", password="pw")

    def test_profile_form_shows_dialogue_language_field(self):
        resp = self.client.get(reverse("profile"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dialogue language")
        self.assertContains(resp, "Enable dialogue personalization memory")
        self.assertContains(resp, "Clear dialogue memory")

    def test_profile_saves_dialogue_language(self):
        resp = self.client.post(
            reverse("profile"),
            {
                "timezone": "UTC",
                "dialogue_language": "fr",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        profile_obj = Profile.objects.get(user=self.user)
        self.assertEqual(profile_obj.dialogue_language, "fr")

    def test_profile_can_disable_dialogue_memory(self):
        resp = self.client.post(
            reverse("profile"),
            {
                "timezone": "UTC",
                "dialogue_language": "en",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        profile_obj = Profile.objects.get(user=self.user)
        self.assertFalse(profile_obj.dialogue_memory_enabled)

    def test_profile_can_enable_byok_with_key(self):
        resp = self.client.post(
            reverse("profile"),
            {
                "timezone": "UTC",
                "dialogue_language": "en",
                "use_personal_openai_key": "on",
                "openai_api_key": "sk-test-123",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        profile_obj = Profile.objects.get(user=self.user)
        self.assertTrue(profile_obj.use_personal_openai_key)
        self.assertEqual(profile_obj.openai_api_key, "sk-test-123")

    def test_profile_clear_memory_action(self):
        profile_obj = Profile.objects.get(user=self.user)
        profile_obj.dialogue_memory = {"last_nl_query": "Find me a story about elephants"}
        profile_obj.save(update_fields=["dialogue_memory", "updated_at"])
        resp = self.client.post(reverse("profile"), {"memory_action": "clear"}, follow=True)
        self.assertEqual(resp.status_code, 200)
        profile_obj.refresh_from_db()
        self.assertEqual(profile_obj.dialogue_memory, {})
