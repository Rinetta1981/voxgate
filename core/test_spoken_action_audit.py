"""Offline regression tests for paired, no-inference spoken-action audit."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from .spoken_action import evaluate_model_choices, fixed_catalog, load_asr_trials, load_labels
from .spoken_action_audit import analyze, read_csv, render_markdown
from .spoken_repair_fresh import evaluate, plan

ROOT = Path(__file__).resolve().parent.parent


class SpokenActionAuditTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        trials, _ = evaluate(plan(), {str(r['clip_id']): str(r['transcript']) for r in plan()})
        # Include one plausible ASR misrecognition to create a paired action-choice change.
        for row in trials:
            if row['case_id'] == 'NR01' and row['condition'] == 'faster':
                row['asr_transcript'] = 'ASR SWITCH forward the contract to finance.'
        with TemporaryDirectory() as folder:
            csv_path = Path(folder) / 'asr.csv'
            with csv_path.open('w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=list(trials[0]))
                writer.writeheader()
                writer.writerows(trials)
            cases = load_asr_trials(csv_path, load_labels(ROOT / 'data/fresh_spoken_action_labels.csv'))
        catalog = fixed_catalog(cases)
        action_regular = 'forward_contract_legal'
        action_switched = 'forward_contract_finance'
        def model(text, choices):
            return json.dumps({'action_id': action_switched if 'ASR SWITCH' in text else action_regular})
        cls.models, cls.policies, cls.comparisons = evaluate_model_choices(cases, catalog, model)
        # CSV output produces strings for numerical values; mirror the real saved reports.
        cls.models = [{k: str(v) for k, v in row.items()} for row in cls.models]
        cls.policies = [{k: str(v) for k, v in row.items()} for row in cls.policies]
        cls.comparisons = [{k: str(v) for k, v in row.items()} for row in cls.comparisons]

    def _run(self, models=None, policies=None, comparisons=None):
        return analyze(self.models if models is None else models,
                       self.policies if policies is None else policies,
                       self.comparisons if comparisons is None else comparisons)

    def test_expected_full_balanced_counts(self):
        result = self._run()
        self.assertEqual(result['n_cases'], 24)
        self.assertEqual(result['n_paired_comparisons'], 48)
        self.assertEqual(result['cohorts'], {'revised': 12, 'not_revised': 12})
        self.assertEqual(len(result['policy_metrics']), 27)

    def test_detects_and_describes_changed_model_choice(self):
        rows = self._run()['changed_rows']
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['case_id'], rows[0]['source']), ('NR01', 'faster'))
        self.assertEqual(rows[0]['transition'], 'wrong_to_correct')

    def test_no_change_has_not_been_confused_with_audio_equivalence(self):
        result = self._run()
        self.assertEqual(sum(x['model_choice_changed'] for x in result['paired_rows']), 1)
        self.assertEqual(sum(x['asr_text_differs'] for x in result['paired_rows']), 1)

    def test_policy_accounting(self):
        result = self._run()
        self.assertTrue(all(m['proposed'] + m['held'] == m['n'] for m in result['policy_metrics']))
        self.assertTrue(all(m['correct'] + m['wrong'] == m['proposed'] for m in result['policy_metrics']))

    def test_missing_model_or_policy_rows_rejected(self):
        with self.assertRaises(ValueError):
            self._run(models=self.models[:-1])
        with self.assertRaises(ValueError):
            self._run(policies=self.policies[:-1])

    def test_missing_comparisons_rejected(self):
        with self.assertRaises(ValueError):
            self._run(comparisons=self.comparisons[:-1])

    def test_duplicate_rows_rejected(self):
        with self.assertRaises(ValueError):
            self._run(models=self.models + [self.models[0]])

    def test_wrong_choice_flag_rejected(self):
        altered = [dict(x) for x in self.comparisons]
        altered[0]['model_choice_changed_vs_reference'] = str(1 - int(altered[0]['model_choice_changed_vs_reference']))
        with self.assertRaises(ValueError):
            self._run(comparisons=altered)

    def test_leaked_held_action_rejected(self):
        altered = [dict(x) for x in self.policies]
        for row in altered:
            if row['held'] == '1':
                row['proposed_action'] = 'should_never_execute'
                break
        else:
            self.fail('Test fixture has no held proposals')
        with self.assertRaises(ValueError):
            self._run(policies=altered)

    def test_label_mismatch_rejected(self):
        altered = [dict(x) for x in self.models]
        altered[0]['gold_final_action'] = 'fake_action'
        with self.assertRaises(ValueError):
            self._run(models=altered)

    def test_invalid_binary_flag_rejected(self):
        altered = [dict(x) for x in self.models]
        altered[0]['correct_proposal'] = 'invalid'
        with self.assertRaises(ValueError):
            self._run(models=altered)

    def test_markdown_has_methodology_cautions(self):
        md = render_markdown(self._run())
        for phrase in ('24 researcher-constructed scenarios', 'not independent', 'not raw audio', 'NR01'):
            self.assertIn(phrase, md)

    def test_read_csv_roundtrip(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'test.csv'
            with path.open('w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=list(self.comparisons[0]))
                writer.writeheader()
                writer.writerows(self.comparisons)
            self.assertEqual(read_csv(path), self.comparisons)
