"""Run controlled, mock-only WaitWise agent-policy comparisons.

From the VOXGATE project directory:
    python simulate_waitwise_agent.py --output-dir ~/Desktop/voxgate-agent-reports
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from core.agent_simulation import POLICIES, decision_to_row, load_scenarios, simulate, summarize
from core.analysis_v3 import detect_instruction_revision_v3
from core.evaluation import calculate_metrics

ROOT = Path(__file__).resolve().parent
SCENARIOS = ROOT / "data" / "waitwise_agent_scenarios.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None, help="Optional directory for detailed reports")
    args = parser.parse_args()
    cases = load_scenarios(SCENARIOS)
    # The same frozen V3 detector is used for every scenario.
    gold = [int(case.revised) for case in cases]
    predicted = [int(bool(detect_instruction_revision_v3(case.transcript))) for case in cases]
    detect_metrics = calculate_metrics(gold, predicted)

    print(f"WAITWISE MOCK AGENT EXPERIMENT — {len(cases)} researcher-constructed scenarios")
    print("No real actions, models, speech, or third-party APIs are used.\n")
    print("V3 transcript-revision detector: "
          f"TP={detect_metrics['tp']} FP={detect_metrics['fp']} "
          f"FN={detect_metrics['fn']} TN={detect_metrics['tn']} "
          f"F1={detect_metrics['f1']:.2f}")
    print("\nPolicy                Coverage Wrong/all Premature/all Held False holds")
    summaries = []
    all_decisions = []
    for policy in POLICIES:
        decisions = [simulate(case, policy, detect_instruction_revision_v3) for case in cases]
        stats = summarize(decisions)
        summaries.append(stats)
        all_decisions.extend(decisions)
        print(f"{policy:<21} {stats['action_coverage']:.0%}      "
              f"{stats['wrong_action_rate_all_cases']:.0%}       "
              f"{stats['premature_action_rate_all_cases']:.0%}           "
              f"{stats['held']:>2}     {stats['false_holds']:>2}")

    print("\nCAUTIONS: End-of-turn and immediate behavior is defined by policy;")
    print("action IDs and corrected targets are researcher-supplied annotations;")
    print("oracle_final is not deployable; confirmation_gate never gets a confirmation;")
    print("scenarios are constructed, partly adapted from earlier development cases.")
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "policy_summary.json").write_text(json.dumps({"detector": detect_metrics, "policies": summaries}, indent=2) + "\n", encoding="utf-8")
        fields = ["case_id", "policy", "phase", "time_ms", "action", "final_action_gold", "gold_revised", "v3_detected_revision", "held", "wrong_action", "premature"]
        with (args.output_dir / "simulated_decisions.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(decision_to_row(d) for d in all_decisions)
        print(f"\nSaved simulated_decisions.csv and policy_summary.json to {args.output_dir}")


if __name__ == "__main__":
    main()
