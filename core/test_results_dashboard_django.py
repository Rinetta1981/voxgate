"""Django integration tests. Run on the Mac with Django installed."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from core.test_results_dashboard import make_fixture


@override_settings(DEBUG=True)
class ResultsDashboardIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        make_fixture(self.root)
        self.patcher = patch("core.results_dashboard_views.AUDIT_DIR", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_results_route_renders_with_sensible_counts(self):
        response = self.client.get(reverse("results_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Research Results")
        self.assertContains(response, "NR23")
        self.assertContains(response, "58.3%")

    def test_missing_audit_shows_recovery_instructions(self):
        (self.root / "audit_summary.json").unlink()
        response = self.client.get(reverse("results_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit report unavailable")
        self.assertContains(response, "audit_spoken_action_results.py")

    def test_does_not_run_on_nonlocal_ip(self):
        response = self.client.get(reverse("results_dashboard"), REMOTE_ADDR="192.0.2.35")
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_does_not_run_in_production(self):
        response = self.client.get(reverse("results_dashboard"))
        self.assertEqual(response.status_code, 404)

    def test_post_rejected(self):
        self.assertEqual(self.client.post(reverse("results_dashboard")).status_code, 405)
