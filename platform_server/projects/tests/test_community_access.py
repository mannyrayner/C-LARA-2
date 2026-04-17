from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.models import Community, CommunityMembership, Project


class CommunityAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="pw")
        self.member = User.objects.create_user(username="member", password="pw")
        self.outsider = User.objects.create_user(username="outsider", password="pw")
        self.community = Community.objects.create(name="Iaai Speakers", language="iai")
        CommunityMembership.objects.create(
            community=self.community,
            user=self.member,
            role=CommunityMembership.ROLE_MEMBER,
        )
        self.public_project = Project.objects.create(
            owner=self.owner,
            title="Public Story",
            source_text="hello",
            language="en",
            target_language="fr",
            is_published=True,
            access_scope=Project.ACCESS_PUBLIC,
        )
        self.community_project = Project.objects.create(
            owner=self.owner,
            title="Community Story",
            source_text="hello",
            language="en",
            target_language="fr",
            is_published=True,
            access_scope=Project.ACCESS_COMMUNITY,
            community=self.community,
        )
        self.private_project = Project.objects.create(
            owner=self.owner,
            title="Private Story",
            source_text="hello",
            language="en",
            target_language="fr",
            is_published=True,
            access_scope=Project.ACCESS_PRIVATE,
        )

    def test_content_list_filters_by_community_membership(self):
        client = Client()
        client.login(username="member", password="pw")
        resp = client.get(reverse("content-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.public_project.title)
        self.assertContains(resp, self.community_project.title)
        self.assertNotContains(resp, self.private_project.title)

    def test_content_detail_blocks_non_member_for_community_only_project(self):
        client = Client()
        client.login(username="outsider", password="pw")
        resp = client.get(reverse("content-detail", args=[self.community_project.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_project_create_requires_community_when_scope_is_community_only(self):
        client = Client()
        client.login(username="owner", password="pw")
        resp = client.post(
            reverse("project-create"),
            {
                "title": "Needs community",
                "input_mode": Project.INPUT_SOURCE,
                "source_text": "abc",
                "description": "",
                "language": "en",
                "target_language": "fr",
                "access_scope": Project.ACCESS_COMMUNITY,
                "community": "",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Please select a community for community-only access.")
