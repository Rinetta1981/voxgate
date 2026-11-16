"""VoiceRank local speech-to-text (ASR) comparison; deliberately no tool execution.

This measures recognition/transcription and downstream *text* action selection.
It does not measure direct acoustic authority sensitivity by an audio model.
"""
from __future__ import annotations

from array import array
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave

from .voicerank import PROMPTS, validate_manifest

AUDIO_RATE = 16000
ASR_CSV_FIELDS = (
    "clip_id", "prompt_id", "condition", "rate_wpm", "voice", "sha256",
    "reference_transcript", "asr_transcript", "reference_words", "word_edits", "wer", "exact_match",
)
VOICE_ACTIONS = tuple(text for _, text in PROMPTS)  # Same catalog for every trial.


def words(text: str) -> list[str]:
    """Lowercase, punctuation-insensitive English tokenization for this small test."""
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text.casefold())


def edit_distance(reference: list[str], candidate: list[str]) -> int:
    """Minimum token insertions, deletions and substitutions."""
    previous = list(range(len(candidate) + 1))
    for i, token in enumerate(reference, 1):
        current = [i]
        for j, other in enumerate(candidate, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (token != other)))
        previous = current
    return previous[-1]


def transcription_score(reference: str, candidate: str) -> dict[str, object]:
    tokens = words(reference)
    if not tokens:
        raise ValueError("Empty reference transcript")
    observed = words(candidate)
    edits = edit_distance(tokens, observed)
    return {
        "reference_words": len(tokens), "word_edits": edits,
        "wer": round(edits / len(tokens), 6),
        "exact_match": int(tokens == observed),
    }


