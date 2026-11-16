"""Run these integration tests on a Mac with Django installed:

    python manage.py test core.test_web_gate_django -v 1
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from .test_authorization_gate import prior_report


class GateLabViewTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name) / "balanced_decisions.csv"
        fixture = prior_report(self.report)
        # Use an ID that actually exists in this four-case balanced fixture.
        self.case_id = fixture["cases"][0].case_id
        path_patch = patch("core.web_views.REPORT", self.report)
        path_patch.start()
        self.addCleanup(path_patch.stop)

    def test_root_still_loads(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_lab_loads_without_inference(self):
        response = self.client.get(reverse("gate_lab"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Authorization Gate Lab")
        self.assertContains(response, "RESEARCH DEMO ONLY")

    def test_propose_confirm_consumes_once(self):
        self.client.get(reverse("gate_lab"))
        response = self.client.post(reverse("gate_lab"), {
            "command": "propose", "case": self.case_id, "policy": "combined_gate"})
        self.assertEqual(response.status_code, 302)
        pending = self.client.session.get("voxgate_web_gate_pending")
        self.assertIsNotNone(pending)
        response = self.client.post(reverse("gate_lab"), {
            "command": "confirm", "case": pending["case_id"],
            "policy": pending["policy"], "token": pending["token"],
            "action": pending["action"]}, follow=True)
        self.assertContains(response, "Symbolically approved")
        self.assertNotIn("voxgate_web_gate_pending", self.client.session)
        self.assertEqual(len(self.client.session.get("voxgate_web_gate_history", [])), 1)
        again = self.client.post(reverse("gate_lab"), {
            "command": "confirm", "case": pending["case_id"],
            "policy": pending["policy"], "token": pending["token"],
            "action": pending["action"]}, follow=True)
        self.assertContains(again, "no pending proposal")
        self.assertEqual(len(self.client.session.get("voxgate_web_gate_history", [])), 1)

    def test_tampered_proposal_consumed_without_approval(self):
        self.client.post(reverse("gate_lab"), {
            "command": "propose", "case": self.case_id, "policy": "combined_gate"})
        pending = self.client.session["voxgate_web_gate_pending"]
        response = self.client.post(reverse("gate_lab"), {
            "command": "confirm", "case": pending["case_id"],
            "policy": pending["policy"], "token": pending["token"],
            "action": "malicious_action"}, follow=True)
        self.assertContains(response, "Confirmation rejected")
        self.assertNotIn("voxgate_web_gate_pending", self.client.session)
        self.assertFalse(self.client.session.get("voxgate_web_gate_history", []))

    def test_rejection(self):
        self.client.post(reverse("gate_lab"), {
            "command": "propose", "case": self.case_id, "policy": "v3_gate"})
        response = self.client.post(reverse("gate_lab"), {
            "command": "reject", "case": self.case_id, "policy": "v3_gate"}, follow=True)
        self.assertContains(response, "Proposal rejected")
        self.assertNotIn("voxgate_web_gate_pending", self.client.session)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("gate_lab"), {
            "command": "propose", "case": self.case_id, "policy": "combined_gate"})
        self.assertEqual(response.status_code, 403)

    def test_missing_report_shows_guidance(self):
        with patch("core.web_views.REPORT", Path(self.temp.name) / "missing.csv"):
            response = self.client.get(reverse("gate_lab"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saved model results required")

    def test_invalid_proposal_selection_is_rejected(self):
        response = self.client.post(reverse("gate_lab"), {
            "command": "propose", "case": "not-a-case", "policy": "combined_gate"}, follow=True)
        self.assertContains(response, "Invalid case")
        self.assertNotIn("voxgate_web_gate_pending", self.client.session)
