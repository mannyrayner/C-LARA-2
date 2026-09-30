from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.views.debug import SafeExceptionReporterFilter


@override_settings(BOOTSTRAP_ADMIN_USERNAMES=[], AUTH_PASSWORD_VALIDATORS=[])
class PasswordManagementTests(TestCase):
    old_password = "Before-the-harbour-42!"
    new_password = "Beyond-the-orchard-63!"

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user("staffer", password=cls.old_password, is_staff=True)
        cls.user = User.objects.create_user("learner", password=cls.old_password, email="learner@example.org")
        cls.peer_admin = User.objects.create_user("other_staff", password=cls.old_password, is_staff=True)
        cls.superuser = User.objects.create_superuser("root", "root@example.org", cls.old_password)
        cls.inactive = User.objects.create_user("inactive", password=cls.old_password, is_active=False)

    def reset_url(self, user=None):
        return reverse("admin-reset-password", args=[(user or self.user).pk])

    def passwords(self, password=None):
        password = password or self.new_password
        return {"new_password1": password, "new_password2": password}

    def test_anonymous_users_must_sign_in(self):
        for url in [reverse("password-change"), reverse("admin-password-reset-users"), self.reset_url()]:
            for method in [self.client.get, self.client.post]:
                with self.subTest(url=url, method=method.__name__):
                    response = method(url)
                    self.assertRedirects(response, reverse("login") + "?next=" + url, fetch_redirect_response=False)

    def test_non_admin_cannot_list_or_reset_accounts(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("admin-password-reset-users")).status_code, 404)
        self.assertEqual(self.client.get(self.reset_url(self.peer_admin)).status_code, 404)
        self.assertEqual(self.client.post(self.reset_url(self.peer_admin), self.passwords()).status_code, 404)
        self.peer_admin.refresh_from_db()
        self.assertTrue(self.peer_admin.check_password(self.old_password))

    def test_admin_menu_excludes_self_inactive_and_superusers(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin-password-reset-users"))
        users = response.context["form"].fields["user"].queryset
        self.assertEqual(set(users), {self.user, self.peer_admin})
        self.assertNotContains(response, self.user.email)
        response = self.client.get(reverse("admin-password-reset-users"), {"user": self.user.pk})
        self.assertRedirects(response, self.reset_url())
        for target in [self.admin, self.inactive, self.superuser]:
            with self.subTest(target=target.username):
                self.assertEqual(self.client.post(self.reset_url(target), self.passwords()).status_code, 404)
                response = self.client.get(reverse("admin-password-reset-users"), {"user": target.pk})
                self.assertTrue(response.context["form"].errors)

    def test_admin_can_reset_without_old_password_and_target_sessions_expire(self):
        target_session = Client()
        target_session.force_login(self.user)
        self.client.force_login(self.admin)
        before = get_user_model().objects.values().get(pk=self.user.pk)
        # The form's URL, not an injected POST user id, determines the target.
        response = self.client.post(self.reset_url(), {**self.passwords(), "user": self.superuser.pk})
        self.assertRedirects(response, reverse("admin-password-reset-users"))
        after = get_user_model().objects.values().get(pk=self.user.pk)
        self.assertNotEqual(before.pop("password"), after.pop("password"))
        self.assertEqual(before, after)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(self.old_password))
        self.assertTrue(self.user.check_password(self.new_password))
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password(self.old_password))
        self.assertEqual(target_session.get(reverse("profile")).status_code, 302)
        self.assertEqual(self.client.get(reverse("admin-password-reset-users")).status_code, 200)
        self.assertFalse(target_session.login(username=self.user.username, password=self.old_password))
        self.assertTrue(target_session.login(username=self.user.username, password=self.new_password))
        audit = LogEntry.objects.get()
        self.assertEqual(audit.user_id, self.admin.pk)
        self.assertEqual(audit.object_id, str(self.user.pk))
        self.assertNotIn(self.new_password, audit.change_message)

    def test_staff_can_reset_peer_and_superuser_can_reset_superuser(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.post(self.reset_url(self.peer_admin), self.passwords()), reverse("admin-password-reset-users"))
        another_superuser = get_user_model().objects.create_superuser("other_root", "other@example.org", self.old_password)
        self.client.force_login(self.superuser)
        self.assertRedirects(self.client.post(self.reset_url(another_superuser), self.passwords()), reverse("admin-password-reset-users"))

    @override_settings(BOOTSTRAP_ADMIN_USERNAMES=["bootstrap"])
    def test_existing_bootstrap_admin_rule_is_honoured(self):
        bootstrap = get_user_model().objects.create_user("bootstrap", password=self.old_password)
        self.client.force_login(bootstrap)
        self.assertEqual(self.client.get(reverse("admin-password-reset-users")).status_code, 200)
        bootstrap.refresh_from_db()
        self.assertTrue(bootstrap.is_staff)

    def test_get_cannot_change_password(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.reset_url(), self.passwords()).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))
        self.assertFalse(LogEntry.objects.exists())

    def test_admin_rejects_mismatch_and_weak_passwords_without_audit(self):
        self.client.force_login(self.admin)
        for data in [
            {"new_password1": self.new_password, "new_password2": "different"},
            self.passwords("short"), self.passwords("password"),
            self.passwords("1234567890345"), self.passwords("learner"),
        ]:
            with self.subTest(data=data):
                response = self.client.post(self.reset_url(), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertNotContains(response, 'value="' + data["new_password1"] + '"')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))
        self.assertFalse(LogEntry.objects.exists())

    def test_self_change_requires_current_password(self):
        self.client.force_login(self.user)
        for old in ["", "wrong"]:
            response = self.client.post(reverse("password-change"), {**self.passwords(), "old_password": old})
            self.assertIn("old_password", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    def test_self_change_keeps_current_session_and_expires_other_sessions(self):
        other_session = Client()
        other_session.force_login(self.user)
        self.client.force_login(self.user)
        response = self.client.post(reverse("password-change"), {
            **self.passwords(), "old_password": self.old_password, "user": self.admin.pk,
        })
        self.assertRedirects(response, reverse("profile"))
        self.assertEqual(self.client.get(reverse("profile")).status_code, 200)
        self.assertEqual(other_session.get(reverse("profile")).status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(self.old_password))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))

    def test_self_change_validates_confirmation_and_strength(self):
        self.client.force_login(self.user)
        for data in [self.passwords("password"), {"new_password1": self.new_password, "new_password2": "wrong"}]:
            response = self.client.post(reverse("password-change"), {**data, "old_password": self.old_password})
            self.assertTrue(response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    @override_settings(AUTH_PASSWORD_VALIDATORS=[{
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 30},
    }])
    def test_configured_password_policy_is_respected(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.reset_url(), self.passwords())
        self.assertContains(response, "at least 30 characters")
        self.assertIn("new_password2", response.context["form"].errors)

    def test_csrf_required_for_both_password_actions(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for url in [self.reset_url(), reverse("password-change")]:
            response = client.post(url, {**self.passwords(), "old_password": self.old_password})
            self.assertEqual(response.status_code, 403)
        client.get(self.reset_url())
        response = client.post(self.reset_url(), self.passwords(), HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 302)

    @override_settings(DEBUG=False)
    def test_password_pages_are_uncached_and_error_reports_redact_post(self):
        self.client.force_login(self.admin)
        for url in [self.reset_url(), reverse("password-change"), reverse("admin-password-reset-users")]:
            self.assertIn("no-store", self.client.get(url)["Cache-Control"])
        for url in [self.reset_url(), reverse("password-change")]:
            response = self.client.post(url, {**self.passwords(), "old_password": "wrong", "new_password2": "mismatch"})
            redacted = SafeExceptionReporterFilter().get_post_parameters(response.wsgi_request)
            for name in ["new_password1", "new_password2", "old_password"]:
                self.assertEqual(redacted[name], "********************")

    def test_account_controls_are_discoverable(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("profile")), reverse("password-change"))
        self.assertContains(self.client.get(reverse("community_dictionary:home")), reverse("profile"))
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("admin-tools")), reverse("admin-password-reset-users"))
