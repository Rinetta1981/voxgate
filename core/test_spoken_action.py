"""Offline tests: the local-model spoken-action benchmark uses no live model."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from .spoken_repair_fresh import evaluate, plan
from .spoken_action import (
    ACTION_ID, balanced_subset, evaluate_model_choices, fixed_catalog,
    load_asr_trials, load_labels, summarize_decisions,
)

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "data" / "fresh_spoken_action_labels.csv"


class SpokenActionTests(TestCase):
    def setUp(self):
        self.labels = load_labels(LABELS)
        self.frozen = plan()
        hypotheses = {str(item["clip_id"]): str(item["transcript"]) for item in self.frozen}
        self.rows, _ = evaluate(self.frozen, hypotheses)

    def _write_trials(self, path, rows=None):
        if rows is None:
            rows = self.rows
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    def _cases(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "trials.csv"
            self._write_trials(path)
            return load_asr_trials(path, self.labels)

    def test_24_manual_action_annotations_match_gold(self):
        self.assertEqual(len(self.labels), 24)
        self.assertEqual(sum(label["revision"] == "1" for label in self.labels.values()), 12)
        self.assertTrue(all(ACTION_ID.fullmatch(r["initial"]) and ACTION_ID.fullmatch(r["final"]) for r in self.labels.values()))

    def test_global_catalog_is_fixed_and_nonempty(self):
        cases = self._cases()
        catalog = fixed_catalog(cases)
        self.assertEqual(catalog, tuple(sorted(set(catalog))))
        self.assertIn("send_invitation_tomorrow", catalog)
        with self.assertRaises(ValueError):
            fixed_catalog(cases[:4])

    def test_balanced_selection_and_determinism(self):
        cases = self._cases()
        for n in (2, 4, 8, 24):
            result = balanced_subset(cases, n)
            self.assertEqual(len(result), n)
            self.assertEqual(sum(c.gold_revision for c in result), n // 2)
            self.assertEqual(result, balanced_subset(list(reversed(cases)), n))
        for n in (0, 1, 3, 25, 26):
            with self.assertRaises(ValueError):
                balanced_subset(cases, n)

    def test_reject_missing_or_duplicate_asr_trials(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "trials.csv"
            self._write_trials(p, self.rows[:-1])
            with self.assertRaises(ValueError):
                load_asr_trials(p, self.labels)
            self._write_trials(p, self.rows[:-1] + [self.rows[0]])
            with self.assertRaises(ValueError):
                load_asr_trials(p, self.labels)

    def test_reject_changed_reference_or_gold(self):
        for field, value in (("gold_revision", "9"), ("reference_transcript", "fake"), ("clip_id", "fake")):
            with self.subTest(field=field), TemporaryDirectory() as d:
                p = Path(d) / "trials.csv"
                altered = [dict(r) for r in self.rows]
                altered[0][field] = value
                self._write_trials(p, altered)
                with self.assertRaises(ValueError):
                    load_asr_trials(p, self.labels)

    def test_reject_empty_transcript(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "trials.csv"
            altered = [dict(r) for r in self.rows]
            altered[0]["asr_transcript"] = ""
            self._write_trials(p, altered)
            with self.assertRaises(ValueError):
                load_asr_trials(p, self.labels)

    def test_three_calls_per_case_and_nine_policy_rows_per_case(self):
        cases = balanced_subset(self._cases(), 4)
        catalog = fixed_catalog(self._cases())
        called = []
        def fake_model(transcript, choices):
            self.assertEqual(choices, catalog)
            called.append(transcript)
            return json.dumps({"action_id": "forward_contract_legal"})
        raw, decisions, comparison = evaluate_model_choices(cases, catalog, fake_model)
        self.assertEqual(len(called), 12)
        self.assertEqual(len(raw), 12)
        self.assertEqual(len(decisions), 36)
        self.assertEqual(len(comparison), 8)
        summary = summarize_decisions(decisions)
        self.assertEqual(len(summary), 9)
        self.assertTrue(all(s["n"] == 4 for s in summary))
        self.assertTrue(all(s["proposed"] + s["held"] == s["n"] for s in summary))
        self.assertTrue(all(s["correct"] + s["wrong"] == s["proposed"] for s in summary))

    def test_revisions_are_reviewed_and_model_is_never_executor(self):
        cases = [c for c in self._cases() if c.case_id in {"NR01", "NR13"}]
        catalog = fixed_catalog(self._cases())
        _, decisions, _ = evaluate_model_choices(cases, catalog, lambda _text, _catalog: '{"action_id":"forward_contract_legal"}')
        revised_v4 = [r for r in decisions if r["case_id"] == "NR01" and r["policy"] == "v4_review"]
        self.assertEqual(len(revised_v4), 3)
        self.assertTrue(all(r["disposition"] == "review_required" for r in revised_v4))
        self.assertTrue(all(r["proposed_action"] == "" for r in revised_v4))
        unrevised_v4 = [r for r in decisions if r["case_id"] == "NR13" and r["policy"] == "v4_review"]
        self.assertTrue(all(r["disposition"] == "proposal_only" for r in unrevised_v4))

    def test_invalid_model_output_abstains(self):
        cases = balanced_subset(self._cases(), 2)
        catalog = fixed_catalog(self._cases())
        _, decisions, _ = evaluate_model_choices(cases, catalog, lambda *_: "not-json")
        self.assertEqual(len(decisions), 18)
        self.assertTrue(all(r["proposed_action"] == "" and r["held"] == 1 for r in decisions))
        self.assertEqual(sum(s["invalid_model_output"] for s in summarize_decisions(decisions)), 18)

    def test_identical_asr_and_reference_do_not_change_model_choice(self):
        cases = balanced_subset(self._cases(), 4)
        catalog = fixed_catalog(self._cases())
        _, _, pairs = evaluate_model_choices(cases, catalog, lambda *_: '{"action_id":"HOLD"}')
        self.assertTrue(all(r["model_choice_changed_vs_reference"] == 0 for r in pairs))
        self.assertTrue(all(r["reference_equals_asr"] == 1 for r in pairs))

    def test_zero_proposals_yields_undefined_wrong_proposal_rate(self):
        cases = balanced_subset(self._cases(), 2)
        catalog = fixed_catalog(self._cases())
        _, decisions, _ = evaluate_model_choices(cases, catalog, lambda *_: '{"action_id":"HOLD"}')
        self.assertTrue(all(row["wrong_among_proposed"] is None for row in summarize_decisions(decisions)))
