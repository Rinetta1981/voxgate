"""Reproducible, text-only evaluation helpers for WaitWise.

These metrics evaluate rule-based transcript classifiers, not AI-agent safety.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Example:
    number: int
    transcript: str
    gold: int
    discourse_function: str = ""


def load_examples(path: str | Path) -> list[Example]:
    """Read and validate a labeled CSV (0 = no revision, 1 = revision)."""
    path = Path(path)
    examples: list[Example] = []
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"transcript", "revises_prior_instruction"}.issubset(reader.fieldnames):
            raise ValueError(f"Missing required columns in {path}")
        for number, row in enumerate(reader, start=1):
            transcript = (row.get("transcript") or "").strip()
            gold_text = (row.get("revises_prior_instruction") or "").strip()
            if not transcript or gold_text not in {"0", "1"}:
                raise ValueError(f"Invalid data in {path}, row {number + 1}")
            if transcript in seen:
                raise ValueError(f"Duplicate transcript in {path}, row {number + 1}")
            seen.add(transcript)
            examples.append(Example(number, transcript, int(gold_text), (row.get("discourse_function") or "").strip()))
    if not examples:
        raise ValueError(f"No examples in {path}")
    return examples


def calculate_metrics(gold: list[int], predicted: list[int]) -> dict[str, float | int]:
    """Compute confusion counts and standard binary-classification metrics."""
    if not gold or len(gold) != len(predicted):
        raise ValueError("Gold labels and predictions must have equal nonzero length")
    if any(value not in (0, 1) for value in gold + predicted):
        raise ValueError("Labels and predictions must be 0 or 1")
    tp = sum(g == 1 and p == 1 for g, p in zip(gold, predicted))
    fp = sum(g == 0 and p == 1 for g, p in zip(gold, predicted))
    fn = sum(g == 1 and p == 0 for g, p in zip(gold, predicted))
    tn = sum(g == 0 and p == 0 for g, p in zip(gold, predicted))
    ratio = lambda a, b: a / b if b else 0.0
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    return {
        "n": len(gold), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall,
        "f1": ratio(2 * precision * recall, precision + recall),
        "specificity": specificity,
        "accuracy": ratio(tp + tn, len(gold)),
        "balanced_accuracy": (recall + specificity) / 2,
    }


def evaluate_examples(examples: list[Example], detector: Callable[[str], object]) -> tuple[dict[str, float | int], list[dict[str, object]]]:
    """Evaluate a detector; return metrics and one prediction record per case."""
    gold = [example.gold for example in examples]
    predicted = [int(bool(detector(example.transcript))) for example in examples]
    metrics = calculate_metrics(gold, predicted)
    rows = []
    for example, prediction in zip(examples, predicted):
        outcome = ("TP" if prediction else "FN") if example.gold else ("FP" if prediction else "TN")
        rows.append({
            "case": example.number, "gold": example.gold,
            "predicted": prediction, "outcome": outcome,
            "discourse_function": example.discourse_function,
            "transcript": example.transcript,
        })
    return metrics, rows
