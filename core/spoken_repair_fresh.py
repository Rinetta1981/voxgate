"""Frozen post-V4 constructed stimuli and auditable speech evaluation.

This module does not modify WaitWise V3/V4 or make authorization decisions.
Cases were newly written after V4; labels are researcher-provisional, not
independently annotated. Re-running or tuning on this set makes it development data.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .analysis_v3 import detect_instruction_revision_v3
from .analysis_v4 import detect_instruction_revision_v4, INITIAL
from .evaluation import calculate_metrics
from .voicerank import audio_is_wav, file_digest
from .voicerank_speech import transcription_score

SCHEMA = 1
CONDITIONS = (("slower", 155), ("faster", 210))
# Frozen, balanced fixture written before the first ASR run. Do not edit after
# inspecting output. The cases are *constructed* and labels are provisional.
CASES = (
    ("NR01", "Forward the contract to Legal. Actually, forward it to Finance.", 1, "recipient_revision"),
    ("NR02", "Delete the duplicate file. No, keep the duplicate file.", 1, "instruction_cancellation"),
    ("NR03", "Move the budget spreadsheet to Shared. Wait, move it to Private.", 1, "destination_revision"),
    ("NR04", "Book the conference room for Tuesday. Sorry, make that Thursday.", 1, "date_revision"),
    ("NR05", "Email the draft to Jordan; instead, email it to Casey.", 1, "recipient_revision"),
    ("NR06", "Share the meeting notes with everyone. On second thought, do not share them.", 1, "instruction_cancellation"),
    ("NR07", "Send the calendar invitation now, but change that to tomorrow.", 1, "time_revision"),
    ("NR08", "Transfer the photos to the group. Actually, transfer them only to the editor.", 1, "recipient_revision"),
    ("NR09", "Put the invoice in Archive. No, put it in Pending.", 1, "destination_revision"),
    ("NR10", "Cancel tomorrow's appointment. Sorry, reschedule it for Friday.", 1, "date_revision"),
    ("NR11", "Keep the draft in Review. Actually, delete the draft.", 1, "action_revision"),
    ("NR12", "Hold the announcement until noon. Wait, send it at three instead.", 1, "time_revision"),
    ("NR13", "Forward the contract to Legal. Actually, the office is closed.", 0, "unrelated_comment"),
    ("NR14", "Delete the duplicate file. No one asked for the original.", 0, "statement_after_instruction"),
    ("NR15", "Move the budget spreadsheet to Shared. Wait, is Shared the right folder?", 0, "question_preface"),
    ("NR16", "Book the conference room for Tuesday. Sorry about the confusion.", 0, "unrelated_apology"),
    ("NR17", "Email the draft to Jordan instead of calling Jordan.", 0, "single_instruction_with_contrast"),
    ("NR18", "Share the meeting notes with everyone. On second thought, the discussion was productive.", 0, "unrelated_comment"),
    ("NR19", "Send the calendar invitation now. But the weather looks bad.", 0, "unrelated_comment"),
    ("NR20", "Transfer the photos to the group. Actually, the gallery looks beautiful.", 0, "unrelated_comment"),
    ("NR21", "Put the invoice in Archive. No files were deleted yesterday.", 0, "statement_after_instruction"),
    ("NR22", "Cancel tomorrow's appointment. Sorry I missed the call.", 0, "unrelated_apology"),
    ("NR23", "Keep the draft in Review. Wait, what is the latest version?", 0, "question_preface"),
    ("NR24", "Hold the announcement until noon. Actually, the team finished early.", 0, "unrelated_comment"),
)


def plan(voice: str = "system_default") -> list[dict[str, object]]:
    if not isinstance(voice, str) or not voice or len(voice) > 100 or any(ord(c) < 32 for c in voice):
        raise ValueError("Invalid TTS voice")
    results = []
    for case_id, text, gold, discourse_function in CASES:
        for condition, rate_wpm in CONDITIONS:
            clip_id = "n" + hashlib.sha256(f"voxgate-fresh-v1:{case_id}:{condition}".encode()).hexdigest()[:12]
            results.append({
                "clip_id": clip_id, "case_id": case_id, "condition": condition,
                "rate_wpm": rate_wpm, "transcript": text, "gold_revision": gold,
                "discourse_function": discourse_function, "voice": voice,
                "file_name": clip_id + ".wav",
            })
    return results


def validate_audio(folder: Path) -> list[dict[str, object]]:
    manifest = folder / "manifest.json"
    if manifest.is_symlink():
        raise ValueError("Refusing symlinked manifest")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or data.get("dataset") != "fresh_v1" or not isinstance(data.get("stimuli"), list):
        raise ValueError("Unexpected manifest schema or dataset")
    observed = data["stimuli"]
    if len(observed) != 48:
        raise ValueError("Expected 48 clips")
    voices = {item.get("voice") for item in observed if isinstance(item, dict)}
    if len(voices) != 1 or not isinstance(next(iter(voices)), str):
        raise ValueError("Inconsistent voice")
    expected = {str(item["clip_id"]): item for item in plan(next(iter(voices)))}
    seen = set()
    for item in observed:
        if not isinstance(item, dict) or item.get("clip_id") not in expected:
            raise ValueError("Unknown trial")
        clip_id = str(item["clip_id"])
        if clip_id in seen:
            raise ValueError("Duplicated trial")
        seen.add(clip_id)
        for field, value in expected[clip_id].items():
            if item.get(field) != value:
                raise ValueError(f"Mismatched metadata in {clip_id}: {field}")
        filename = item["file_name"]
        if not re.fullmatch(r"n[a-f0-9]{12}\.wav", filename):
            raise ValueError("Invalid clip filename")
        audio_path = folder / filename
        if audio_path.is_symlink() or not audio_is_wav(audio_path) or item.get("sha256") != file_digest(audio_path):
            raise ValueError(f"Invalid or altered audio clip: {filename}")
    return observed



def review_triage(transcript: str) -> str:
    """Flag uncertainty for human review; NEVER authorize or execute actions.

    `not_flagged` means this limited screen found no reason; it is NOT safe,
    correct, or authorized. ASR corruption may also be undetectable.
    """
    if not isinstance(transcript, str) or not transcript.strip():
        return "empty_transcript"
    if detect_instruction_revision_v4(transcript):
        return "candidate_revision"
    if detect_instruction_revision_v3(transcript):
        return "classifier_disagreement"
    if not INITIAL.match(re.sub(r"\be[\s-]?mail\b", "email", transcript.casefold())):
        return "unrecognized_opening"
    return "not_flagged"

def evaluate(entries: list[dict[str, object]], hypotheses: dict[str, str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Score ASR and V3/V4, without changing either detector or labels."""
    if len(entries) != 48 or set(hypotheses) != {str(r["clip_id"]) for r in entries}:
        raise ValueError("Expected exactly 48 recognized trial IDs")
    if len({str(r["clip_id"]) for r in entries}) != 48:
        raise ValueError("Duplicate trial IDs")
    predicted_rows = []
    for entry in entries:
        recognized = hypotheses[str(entry["clip_id"])]
        if not isinstance(recognized, str) or len(recognized) > 4000:
            raise ValueError("Invalid ASR text")
        ref = str(entry["transcript"])
        score = transcription_score(ref, recognized)
        v3 = int(detect_instruction_revision_v3(recognized))
        v4 = int(detect_instruction_revision_v4(recognized))
        gold = int(entry["gold_revision"])
        triage = review_triage(recognized)
        predicted_rows.append({
            "clip_id": entry["clip_id"], "case_id": entry["case_id"], "condition": entry["condition"],
            "gold_revision": gold, "discourse_function": entry["discourse_function"],
            "reference_transcript": ref, "asr_transcript": recognized,
            "reference_v3": int(detect_instruction_revision_v3(ref)),
            "reference_v4": int(detect_instruction_revision_v4(ref)),
            "asr_v3": v3, "asr_v4": v4,
            "v3_result": "TP" if (gold, v3) == (1, 1) else "FN" if gold else "FP" if v3 else "TN",
            "v4_result": "TP" if (gold, v4) == (1, 1) else "FN" if gold else "FP" if v4 else "TN",
            # Triage means "requires review", never "approved to execute".
            "needs_review_v4": v4,
            "triage_reason": triage,
            "triage_review_flag": int(triage != "not_flagged"),
            **score,
        })
    summaries = []
    for condition in ("slower", "faster", "both"):
        group = predicted_rows if condition == "both" else [r for r in predicted_rows if r["condition"] == condition]
        total_words = sum(int(r["reference_words"]) for r in group)
        edits = sum(int(r["word_edits"]) for r in group)
        triage_metrics = calculate_metrics([int(r["gold_revision"]) for r in group], [int(r["triage_review_flag"]) for r in group])
        summaries.append({
            "condition": condition, "version": "triage",
            "word_edits": edits, "reference_words": total_words,
            "micro_wer": round(edits / total_words, 6),
            "exact_matches": sum(int(r["exact_match"]) for r in group),
            "review_flagged": sum(int(r["triage_review_flag"]) for r in group),
            **triage_metrics,
        })
        for detector in ("v3", "v4"):
            metrics = calculate_metrics([int(r["gold_revision"]) for r in group], [int(r[f"asr_{detector}"]) for r in group])
            summaries.append({
                "condition": condition, "version": detector,
                "word_edits": edits, "reference_words": total_words,
                "micro_wer": round(edits / total_words, 6),
                "exact_matches": sum(int(r["exact_match"]) for r in group),
                "review_flagged": sum(int(r[f"asr_{detector}"]) for r in group),
                **metrics,
            })
    return predicted_rows, summaries
