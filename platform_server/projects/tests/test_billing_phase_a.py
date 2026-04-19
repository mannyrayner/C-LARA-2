import json
import shutil

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from projects.billing import estimate_openai_token_cost_usd, get_user_balance_usd, record_openai_usage_and_charge
from projects import views
from projects.models import AIUsageCharge, CreditLedgerEntry, OpenAIModelPricing, Project


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

    def test_usage_charge_updates_project_total_and_request_type_breakdown(self):
        self.client.login(username="billing_admin", password="pw")
        self.client.post(
            reverse("admin-tools"),
            {
                "action": "adjust_credits",
                "user": self.user.pk,
                "amount_usd": "10.0000",
                "reason": "Funding for usage test",
            },
            follow=True,
        )
        record_openai_usage_and_charge(
            user_id=self.user.id,
            project_id=self.project.id,
            model="gpt-4o-mini",
            operation="chat_json",
            request_type="segmentation_phase_1",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )
        self.project.refresh_from_db()
        self.assertGreater(self.project.total_cost_usd, 0)
        usage = AIUsageCharge.objects.filter(project=self.project).latest("created_at")
        self.assertEqual(usage.request_type, "segmentation_phase_1")

        self.client.login(username="billing_user", password="pw")
        resp = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertContains(resp, "Project cost (USD):")
        self.assertContains(resp, "segmentation_phase_1")

    def test_image_usage_reporter_charges_using_per_call_fallback_units(self):
        self.client.login(username="billing_admin", password="pw")
        self.client.post(
            reverse("admin-tools"),
            {
                "action": "adjust_credits",
                "user": self.user.pk,
                "amount_usd": "10.0000",
                "reason": "Funding for image usage test",
            },
            follow=True,
        )
        OpenAIModelPricing.objects.update_or_create(
            model_name="gpt-image-1",
            defaults={
                "input_usd_per_1m": "0.000000",
                "output_usd_per_1m": "0.040000",
                "status": OpenAIModelPricing.STATUS_HUMAN_REVISED,
            },
        )
        reporter = views._billing_usage_reporter(
            user_id=self.user.id,
            project_id=self.project.id,
            request_type="image_pages_generate_image",
        )
        reporter(
            {
                "model": "gpt-image-1",
                "operation": "image_generate",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        )

        self.project.refresh_from_db()
        self.assertEqual(str(self.project.total_cost_usd), "0.0400")
        self.assertEqual(str(get_user_balance_usd(self.user)), "9.9600")
        usage = AIUsageCharge.objects.filter(project=self.project).latest("created_at")
        self.assertEqual(usage.request_type, "image_pages_generate_image")
        self.assertEqual(str(usage.cost_usd), "0.040000")
        billing_telemetry_path = self.project.artifact_dir() / "images" / "billing_telemetry.jsonl"
        self.assertTrue(billing_telemetry_path.exists())
        entries = [
            json.loads(line)
            for line in billing_telemetry_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(entries)
        self.assertEqual(entries[-1].get("event"), "billing_usage_recorded")
        self.assertEqual(entries[-1].get("request_type"), "image_pages_generate_image")
        self.assertEqual(entries[-1].get("usage_status"), AIUsageCharge.STATUS_CHARGED)

    def test_pricing_falls_back_to_settings_default_for_models_missing_from_db_table(self):
        OpenAIModelPricing.objects.update_or_create(
            model_name="gpt-4o-mini",
            defaults={
                "input_usd_per_1m": "0.150000",
                "output_usd_per_1m": "0.600000",
                "status": OpenAIModelPricing.STATUS_HUMAN_REVISED,
            },
        )
        cost = estimate_openai_token_cost_usd("gpt-image-1", prompt_tokens=0, completion_tokens=1000)
        self.assertEqual(str(cost), "0.015000")

    def test_pricing_falls_back_to_settings_default_for_models_missing_from_db_table(self):
        OpenAIModelPricing.objects.update_or_create(
            model_name="gpt-4o-mini",
            defaults={
                "input_usd_per_1m": "0.150000",
                "output_usd_per_1m": "0.600000",
                "status": OpenAIModelPricing.STATUS_HUMAN_REVISED,
            },
        )
        cost = estimate_openai_token_cost_usd("gpt-image-1", prompt_tokens=0, completion_tokens=1000)
        self.assertEqual(str(cost), "0.015000")

    def test_admin_can_save_human_reviewed_openai_pricing_row(self):
        self.client.login(username="billing_admin", password="pw")
        resp = self.client.post(
            reverse("admin-tools"),
            {
                "action": "save_openai_pricing",
                "model_name": "gpt-4o-mini",
                "input_usd_per_1m": "0.200000",
                "output_usd_per_1m": "0.800000",
                "source_url": "https://openai.com/api/pricing/",
                "status": OpenAIModelPricing.STATUS_HUMAN_REVISED,
                "notes": "Reviewed by admin.",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        row = OpenAIModelPricing.objects.get(model_name="gpt-4o-mini")
        self.assertEqual(row.status, OpenAIModelPricing.STATUS_HUMAN_REVISED)
        self.assertEqual(str(row.input_usd_per_1m), "0.200000")

    def test_admin_can_save_bulk_manual_pricing_table(self):
        self.client.login(username="billing_admin", password="pw")
        resp = self.client.post(
            reverse("admin-tools"),
            {
                "action": "save_openai_pricing_bulk",
                "source_url": "https://developers.openai.com/api/docs/pricing",
                "bulk_input_gpt-4o": "5.000000",
                "bulk_output_gpt-4o": "15.000000",
                "bulk_input_gpt-image-1": "0.000000",
                "bulk_output_gpt-image-1": "0.040000",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Saved manual pricing for 2 model row(s).")
        self.assertTrue(OpenAIModelPricing.objects.filter(model_name="gpt-4o").exists())
        self.assertTrue(OpenAIModelPricing.objects.filter(model_name="gpt-image-1").exists())
