"""Run: python manage.py test core.test_voicerank_study_django -v 2."""
from __future__ import annotations

import csv
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .test_voicerank import create_fixture
from .voicerank_study_views import KEY


@override_settings(DEBUG=True)
class ExpandedVoiceRankDjangoTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        create_fixture(self.directory)
        patcher = patch("core.voicerank_study_views.VOICE_DIR", self.directory)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_study_page_requires_explicit_consent(self):
        url = reverse("voicerank_study")
        self.assertEqual(url, "/voice/study/")
        response = self.client.get(url)
        self.assertContains(response, "Before you begin")
        self.assertNotIn(KEY, self.client.session)
        response = self.client.post(url, {"command": "start"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(KEY, self.client.session)

    def _start(self):
        response = self.client.post(reverse("voicerank_study"), {"command": "start", "consent": "yes"})
        self.assertEqual(response.status_code, 302)
        return self.client.session[KEY]

    def test_study_creates_pseudonymous_id_and_clips(self):
        state = self._start()
        self.assertEqual(len(state["order"]), 8)
        self.assertRegex(state["participant_id"], r"^vr2-[a-f0-9]{20}$")
        response = self.client.get(reverse("voicerank_study"))
        self.assertContains(response, "<audio", html=False)
        self.assertNotContains(response, "210 words")

    def test_export_requires_all_eight_and_contains_no_name_ip(self):
        self._start()
        self.assertEqual(self.client.get(reverse("voicerank_study") + "?export=csv").status_code, 409)
        for clip in self.client.session[KEY]["order"]:
            response = self.client.post(reverse("voicerank_study"), {
                "command": "rate", "clip_id": clip,
                "authority": "4", "clarity": "3", "urgency": "2",
            })
            self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("voicerank_study") + "?export=csv")
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8"))))
        self.assertEqual(len(rows), 8)
        self.assertEqual(len({r["participant_id"] for r in rows}), 1)
        self.assertNotIn("name", rows[0])
        self.assertNotIn("ip_address", rows[0])
        self.assertEqual({r["authority"] for r in rows}, {"4"})

    def test_repeated_rating_is_rejected(self):
        state = self._start()
        first = state["order"][0]
        data = {"command": "rate", "clip_id": first, "authority": "3", "clarity": "4", "urgency": "5"}
        self.assertEqual(self.client.post(reverse("voicerank_study"), data).status_code, 302)
        self.assertEqual(self.client.post(reverse("voicerank_study"), data).status_code, 400)
        self.assertEqual(len(self.client.session[KEY]["ratings"]), 1)

    def test_invalid_rating_not_recorded(self):
        state = self._start()
        first = state["order"][0]
        response = self.client.post(reverse("voicerank_study"), {
            "command": "rate", "clip_id": first, "authority": "0", "clarity": "4", "urgency": "5",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.client.session[KEY]["ratings"]), 0)

    def test_reset_removes_current_study_but_preserves_pilot(self):
        self._start()
        session = self.client.session
        session["voicerank_ratings_v1"] = {"keep": {"authority": 5}}
        session.save()
        self.assertEqual(self.client.post(reverse("voicerank_study"), {"command": "reset"}).status_code, 302)
        self.assertNotIn(KEY, self.client.session)
        self.assertIn("voicerank_ratings_v1", self.client.session)

    def test_cross_site_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("voicerank_study"), {"command": "start", "consent": "yes"})
        self.assertEqual(response.status_code, 403)

    def test_original_voice_route_stays_live(self):
        self.assertEqual(reverse("voicerank_lab"), "/voice/")
        self.assertEqual(reverse("voicerank_audio", args=["abc"]), "/voice/audio/abc/")

    def test_disabled_outside_local_dev(self):
        from django.test import override_settings
        with override_settings(DEBUG=False):
            self.assertEqual(self.client.get(reverse("voicerank_study")).status_code, 404)
