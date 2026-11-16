"""Local Django tests: python manage.py test core.test_voicerank_django -v 1."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from .test_voicerank import create_fixture
from .voicerank_views import ORDER_KEY, RATINGS_KEY


class VoiceRankDjangoTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.records = create_fixture(self.directory)
        patcher = patch("core.voicerank_views.VOICE_DIR", self.directory)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_home_and_gate_lab_paths_are_preserved(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        self.assertEqual(reverse("gate_lab"), "/lab/")

    def test_voice_page_has_blinded_audio(self):
        response = self.client.get(reverse("voicerank_lab"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blinded Speech Perception Pilot")
        self.assertContains(response, "<audio", html=False)
        self.assertNotContains(response, "155 words")
        self.assertNotContains(response, self.records[0]["transcript"])

    def test_audio_valid_clip_and_unknown_clip(self):
        clip_id = self.records[0]["clip_id"]
        response = self.client.get(reverse("voicerank_audio", args=[clip_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/wav")
        response.close()
        bad = self.client.get(reverse("voicerank_audio", args=["unknownclip"]))
        self.assertEqual(bad.status_code, 404)

    def test_missing_audio_directory_gives_instructions(self):
        with patch("core.voicerank_views.VOICE_DIR", self.directory / "missing"):
            response = self.client.get(reverse("voicerank_lab"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audio stimuli not ready")

    def test_proper_rating_advances_then_replay_rejected(self):
        self.client.get(reverse("voicerank_lab"))
        first = self.client.session[ORDER_KEY][0]
        response = self.client.post(reverse("voicerank_lab"), {
            "command": "rate", "clip_id": first,
            "authority": "5", "clarity": "3", "urgency": "1",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session[RATINGS_KEY][first], {"authority": 5, "clarity": 3, "urgency": 1})
        repeated = self.client.post(reverse("voicerank_lab"), {
            "command": "rate", "clip_id": first,
            "authority": "4", "clarity": "4", "urgency": "4",
        })
        self.assertEqual(repeated.status_code, 400)
        self.assertEqual(len(self.client.session[RATINGS_KEY]), 1)

    def test_invalid_rating_stays_pending(self):
        self.client.get(reverse("voicerank_lab"))
        first = self.client.session[ORDER_KEY][0]
        response = self.client.post(reverse("voicerank_lab"), {
            "command": "rate", "clip_id": first,
            "authority": "0", "clarity": "3", "urgency": "4",
        })
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(first, self.client.session[RATINGS_KEY])

    def test_export_contains_anonymous_ratings(self):
        self.client.get(reverse("voicerank_lab"))
        first = self.client.session[ORDER_KEY][0]
        self.client.post(reverse("voicerank_lab"), {
            "command": "rate", "clip_id": first,
            "authority": "4", "clarity": "3", "urgency": "2",
        })
        response = self.client.get(reverse("voicerank_lab") + "?export=csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn(b"rate_wpm", response.content)
        self.assertIn(b"trial_index", response.content)
        self.assertEqual(response.content.count(b"\n"), 2)

    def test_reset_erases_previous_ratings(self):
        self.client.get(reverse("voicerank_lab"))
        first = self.client.session[ORDER_KEY][0]
        self.client.post(reverse("voicerank_lab"), {
            "command": "rate", "clip_id": first,
            "authority": "5", "clarity": "5", "urgency": "5",
        })
        self.client.post(reverse("voicerank_lab"), {"command": "reset"})
        self.assertNotIn(RATINGS_KEY, self.client.session)

    def test_csrf_required_on_rating(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("voicerank_lab"), {
            "command": "rate", "clip_id": self.records[0]["clip_id"],
            "authority": "2", "clarity": "2", "urgency": "2",
        })
        self.assertEqual(response.status_code, 403)
