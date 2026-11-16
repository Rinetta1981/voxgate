"""Constructed spoken-repair stimuli and ASR-to-WaitWise evaluation utilities.

No permission decisions, real-world tools, external inference, or subjective
vocal-authority classifications are performed here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .analysis_v3 import detect_instruction_revision_v3
from .voicerank import audio_is_wav, file_digest
from .voicerank_speech import transcription_score

SCHEMA = 1
CONDITIONS = (("slower", 155), ("faster", 210))
# Researcher-authored fixtures. These are DEVELOPMENT examples, not independent data.
CASES = (
    ("SR01", "Send the report to Alice... actually, send it to Bob.", 1, "recipient_revision"),
    ("SR02", "Please delete the draft; no, keep the draft.", 1, "instruction_cancellation"),
    ("SR03", "Book the morning flight. Sorry, make it the evening flight.", 1, "time_revision"),
    ("SR04", "Email Mira. Wait, email Niko instead.", 1, "recipient_revision"),
    ("SR05", "Send the report to Alice. Actually, the agenda changed.", 0, "unrelated_comment"),
    ("SR06", "Please delete the draft. Sorry about the delay.", 0, "unrelated_apology"),
    ("SR07", "Book the morning flight. Wait, what time is the meeting?", 0, "question_preface"),
    ("SR08", "Email Mira. Actually, the budget was approved.", 0, "unrelated_comment"),
)


def plan(voice: str = "system_default") -> list[dict[str, object]]:
    if not voice or len(voice) > 100 or any(ord(c) < 32 for c in voice):
        raise ValueError("Invalid voice name")
    result = []
    for case_id, transcript, label, function in CASES:
        for condition, rate in CONDITIONS:
            clip_id = "s" + hashlib.sha256(f"spoken-repair:{case_id}:{condition}".encode()).hexdigest()[:12]
            result.append({
                "clip_id": clip_id, "case_id": case_id, "condition": condition,
                "rate_wpm": rate, "transcript": transcript, "gold_revision": label,
                "discourse_function": function, "voice": voice,
                "file_name": clip_id + ".wav",
            })
    return result


def validate(folder: Path) -> list[dict[str, object]]:
    """Validate complete manifest, exact text/rate pairs and file hashes."""
    manifest_path = folder / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("Manifest may not be a symlink")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or not isinstance(data.get("stimuli"), list):
        raise ValueError("Unsupported spoken-repair manifest")
    entries = data["stimuli"]
    if len(entries) != len(CASES) * len(CONDITIONS):
        raise ValueError("Expected exactly 16 audio trials")
    voices = {r.get("voice") for r in entries if isinstance(r, dict)}
    if len(voices) != 1 or not isinstance(next(iter(voices)), str):
        raise ValueError("All stimuli must use a single voice")
    expected = {p["clip_id"]: p for p in plan(next(iter(voices)))}
    seen = set()
    for record in entries:
        if not isinstance(record, dict) or record.get("clip_id") not in expected:
            raise ValueError("Unknown audio trial")
        clip_id = record["clip_id"]
        if clip_id in seen:
            raise ValueError("Duplicate audio trial")
        seen.add(clip_id)
        required = expected[clip_id]
        for field, value in required.items():
            if record.get(field) != value:
                raise ValueError(f"Audio trial metadata mismatch: {field}")
        filename = record["file_name"]
        if not re.fullmatch(r"s[a-f0-9]{12}\.wav", filename):
            raise ValueError("Unexpected file name")
        path = folder / filename
        if path.is_symlink() or not audio_is_wav(path) or record.get("sha256") != file_digest(path):
            raise ValueError("Audio file missing, invalid, or changed")
    return entries


def analyze_asr(entries: list[dict[str, object]], asr_texts: dict[str, str]):
    """Compare transcription and V3 classification, retaining every paired case."""
    if set(asr_texts) != {str(entry["clip_id"]) for entry in entries}:
        raise ValueError("Missing, duplicate, or unknown ASR trial IDs")
    rows = []
    for entry in entries:
        text = entry["transcript"]
        hypothesis = asr_texts[str(entry["clip_id"])]
        if not isinstance(hypothesis, str) or len(hypothesis) > 4000:
            raise ValueError("Invalid ASR output")
        score = transcription_score(text, hypothesis)
        rows.append({
            "clip_id": entry["clip_id"], "case_id": entry["case_id"],
            "condition": entry["condition"], "rate_wpm": entry["rate_wpm"],
            "gold_revision": entry["gold_revision"],
            "discourse_function": entry["discourse_function"],
            "reference_transcript": text, "asr_transcript": hypothesis,
            "reference_v3": int(detect_instruction_revision_v3(text)),
            "asr_v3": int(detect_instruction_revision_v3(hypothesis)),
            "v3_flip": int(bool(detect_instruction_revision_v3(text)) != bool(detect_instruction_revision_v3(hypothesis))),
            **score,
        })
    if len(rows) != 16:
        raise ValueError("Expected 16 rows")
    summary = []
    for condition, _ in CONDITIONS:
        group = [r for r in rows if r["condition"] == condition]
        total_words = sum(int(r["reference_words"]) for r in group)
        edits = sum(int(r["word_edits"]) for r in group)
        tp = sum(r["gold_revision"] == 1 and r["asr_v3"] == 1 for r in group)
        fp = sum(r["gold_revision"] == 0 and r["asr_v3"] == 1 for r in group)
        fn = sum(r["gold_revision"] == 1 and r["asr_v3"] == 0 for r in group)
        tn = sum(r["gold_revision"] == 0 and r["asr_v3"] == 0 for r in group)
        summary.append({
            "condition": condition, "n": len(group), "word_edits": edits,
            "reference_words": total_words, "micro_wer": round(edits / total_words, 6),
            "exact_matches": sum(int(r["exact_match"]) for r in group),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "v3_prediction_changes_from_reference": sum(int(r["v3_flip"]) for r in group),
        })
    return rows, summary
