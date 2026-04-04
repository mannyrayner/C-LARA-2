import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class ReportsViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="reporter", password="pw")
        self.client = Client()

    def test_reports_page_requires_login(self):
        resp = self.client.get(reverse("reports-home"))
        self.assertEqual(resp.status_code, 302)

    def test_reports_page_lists_most_recent_first(self):
        self.client.login(username="reporter", password="pw")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            updates = root / "reports" / "updates"
            updates.mkdir(parents=True, exist_ok=True)
            older = updates / "2026-04-01-status.html"
            newer = updates / "2026-04-02-status.html"
            older.write_text("<html><body>old</body></html>", encoding="utf-8")
            newer.write_text("<html><body>new</body></html>", encoding="utf-8")
            with patch("projects.views._reports_root", return_value=root / "reports"):
                resp = self.client.get(reverse("reports-home"))
                self.assertEqual(resp.status_code, 200)
                reports = list(resp.context["reports"])
                self.assertEqual(reports[0]["name"], "2026-04-02-status.html")
                self.assertEqual(reports[1]["name"], "2026-04-01-status.html")

    def test_report_detail_serves_html(self):
        self.client.login(username="reporter", password="pw")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            updates = root / "reports" / "updates"
            updates.mkdir(parents=True, exist_ok=True)
            report = updates / "report.html"
            report.write_text("<html><body>report body</body></html>", encoding="utf-8")
            with patch("projects.views._reports_root", return_value=root / "reports"):
                resp = self.client.get(reverse("report-detail", args=["report.html"]))
                self.assertEqual(resp.status_code, 200)
                self.assertIn("report body", resp.content.decode("utf-8"))
