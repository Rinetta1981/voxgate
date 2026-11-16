"""Fully offline tests for balanced sample design and local-only experiment runner."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from .agent_simulation import load_scenarios
from .experiment_design import audit_by_stratum, balanced_sample
from .live_agent import build_global_catalog, evaluate_with_model

ROOT = Path(__file__).resolve().parent.parent


class BalancedExperimentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all_cases = load_scenarios(ROOT / "data/waitwise_agent_scenarios.csv")

    def test_balanced_eight(self):
        selected = balanced_sample(self.all_cases, 8)
        self.assertEqual(len(selected), 8)
        self.assertEqual(sum(c.revised for c in selected), 4)
        self.assertEqual(sum(not c.revised for c in selected), 4)
        self.assertEqual(len({c.case_id for c in selected}), 8)

    def test_balanced_four_not_only_revisions(self):
        selected = balanced_sample(self.all_cases, 4)
        self.assertEqual(sum(c.revised for c in selected), 2)
        self.assertEqual(sum(not c.revised for c in selected), 2)

    def test_order_independent_reproducible(self):
        self.assertEqual([c.case_id for c in balanced_sample(self.all_cases, 8, 5)],
                         [c.case_id for c in balanced_sample(list(reversed(self.all_cases)), 8, 5)])

    def test_full_sample_covers_all_cases(self):
        selected = balanced_sample(self.all_cases, 24)
        self.assertEqual({c.case_id for c in selected}, {c.case_id for c in self.all_cases})

    def test_reject_odd_or_out_of_range(self):
        for n in (-2, 0, 1, 3, 26):
            with self.subTest(n=n), self.assertRaises(ValueError):
                balanced_sample(self.all_cases, n)

    def test_audit_counts_and_undefined_zero_coverage_rate(self):
        cases = balanced_sample(self.all_cases, 4)
        catalog = build_global_catalog(self.all_cases)
        def fake_model(text, catalog):
            return json.dumps({"action_id": catalog[0]})
        events = evaluate_with_model(cases, fake_model, catalog)
        rows = audit_by_stratum(cases, events)
        self.assertEqual(len(rows), 9)
        for condition in {r["condition"] for r in rows}:
            all_row = next(r for r in rows if r["condition"] == condition and r["stratum"] == "all")
            sub_rows = [r for r in rows if r["condition"] == condition and r["stratum"] != "all"]
            self.assertEqual(all_row["n"], sum(r["n"] for r in sub_rows))
            self.assertEqual(all_row["wrong"], sum(r["wrong"] for r in sub_rows))
            self.assertEqual(all_row["executed"], sum(r["executed"] for r in sub_rows))
            self.assertEqual(all_row["executed"] + all_row["held"], all_row["n"])
            if all_row["executed"] == 0:
                self.assertIsNone(all_row["wrong_rate_executed"])

    def test_reject_duplicate_or_missing_events(self):
        cases = balanced_sample(self.all_cases, 2)
        events = evaluate_with_model(cases, lambda text, catalog: '{"action_id":"HOLD"}', build_global_catalog(self.all_cases))
        with self.assertRaises(ValueError):
            audit_by_stratum(cases, events[:-1])
        with self.assertRaises(ValueError):
            audit_by_stratum(cases, events + [events[0]])

    def test_preview_never_calls_local_model(self):
        import balanced_local_waitwise_agent as runner
        with patch("sys.argv", ["balanced_local_waitwise_agent.py", "--limit", "4"]), patch.object(runner, "LocalOllamaModel") as model:
            self.assertEqual(runner.main(), 0)
            model.assert_not_called()

    def test_runner_writes_stratified_reports_offline_mock(self):
        import balanced_local_waitwise_agent as runner
        class FakeModel:
            def __init__(self, model):
                self.model = model
                self.call_stats = []
            def check_ready(self):
                return {"name": self.model, "digest": "fake"}
            def __call__(self, text, catalog):
                return json.dumps({"action_id": catalog[0]})
        with TemporaryDirectory() as directory:
            with patch("sys.argv", ["balanced_local_waitwise_agent.py", "--run-local", "--limit", "4", "--output-dir", directory]), \
                 patch.object(runner, "LocalOllamaModel", FakeModel):
                self.assertEqual(runner.main(), 0)
            summary = json.loads((Path(directory) / "balanced_summary.json").read_text())
            self.assertEqual(summary["n_revised"], 2)
            self.assertEqual(summary["n_not_revised"], 2)
            self.assertEqual(len(summary["metrics_by_stratum"]), 9)
            with (Path(directory) / "balanced_decisions.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 12)
