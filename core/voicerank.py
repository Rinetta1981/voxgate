"""Offline VoiceRank stimulus definitions and blinded perception-rating tools.

Scope: rate manipulation of one macOS TTS voice. NOT a validated 'authority'
voice manipulation, and NOT an AI-agent permission-decision experiment.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

VOICE_DIR = Path.home() / "Desktop" / "voxgate-voice-stimuli"
SCHEMA_VERSION = 1
PROMPTS = (
    ("VR01", "Send the summary to the review team."),
    ("VR02", "Share the draft with the committee."),
    ("VR03", "Move the project notes into the archive folder."),
    ("VR04", "Email the revised agenda to the participants."),
)
CONDITIONS = (("slower", 155), ("faster", 210))
REQUIRED_RATINGS = ("authority", "clarity", "urgency")
EXPORT_FIELDS = (
    "trial_index", "clip_id", "prompt_id", "condition", "rate_wpm", "voice",
    "authority", "clarity", "urgency", "transcript",
)


def stimulus_plan(voice: str = "system_default") -> list[dict[str, str | int]]:
    """Build eight reproducible audio-trial records, without synthesizing audio."""
    if not voice or len(voice) > 100 or any(c in voice for c in "\r\n\x00"):
        raise ValueError("Voice name is invalid")
    result: list[dict[str, str | int]] = []
    for prompt_id, text in PROMPTS:
        for condition, rate in CONDITIONS:
            clip_id = "v" + hashlib.sha256(f"{prompt_id}:{condition}".encode()).hexdigest()[:12]
            result.append({
                "clip_id": clip_id, "prompt_id": prompt_id, "transcript": text,
                "condition": condition, "rate_wpm": rate, "voice": voice,
                "file_name": f"{clip_id}.wav",
            })
    return result


def audio_is_wav(path: Path) -> bool:
    if not path.is_file() or not 44 <= path.stat().st_size <= 30 * 1024 * 1024:
        return False
    with path.open("rb") as handle:
        header = handle.read(12)
    return header[:4] == b"RIFF" and header[8:12] == b"WAVE"


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_manifest(directory: Path | str) -> list[dict[str, str | int]]:
    """Check metadata, all local audio files, paired text identity, and hashes."""
    directory = Path(directory)
    data = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("stimuli"), list):
        raise ValueError("Unsupported VoiceRank manifest format")
    records = data["stimuli"]
    expected = {entry["clip_id"]: entry for entry in stimulus_plan()}
    if len(records) != len(expected):
        raise ValueError("Incorrect number of paired audio clips")
    used: set[str] = set()
    voice_set: set[str] = set()
    for entry in records:
        if not isinstance(entry, dict) or entry.get("clip_id") not in expected:
            raise ValueError("Unexpected clip ID")
        clip_id = entry["clip_id"]
        if clip_id in used:
            raise ValueError("Duplicate audio clip")
        used.add(clip_id)
        definition = expected[clip_id]
        for key in ("prompt_id", "transcript", "condition", "rate_wpm", "file_name"):
            if entry.get(key) != definition[key]:
                raise ValueError(f"Mismatched stimulus field: {key}")
        voice = entry.get("voice")
        if not isinstance(voice, str) or not voice or len(voice) > 100:
            raise ValueError("Invalid voice description")
        voice_set.add(voice)
        filename = entry["file_name"]
        if not re.fullmatch(r"v[a-f0-9]{12}\.wav", filename):
            raise ValueError("Unsafe or unexpected audio filename")
        audio_path = directory / filename
        if audio_path.is_symlink() or not audio_is_wav(audio_path):
            raise ValueError(f"Missing or invalid WAV file: {filename}")
        if entry.get("sha256") != file_digest(audio_path):
            raise ValueError(f"Audio integrity check failed: {filename}")
    if len(voice_set) != 1:
        raise ValueError("Paired conditions must use the same TTS voice")
    return records


def validate_ratings(values: dict[str, object]) -> dict[str, int]:
    """Accept three integer Likert-scale responses, 1–5 (no missing values)."""
    result: dict[str, int] = {}
    for key in REQUIRED_RATINGS:
        value = values.get(key)
        if not isinstance(value, str) or value not in {"1", "2", "3", "4", "5"}:
            raise ValueError(f"{key} must be an integer from 1 to 5")
        result[key] = int(value)
    return result


def export_rows(records: list[dict[str, str | int]], order: list[str],
                ratings: dict[str, dict[str, int]]) -> list[dict[str, object]]:
    """Return rating rows in presentation order, including condition labels."""
    by_id = {str(r["clip_id"]): r for r in records}
    if set(order) != set(by_id) or len(order) != len(by_id):
        raise ValueError("The stored presentation order is invalid")
    result = []
    for index, clip_id in enumerate(order, 1):
        if clip_id not in ratings:
            continue
        scores = ratings[clip_id]
        validated = validate_ratings({k: str(scores.get(k, "")) for k in REQUIRED_RATINGS})
        row = by_id[clip_id]
        result.append({
            "trial_index": index, "clip_id": clip_id,
            "prompt_id": row["prompt_id"], "condition": row["condition"],
            "rate_wpm": row["rate_wpm"], "voice": row["voice"],
            **validated, "transcript": row["transcript"],
        })
    return result


def paired_authority_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    """Compute descriptive means and within-prompt differences, not significance."""
    seen: set[str] = set()
    paired: dict[str, dict[str, int]] = {}
    for row in rows:
        clip_id = row.get("clip_id", "")
        prompt_id = row.get("prompt_id", "")
        condition = row.get("condition", "")
        if clip_id in seen or not clip_id or prompt_id not in dict(PROMPTS) or condition not in {"slower", "faster"}:
            raise ValueError("Duplicate or unknown trial")
        seen.add(clip_id)
        score_text = str(row.get("authority", ""))
        if score_text not in {"1", "2", "3", "4", "5"}:
            raise ValueError("Invalid authority rating")
        if condition in paired.setdefault(prompt_id, {}):
            raise ValueError("Duplicate condition for a prompt")
        paired[prompt_id][condition] = int(score_text)
    complete = [ratings for ratings in paired.values() if set(ratings) == {"slower", "faster"}]
    if not complete:
        return {"complete_pairs": 0, "mean_slower": None, "mean_faster": None, "mean_difference_faster_minus_slower": None}
    n = len(complete)
    slow = sum(r["slower"] for r in complete) / n
    fast = sum(r["faster"] for r in complete) / n
    return {"complete_pairs": n, "mean_slower": slow, "mean_faster": fast, "mean_difference_faster_minus_slower": fast - slow}
