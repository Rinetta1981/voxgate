"""Tests for WaitWise's entirely offline policy simulator."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from core.agent_simulation import POLICIES, Scenario, load_scenarios, simulate, summarize
from core.analysis_v3 import detect_instruction_revision_v3

DATA = Path(__file__).resolve().parent.parent / "data" / "waitwise_agent_scenarios.csv"


class AgentSimulationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_scenarios(DATA)

    def test_scenario_counts_and_labels(self):
        self.assertEqual(len(self.cases), 24)
        self.assertEqual(sum(c.revised for c in self.cases), 12)
        self.assertEqual(len({c.case_id for c in self.cases}), 24)

    def test_immediate_is_early_and_can_be_wrong(self):
        case = self.cases[0]
        decision = simulate(case, "immediate", detect_instruction_revision_v3)
        self.assertEqual(decision.phase, "initial")
        self.assertEqual(decision.t_ms, 0)
        self.assertTrue(decision.premature)
        self.assertTrue(decision.wrong_action)

    def test_turn_end_is_not_automatically_correct(self):
        decision = simulate(self.cases[0], "turn_end", detect_instruction_revision_v3)
        self.assertFalse(decision.premature)
        self.assertTrue(decision.wrong_action)

    def test_repair_gate_holds_detected_revision(self):
        decision = simulate(self.cases[0], "repair_gate", detect_instruction_revision_v3)
        self.assertTrue(decision.held)
        self.assertTrue(decision.detected_revision)
        self.assertFalse(decision.wrong_action)

    def test_repair_gate_can_miss_implicit_revision(self):
        case = next(c for c in self.cases if c.case_id == "AG09")
        decision = simulate(case, "repair_gate", detect_instruction_revision_v3)
        self.assertFalse(decision.held)
        self.assertTrue(decision.wrong_action)
        self.assertFalse(decision.detected_revision)

    def test_confirmation_gate_zero_coverage(self):
        summary = summarize([simulate(c, "confirmation_gate", detect_instruction_revision_v3) for c in self.cases])
        self.assertEqual(summary["action_coverage"], 0)
        self.assertEqual(summary["wrong_actions"], 0)
        self.assertEqual(summary["false_holds"], 12)

    def test_oracle_is_upper_bound_not_deployable(self):
        summary = summarize([simulate(c, "oracle_final", detect_instruction_revision_v3) for c in self.cases])
        self.assertEqual(summary["action_coverage"], 1)
        self.assertEqual(summary["wrong_actions"], 0)
        self.assertEqual(summary["premature_actions"], 0)

    def test_every_policy_has_24_decisions(self):
        for policy in POLICIES:
            with self.subTest(policy=policy):
                decisions = [simulate(c, policy, detect_instruction_revision_v3) for c in self.cases]
                self.assertEqual(summarize(decisions)["n"], 24)

    def test_summarize_rejects_mixed_policies(self):
        with self.assertRaises(ValueError):
            summarize([simulate(self.cases[0], "immediate", detect_instruction_revision_v3),
                       simulate(self.cases[0], "turn_end", detect_instruction_revision_v3)])

    def test_load_rejects_annotation_conflict(self):
        with TemporaryDirectory() as temp:
            file = Path(temp) / "bad.csv"
            file.write_text("case_id,transcript,initial_action,final_action,revises_prior_instruction,discourse_function\n"
                            "X,Send X then send Y,send_x,send_y,0,wrong_label\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_scenarios(file)
