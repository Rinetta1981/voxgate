"""Replay authorization policies from an existing local WaitWise report.

No Ollama calls, network requests, action execution, or paid APIs.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from core.authorization_gate import read_saved_choices, run_policy_replay, summarize_gate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=Path.home() / "Desktop" / "voxgate-balanced-reports" / "balanced_decisions.csv")
    parser.add_argument("--output-dir", type=Path,
                        default=Path.home() / "Desktop" / "voxgate-gate-reports")
    args = parser.parse_args()
    try:
        cases = read_saved_choices(args.input)
    except (ValueError, OSError) as exc:
        parser.error(f"Cannot read prior balanced results: {exc}")
    decisions = run_policy_replay(cases)
    metrics = summarize_gate(decisions)
    print(f"AUTHORIZATION GATE REPLAY — {len(cases)} existing constructed scenarios")
    print("No new model requests, payments, downloads or tool actions.\n")
    print("Policy                  Group          N  Done Wrong Correct Held  Wrong/done")
    for row in metrics:
        rate = "n/a" if row["wrong_rate_executed"] is None else f'{row["wrong_rate_executed"]:.0%}'
        print(f'{row["policy"]:<24}{row["stratum"]:<14}{row["n"]:>3}'
              f'{row["executed"]:>6}{row["wrong"]:>6}{row["correct"]:>8}{row["held"]:>5}{rate:>12}')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "gate_summary.json").write_text(json.dumps({
        "type": "retrospective_policy_replay_not_prospective_validation",
        "input": str(args.input), "n": len(cases), "metrics": metrics,
        "limitations": "Policies reuse model outputs on researcher-constructed and previously examined cases. "
        "No independent test, spoken data, model training, authorization validation or external actions. "
        "The gate never performs confirmation in this replay; held requests remain unresolved."
    }, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "gate_decisions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "policy", "proposed_action", "status", "reason", "gold_action", "gold_revised", "wrong"])
        writer.writeheader()
        for d in decisions:
            writer.writerow({"case_id": d.case_id, "policy": d.policy,
                             "proposed_action": d.action or "", "status": "HOLD" if d.held else "PROPOSED",
                             "reason": d.reason, "gold_action": d.gold_action,
                             "gold_revised": int(d.gold_revised), "wrong": int(d.wrong)})
    print(f"\nReports saved: {args.output_dir}")
    print("This is exploratory, retrospective replay; held cases have no recorded user confirmations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
