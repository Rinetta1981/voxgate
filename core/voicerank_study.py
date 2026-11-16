"""Counterbalanced, single-listener VoiceRank study and descriptive multi-listener analysis.

Does not do AI inference, evaluate authorization, or contact third parties.
Existing v1 audio stimuli are reused without changes.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import statistics
from collections import defaultdict
from pathlib import Path

from .voicerank import PROMPTS, REQUIRED_RATINGS, export_rows, stimulus_plan

STUDY_VERSION = "2"
N_ASSIGNMENTS = 8
PARTICIPANT_PATTERN = re.compile(r"^vr2-[a-f0-9]{20}$")
EXPORT_FIELDS_V2 = (
    "study_version", "participant_id", "assignment_id", "audio_fingerprint",
    "trial_index", "clip_id", "prompt_id", "condition", "rate_wpm", "voice",
    "authority", "clarity", "urgency", "transcript",
)


def counterbalanced_order(records: list[dict], assignment_id: int) -> list[str]:
    """Eight balanced schedules, with nonadjacent paired prompts.

    Across all eight schedules: each prompt is at each within-block position
    twice, and each prompt receives slower-first vs faster-first four times.
    Assignment among schedules is random, not guaranteed balanced in a small
    realized sample.
    """
    if isinstance(assignment_id, bool) or not isinstance(assignment_id, int) or not 0 <= assignment_id < N_ASSIGNMENTS:
        raise ValueError("Assignment must be one of 0–7")
    by_key = {}
    for item in records:
        key = (item.get("prompt_id"), item.get("condition"))
        if key in by_key:
            raise ValueError("Duplicate prompt/condition")
        by_key[key] = item.get("clip_id")
    prompts = [p for p, _ in PROMPTS]
    if set(by_key) != {(prompt, condition) for prompt in prompts for condition in ("slower", "faster")}:
        raise ValueError("Expected exactly four matched slower/faster pairs")
    offset = assignment_id // 2
    permuted = prompts[offset:] + prompts[:offset]
    first = {prompt: ("slower" if (i + assignment_id % 2) % 2 == 0 else "faster")
             for i, prompt in enumerate(prompts)}
    block_one = [str(by_key[(p, first[p])]) for p in permuted]
    second_order = permuted[2:] + permuted[:2]
    block_two = [str(by_key[(p, "faster" if first[p] == "slower" else "slower")]) for p in second_order]
    return block_one + block_two


def fingerprint_audio(records: list[dict]) -> str:
    """Identify an identical *set of WAV files*, not the nominal voice name."""
    if len(records) != 8:
        raise ValueError("Eight stimuli are required")
    pairs = []
    for item in records:
        clip_id, digest = item.get("clip_id"), item.get("sha256")
        if not isinstance(clip_id, str) or not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            raise ValueError("Stimulus hashes missing or invalid")
        pairs.append((clip_id, str(digest)))
    if len(set(clip for clip, _ in pairs)) != 8:
        raise ValueError("Repeated audio clip")
    basis = "\n".join(f"{clip}:{digest}" for clip, digest in sorted(pairs))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def export_study_rows(records: list[dict], order: list[str], ratings: dict,
                      participant_id: str, assignment_id: int) -> list[dict]:
    if not PARTICIPANT_PATTERN.fullmatch(participant_id):
        raise ValueError("Invalid participant code")
    if order != counterbalanced_order(records, assignment_id):
        raise ValueError("Stored presentation order does not match assignment")
    if set(ratings) != set(order) or len(ratings) != 8:
        raise ValueError("Complete eight-clip ratings required before exporting")
    fingerprint = fingerprint_audio(records)
    data = export_rows(records, order, ratings)
    if len(data) != 8:
        raise ValueError("Incomplete ratings")
    return [{"study_version": STUDY_VERSION, "participant_id": participant_id,
             "assignment_id": assignment_id, "audio_fingerprint": fingerprint, **row}
            for row in data]


def read_study_csvs(paths: list[Path]) -> list[dict[str, str]]:
    """Read exports, rejecting duplicate participant codes and malformed files."""
    if not paths:
        raise ValueError("At least one study CSV is required")
    all_rows = []
    used_codes = set()
    for path in paths:
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not set(EXPORT_FIELDS_V2).issubset(reader.fieldnames):
                raise ValueError(f"{path}: not a VoiceRank expanded-study export")
            rows = list(reader)
        if len(rows) != 8:
            raise ValueError(f"{path}: expected exactly eight completed trials")
        codes = {row["participant_id"] for row in rows}
        if len(codes) != 1:
            raise ValueError(f"{path}: mixed participant codes")
        code = next(iter(codes))
        if code in used_codes:
            raise ValueError(f"Duplicate participant ID across files: {code}. Keep one export per participant")
        used_codes.add(code)
        all_rows.extend(rows)
    return all_rows


def summarize_participants(rows: list[dict]) -> tuple[list[dict], dict]:
    """One independent unit per participant, not per clip or prompt.

    Returns individual participant averages and descriptive group means only.
    """
    if not rows:
        raise ValueError("No ratings supplied")
    participants = defaultdict(list)
    for row in rows:
        participants[str(row.get("participant_id", ""))].append(row)
    fingerprint_set = set()
    participant_results = []
    expected = {item["clip_id"]: item for item in stimulus_plan()}
    for pid, group in sorted(participants.items()):
        if not PARTICIPANT_PATTERN.fullmatch(pid) or len(group) != 8:
            raise ValueError("Each participant must contribute exactly eight valid trials")
        assignment_set = {str(item.get("assignment_id", "")) for item in group}
        if len(assignment_set) != 1:
            raise ValueError(f"Mixed assignment for {pid}")
        try:
            assignment = int(next(iter(assignment_set)))
        except ValueError as exc:
            raise ValueError("Non-integer assignment") from exc
        if not 0 <= assignment < N_ASSIGNMENTS or str(assignment) not in assignment_set:
            raise ValueError("Unexpected assignment")
        fp = {str(item.get("audio_fingerprint", "")) for item in group}
        if len(fp) != 1 or not re.fullmatch(r"[a-f0-9]{64}", next(iter(fp))):
            raise ValueError("Invalid audio fingerprint")
        fingerprint_set.update(fp)
        trial_map = {}
        keys = set()
        scores = {key: defaultdict(dict) for key in REQUIRED_RATINGS}
        for item in group:
            if str(item.get("study_version")) != STUDY_VERSION:
                raise ValueError("Unsupported study version")
            clip = str(item.get("clip_id", ""))
            canonical = expected.get(clip)
            if canonical is None:
                raise ValueError("Unknown clip")
            if (str(item.get("prompt_id")) != canonical["prompt_id"]
                    or str(item.get("condition")) != canonical["condition"]
                    or str(item.get("rate_wpm")) != str(canonical["rate_wpm"])
                    or str(item.get("transcript")) != canonical["transcript"]):
                raise ValueError("Clip metadata altered")
            if not str(item.get("voice", "")).strip():
                raise ValueError("Missing voice")
            try:
                trial = int(str(item.get("trial_index", "")))
            except ValueError as exc:
                raise ValueError("Non-integer trial index") from exc
            if str(trial) != str(item["trial_index"]) or trial not in range(1, 9) or trial in trial_map:
                raise ValueError("Invalid or duplicate trial index")
            trial_map[trial] = clip
            key = (canonical["prompt_id"], canonical["condition"])
            if key in keys:
                raise ValueError("Duplicate prompt/condition")
            keys.add(key)
            for dim in REQUIRED_RATINGS:
                val = str(item.get(dim, ""))
                if val not in {"1", "2", "3", "4", "5"}:
                    raise ValueError(f"Invalid {dim} score")
                scores[dim][canonical["prompt_id"]][canonical["condition"]] = int(val)
        expected_order = counterbalanced_order(list(expected.values()), assignment)
        if [trial_map[i] for i in range(1, 9)] != expected_order:
            raise ValueError("Trials do not match assigned sequence")
        summary = {"participant_id": pid, "assignment_id": assignment}
        for dim in REQUIRED_RATINGS:
            ratings_by_prompt = scores[dim]
            if (len(ratings_by_prompt) != len(PROMPTS)
                    or any(set(pair) != {"slower", "faster"} for pair in ratings_by_prompt.values())):
                raise ValueError("Incomplete within-prompt ratings")
            slower = [ratings_by_prompt[p]["slower"] for p, _ in PROMPTS]
            faster = [ratings_by_prompt[p]["faster"] for p, _ in PROMPTS]
            summary[f"{dim}_slower_mean"] = statistics.mean(slower)
            summary[f"{dim}_faster_mean"] = statistics.mean(faster)
            summary[f"{dim}_difference"] = statistics.mean(f - s for f, s in zip(faster, slower))
        participant_results.append(summary)
    if len(fingerprint_set) != 1:
        raise ValueError("Audio clips differ across participants; analyze each audio set separately")
    group_result = {"study_version": STUDY_VERSION, "participants": len(participant_results),
                    "trials": len(rows), "audio_fingerprint": next(iter(fingerprint_set)),
                    "assignment_counts": {str(i): sum(p["assignment_id"] == i for p in participant_results)
                                          for i in range(N_ASSIGNMENTS)}}
    for dim in REQUIRED_RATINGS:
        vals = [p[f"{dim}_difference"] for p in participant_results]
        group_result[dim] = {
            "mean_slower": statistics.mean(p[f"{dim}_slower_mean"] for p in participant_results),
            "mean_faster": statistics.mean(p[f"{dim}_faster_mean"] for p in participant_results),
            "mean_participant_difference_faster_minus_slower": statistics.mean(vals),
            "participant_sd_difference": statistics.stdev(vals) if len(vals) > 1 else None,
            "min_participant_difference": min(vals), "max_participant_difference": max(vals),
        }
    return participant_results, group_result
