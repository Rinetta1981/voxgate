"""Fresh constructed WaitWise speech benchmark; FREE macOS TTS + local Whisper.

python spoken_repair_fresh_benchmark.py --generate
python spoken_repair_fresh_benchmark.py --run-asr
python spoken_repair_fresh_benchmark.py --check

Never executes external actions or makes autonomous authorization decisions.
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

from core.spoken_repair_fresh import SCHEMA, plan, validate_audio, evaluate
from core.voicerank import audio_is_wav, file_digest
from core.voicerank_speech import require_whisper, recognize_clip

AUDIO_DIR = Path.home() / "Desktop" / "voxgate-fresh-spoken-repair-stimuli"
REPORT_DIR = Path.home() / "Desktop" / "voxgate-fresh-spoken-repair-reports"
MODEL = Path.home() / "Desktop" / "voxgate-models" / "ggml-tiny.en.bin"


def generate(folder: Path, voice: str) -> None:
    if platform.system() != "Darwin" or not shutil.which("say") or not shutil.which("afconvert"):
        raise RuntimeError("Requires macOS 'say' and 'afconvert'")
    entries = plan(voice)
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError(f"Refusing to overwrite existing audio in {folder}")
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    with TemporaryDirectory(prefix="voxgate-fresh-speech-") as temporary:
        for index, entry in enumerate(entries, 1):
            aiff = Path(temporary) / "voice.aiff"
            wav = Path(temporary) / "voice.wav"
            cmd = ["say", "-r", str(entry["rate_wpm"]), "-o", str(aiff)]
            if voice != "system_default":
                cmd.extend(["-v", voice])
            subprocess.run(cmd, input=str(entry["transcript"]), text=True, check=True, timeout=60)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(wav)], check=True, timeout=60)
            if not audio_is_wav(wav):
                raise ValueError("macOS produced an invalid audio file")
            final = folder / str(entry["file_name"])
            shutil.move(str(wav), str(final))
            written.append({**entry, "sha256": file_digest(final)})
            print(f"{index:>2}/48 {entry['case_id']}/{entry['condition']}", flush=True)
    tmp = folder / "manifest.json.tmp"
    tmp.write_text(json.dumps({
        "schema": SCHEMA, "dataset": "fresh_v1", "source": "constructed_post_v4_unreviewed",
        "method": "macos_say_paired_rate", "stimuli": written,
    }, indent=2) + "\n", encoding="utf-8")
    tmp.replace(folder / "manifest.json")
    validate_audio(folder)
    print(f"Verified 48 paired speech clips in {folder}")


def run_asr(folder: Path, output: Path, model: Path) -> None:
    entries = validate_audio(folder)
    executable = require_whisper(model)
    hypotheses: dict[str, str] = {}
    for index, entry in enumerate(entries, 1):
        with TemporaryDirectory(prefix="voxgate-fresh-asr-") as temp:
            hypotheses[str(entry["clip_id"])] = recognize_clip(
                folder / str(entry["file_name"]), model, executable, Path(temp)
            )
        print(f"{index:>2}/48 {entry['case_id']}/{entry['condition']}: {hypotheses[str(entry['clip_id'])]}", flush=True)
    rows, summary = evaluate(entries, hypotheses)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "fresh_spoken_repair_trials.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "fresh_spoken_repair_summary.json").write_text(json.dumps({
        "dataset": "fresh_v1", "scope": "Constructed, researcher-provisional labels, synthetic speech",
        "asr_model": model.name, "result": summary,
        "warnings": [
            "Not independently annotated; not a population-representative held-out test",
            "V3 and V4 unchanged from prior experiment; do not tune on this dataset and continue calling it held-out",
            "The flag is a review request, not consent, authorization or tool execution",
        ],
    }, indent=2) + "\n", encoding="utf-8")
    print("\nFRESH SPOKEN-REPAIR BENCHMARK — 24 cases × two speaking rates")
    print("Rate    Version  TP FP FN TN  Recall Precision  WER   Accuracy")
    for r in summary:
        print(f"{r['condition']:<8}{r['version']:<8} {r['tp']:>2} {r['fp']:>2} {r['fn']:>2} {r['tn']:>2} "
              f" {r['recall']:.0%}   {r['precision']:.0%}     {r['micro_wer']:.1%}   {r['accuracy']:.0%}")
    print("\nTRIAGE = review request only; it does NOT authorize execution.")
    print("\nV4 errors requiring analysis:")
    failures = [r for r in rows if r["v4_result"] in {"FP", "FN"}]
    for r in failures:
        print(f"  {r['case_id']}/{r['condition']} {r['v4_result']}: {r['asr_transcript']}")
    if not failures:
        print("  None in this constructed sample")
    print(f"Saved CSV and JSON reports in {output}")
    print("Text revision classification only; no real actions, authority inference or paid services.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--generate", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--run-asr", action="store_true")
    parser.add_argument("--audio-dir", type=Path, default=AUDIO_DIR)
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--whisper-model", type=Path, default=MODEL)
    parser.add_argument("--voice", default="system_default")
    args = parser.parse_args()
    try:
        if args.generate:
            generate(args.audio_dir, args.voice)
        elif args.check:
            print(f"VERIFIED {len(validate_audio(args.audio_dir))} fresh audio clips")
        else:
            run_asr(args.audio_dir, args.output_dir, args.whisper_model)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as e:
        print(f"Fresh spoken-repair experiment failed: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
