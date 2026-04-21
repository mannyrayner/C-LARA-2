from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import Project


class AnnotationDialoguePlanTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="annot_user", password="pw")
        self.client = Client()
        self.client.login(username="annot_user", password="pw")

    def test_annotation_home_suggests_text_generation_when_no_plain_text(self):
        project = Project.objects.create(
            owner=self.user,
            title="No Text Yet",
            source_text="",
            description="",
            input_mode=Project.INPUT_DESCRIPTION,
            language="en",
            target_language="fr",
        )
        resp = self.client.get(reverse("project-annotation-home", args=[project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Suggested next step: create a first plain-text draft")
        self.assertContains(resp, "Run text_gen → text_gen")

    def test_annotation_home_suggests_segmentation_when_plain_text_exists(self):
        project = Project.objects.create(
            owner=self.user,
            title="Plain Text",
            source_text="This is plain text.",
            input_mode=Project.INPUT_SOURCE,
            language="en",
            target_language="fr",
        )
        resp = self.client.get(reverse("project-annotation-home", args=[project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "split into pages/segments")
        self.assertContains(resp, "Run segmentation_phase_1 → segmentation_phase_2")
