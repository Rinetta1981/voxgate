"""Compare frozen V3 with experimental V4 using saved spoken-repair CSV.

NO new Whisper inference, cloud calls, or action execution.

    python compare_spoken_repair_v4.py
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

from core.analysis_v3 import detect_instruction_revision_v3
from core.analysis_v4 import detect_instruction_revision_v4
from core.evaluation import calculate_metrics
from core.spoken_repair import plan
from core.voicerank_speech import transcription_score

DEFAULT_SOURCE = Path.home() / "Desktop/voxgate-spoken-repair-reports/spoken_repair_trials.csv"
DEFAULT_OUTPUT = Path.home() / "Desktop/voxgate-spoken-repair-v4-reports"


def read_verified_results(path: Path) -> list[dict[str, str]]:
    """Validate saved trial identities, labels and transcript/scoring provenance."""
    expected = {str(record["clip_id"]): record for record in plan()}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(expected):
        raise ValueError("Expected exactly 16 previously recorded trials")
    seen = set()
    for row in rows:
        clip = row.get("clip_id", "")
        if clip in seen or clip not in expected:
            raise ValueError("Duplicated or unknown clip ID")
        seen.add(clip)
        source = expected[clip]
        for key in ("case_id", "condition", "discourse_function", "reference_transcript"):
            desired = source["transcript"] if key == "reference_transcript" else source[key]
            if row.get(key) != desired:
                raise ValueError(f"Mismatched {key} for {clip}")
        if row.get("gold_revision") != str(source["gold_revision"]):
            raise ValueError("Mismatched gold revision label")
        try:
            score = transcription_score(str(source["transcript"]), row["asr_transcript"])
            if (int(row["reference_words"]) != score["reference_words"]
                    or int(row["word_edits"]) != score["word_edits"]
                    or abs(float(row["wer"]) - score["wer"]) > 0.00001
                    or int(row["exact_match"]) != score["exact_match"]):
                raise ValueError("ASR scoring fields inconsistent with transcripts")
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Malformed saved score for {clip}: {error}") from error
    return rows


def compare(rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    result = []
    summaries = []
    for record in rows:
        gold = int(record["gold_revision"])
        text = record["asr_transcript"]
        p3 = int(detect_instruction_revision_v3(text))
        p4 = int(detect_instruction_revision_v4(text))
        result.append({
            "case_id": record["case_id"], "condition": record["condition"], "gold_revision": gold,
            "asr_transcript": text, "v3": p3, "v4": p4,
            "v4_result": "TP" if (gold, p4) == (1, 1) else "FN" if gold else "FP" if p4 else "TN",
            "changed_from_v3": int(p3 != p4),
        })
    for condition in ("slower", "faster", "both"):
        subset = result if condition == "both" else [r for r in result if r["condition"] == condition]
        for version in ("v3", "v4"):
            metrics = calculate_metrics([r["gold_revision"] for r in subset], [r[version] for r in subset])
            summaries.append({"condition": condition, "version": version, **metrics})
    return result, summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        rows = read_verified_results(args.input)
        outcomes, summaries = compare(rows)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with (args.output_dir / "v3_v4_trials.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(outcomes[0]))
            writer.writeheader()
            writer.writerows(outcomes)
        (args.output_dir / "v3_v4_summary.json").write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
        print("WAITWISE ASR REPAIR COMPARISON — saved transcripts, zero new model calls")
        print("Rate   Version  TP FP FN TN  Recall  Precision  Correct/All")
        for row in summaries:
            print(f"{row['condition']:<7}{row['version']:<8}{row['tp']:>2} {row['fp']:>2} {row['fn']:>2} {row['tn']:>2}"
                  f"   {row['recall']:.0%}       {row['precision']:.0%}       {row['tp']+row['tn']}/{row['n']}")
        print("\nRemaining V4 errors:")
        bad = [r for r in outcomes if r["v4_result"] in ("FN", "FP")]
        for r in bad:
            print(f"  {r['case_id']}/{r['condition']} ({r['v4_result']}): {r['asr_transcript']}")
        if not bad:
            print("  None on these researcher-constructed development examples")
        print("\nV4 is experimental, tuned after inspecting these very examples; results are NOT held-out validation.")
        print("No action authorization or execution; no paid API; no audio-only authority inference.")
        print(f"Reports: {args.output_dir}")
        return 0
    except (OSError, ValueError) as error:
        print(f"Comparison failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
