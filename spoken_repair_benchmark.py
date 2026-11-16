"""Generate and evaluate 16 local spoken self-repair examples, with no cloud APIs.

    python spoken_repair_benchmark.py --generate
    python spoken_repair_benchmark.py --run-asr
    python spoken_repair_benchmark.py --check

WARNING: This examines ASR and a simple text heuristic, not real agent safety.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from core.spoken_repair import plan, validate, analyze_asr
from core.voicerank import audio_is_wav, file_digest
from core.voicerank_speech import recognize_clip, require_whisper

DEFAULT_AUDIO = Path.home() / "Desktop" / "voxgate-spoken-repair-stimuli"
DEFAULT_REPORT = Path.home() / "Desktop" / "voxgate-spoken-repair-reports"
DEFAULT_MODEL = Path.home() / "Desktop" / "voxgate-models" / "ggml-tiny.en.bin"


def generate_audio(folder: Path, voice: str) -> None:
    if platform.system() != "Darwin" or not shutil.which("say") or not shutil.which("afconvert"):
        raise RuntimeError("Audio generation requires macOS 'say' and 'afconvert'")
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError(f"Refusing to overwrite {folder}; use --check or --run-asr")
    folder.mkdir(parents=True, exist_ok=True)
    items = []
    with TemporaryDirectory(prefix="voxgate-repairs-") as temp:
        for i, entry in enumerate(plan(voice), start=1):
            aiff = Path(temp) / "audio.aiff"
            wav = Path(temp) / "audio.wav"
            command = ["say", "-r", str(entry["rate_wpm"]), "-o", str(aiff)]
            if voice != "system_default":
                command += ["-v", voice]
            subprocess.run(command, input=str(entry["transcript"]), text=True,
                           check=True, timeout=60)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(wav)],
                           check=True, timeout=60)
            if not audio_is_wav(wav):
                raise ValueError("Generated WAV is not valid")
            final = folder / str(entry["file_name"])
            shutil.move(str(wav), str(final))
            items.append({**entry, "sha256": file_digest(final)})
            print(f"{i:>2}/16  {entry['case_id']}/{entry['condition']}")
    temporary = folder / "manifest.json.tmp"
    temporary.write_text(json.dumps({"schema": 1, "method": "macos_say_paired_rate",
                                     "stimuli": items}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(folder / "manifest.json")
    validate(folder)
    print(f"Generated and validated 16 new audio clips in {folder}")
    print("Your original VoiceRank audio was not modified.")


def run_asr(folder: Path, report: Path, model_file: Path) -> None:
    entries = validate(folder)
    exe = require_whisper(model_file)
    predictions = {}
    for i, entry in enumerate(entries, 1):
        with TemporaryDirectory(prefix="voxgate-repair-asr-") as temporary:
            predictions[str(entry["clip_id"])] = recognize_clip(
                folder / str(entry["file_name"]), model_file, exe, Path(temporary))
        print(f"{i:>2}/16 {entry['case_id']}/{entry['condition']}: {predictions[str(entry['clip_id'])]}")
    rows, summary = analyze_asr(entries, predictions)
    report.mkdir(parents=True, exist_ok=True)
    with (report / "spoken_repair_trials.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (report / "spoken_repair_summary.json").write_text(
        json.dumps({"model": "whisper.cpp local ASR", "summary": summary,
                    "scope": "Constructed macOS synthetic speech, text revision heuristic; no authorization experiment"},
                   indent=2) + "\n", encoding="utf-8")
    print("\nSPOKEN-REPAIR RESULTS — eight cases at each rate (4 revisions + 4 non-revisions)")
    for r in summary:
        print(f"{r['condition']:<7} WER={r['micro_wer']:.1%} "
              f"exact={r['exact_matches']}/{r['n']}; "
              f"V3 TP={r['tp']} FP={r['fp']} FN={r['fn']} TN={r['tn']}; "
              f"prediction flips={r['v3_prediction_changes_from_reference']}")
    print(f"Reports saved to {report}")
    print("ASR punctuation and segmentation may alter rule-based decisions even when word error rate is low.")
    print("No real actions, paid APIs, or direct audio-based authority judgments.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--generate", action="store_true")
    mode.add_argument("--run-asr", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--whisper-model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--voice", default="system_default")
    args = parser.parse_args()
    try:
        if args.generate:
            generate_audio(args.audio_dir, args.voice)
        elif args.run_asr:
            run_asr(args.audio_dir, args.output_dir, args.whisper_model)
        else:
            entries = validate(args.audio_dir)
            print(f"Verified {len(entries)} spoken-repair recordings in {args.audio_dir}")
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Spoken-repair experiment failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
