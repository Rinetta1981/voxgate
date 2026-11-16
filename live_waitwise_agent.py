"""Text-only LLM comparison through a strictly inert action catalog.

Safe offline preview (no API): python live_waitwise_agent.py
Live API calls (opt-in):     python live_waitwise_agent.py --live --model gpt-4.1-mini --limit 4
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from core.agent_simulation import load_scenarios
from core.analysis_v3 import split_instruction_and_followup
from core.live_agent import (ModelResponseError, OpenAIResponsesModel, build_global_catalog,
                             build_user_input, evaluate_with_model, summarize_events)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data/waitwise_agent_scenarios.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly allow paid network requests to OpenAI")
    parser.add_argument("--model", default="gpt-4.1-mini", help="OpenAI model identifier; access may vary")
    parser.add_argument("--limit", type=int, default=4, help="First N cases (2 requests each in live mode, max 24)")
    parser.add_argument("--output-dir", type=Path, default=Path.home() / "Desktop" / "voxgate-live-reports")
    args = parser.parse_args()
    if not 1 <= args.limit <= 24:
        parser.error("--limit must be between 1 and 24")
    cases = load_scenarios(DATA)[:args.limit]
    # Catalog always built from all 24 cases, not the current evaluation subset.
    catalog = build_global_catalog(load_scenarios(DATA))
    if not args.live:
        first, _ = split_instruction_and_followup(cases[0].transcript)
        print("OFFLINE PREVIEW — no model requests, charges, or tools executed")
        print(f"Loaded {len(cases)} cases; {len(catalog)} globally available symbolic actions")
        print(f"Example first segment: {first}")
        print("Preview model-input keys:", ", ".join(json.loads(build_user_input(first, catalog))))
        print("To run an actual model: set OPENAI_API_KEY locally, then use --live.")
        return 0

    try:
        model = OpenAIResponsesModel(args.model)
        # Freeze the catalog across all 24 cases, including small evaluation subsets.
        events = evaluate_with_model(cases, model, catalog)
    except ModelResponseError as exc:
        print("Live experiment stopped: " + str(exc), file=sys.stderr)
        return 2

    summaries = summarize_events(events)
    print(f"LIVE MODEL RESULTS — {args.model} — {len(cases)} CONSTRUCTED CASES")
    print("These are text-only hypothetical action selections; NO real-world tools were run.\n")
    print("Condition                 Coverage  Wrong/all  Correct completion/all  Invalid")
    for row in summaries:
        print(f"{row['condition']:<26} {row['coverage']:>6.0%}     {row['wrong_rate_all']:>6.0%}    "
              f"{row['correct_completion_rate_all']:>6.0%}                  {row['invalid_outputs']:>3}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "llm_summary.json").write_text(
        json.dumps({"model": args.model, "cases": len(cases), "results": summaries}, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "llm_decisions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "condition", "selected_action", "status", "gold_action", "wrong", "held"])
        writer.writeheader()
        for e in events:
            writer.writerow({"case_id": e.case_id, "condition": e.condition,
                             "selected_action": e.selected_action or "", "status": e.status,
                             "gold_action": e.gold_action, "wrong": int(e.wrong), "held": int(e.held)})
    print(f"\nReports saved: {args.output_dir}")
    print("NOTICE: Some prompts are reused from detector development; not independent validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
