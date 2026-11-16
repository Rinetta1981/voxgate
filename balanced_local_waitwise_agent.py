"""Run a balanced, fully-local WaitWise model experiment.

Preview (no requests):  python balanced_local_waitwise_agent.py
Actual local model:     python balanced_local_waitwise_agent.py --run-local --limit 8

Only the already-installed Ollama localhost adapter is used. No external APIs,
real actions, or new package dependencies. Existing benchmarks are unchanged.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from core.agent_simulation import load_scenarios
from core.analysis_v3 import detect_instruction_revision_v3
from core.experiment_design import audit_by_stratum, balanced_sample
from core.live_agent import ModelResponseError, build_global_catalog, evaluate_with_model
from core.local_agent import DEFAULT_MODEL, LocalOllamaModel

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data/waitwise_agent_scenarios.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-local", action="store_true", help="Explicitly send prompts to the local Ollama server")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Locally installed Ollama model tag")
    parser.add_argument("--limit", type=int, default=8, help="Even number of cases, balanced across revision labels (2–24)")
    parser.add_argument("--seed", type=int, default=2026, help="Deterministic selection seed")
    parser.add_argument("--output-dir", type=Path, default=Path.home() / "Desktop" / "voxgate-balanced-reports")
    args = parser.parse_args()

    all_cases = load_scenarios(DATA)
    try:
        cases = balanced_sample(all_cases, args.limit, args.seed)
    except ValueError as exc:
        parser.error(str(exc))
    catalog = build_global_catalog(all_cases)  # Fixed GLOBAL catalog; no subset-specific labels
    print(f"BALANCED WAITWISE — {len(cases)} constructed cases, model {args.model}")
    print(f"{sum(c.revised for c in cases)} revisions / {sum(not c.revised for c in cases)} non-revisions")
    print("Selected cases:", ", ".join(c.case_id for c in cases))
    print(f"Global symbolic actions: {len(catalog)} (unchanged across selections)")
    if not args.run_local:
        print("OFFLINE PREVIEW — no model inference, downloads, API fees, or actions")
        print("To perform local inference, run with --run-local.")
        return 0

    try:
        model = LocalOllamaModel(args.model)
        info = model.check_ready()
        events = evaluate_with_model(cases, model, catalog)
    except ModelResponseError as exc:
        print("Local experiment stopped: " + str(exc), file=sys.stderr)
        return 2

    report = audit_by_stratum(cases, events)
    print("\nRESULTS — total outcomes and separately for revised / non-revised inputs")
    print("Condition                 Subset          N    Done   Wrong  Correct  Held  Invalid")
    for r in report:
        print(f"{r['condition']:<26}{r['stratum']:<14}{r['n']:>3}{r['executed']:>8}"
              f"{r['wrong']:>8}{r['correct']:>9}{r['held']:>6}{r['invalid']:>9}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = {
        "type": "constructed_text_only_action_selection",
        "model": model.model, "model_info": info,
        "sample_size": len(cases), "seed": args.seed,
        "selected_case_ids": [case.case_id for case in cases],
        "n_revised": sum(case.revised for case in cases),
        "n_not_revised": sum(not case.revised for case in cases),
        "global_catalog_count": len(catalog),
        "call_stats": model.call_stats, "metrics_by_stratum": report,
        "limitations": "Constructed, previously examined examples; no audio, time streaming, real tools or independent validation.",
    }
    (args.output_dir / "balanced_summary.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "balanced_decisions.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["case_id", "gold_revised", "v3_detected", "condition", "selected_action", "status", "gold_action", "wrong", "held"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        cases_by_id = {case.case_id: case for case in cases}
        for event in events:
            case = cases_by_id[event.case_id]
            writer.writerow({
                "case_id": event.case_id, "gold_revised": int(case.revised),
                "v3_detected": int(detect_instruction_revision_v3(case.transcript)),
                "condition": event.condition, "selected_action": event.selected_action or "",
                "status": event.status, "gold_action": event.gold_action,
                "wrong": int(event.wrong), "held": int(event.held),
            })
    print(f"\nReports saved: {args.output_dir}")
    print("NOTE: No real tools. This is not independent validation of safety or authorization.")
    print("For groups with Done=0, wrong rate among executed is undefined, not zero-risk evidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
