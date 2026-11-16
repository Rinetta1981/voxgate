"""Deterministic balanced sampling and stratified evaluation for WaitWise.

This module does not modify any detector, scenario, or prompt.
Researcher-created labels determine *sampling and scoring*, never model input.
"""
from __future__ import annotations

from hashlib import sha256
from .agent_simulation import Scenario
from .live_agent import InertToolEvent


def balanced_sample(cases: list[Scenario], limit: int, seed: int = 2026) -> list[Scenario]:
    """Choose an equal number of gold-revised and nonrevised scenarios.

    Stable hashing makes selection independent of input row order and Python's
    random implementation. Restrict to an even sample size to ensure balance.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 2 or limit % 2:
        raise ValueError("Balanced --limit must be an even integer of at least 2")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("Seed must be an integer")
    if len({c.case_id for c in cases}) != len(cases):
        raise ValueError("Scenario IDs must be unique")
    revised = [case for case in cases if case.revised]
    unrevised = [case for case in cases if not case.revised]
    per_group = limit // 2
    if min(len(revised), len(unrevised)) < per_group:
        raise ValueError(f"Insufficient scenarios for {limit} balanced cases")

    def rank(case: Scenario) -> str:
        return sha256(f"{seed}:{case.case_id}".encode("utf-8")).hexdigest()

    revised = sorted(revised, key=rank)[:per_group]
    unrevised = sorted(unrevised, key=rank)[:per_group]
    # Interleave classes, rather than putting every positive before every negative.
    return [item for pair in zip(revised, unrevised) for item in pair]


def audit_by_stratum(cases: list[Scenario], events: list[InertToolEvent]) -> list[dict[str, object]]:
    """Compute metrics by condition and by true revision category.

    Rates with zero executed choices have an undefined wrong-per-executed rate
    (None); report all denominators rather than claiming zero risk.
    """
    index = {case.case_id: case for case in cases}
    if len(index) != len(cases) or not cases:
        raise ValueError("Scenarios must be nonempty with unique IDs")
    conditions = list(dict.fromkeys(event.condition for event in events))
    expected = {(case.case_id, condition) for case in cases for condition in conditions}
    found = [(event.case_id, event.condition) for event in events]
    if len(found) != len(set(found)) or set(found) != expected:
        raise ValueError("Expected exactly one event per condition and scenario")

    rows: list[dict[str, object]] = []
    for condition in conditions:
        for stratum, subset in (
            ("all", cases),
            ("revised", [case for case in cases if case.revised]),
            ("not_revised", [case for case in cases if not case.revised]),
        ):
            ids = {case.case_id for case in subset}
            group = [event for event in events if event.condition == condition and event.case_id in ids]
            n = len(group)
            executed = sum(not e.held for e in group)
            wrong = sum(e.wrong for e in group)
            invalid = sum(e.status in {"invalid_json", "invalid_schema", "unallowlisted_action"} for e in group)
            rows.append({
                "condition": condition, "stratum": stratum, "n": n,
                "executed": executed, "held": n - executed,
                "wrong": wrong, "correct": executed - wrong,
                "invalid": invalid,
                "coverage": executed / n if n else None,
                "wrong_rate_all": wrong / n if n else None,
                "wrong_rate_executed": wrong / executed if executed else None,
                "correct_completion_rate_all": (executed - wrong) / n if n else None,
            })
    return rows
