from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import Profile


class ProfileTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="profile_user", password="pw")
        self.client = Client()
        self.client.login(username="profile_user", password="pw")

    def test_profile_form_shows_dialogue_language_field(self):
        resp = self.client.get(reverse("profile"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dialogue language")

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
