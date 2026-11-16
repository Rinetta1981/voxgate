"""Generate VoiceRank TTS rate-manipulation stimuli using macOS built-in voices.

No internet, paid APIs, or model downloads are requested by this script.
The same macOS TTS voice reads identical text at two speaking rates.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from core.voicerank import VOICE_DIR, SCHEMA_VERSION, audio_is_wav, file_digest, stimulus_plan, validate_manifest


def generate(directory: Path, voice: str = "system_default") -> int:
    if platform.system() != "Darwin" or not shutil.which("say") or not shutil.which("afconvert"):
        raise RuntimeError("Audio generation needs macOS with built-in 'say' and 'afconvert' commands")
    directory = directory.expanduser()
    if (directory / "manifest.json").exists():
        validate_manifest(directory)
        raise FileExistsError(f"Existing verified manifest in {directory}; refusing to overwrite prior trial audio")
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(f"Output folder {directory} is not empty; choose another folder to avoid overwriting data")
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    with TemporaryDirectory(prefix="voicerank-tmp-") as temporary:
        tmp = Path(temporary)
        for entry in stimulus_plan(voice):
            aiff = tmp / "sample.aiff"
            wav = tmp / "sample.wav"
            command = ["say", "-r", str(entry["rate_wpm"]), "-o", str(aiff)]
            if voice != "system_default":
                command.extend(["-v", voice])
            # Use stdin: the transcript is never parsed as a command-line option.
            subprocess.run(command, input=str(entry["transcript"]), text=True, check=True, timeout=45)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(wav)], check=True, timeout=45)
            if not audio_is_wav(wav):
                raise RuntimeError("macOS did not create a supported WAV recording")
            final = directory / str(entry["file_name"])
            shutil.move(str(wav), str(final))
            entry = {**entry, "sha256": file_digest(final)}
            records.append(entry)
        manifest = {"schema_version": SCHEMA_VERSION, "method": "same_voice_two_speech_rates", "stimuli": records}
        temporary_manifest = directory / "manifest.json.tmp"
        temporary_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary_manifest.replace(directory / "manifest.json")
    validate_manifest(directory)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=VOICE_DIR, help="Local output folder (default: Desktop)")
    parser.add_argument("--voice", default="system_default", help="Installed macOS voice, or system_default")
    parser.add_argument("--check", action="store_true", help="Validate existing audio; generate nothing")
    args = parser.parse_args()
    try:
        if args.check:
            count = len(validate_manifest(args.output))
            print(f"VALIDATED {count} paired-condition audio clips in {args.output}")
        else:
            count = generate(args.output, args.voice)
            print(f"GENERATED {count} free local VoiceRank WAV clips in {args.output}")
            print("Manipulation: same voice and text; 155 vs 210 words/minute. No authority effect assumed.")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"VoiceRank error: {exc}\n")


if __name__ == "__main__":
    main()
