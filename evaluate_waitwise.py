"""Run WaitWise V1/V2/V3 text-only benchmark comparisons.

Example:
    python evaluate_waitwise.py --output-dir reports/waitwise
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from core.analysis import detect_repair_cues
from core.analysis_v2 import detect_instruction_revision
from core.analysis_v3 import detect_instruction_revision_v3
from core.evaluation import evaluate_examples, load_examples

ROOT = Path(__file__).resolve().parent
DATASETS = {
    "development": ROOT / "data/waitwise_cases.csv",
    "challenge": ROOT / "data/waitwise_challenge.csv",
    "stress": ROOT / "data/waitwise_stress.csv",
}
DETECTORS = {
    "V1": detect_repair_cues,
    "V2": detect_instruction_revision,
    "V3": detect_instruction_revision_v3,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["all", *DATASETS], default="all")
    parser.add_argument("--output-dir", type=Path, help="Optional folder for CSV/JSON reports")
    args = parser.parse_args()

    summaries: list[dict[str, object]] = []
    cases: list[dict[str, object]] = []
    selected = DATASETS if args.dataset == "all" else {args.dataset: DATASETS[args.dataset]}
    for dataset, path in selected.items():
        examples = load_examples(path)
        print(f"\n{dataset.upper()} — {len(examples)} constructed examples")
        print("Model  TP FP FN TN  Precision Recall F1  Accuracy")
        for name, detector in DETECTORS.items():
            metrics, predictions = evaluate_examples(examples, detector)
            summaries.append({"dataset": dataset, "detector": name, **metrics})
            cases.extend({"dataset": dataset, "detector": name, **case} for case in predictions)
            print(f"{name:<5} {metrics['tp']:>2} {metrics['fp']:>2} {metrics['fn']:>2} {metrics['tn']:>2} "
                  f"{metrics['precision']:.2f}     {metrics['recall']:.2f}   {metrics['f1']:.2f} {metrics['accuracy']:.2f}")
        print("V3 errors:")
        v3_errors = [row for row in cases if row["dataset"] == dataset and row["detector"] == "V3" and row["outcome"] in ("FP", "FN")]
        if not v3_errors:
            print("  None in these constructed cases")
        for row in v3_errors:
            print(f"  Case {row['case']} ({row['outcome']}): {row['transcript']}")

    print("\nCAUTION: Rule-based, text-only benchmarks; no speech or AI-agent safety tested.")
    print("These researcher-constructed examples are not independent validation.")
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
        with (args.output_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["dataset", "detector", "case", "gold", "predicted", "outcome", "discourse_function", "transcript"])
            writer.writeheader()
            writer.writerows(cases)
        print(f"Saved reports in {args.output_dir}")


if __name__ == "__main__":
    main()
