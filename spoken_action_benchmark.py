"""Free, local-only VOXGATE speech->ASR->Qwen action-proposal comparison.

    python spoken_action_benchmark.py                 # no inference
    python spoken_action_benchmark.py --run-local     # 4 balanced cases, 12 local calls
    python spoken_action_benchmark.py --run-local --limit 24

No tool execution, no remote APIs, no model downloads, no release authorization.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from core.live_agent import ModelResponseError
from core.local_agent import DEFAULT_MODEL, LocalOllamaModel
from core.spoken_action import (
    balanced_subset, evaluate_model_choices, fixed_catalog,
    load_asr_trials, load_labels, summarize_decisions,
)

ROOT = Path(__file__).resolve().parent
ASR_FILE = Path.home() / "Desktop" / "voxgate-fresh-spoken-repair-reports" / "fresh_spoken_repair_trials.csv"
LABEL_FILE = ROOT / "data" / "fresh_spoken_action_labels.csv"
REPORTS = Path.home() / "Desktop" / "voxgate-spoken-action-reports"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("Refusing to save an empty experiment")
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-local", action="store_true", help="Opt into free local inference")
    parser.add_argument("--limit", type=int, default=4, help="Balanced scenario count: even integer 2–24")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Already-installed local Ollama model")
    parser.add_argument("--asr-csv", type=Path, default=ASR_FILE, help="Existing 48-trial ASR CSV")
    parser.add_argument("--output-dir", type=Path, default=REPORTS)
    args = parser.parse_args()

    try:
        labels = load_labels(LABEL_FILE)
        cases = load_asr_trials(args.asr_csv, labels)
        catalog = fixed_catalog(cases)
        selected = balanced_subset(cases, args.limit)
        if not args.run_local:
            print("OFFLINE PREVIEW — no model inference or real actions")
            print(f"Validated {len(cases)} cases, {len(catalog)} globally shared action symbols")
            print(f"Selected balanced {len(selected)} cases: {', '.join(c.case_id for c in selected)}")
            print(f"Local calls if enabled: {3 * len(selected)} (reference + slower + faster)")
            print("Run with --run-local to opt into local Ollama inference.")
            return 0

        model = LocalOllamaModel(args.model)
        info = model.check_ready()
        raw, decisions, comparisons = evaluate_model_choices(selected, catalog, model)
        summaries = summarize_decisions(decisions)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_csv(args.output_dir / "model_choices.csv", raw)
        write_csv(args.output_dir / "policy_replay.csv", decisions)
        write_csv(args.output_dir / "asr_model_comparisons.csv", comparisons)
        (args.output_dir / "summary.json").write_text(json.dumps({
            "scope": "Constructed speech-to-text-to-local-model symbolic PROPOSALS only",
            "model": model.model, "model_digest": info.get("digest"),
            "selected_case_ids": [c.case_id for c in selected],
            "global_catalog_size": len(catalog),
            "model_calls": len(model.call_stats),
            "call_stats": model.call_stats,
            "summary": summaries,
            "warnings": [
                "No real tool calls, no action authorization, no paid API",
                "Nominal speech rate is not directly available to the text-only model",
                "Researcher-provisional action labels were written after the speech scenarios and are not independently adjudicated",
                "These constructed cases and model comparisons are exploratory, not proof of generalization",
                "not_flagged does not mean safe or user-authorized",
            ],
        }, indent=2) + "\n", encoding="utf-8")

        print(f"SPOKEN ACTION EVALUATION — {len(selected)} balanced cases — {model.model}")
        print("No tools/actions executed; these are hypothetical proposals and review flags.")
        print("Source     Policy         Proposed Correct Wrong Held Review  Wrong/proposed")
        for row in summaries:
            ratio = (f"{row['wrong_among_proposed']:.0%}" if row["wrong_among_proposed"] is not None else "n/a")
            print(f"{row['source']:<10} {row['policy']:<14} {row['proposed']:>3} {row['correct']:>7} "
                  f"{row['wrong']:>5} {row['held']:>4} {row['review_requested']:>6}  {ratio:>8}")
        changed = sum(int(r["model_choice_changed_vs_reference"]) for r in comparisons)
        print(f"\nASR-vs-reference model-choice differences: {changed}/{len(comparisons)} paired comparisons")
        print(f"Reports: {args.output_dir}")
        print("Do not interpret absence of a review flag as permission to execute.")
        return 0
    except (OSError, ValueError, ModelResponseError) as exc:
        print(f"Spoken action experiment stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
