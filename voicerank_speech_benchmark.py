"""Free local speech recognition and downstream *text* action selection for VoiceRank.

    python voicerank_speech_benchmark.py --check
    python voicerank_speech_benchmark.py --run-asr
    python voicerank_speech_benchmark.py --run-model

Neither command performs real-world actions or sends audio to a cloud service.
--run-model contacts only localhost Ollama, using prior --run-asr results.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from core.voicerank import VOICE_DIR
from core.live_agent import ModelResponseError
from core.voicerank_speech import (
    ASR_CSV_FIELDS, VOICE_ACTIONS, asr_summary, build_asr_row,
    load_verified_stimuli, recognize_clip, require_whisper,
    validate_asr_rows,
)

DEFAULT_MODEL_FILE = Path.home() / "Desktop" / "voxgate-models" / "ggml-tiny.en.bin"
DEFAULT_REPORT = Path.home() / "Desktop" / "voxgate-voice-asr-reports"


def write_csv(path: Path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run_asr(stimuli: list[dict[str, object]], voice_dir: Path, out_dir: Path, model_file: Path) -> None:
    exe = require_whisper(model_file)
    model_file = model_file.expanduser()
    rows = []
    for index, item in enumerate(stimuli, 1):
        with TemporaryDirectory(prefix="voxgate-asr-") as temp:
            asr_text = recognize_clip(voice_dir / str(item["file_name"]), model_file, exe, Path(temp))
        row = build_asr_row(item, asr_text)
        rows.append(row)
        print(f"{index}/8  {item['prompt_id']}/{item['condition']}: {asr_text or '[EMPTY]'}")
    validate_asr_rows(stimuli, [{k: str(v) for k, v in row.items()} for row in rows])
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "voicerank_asr_trials.csv", ASR_CSV_FIELDS, rows)
    summary = asr_summary(rows)
    (out_dir / "voicerank_asr_summary.json").write_text(
        json.dumps({"model": model_file.name, "results": summary,
                    "scope": "Researcher-constructed macOS TTS samples; WER not authorization"}, indent=2) + "\n",
        encoding="utf-8",
    )
    print("\nLOCAL SPEECH RECOGNITION RESULTS")
    for group in summary:
        print(f"{group['condition']:<7}: WER={group['micro_wer']:.1%}; "
              f"exact={group['exact_matches']}/{group['n']}; "
              f"edits={group['word_edits']}/{group['reference_words']}")
    print(f"Reports saved: {out_dir}")
    print("No external actions or paid API. This is ASR, not model perception of authority.")


def run_model(stimuli: list[dict[str, object]], out_dir: Path, model_name: str) -> None:
    from core.local_agent import LocalOllamaModel
    from core.live_agent import HOLD, parse_choice

    path = out_dir / "voicerank_asr_trials.csv"
    if not path.exists():
        raise RuntimeError("Run --run-asr first; verified ASR results were not found")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    validate_asr_rows(stimuli, rows)
    model = LocalOllamaModel(model_name)
    model.check_ready()  # Strictly local, rejects cloud models.
    decisions = []
    for trial in rows:
        for mode, text in (("reference_text", trial["reference_transcript"]),
                           ("recognized_text", trial["asr_transcript"])):
            if text.strip():
                raw = model(text, VOICE_ACTIONS)
                choice, status = parse_choice(raw, VOICE_ACTIONS)
            else:
                choice, status = HOLD, "empty_transcript"
            gold = trial["reference_transcript"]
            decisions.append({
                "clip_id": trial["clip_id"], "prompt_id": trial["prompt_id"],
                "condition": trial["condition"], "input_mode": mode,
                "selected_action": choice, "status": status,
                "correct": int(choice == gold), "held": int(choice == HOLD),
                "incorrect": int(choice != gold and choice != HOLD),
            })
    write_csv(out_dir / "voicerank_text_decisions.csv", (
        "clip_id", "prompt_id", "condition", "input_mode", "selected_action", "status", "correct", "held", "incorrect",
    ), decisions)
    summaries = []
    for mode in ("reference_text", "recognized_text"):
        for condition in ("slower", "faster"):
            group = [x for x in decisions if x["input_mode"] == mode and x["condition"] == condition]
            summaries.append({"input_mode": mode, "condition": condition, "n": len(group),
                              "correct": sum(x["correct"] for x in group),
                              "held": sum(x["held"] for x in group),
                              "incorrect": sum(x["incorrect"] for x in group)})
    (out_dir / "voicerank_text_decisions_summary.json").write_text(
        json.dumps({"model": model.model, "action_catalog": list(VOICE_ACTIONS),
                    "results": summaries,
                    "scope": "Text model processes human transcripts or local ASR text, not acoustic signal"}, indent=2) + "\n",
        encoding="utf-8",
    )
    print("\nDOWNSTREAM TEXT-ONLY ACTION SELECTION — NO REAL TOOLS")
    for row in summaries:
        print(f"{row['input_mode']:<15} {row['condition']:<6}  correct={row['correct']}/4 "
              f"held={row['held']}/4 incorrect={row['incorrect']}/4")
    print(f"Reports saved: {out_dir}")
    print("This compares ASR-mediated text inputs, NOT direct vocal-authority effects.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--run-asr", action="store_true")
    mode.add_argument("--run-model", action="store_true")
    parser.add_argument("--voice-dir", type=Path, default=VOICE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--whisper-model", type=Path, default=DEFAULT_MODEL_FILE)
    parser.add_argument("--ollama-model", default="qwen2.5:0.5b")
    args = parser.parse_args()
    try:
        stimuli = load_verified_stimuli(args.voice_dir)
        if args.run_asr:
            run_asr(stimuli, args.voice_dir, args.output_dir, args.whisper_model)
        elif args.run_model:
            run_model(stimuli, args.output_dir, args.ollama_model)
        else:
            print(f"VOICE ASR EXPERIMENT READY — {len(stimuli)} validated VoiceRank recordings")
            print("No model inference or downloads performed.")
            try:
                require_whisper(args.whisper_model)
                print("Whisper executable and local model file found; use --run-asr.")
            except RuntimeError as e:
                print("To run ASR:", str(e))
                print("See docs/VOICERANK_SPEECH_ASR.md for installation instructions.")
        return 0
    except (ValueError, OSError, RuntimeError, ModelResponseError) as exc:
        print("VoiceRank speech experiment failed: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
