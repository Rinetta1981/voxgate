"""Offline tests for exact-match, time-limited symbolic confirmation."""
from unittest import TestCase

from .web_gate import MAX_PENDING_SECONDS, confirm_pending, make_pending


class WebGateLogicTests(TestCase):
    def setUp(self):
        self.catalog = ("email_pat", "email_robin")
        self.transcript = "Email Pat. Actually, email Robin."
        self.pending = make_pending(
            case_id="AG01", policy="combined_gate", transcript=self.transcript,
            action="email_robin", allowed_actions=self.catalog,
            reason="v3_flag", was_held=True, now=100.0)

    def confirm(self, **kwargs):
        fields = {"token": self.pending["token"], "action": "email_robin",
                  "transcript": self.transcript, "expected_action": "email_robin", "now": 200.0}
        fields.update(kwargs)
        return confirm_pending(self.pending, **fields)

    def test_approve_exact_action(self):
        self.assertEqual(self.confirm(), "email_robin")

    def test_wrong_action_rejected(self):
        with self.assertRaises(ValueError):
            self.confirm(action="email_pat")

    def test_tampered_token_rejected(self):
        with self.assertRaises(ValueError):
            self.confirm(token="fake-token")

    def test_changed_transcript_rejected(self):
        with self.assertRaises(ValueError):
            self.confirm(transcript="Email Pat.")

    def test_stale_saved_model_choice_rejected(self):
        with self.assertRaises(ValueError):
            self.confirm(expected_action="email_pat")

    def test_proposal_expires(self):
        with self.assertRaises(ValueError):
            self.confirm(now=100.0 + MAX_PENDING_SECONDS + 1)

    def test_future_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            self.confirm(now=99.0)

    def test_hold_never_approvable(self):
        with self.assertRaises(ValueError):
            make_pending(case_id="AG01", policy="combined_gate", transcript=self.transcript,
                         action="HOLD", allowed_actions=self.catalog,
                         reason="v3_flag", was_held=True)

    def test_unallowlisted_action_rejected(self):
        with self.assertRaises(ValueError):
            make_pending(case_id="AG01", policy="combined_gate", transcript=self.transcript,
                         action="delete_everything", allowed_actions=self.catalog,
                         reason="v3_flag", was_held=True)

    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            make_pending(case_id="AG01", policy="combined_gate", transcript=" ",
                         action="email_robin", allowed_actions=self.catalog,
                         reason="v3_flag", was_held=True)

    def test_incomplete_proposal_rejected(self):
        with self.assertRaises(ValueError):
            confirm_pending({}, token="", action="email_robin",
                            transcript=self.transcript, expected_action="email_robin")
