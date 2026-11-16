"""Combine one completed VoiceRank expanded-study CSV per participant.

Example: python analyze_voicerank_study.py ~/Downloads/voicerank_study_*.csv
Reports (optional): --output-dir ~/Desktop/voxgate-voice-study-reports
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from core.voicerank_study import read_study_csvs, summarize_participants


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_files", nargs="+", type=Path, help="One completed export per participant")
    parser.add_argument("--output-dir", type=Path, help="Write descriptive reports here")
    args = parser.parse_args()
    try:
        rows = read_study_csvs(args.csv_files)
        per_participant, group = summarize_participants(rows)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"VoiceRank analysis error: {exc}\n")
    print(f"VOICERANK EXPANDED PERCEPTION STUDY — {group['participants']} participants; {group['trials']} trials")
    print("Each participant, not each audio clip, is the descriptive analysis unit.")
    for name in ("authority", "clarity", "urgency"):
        metric = group[name]
        print(f"{name.capitalize():<10}: slower={metric['mean_slower']:.2f}, faster={metric['mean_faster']:.2f}, "
              f"participant-level (faster–slower)={metric['mean_participant_difference_faster_minus_slower']:+.2f}")
    print("Assignment counts:", group["assignment_counts"])
    print("Descriptive pilot only; no inferential significance or agent-permission result.")
    if args.output_dir:
        target = args.output_dir.expanduser()
        target.mkdir(parents=True, exist_ok=True)
        (target / "summary.json").write_text(json.dumps(group, indent=2) + "\n", encoding="utf-8")
        with (target / "participant_summary.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(per_participant[0]))
            writer.writeheader()
            writer.writerows(per_participant)
        print(f"Reports saved in {target}")


if __name__ == "__main__":
    main()
