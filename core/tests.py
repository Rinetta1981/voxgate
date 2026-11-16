"""Regression tests for WaitWise's text-only evaluation utilities."""

from pathlib import Path

from unittest import TestCase

from core.analysis import detect_repair_cues
from core.analysis_v2 import detect_instruction_revision
from core.analysis_v3 import detect_instruction_revision_v3
from core.evaluation import calculate_metrics, evaluate_examples, load_examples

ROOT = Path(__file__).resolve().parent.parent


class WaitWiseBenchmarkTests(TestCase):
    def test_data_loads_and_has_expected_sizes(self):
        for filename, size in (("waitwise_cases.csv", 8), ("waitwise_challenge.csv", 12), ("waitwise_stress.csv", 20)):
            with self.subTest(filename=filename):
                self.assertEqual(len(load_examples(ROOT / "data" / filename)), size)

    def test_v1_development_regression(self):
        examples = load_examples(ROOT / "data/waitwise_cases.csv")
        metrics, _ = evaluate_examples(examples, detect_repair_cues)
        self.assertEqual((metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"]), (3, 2, 1, 2))

    def test_v2_challenge_regression(self):
        examples = load_examples(ROOT / "data/waitwise_challenge.csv")
        metrics, _ = evaluate_examples(examples, detect_instruction_revision)
        self.assertEqual((metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"]), (3, 3, 3, 3))

    def test_v3_challenge_regression(self):
        examples = load_examples(ROOT / "data/waitwise_challenge.csv")
        metrics, _ = evaluate_examples(examples, detect_instruction_revision_v3)
        self.assertEqual((metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"]), (6, 0, 0, 6))

    def test_zero_denominators(self):
        metrics = calculate_metrics([0, 0], [0, 0])
        self.assertEqual(metrics["precision"], 0)
        self.assertEqual(metrics["recall"], 0)
        self.assertEqual(metrics["f1"], 0)
        self.assertEqual(metrics["accuracy"], 1)

    def test_invalid_labels_are_rejected(self):
        with self.assertRaises(ValueError):
            calculate_metrics([0, 2], [0, 1])
