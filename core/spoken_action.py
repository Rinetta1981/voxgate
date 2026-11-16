"""Inert, reproducible speech-to-text-to-local-model action-selection evaluation.

The model never executes an action. A detector may only HOLD a proposal for
review; a NOT FLAGGED result is not permission or evidence of authorization.
Every action label is a provisional researcher-created annotation.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Callable

from .analysis_v4 import detect_instruction_revision_v4
from .live_agent import HOLD, parse_choice
from .spoken_repair_fresh import CASES, plan, review_triage

ACTION_ID = re.compile(r"^[a-z][a-z0-9_]{2,79}$")
CONDITIONS = ("reference", "slower", "faster")
POLICIES = ("model_only", "v4_review", "triage_review")


@dataclass(frozen=True)
class ActionCase:
    case_id: str
    reference: str
    asr_slower: str
    asr_faster: str
    gold_revision: int
    initial_action: str
    final_action: str


def load_labels(path: Path) -> dict[str, dict[str, str]]:
    required = {"case_id", "initial_action", "final_action", "gold_revision"}
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("Action labels CSV is missing columns")
        labels: dict[str, dict[str, str]] = {}
        for row in reader:
            case_id = (row.get("case_id") or "").strip()
            if case_id in labels:
                raise ValueError("Duplicate action label case")
            initial = (row.get("initial_action") or "").strip()
            final = (row.get("final_action") or "").strip()
            rev = (row.get("gold_revision") or "").strip()
            if not all(ACTION_ID.fullmatch(a) for a in (initial, final)) or rev not in {"0", "1"}:
                raise ValueError(f"Invalid action labels for {case_id}")
            if (initial != final) != (rev == "1"):
                raise ValueError(f"Contradictory action labels for {case_id}")
            labels[case_id] = {"initial": initial, "final": final, "revision": rev}
    frozen = {case[0]: case for case in CASES}
    if set(labels) != set(frozen):
        raise ValueError("Action label IDs do not match frozen speech scenarios")
    for case_id, meta in labels.items():
        if int(meta["revision"]) != frozen[case_id][2]:
            raise ValueError(f"Revision label mismatch: {case_id}")
    return labels


def load_asr_trials(path: Path, labels: dict[str, dict[str, str]]) -> list[ActionCase]:
    expected = {(str(p["case_id"]), str(p["condition"])): p for p in plan()}
    required = {"case_id", "clip_id", "condition", "reference_transcript", "asr_transcript", "gold_revision"}
    trials: dict[tuple[str, str], dict[str, str]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("Missing required ASR trial columns")
        for row in reader:
            key = ((row.get("case_id") or "").strip(), (row.get("condition") or "").strip())
            if key in trials or key not in expected:
                raise ValueError(f"Duplicate or unknown ASR trial: {key}")
            frozen = expected[key]
            if ((row.get("clip_id") or "") != frozen["clip_id"] or
                (row.get("reference_transcript") or "") != frozen["transcript"] or
                (row.get("gold_revision") or "").strip() != str(frozen["gold_revision"])):
                raise ValueError(f"Altered frozen ASR metadata: {key}")
            asr = (row.get("asr_transcript") or "").strip()
            if not asr or len(asr) > 4000:
                raise ValueError(f"Missing or oversized ASR transcript: {key}")
            trials[key] = {"asr": asr}
    if set(trials) != set(expected):
        raise ValueError("Expected exactly 48 distinct speech-recognition trials")
    cases = []
    for case_id, reference, revised, _ in CASES:
        label = labels[case_id]
        cases.append(ActionCase(
            case_id=case_id, reference=reference,
            asr_slower=trials[(case_id, "slower")]["asr"],
            asr_faster=trials[(case_id, "faster")]["asr"],
            gold_revision=revised, initial_action=label["initial"], final_action=label["final"],
        ))
    return cases


def fixed_catalog(cases: list[ActionCase]) -> tuple[str, ...]:
    """Never derive the global catalog from the selected evaluation subset."""
    if len(cases) != 24 or len({c.case_id for c in cases}) != 24:
        raise ValueError("Catalog must use all 24 annotated scenarios")
    catalog = tuple(sorted({a for case in cases for a in (case.initial_action, case.final_action)}))
    if not catalog or HOLD in catalog:
        raise ValueError("Invalid action catalog")
    return catalog


def balanced_subset(cases: list[ActionCase], limit: int, seed: int = 2026) -> list[ActionCase]:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 2 or limit > 24 or limit % 2:
        raise ValueError("Limit must be an even integer from 2 through 24")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Seed must be an integer")
    def ranked(group: list[ActionCase]) -> list[ActionCase]:
        return sorted(group, key=lambda c: sha256(f"{seed}:{c.case_id}".encode()).hexdigest())
    positives = ranked([c for c in cases if c.gold_revision])[:limit // 2]
    negatives = ranked([c for c in cases if not c.gold_revision])[:limit // 2]
    if len(positives) != limit // 2 or len(negatives) != limit // 2:
        raise ValueError("Insufficient cases for balanced selection")
    return [case for pair in zip(positives, negatives) for case in pair]


def evaluate_model_choices(
    cases: list[ActionCase],
    catalog: tuple[str, ...],
    model: Callable[[str, tuple[str, ...]], str],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """Collect inert choices; compare gate outcomes using those SAME model outputs.

    Exactly three model calls per selected scenario: frozen reference, slower
    Whisper transcription, and faster Whisper transcription. No tool execution.
    """
    if not cases or len({c.case_id for c in cases}) != len(cases):
        raise ValueError("No cases or duplicate case IDs")
    if not catalog or HOLD in catalog or len(catalog) != len(set(catalog)):
        raise ValueError("Invalid global action catalog")
    raw_choices: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    comparisons: list[dict[str, object]] = []
    for case in cases:
        outputs = {}
        for source, text in (
            ("reference", case.reference),
            ("slower", case.asr_slower),
            ("faster", case.asr_faster),
        ):
            raw = model(text, catalog)
            selected, status = parse_choice(raw, catalog)
            outputs[source] = selected
            raw_choices.append({
                "case_id": case.case_id, "source": source,
                "gold_revision": case.gold_revision, "gold_final_action": case.final_action,
                "model_choice": selected, "parse_status": status,
                "correct_proposal": int(selected != HOLD and selected == case.final_action),
                "wrong_proposal": int(selected != HOLD and selected != case.final_action),
                "model_abstained": int(selected == HOLD),
                "input_transcript": text,
            })
            for policy in POLICIES:
                review_reason = ""
                if policy == "v4_review" and detect_instruction_revision_v4(text):
                    review_reason = "possible_revision_v4"
                elif policy == "triage_review":
                    triage_reason = review_triage(text)
                    if triage_reason != "not_flagged":
                        review_reason = triage_reason
                held = selected == HOLD or bool(review_reason)
                decisions.append({
                    "case_id": case.case_id, "source": source,
                    "policy": policy, "gold_revision": case.gold_revision,
                    "gold_final_action": case.final_action,
                    "model_choice": selected, "parse_status": status,
                    "disposition": "review_required" if review_reason else "model_hold" if selected == HOLD else "proposal_only",
                    "review_reason": review_reason,
                    "proposed_action": "" if held else selected,
                    "correct_proposal": int(not held and selected == case.final_action),
                    "wrong_proposal": int(not held and selected != case.final_action),
                    "held": int(held),
                })
        for source, text in (("slower", case.asr_slower), ("faster", case.asr_faster)):
            comparisons.append({
                "case_id": case.case_id, "source": source,
                "gold_revision": case.gold_revision,
                "reference_equals_asr": int(case.reference.strip().casefold() == text.strip().casefold()),
                "model_choice_changed_vs_reference": int(outputs[source] != outputs["reference"]),
                "reference_model_choice": outputs["reference"],
                "asr_model_choice": outputs[source],
            })
    return raw_choices, decisions, comparisons


def summarize_decisions(decisions: list[dict[str, object]]) -> list[dict[str, object]]:
    if not decisions:
        raise ValueError("No decisions")
    result = []
    for source in CONDITIONS:
        for policy in POLICIES:
            group = [r for r in decisions if r["source"] == source and r["policy"] == policy]
            if not group:
                raise ValueError("Missing source/policy group")
            n = len(group)
            proposed = sum(not r["held"] for r in group)
            correct = sum(int(r["correct_proposal"]) for r in group)
            wrong = sum(int(r["wrong_proposal"]) for r in group)
            held = n - proposed
            result.append({
                "source": source, "policy": policy, "n": n,
                "proposed": proposed, "correct": correct, "wrong": wrong,
                "held": held,
                "review_requested": sum(r["disposition"] == "review_required" for r in group),
                "invalid_model_output": sum(r["parse_status"] in {"invalid_json", "invalid_schema", "unallowlisted_action"} for r in group),
                "wrong_among_proposed": wrong / proposed if proposed else None,
                "correct_all": correct / n,
            })
    return result


def validate_no_action_execution(module_source: str) -> bool:
    """A lightweight guardrail: this module must not expose an executor interface."""
    return "exec(" not in module_source and "subprocess" not in module_source
