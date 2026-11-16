"""Research-only Django UI for reviewing saved symbolic action selections.

No new model calls, API calls, file writes, external tools or real actions.
Confirmation updates the current browser session only.
"""
from __future__ import annotations

from pathlib import Path

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .agent_simulation import load_scenarios
from .authorization_gate import POLICIES, apply_gate, read_saved_choices
from .live_agent import build_global_catalog
from .web_gate import confirm_pending, make_pending

ROOT = Path(__file__).resolve().parent.parent
REPORT = Path.home() / "Desktop" / "voxgate-balanced-reports" / "balanced_decisions.csv"
SCENARIOS = ROOT / "data" / "waitwise_agent_scenarios.csv"
SESSION_PENDING = "voxgate_web_gate_pending"
SESSION_HISTORY = "voxgate_web_gate_history"

POLICY_LABELS = {
    "full_text": "Ungated full text",
    "v3_gate": "WaitWise V3 gate",
    "disagreement_gate": "Partial vs. full disagreement gate",
    "combined_gate": "Combined gate",
}


def _remember(request, *, case_id: str, outcome: str, action: str) -> None:
    """Store a small local-session demonstration history, not a research dataset."""
    history = list(request.session.get(SESSION_HISTORY, []))
    history.append({"case_id": case_id, "outcome": outcome, "action": action})
    request.session[SESSION_HISTORY] = history[-20:]


def _case_url(case_id: str, policy: str) -> str:
    from urllib.parse import urlencode
    return reverse("gate_lab") + "?" + urlencode({"case": case_id, "policy": policy})


@require_http_methods(["GET", "POST"])
def gate_lab(request):
    try:
        scenarios = load_scenarios(SCENARIOS)
        saved = read_saved_choices(REPORT)
    except (ValueError, OSError) as exc:
        return render(request, "core/gate_lab.html", {
            "ready": False,
            "error": str(exc),
        })

    scenario_map = {scenario.case_id: scenario for scenario in scenarios}
    case_ids = sorted(set(saved) & set(scenario_map))
    if not case_ids:
        return render(request, "core/gate_lab.html", {
            "ready": False, "error": "No matching scenario IDs in the saved results."
        })
    catalog = build_global_catalog(scenarios)
    selected_id = request.GET.get("case") if request.method == "GET" else request.POST.get("case")
    policy = request.GET.get("policy") if request.method == "GET" else request.POST.get("policy")
    invalid_post_selection = (request.method == "POST" and
                              (selected_id not in case_ids or policy not in POLICIES))
    if selected_id not in case_ids:
        selected_id = case_ids[0]
    if policy not in POLICIES:
        policy = "combined_gate"
    if invalid_post_selection and request.POST.get("command") == "propose":
        messages.warning(request, "Invalid case or gate policy; no proposal created.")
        return redirect(_case_url(selected_id, policy))

    # POST-only commands are CSRF protected by Django's middleware.
    if request.method == "POST":
        command = request.POST.get("command", "")
        if command == "propose":
            decision = apply_gate(saved[selected_id], policy)
            # A held action is NEVER automatically released. The candidate is
            # shown solely for explicit human review, if the saved model made one.
            candidate = decision.action or saved[selected_id]["full_text"].action
            if candidate is None:
                messages.warning(request, "No valid action candidate exists for this case. The gate remains on HOLD.")
            else:
                try:
                    pending = make_pending(
                        case_id=selected_id, policy=policy,
                        transcript=scenario_map[selected_id].transcript,
                        action=candidate, allowed_actions=catalog,
                        reason=decision.reason, was_held=decision.held)
                    request.session[SESSION_PENDING] = pending
                    messages.info(request, "A symbolic proposal is ready for your review. Nothing has been executed.")
                except ValueError as exc:
                    messages.warning(request, f"Could not create proposal: {exc}")
        elif command in {"confirm", "reject"}:
            # Consume FIRST, whether the request is approved or not; this
            # prevents replay, including mismatched or expired confirmations.
            pending = request.session.pop(SESSION_PENDING, None)
            request.session.modified = True
            if not pending:
                messages.warning(request, "There is no pending proposal to resolve.")
            else:
                original_case = pending.get("case_id")
                original_policy = pending.get("policy")
                if original_case in case_ids and original_policy in POLICIES:
                    selected_id, policy = original_case, original_policy
                if command == "reject":
                    _remember(request, case_id=str(original_case), outcome="REJECTED", action=str(pending.get("action", "")))
                    messages.success(request, "Proposal rejected. No action occurred.")
                else:
                    try:
                        if original_case not in case_ids or original_policy not in POLICIES:
                            raise ValueError("Proposal no longer identifies a valid scenario or policy")
                        decision = apply_gate(saved[original_case], original_policy)
                        expected = decision.action or saved[original_case]["full_text"].action
                        approved = confirm_pending(
                            pending,
                            token=request.POST.get("token", ""),
                            action=request.POST.get("action", ""),
                            transcript=scenario_map[original_case].transcript,
                            expected_action=expected or "",
                        )
                    except (ValueError, TypeError, KeyError) as exc:
                        messages.error(request, f"Confirmation rejected: {exc}. Nothing was executed.")
                    else:
                        _remember(request, case_id=original_case, outcome="SYMBOLICALLY_APPROVED", action=approved)
                        messages.success(request, f"Symbolically approved: {approved}. No tool was executed.")
        else:
            messages.warning(request, "Unknown operation; no action taken.")
        return redirect(_case_url(selected_id, policy))

    selected = scenario_map[selected_id]
    decision = apply_gate(saved[selected_id], policy)
    candidate = decision.action or saved[selected_id]["full_text"].action
    pending = request.session.get(SESSION_PENDING)
    pending_case = scenario_map.get(pending.get("case_id")) if isinstance(pending, dict) else None
    return render(request, "core/gate_lab.html", {
        "ready": True,
        "cases": [scenario_map[case_id] for case_id in case_ids],
        "policies": [(key, POLICY_LABELS[key]) for key in POLICIES],
        "selected_id": selected_id,
        "selected_policy": policy,
        "selected": selected,
        "decision": decision,
        "candidate": candidate,
        "pending": pending,
        "pending_transcript": pending_case.transcript if pending_case else "",
        "history": list(reversed(request.session.get(SESSION_HISTORY, []))),
    })
