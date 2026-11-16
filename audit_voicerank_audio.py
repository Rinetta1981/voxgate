"""Audit the existing synthesized VoiceRank WAV stimuli, without APIs or model calls.

Run: python audit_voicerank_audio.py
Reports: ~/Desktop/voxgate-acoustic-reports
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from core.voicerank import VOICE_DIR
from core.voicerank_acoustics import audit_stimuli


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-dir", type=Path, default=VOICE_DIR)
    parser.add_argument("--output-dir", type=Path, default=Path.home() / "Desktop" / "voxgate-acoustic-reports")
    args = parser.parse_args()
    try:
        clips, pairs = audit_stimuli(args.audio_dir)
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        parser.exit(1, f"VoiceRank acoustic audit failed: {exc}\n")
    print(f"VOICERANK ACOUSTIC AUDIT — {len(clips)} verified WAV clips, {len(pairs)} matched pairs")
    print("Prompt  Slower(s) Faster(s) Realized rate ratio Fast shorter?  RMS diff (dB)")
    for row in pairs:
        print(f"{row['prompt_id']:<6}  {row['slower_duration_s']:>8.2f} {row['faster_duration_s']:>8.2f} "
              f"{row['fast_to_slow_observed_whole_clip_rate_ratio']:>16.2f} "
              f"{str(row['fast_clip_is_shorter']):>13}  {row['rms_difference_fast_minus_slow_db']:>7.2f}")
    if not all(r['fast_clip_is_shorter'] for r in pairs):
        print("WARNING: At least one faster-labeled clip is not shorter than its matched slower clip")
    if any(r['any_near_clipping'] for r in pairs):
        print("WARNING: At least one clip approaches the PCM16 amplitude limit")
    target = args.output_dir.expanduser()
    target.mkdir(parents=True, exist_ok=True)
    for name, records in (("clip_acoustics.csv", clips), ("paired_acoustics.csv", pairs)):
        with (target / name).open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    summary = {
        "clips": len(clips), "matched_pairs": len(pairs),
        "all_faster_clips_shorter": all(r["fast_clip_is_shorter"] for r in pairs),
        "average_realized_rate_ratio": sum(r["fast_to_slow_observed_whole_clip_rate_ratio"] for r in pairs) / len(pairs),
        "any_near_clipping": any(r["any_near_clipping"] for r in pairs),
        "interpretation": "Duration/amplitude audit only; nominal WPM is a synthesis setting, not a verified realized speech rate. No F0, prosody, perceived authority, or agent authorization measured.",
    }
    (target / "acoustic_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Reports saved in {target}")
    print("CAUTION: Whole-clip rate includes pauses/silence; dBFS is not perceived loudness.")


if __name__ == "__main__":
    main()
