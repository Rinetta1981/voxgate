"""Offline tests for policy replay and inert confirmation mechanics."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from .authorization_gate import (InertConfirmationQueue, apply_gate, read_saved_choices,
                                 run_policy_replay, summarize_gate)
from .agent_simulation import load_scenarios
from .experiment_design import balanced_sample
from .live_agent import build_global_catalog, evaluate_with_model

ROOT = Path(__file__).resolve().parent.parent


def prior_report(path: Path, model=None) -> dict:
    """Synthetic, never-networked output mirroring the user's report structure."""
    cases = load_scenarios(ROOT / "data" / "waitwise_agent_scenarios.csv")
    selected = balanced_sample(cases, 4)
    catalog = build_global_catalog(cases)
    if model is None:
        model = lambda text, _: json.dumps({"action_id": catalog[0]})
    events = evaluate_with_model(selected, model, catalog)
    by_id = {c.case_id: c for c in selected}
    from .analysis_v3 import detect_instruction_revision_v3
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "gold_revised", "v3_detected", "condition", "selected_action", "status", "gold_action", "wrong", "held"])
        writer.writeheader()
        for event in events:
            case = by_id[event.case_id]
            writer.writerow({"case_id": event.case_id, "gold_revised": int(case.revised),
                             "v3_detected": int(detect_instruction_revision_v3(case.transcript)),
                             "condition": event.condition, "selected_action": event.selected_action or "",
                             "status": event.status, "gold_action": event.gold_action,
                             "wrong": int(event.wrong), "held": int(event.held)})
    return {"cases": selected, "catalog": catalog}


class AuthorizationGateTests(TestCase):
    def test_policy_replay_has_four_policies_and_strata(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "balanced_decisions.csv"
            prior_report(path)
            saved = read_saved_choices(path)
            decisions = run_policy_replay(saved)
            self.assertEqual(len(saved), 4)
            self.assertEqual(len(decisions), 16)
            summary = summarize_gate(decisions)
            self.assertEqual(len(summary), 12)
            self.assertEqual({r["policy"] for r in summary}, {"full_text", "v3_gate", "disagreement_gate", "combined_gate"})
            self.assertEqual(next(r for r in summary if r["policy"] == "full_text" and r["stratum"] == "all")["executed"], 4)

    def test_detector_gate_reproduces_saved_v3(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "saved.csv"
            prior_report(path)
            for rows in read_saved_choices(path).values():
                d = apply_gate(rows, "v3_gate")
                self.assertEqual(d.action, rows["full_text_plus_v3_gate"].action)

    def test_policy_is_independent_of_gold_label(self):
        from dataclasses import replace
        with TemporaryDirectory() as temp:
            path = Path(temp) / "saved.csv"
            prior_report(path)
            case = next(iter(read_saved_choices(path).values()))
            changed = {key: replace(value, gold_action="fictional_new_gold", gold_revised=not value.gold_revised)
                       for key, value in case.items()}
            for policy in ("full_text", "v3_gate", "disagreement_gate", "combined_gate"):
                original = apply_gate(case, policy)
                relabeled = apply_gate(changed, policy)
                self.assertEqual((original.action, original.reason), (relabeled.action, relabeled.reason))

    def test_disagreement_gate_holds_when_model_changes_choice(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "saved.csv"
            catalog = prior_report(path)["catalog"]
            # One choice for initial text, another for complete text.
            def model(text, _):
                return json.dumps({"action_id": catalog[0] if len(text) < 25 else catalog[1]})
            prior_report(path, model)
            saved = read_saved_choices(path)
            self.assertTrue(any(apply_gate(r, "disagreement_gate").held for r in saved.values()))

    def test_disagreement_gate_holds_if_partial_invalid(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "saved.csv"
            catalog = prior_report(path)["catalog"]
            def model(text, _):
                return "not json" if len(text) < 25 else json.dumps({"action_id": catalog[0]})
            prior_report(path, model)
            saved = read_saved_choices(path)
            self.assertTrue(any(apply_gate(r, "disagreement_gate").held for r in saved.values()))

    def test_combined_gate_never_executes_when_v3_holds(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "saved.csv"
            prior_report(path)
            for rows in read_saved_choices(path).values():
                if rows["full_text"].v3_detected:
                    self.assertTrue(apply_gate(rows, "combined_gate").held)

    def test_reject_missing_or_duplicate_rows(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "saved.csv"
            prior_report(path)
            lines = path.read_text().splitlines(keepends=True)
            path.write_text("".join(lines[:-1]))
            with self.assertRaises(ValueError):
                read_saved_choices(path)
            prior_report(path)
            with path.open("a") as handle:
                handle.write(path.read_text().splitlines()[-1] + "\n")
            with self.assertRaises(ValueError):
                read_saved_choices(path)

    def test_confirmation_is_exact_match_one_use(self):
        queue = InertConfirmationQueue()
        p = queue.propose("Send the memo to Robin", "send_memo_robin", ("send_memo_robin", "send_memo_pat"))
        self.assertEqual(queue.confirm(p.request_id, "send_memo_robin", transcript="Send the memo to Robin"), "send_memo_robin")
        with self.assertRaises(ValueError):
            queue.confirm(p.request_id, "send_memo_robin", transcript="Send the memo to Robin")

    def test_confirmation_rejects_changed_action_or_text(self):
        q = InertConfirmationQueue()
        p = q.propose("Email Robin", "email_robin", ("email_robin", "email_pat"))
        with self.assertRaises(ValueError):
            q.confirm(p.request_id, "email_pat", transcript="Email Robin")
        with self.assertRaises(ValueError):
            q.confirm(p.request_id, "email_robin", transcript="Email Robin")
        p2 = q.propose("Email Robin", "email_robin", ("email_robin",))
        with self.assertRaises(ValueError):
            q.confirm(p2.request_id, "email_robin", transcript="Email Pat")

    def test_queue_rejects_invalid_proposal(self):
        q = InertConfirmationQueue()
        for transcript, action in (("", "email_robin"), ("Email Robin", "bad_action"), ("Email Robin", "HOLD")):
            with self.subTest(action=action), self.assertRaises(ValueError):
                q.propose(transcript, action, ("email_robin",))

    def test_queue_rejects_repeat_rejection(self):
        q = InertConfirmationQueue()
        p = q.propose("Email Robin", "email_robin", ("email_robin",))
        q.reject(p.request_id)
        with self.assertRaises(ValueError):
            q.reject(p.request_id)

    def test_cli_creates_reports_without_model_calls(self):
        import audit_authorization_gate as cli
        with TemporaryDirectory() as temp:
            src = Path(temp) / "saved.csv"
            prior_report(src)
            output = Path(temp) / "reports"
            with patch("sys.argv", ["audit_authorization_gate.py", "--input", str(src), "--output-dir", str(output)]):
                self.assertEqual(cli.main(), 0)
            self.assertTrue((output / "gate_summary.json").exists())
            with (output / "gate_decisions.csv").open(newline="", encoding="utf-8") as report_file:
                self.assertEqual(len(list(csv.DictReader(report_file))), 16)