def asr_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Micro-WER by condition, plus simple trial-level exact match counts."""
    summary = []
    for condition in ("slower", "faster"):
        group = [row for row in rows if row["condition"] == condition]
        if len(group) != 4 or len({row["prompt_id"] for row in group}) != 4:
            raise ValueError(f"Expected exactly four distinct {condition} prompts")
        edits = sum(int(row["word_edits"]) for row in group)
        ref_words = sum(int(row["reference_words"]) for row in group)
        summary.append({
            "condition": condition, "n": len(group), "reference_words": ref_words,
            "word_edits": edits, "micro_wer": round(edits / ref_words, 6),
            "exact_matches": sum(int(row["exact_match"]) for row in group),
        })
    return summary


def validate_asr_rows(records: list[dict[str, object]], rows: list[dict[str, str]]) -> None:
    """Reject stale, incomplete, duplicated, or mismatched ASR result files."""
    expected = {str(item["clip_id"]): item for item in records}
    if len(rows) != len(expected):
        raise ValueError("ASR CSV must contain exactly one row per audio clip")
    seen: set[str] = set()
    for row in rows:
        clip_id = row.get("clip_id", "")
        if clip_id not in expected or clip_id in seen:
            raise ValueError("Unknown or duplicate clip ID in ASR CSV")
        seen.add(clip_id)
        entry = expected[clip_id]
        for key in ("prompt_id", "condition", "voice", "sha256"):
            if row.get(key) != str(entry[key]):
                raise ValueError(f"ASR CSV audio mismatch: {key}")
        if row.get("reference_transcript") != entry["transcript"]:
            raise ValueError("ASR CSV reference transcript mismatch")
        if row.get("rate_wpm") != str(entry["rate_wpm"]):
            raise ValueError("ASR CSV speaking-rate metadata mismatch")
        try:
            observed = transcription_score(str(entry["transcript"]), row.get("asr_transcript", ""))
            valid = (
                int(row.get("reference_words", "-1")) == observed["reference_words"]
                and int(row.get("word_edits", "-1")) == observed["word_edits"]
                and abs(float(row.get("wer", "-1")) - float(observed["wer"])) <= 0.000001
                and int(row.get("exact_match", "-1")) == observed["exact_match"]
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("ASR CSV scores are malformed") from exc
        if not valid:
            raise ValueError("ASR CSV scores do not match transcripts")



def convert_wav_to_whisper(src: Path, dst: Path) -> None:
    """Convert verified PCM16 WAV into 16 kHz mono via standard-library interpolation.

    Linear resampling is sufficient for a first experimental pipeline; later
    experiments should use a validated antialiasing resampler for high fidelity.
    """
    if src.is_symlink() or not src.is_file():
        raise ValueError("Source audio missing or is a symlink")
    with wave.open(str(src), "rb") as sound:
        channels, width, rate, frames = (sound.getnchannels(), sound.getsampwidth(),
                                         sound.getframerate(), sound.getnframes())
        if (sound.getcomptype() != "NONE" or channels not in (1, 2) or width != 2
                or not 8000 <= rate <= 96000 or not 1 <= frames <= rate * 120):
            raise ValueError("Unsupported audio; expected PCM16 mono/stereo WAV at most 120s")
        samples = array("h")
        samples.frombytes(sound.readframes(frames))
    if sys.byteorder != "little":
        samples.byteswap()
    if len(samples) != channels * frames:
        raise ValueError("Truncated WAV audio")
    mono = [sum(samples[i * channels + c] for c in range(channels)) / channels for i in range(frames)]
    target_frames = max(1, round(frames * AUDIO_RATE / rate))
    output = array("h")
    for i in range(target_frames):
        position = i * rate / AUDIO_RATE
        a = min(int(position), frames - 1)
        b = min(a + 1, frames - 1)
        fraction = min(position - a, 1)
        value = round(mono[a] * (1 - fraction) + mono[b] * fraction)
        output.append(max(-32768, min(32767, value)))
    if sys.byteorder != "little":
        output.byteswap()
    with wave.open(str(dst), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(AUDIO_RATE)
        sound.writeframes(output.tobytes())


def require_whisper(model_path: Path, cli: str = "whisper-cli") -> str:
    """Check local executable and downloaded GGML model; never download them."""
    executable = shutil.which(cli)
    if not executable:
        raise RuntimeError("whisper-cli not found. Install with: brew install whisper.cpp")
    model_path = model_path.expanduser()
    if model_path.is_symlink() or not model_path.is_file() or model_path.stat().st_size < 1_000_000:
        raise RuntimeError(f"Whisper model missing or invalid: {model_path}")
    return executable


def recognize_clip(source_path: Path, model_path: Path, executable: str, temp_folder: Path) -> str:
    """Run local whisper-cli without a shell and read one UTF-8 text output."""
    converted = temp_folder / "input.wav"
    output_base = temp_folder / "recognition"
    convert_wav_to_whisper(source_path, converted)
    cmd = [executable, "--model", str(model_path), "--file", str(converted),
           "--language", "en", "--output-txt", "--output-file", str(output_base), "--no-prints"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Local whisper-cli failed to execute") from exc
    output_file = temp_folder / "recognition.txt"
    if result.returncode != 0 or not output_file.is_file():
        raise RuntimeError(f"Local whisper-cli failed (exit {result.returncode}): {result.stderr[-350:]}")
    output = output_file.read_text(encoding="utf-8").strip()
    if len(output) > 4000:
        raise ValueError("Unexpectedly long ASR output")
    return " ".join(output.split())


def build_asr_row(entry: dict[str, object], asr_text: str) -> dict[str, object]:
    reference = str(entry["transcript"])
    return {
        "clip_id": entry["clip_id"], "prompt_id": entry["prompt_id"],
        "condition": entry["condition"], "rate_wpm": entry["rate_wpm"],
        "voice": entry["voice"], "sha256": entry["sha256"],
        "reference_transcript": reference, "asr_transcript": asr_text,
        **transcription_score(reference, asr_text),
    }


def load_verified_stimuli(folder: Path) -> list[dict[str, object]]:
    return validate_manifest(folder)
