"""Validated, read-only presentation of saved VOXGATE spoken-action audits.

This code does not import a model, execute tools, or infer authorization.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

SOURCES = ("reference", "slower", "faster")
POLICIES = ("model_only", "v4_review", "triage_review")
GROUPS = ("all", "revised", "not_revised")
REQUIRED_FIELDS = {"source", "policy", "group", "n", "proposed", "correct", "wrong", "held", "review_requests"}
MAX_BYTES = 2_000_000


class AuditReadError(ValueError):
    """An audit is missing, malformed, or inconsistent."""


def _read_small_file(path: Path) -> str:
    if path.is_symlink():
        raise AuditReadError(f"Symbolic links are not accepted: {path.name}")
    try:
        if path.stat().st_size > MAX_BYTES:
            raise AuditReadError(f"Audit file exceeds {MAX_BYTES} bytes: {path.name}")
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise AuditReadError(f"Missing {path.name}. Run python audit_spoken_action_results.py") from exc
    except (OSError, UnicodeError) as exc:
        raise AuditReadError(f"Cannot read {path.name}") from exc


def _int(row: dict, key: str) -> int:
    value = str(row.get(key, ""))
    if not value.isdecimal():
        raise AuditReadError(f"Invalid {key} count: {value!r}")
    return int(value)


def load_dashboard(directory: str | Path) -> dict:
    """Read the fixed audit files and independently check their accounting."""
    root = Path(directory)
    try:
        summary = json.loads(_read_small_file(root / "audit_summary.json"))
    except json.JSONDecodeError as exc:
        raise AuditReadError("Malformed audit_summary.json") from exc
    if not isinstance(summary, dict) or summary.get("n_cases") != 24 or summary.get("n_paired_comparisons") != 48:
        raise AuditReadError("Audit summary is not a complete 24-case, 48-pair run")
    changes = summary.get("changed_cases")
    if (not isinstance(changes, list) or not isinstance(summary.get("n_model_changes"), int)
            or len(changes) != summary["n_model_changes"] or len(changes) > 48):
        raise AuditReadError("Changed-case summary is inconsistent")
    clean_changes = []
    seen_changes = set()
    for change in changes:
        if not isinstance(change, dict):
            raise AuditReadError("Invalid changed-case entry")
        case_id, source, transition = (change.get("case_id"), change.get("source"), change.get("transition"))
        if not isinstance(case_id, str) or not case_id or source not in ("slower", "faster"):
            raise AuditReadError("Invalid changed-case identifier")
        if transition not in {"wrong_to_correct", "correct_to_wrong", "wrong_to_wrong", "correct_to_correct", "abstained_to_wrong", "abstained_to_correct", "correct_to_abstained", "wrong_to_abstained"}:
            raise AuditReadError("Unrecognized transition outcome")
        if (case_id, source) in seen_changes:
            raise AuditReadError("Repeated changed-case entry")
        seen_changes.add((case_id, source))
        clean_changes.append({"case": case_id, "source": source, "transition": transition.replace("_", " ")})

    import io
    handle = io.StringIO(_read_small_file(root / "policy_by_group.csv"))
    reader = csv.DictReader(handle)
    if not reader.fieldnames or not REQUIRED_FIELDS.issubset(reader.fieldnames):
        raise AuditReadError("Audit policy CSV is missing required columns")
    metrics = {}
    for row in reader:
        source, policy, group = row["source"], row["policy"], row["group"]
        key = (source, policy, group)
        if source not in SOURCES or policy not in POLICIES or group not in GROUPS or key in metrics:
            raise AuditReadError("Unexpected or repeated source/policy/group")
        n, proposed, correct, wrong, held, review = (_int(row, field) for field in ("n", "proposed", "correct", "wrong", "held", "review_requests"))
        if (n != (24 if group == "all" else 12) or proposed + held != n or correct + wrong != proposed
                or review > held or held > n):
            raise AuditReadError(f"Inconsistent policy accounting: {key}")
        metrics[key] = {
            "source": source, "policy": policy, "group": group,
            "n": n, "proposed": proposed, "correct": correct, "wrong": wrong, "held": held,
            "review": review, "wrong_percent": f"{100 * wrong / proposed:.1f}%" if proposed else "Undefined",
            "completion_percent": f"{100 * correct / n:.1f}%",
        }
    expected = {(s, p, g) for s in SOURCES for p in POLICIES for g in GROUPS}
    if set(metrics) != expected:
        raise AuditReadError(f"Missing policy combinations: {len(expected - set(metrics))}")
    for source in SOURCES:
        for policy in POLICIES:
            all_row = metrics[source, policy, "all"]
            a = metrics[source, policy, "revised"]
            b = metrics[source, policy, "not_revised"]
            for key in ("n", "proposed", "correct", "wrong", "held", "review"):
                if all_row[key] != a[key] + b[key]:
                    raise AuditReadError(f"Group totals disagree for {source}/{policy}: {key}")

    return {
        "summary": {"cases": 24, "comparisons": 48, "changes": len(clean_changes),
                    "improvements": sum(c["transition"] == "wrong to correct" for c in clean_changes),
                    "regressions": sum(c["transition"] == "correct to wrong" for c in clean_changes)},
        "overview": [metrics[s, p, "all"] for s in SOURCES for p in POLICIES],
        "breakdown": [metrics[s, p, g] for s in SOURCES for p in POLICIES for g in ("revised", "not_revised")],
        "changes": clean_changes,
    }
