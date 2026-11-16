"""Side-effect-free, explicitly simplified AI-agent authorization simulation.

No real tools, models, speech, or external APIs are accessed by this module.
Human-provided action IDs are ground-truth annotations, not model outputs.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

Policy = Literal["immediate", "turn_end", "repair_gate", "confirmation_gate", "oracle_final"]
POLICIES: tuple[Policy, ...] = ("immediate", "turn_end", "repair_gate", "confirmation_gate", "oracle_final")
TURN_END_MS = 2000  # A deliberately fixed simulation parameter, not an observed latency.


@dataclass(frozen=True)
class Scenario:
    case_id: str
    transcript: str
    initial_action: str
    final_action: str
    revised: bool
    discourse_function: str


@dataclass(frozen=True)
class Decision:
    case_id: str
    policy: Policy
    action: str | None
    phase: str
    t_ms: int | None
    detected_revision: bool | None
    gold_revised: bool
    final_action: str

    @property
    def held(self) -> bool:
        return self.action is None

    @property
    def wrong_action(self) -> bool:
        return self.action is not None and self.action != self.final_action

    @property
    def premature(self) -> bool:
        return self.action is not None and self.phase == "initial"


def load_scenarios(path: Path | str) -> list[Scenario]:
    """Read controlled scenario annotations, rejecting inconsistent action labels."""
    cases: list[Scenario] = []
    seen: set[str] = set()
    required = {"case_id", "transcript", "initial_action", "final_action", "revises_prior_instruction", "discourse_function"}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV is missing required columns: {sorted(required)}")
        for line, row in enumerate(reader, start=2):
            fields = {name: (row.get(name) or "").strip() for name in required}
            if any(not v for v in fields.values()):
                raise ValueError(f"Blank required value on CSV line {line}")
            if fields["revises_prior_instruction"] not in {"0", "1"}:
                raise ValueError(f"Invalid revision label on CSV line {line}")
            if fields["case_id"] in seen:
                raise ValueError(f"Duplicate case_id on line {line}")
            seen.add(fields["case_id"])
            revised = fields["revises_prior_instruction"] == "1"
            action_changed = fields["initial_action"] != fields["final_action"]
            if revised != action_changed:
                raise ValueError(f"Revision label/action conflict on line {line}")
            cases.append(Scenario(fields["case_id"], fields["transcript"], fields["initial_action"], fields["final_action"], revised, fields["discourse_function"]))
    if not cases:
        raise ValueError("Scenario file is empty")
    return cases


def simulate(case: Scenario, policy: Policy, detector: Callable[[str], object]) -> Decision:
    """Decide whether/when an abstract action is committed.

    - immediate: sends initial action before the speaker finishes.
    - turn_end: waits for turn end but ignores possible revisions.
    - repair_gate: after turn end, holds if V3 detects a revision;
      otherwise commits the *original* action (cannot resolve new intent).
    - confirmation_gate: always holds pending confirmation, which this
      experiment never provides (a deliberately zero-utility baseline).
    - oracle_final: unattainable best-case comparator that uses the gold
      final action, not a model-generated revision.
    """
    if policy not in POLICIES:
        raise ValueError(f"Unknown policy: {policy}")
    detected = bool(detector(case.transcript)) if policy == "repair_gate" else None
    if policy == "immediate":
        return Decision(case.case_id, policy, case.initial_action, "initial", 0, detected, case.revised, case.final_action)
    if policy == "turn_end":
        return Decision(case.case_id, policy, case.initial_action, "turn_end", TURN_END_MS, detected, case.revised, case.final_action)
    if policy == "repair_gate":
        if detected:
            return Decision(case.case_id, policy, None, "held_after_turn_end", None, True, case.revised, case.final_action)
        return Decision(case.case_id, policy, case.initial_action, "turn_end", TURN_END_MS, False, case.revised, case.final_action)
    if policy == "confirmation_gate":
        return Decision(case.case_id, policy, None, "awaiting_confirmation", None, detected, case.revised, case.final_action)
    return Decision(case.case_id, policy, case.final_action, "turn_end_oracle", TURN_END_MS, detected, case.revised, case.final_action)


def summarize(decisions: list[Decision]) -> dict[str, int | float | str]:
    """Count outcomes per policy, with every rate denominator explicit."""
    if not decisions or len({d.policy for d in decisions}) != 1:
        raise ValueError("Pass at least one decision for exactly one policy")
    n = len(decisions)
    executed = sum(not d.held for d in decisions)
    held = n - executed
    wrong = sum(d.wrong_action for d in decisions)
    premature = sum(d.premature for d in decisions)
    false_holds = sum(d.held and not d.gold_revised for d in decisions)
    missed_revisions = sum(d.gold_revised and d.wrong_action for d in decisions)
    return {
        "policy": decisions[0].policy, "n": n,
        "executed": executed, "held": held,
        "wrong_actions": wrong, "premature_actions": premature,
        "false_holds": false_holds, "missed_revisions": missed_revisions,
        "action_coverage": executed / n,
        "wrong_action_rate_all_cases": wrong / n,
        "wrong_action_rate_executed": wrong / executed if executed else 0.0,
        "premature_action_rate_all_cases": premature / n,
        "false_hold_rate_all_cases": false_holds / n,
    }


def decision_to_row(d: Decision) -> dict[str, str | int | bool]:
    """Flatten a simulated decision for a CSV report."""
    return {
        "case_id": d.case_id, "policy": d.policy, "phase": d.phase,
        "time_ms": "" if d.t_ms is None else d.t_ms,
        "action": d.action or "", "final_action_gold": d.final_action,
        "gold_revised": int(d.gold_revised),
        "v3_detected_revision": "" if d.detected_revision is None else int(d.detected_revision),
        "held": int(d.held), "wrong_action": int(d.wrong_action), "premature": int(d.premature),
    }
