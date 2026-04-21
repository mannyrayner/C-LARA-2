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
        # Keep tests deterministic even when a local MEDIA_ROOT already contains
        # historical artifacts from prior runs.
        Project.objects.filter(owner=self.user).delete()
        artifact_root = Project(owner=self.user, title="tmp").artifact_dir().parent
        if artifact_root.exists():
            import shutil

            shutil.rmtree(artifact_root)

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
        self.assertContains(resp, "Show plain text")
        self.assertContains(resp, "This is plain text.")

    def test_annotation_home_open_compiled_html_points_to_compiled_output(self):
        project = Project.objects.create(
            owner=self.user,
            title="Compiled",
            source_text="This is plain text.",
            input_mode=Project.INPUT_SOURCE,
            language="en",
            target_language="fr",
            compiled_path="runs/run_demo/html/page_2.html",
        )
        artifact_file = project.artifact_dir() / "runs" / "run_demo" / "html" / "page_1.html"
        artifact_file.parent.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text("<html></html>", encoding="utf-8")
        seg_file = project.artifact_dir() / "runs" / "run_demo" / "stages" / "segmentation_phase_2.json"
        seg_file.parent.mkdir(parents=True, exist_ok=True)
        seg_file.write_text("{}", encoding="utf-8")

        resp = self.client.get(reverse("project-annotation-home", args=[project.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp,
            reverse("project-compiled", args=[project.pk, "runs/run_demo/html/page_1.html"]),
        )
