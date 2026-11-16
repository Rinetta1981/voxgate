"""Free, local-only model evaluation; no API keys or real-world tools.

    python local_waitwise_agent.py                  # offline preview
    python local_waitwise_agent.py --check          # checks Ollama installation
    python local_waitwise_agent.py --run-local      # 4-case model experiment
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from core.agent_simulation import load_scenarios
from core.analysis_v3 import split_instruction_and_followup
from core.live_agent import (ModelResponseError, build_global_catalog,
                             build_user_input, evaluate_with_model, summarize_events)
from core.local_agent import DEFAULT_MODEL, LocalOllamaModel

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "waitwise_agent_scenarios.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--check", action="store_true", help="Verify local Ollama/model without inference")
    choice.add_argument("--run-local", action="store_true", help="Explicitly run a local language model")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Locally downloaded Ollama tag; cloud models rejected")
    parser.add_argument("--limit", type=int, default=4, help="First N scenarios (2 local model calls each; 1–24)")
    parser.add_argument("--output-dir", type=Path, default=Path.home() / "Desktop" / "voxgate-local-reports")
    args = parser.parse_args()
    if not 1 <= args.limit <= 24:
        parser.error("--limit must be 1 to 24")
    all_cases = load_scenarios(DATA)
    cases = all_cases[:args.limit]
    catalog = build_global_catalog(all_cases)  # fixed across limits and conditions
    if not (args.check or args.run_local):
        first, _ = split_instruction_and_followup(cases[0].transcript)
        print("OFFLINE PREVIEW — no model calls, downloads, charges, or actions")
        print(f"Cases: {len(cases)} | Global symbolic actions: {len(catalog)}")
        print(f"Example: {first}")
        print("Input fields:", ", ".join(json.loads(build_user_input(first, catalog))))
        print("To use a real free local model: see docs/LOCAL_MODELS.md")
        return 0

    try:
        model = LocalOllamaModel(args.model)
        info = model.check_ready()
        if args.check:
            print(f"LOCAL MODEL READY: {info['name']}")
            print("Digest:", info.get("digest") or "unavailable")
            print("No inference performed or API fees charged.")
            return 0
        events = evaluate_with_model(cases, model, catalog)
    except ModelResponseError as exc:
        print("Local experiment stopped: " + str(exc), file=sys.stderr)
        return 2

    summary = summarize_events(events)
    print(f"LOCAL MODEL RESULTS — {model.model} — {len(cases)} constructed scenarios")
    print("Simulated symbolic actions only; no real external tools or cloud API.\n")
    print("Condition                 Coverage  Wrong/all  Correct completion/all  Invalid")
    for row in summary:
        print(f"{row['condition']:<26} {row['coverage']:>6.0%}     {row['wrong_rate_all']:>6.0%}    "
              f"{row['correct_completion_rate_all']:>6.0%}                  {row['invalid_outputs']:>3}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "local_llm_summary.json").write_text(
        json.dumps({"model": model.model, "model_info": info, "cases": len(cases),
                    "call_stats": model.call_stats, "results": summary}, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "local_llm_decisions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "condition", "selected_action", "status", "gold_action", "wrong", "held"])
        writer.writeheader()
        for event in events:
            writer.writerow({"case_id": event.case_id, "condition": event.condition,
                             "selected_action": event.selected_action or "", "status": event.status,
                             "gold_action": event.gold_action, "wrong": int(event.wrong), "held": int(event.held)})
    print(f"\nReports saved: {args.output_dir}")
    print("This is closed-world text action selection on constructed cases, NOT demonstrated real-world AI safety.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
