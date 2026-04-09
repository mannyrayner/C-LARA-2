import shutil

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from projects.billing import get_user_balance_usd
from projects.models import CreditLedgerEntry, Project


@override_settings(CREDITS_ENABLED=True, CREDITS_MIN_BALANCE_USD="0.0500")
class BillingPhaseATests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="billing_user", password="pw")
        self.admin = User.objects.create_user(username="billing_admin", password="pw", is_staff=True)
        self.project = Project.objects.create(
            owner=self.user,
            title="Billing Project",
            source_text="Hello world",
            language="en",
            target_language="fr",
        )
        self.client = Client()
        shutil.rmtree(self.project.artifact_dir(), ignore_errors=True)

    def test_compile_is_blocked_when_balance_is_below_threshold(self):
        self.client.login(username="billing_user", password="pw")
        resp = self.client.post(
            reverse("project-compile", args=[self.project.pk]),
            {"start_stage": "segmentation_phase_1", "end_stage": "segmentation_phase_1"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Insufficient credits to start compile")

    def test_admin_can_adjust_credits_and_create_ledger_entry(self):
        self.client.login(username="billing_admin", password="pw")
        resp = self.client.post(
            reverse("admin-tools"),
            {
                "action": "adjust_credits",
                "user": self.user.pk,
                "amount_usd": "3.2500",
                "reason": "Initial funding",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Adjusted billing_user by $3.2500")
        self.assertEqual(str(get_user_balance_usd(self.user)), "3.2500")
        entry = CreditLedgerEntry.objects.filter(user=self.user).latest("created_at")
        self.assertEqual(entry.entry_type, CreditLedgerEntry.ENTRY_ADMIN_ADJUST)
        self.assertEqual(str(entry.amount_usd), "3.2500")
        self.assertEqual(entry.metadata.get("admin_user_id"), self.admin.id)
