"""Descriptive paired analysis for an exported VoiceRank pilot CSV.

Example: python analyze_voicerank.py ~/Downloads/voicerank_pilot.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from core.voicerank import paired_authority_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ratings", type=Path, help="CSV downloaded from /voice/")
    args = parser.parse_args()
    with args.ratings.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    result = paired_authority_summary(rows)
    print("VOICERANK PERCEPTION PILOT — descriptive, one local session")
    print(f"Complete matched pairs: {result['complete_pairs']}")
    if result["complete_pairs"]:
        print(f"Mean perceived authority — slower: {result['mean_slower']:.2f}/5")
        print(f"Mean perceived authority — faster: {result['mean_faster']:.2f}/5")
        print(f"Faster minus slower: {result['mean_difference_faster_minus_slower']:+.2f} points")
    print("No inferential statistics: multiple prompts rated by one listener are not independent participants.")
    print("This does not test whether an AI model grants unauthorized permissions.")


if __name__ == "__main__":
    main()
