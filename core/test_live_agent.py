"""Safe offline tests: no network and no real tool calls."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from .agent_simulation import load_scenarios
from .live_agent import (HOLD, InertToolExecutor, ModelResponseError, OpenAIResponsesModel,
                         build_global_catalog, build_user_input, evaluate_with_model,
                         extract_response_text, parse_choice, summarize_events)

ROOT = Path(__file__).resolve().parent.parent


class LiveAgentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_scenarios(ROOT / "data/waitwise_agent_scenarios.csv")
        cls.catalog = build_global_catalog(cls.cases)

    def test_catalog_is_global_and_sorted(self):
        self.assertIn(self.cases[0].initial_action, self.catalog)
        self.assertIn(self.cases[0].final_action, self.catalog)
        self.assertEqual(tuple(sorted(self.catalog)), self.catalog)

    def test_prompt_contains_no_case_gold_metadata(self):
        prompt = json.loads(build_user_input(self.cases[0].transcript, self.catalog))
        self.assertEqual(set(prompt), {"transcript", "global_action_catalog", "hold_option"})
        self.assertNotIn("revises_prior_instruction", prompt)
        self.assertNotIn("final_action", prompt)
        self.assertNotIn("initial_action", prompt)
        self.assertNotIn("case_id", prompt)

    def test_no_key_disallows_api_client(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            with self.assertRaises(ModelResponseError):
                OpenAIResponsesModel("gpt-4.1-mini")

    def test_invalid_json_is_hold(self):
        self.assertEqual(parse_choice("send_memo_pat", self.catalog), (HOLD, "invalid_json"))

    def test_extra_keys_are_rejected(self):
        self.assertEqual(parse_choice('{"action_id":"HOLD","reason":"x"}', self.catalog), (HOLD, "invalid_schema"))

    def test_nonallowlisted_choice_is_hold(self):
        self.assertEqual(parse_choice('{"action_id":"wire_money"}', self.catalog), (HOLD, "unallowlisted_action"))

    def test_valid_choice(self):
        action = self.cases[0].final_action
        self.assertEqual(parse_choice(json.dumps({"action_id": action}), self.catalog), (action, "valid"))

    def test_completed_response_extracts_text(self):
        response = {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"action_id":"HOLD"}'}]}]}
        self.assertEqual(extract_response_text(response), '{"action_id":"HOLD"}')

    def test_unfinished_response_aborts(self):
        with self.assertRaises(ModelResponseError):
            extract_response_text({"status": "incomplete", "output": []})

    def test_executor_records_only(self):
        tool = InertToolExecutor(self.catalog)
        choice = self.cases[0].initial_action
        event = tool.record(self.cases[0], "test", choice, "valid")
        self.assertTrue(event.wrong)
        self.assertEqual(event.selected_action, choice)
        self.assertEqual(len(tool.events), 1)

    def test_executor_rejects_unknown_action(self):
        with self.assertRaises(ValueError):
            InertToolExecutor(self.catalog).record(self.cases[0], "test", "real_action", "valid")

    def test_pipeline_with_fake_model_and_gate(self):
        calls = []
        def fake_model(transcript, catalog):
            calls.append(transcript)
            return json.dumps({"action_id": catalog[0]})
        events = evaluate_with_model(self.cases[:2], fake_model)
        self.assertEqual(len(calls), 4)
        self.assertEqual(len(events), 6)
        summary = summarize_events(events)
        self.assertEqual(len(summary), 3)
        self.assertTrue(any(event.condition == "full_text_plus_v3_gate" and event.held for event in events))

    def test_no_model_invocation_for_offline_preview(self):
        # Guard against accidental live requests in the default command.
        import live_waitwise_agent
        with patch("sys.argv", ["live_waitwise_agent.py", "--limit", "1"]), patch.object(live_waitwise_agent, "OpenAIResponsesModel") as provider:
            self.assertEqual(live_waitwise_agent.main(), 0)
            provider.assert_not_called()
