"""Session-only, voluntary local VoiceRank expanded study."""
from __future__ import annotations

import csv
import io
import secrets

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .voicerank import validate_manifest, validate_ratings, VOICE_DIR
from .voicerank_study import (
    EXPORT_FIELDS_V2, counterbalanced_order, export_study_rows,
)

KEY = "vr_study_v2"


def _manifest():
    if not settings.DEBUG:
        raise Http404("VoiceRank is disabled outside local development")
    try:
        return validate_manifest(VOICE_DIR)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return exc


def _context(state: dict | None, records: list | Exception, error: str = "") -> dict:
    if isinstance(records, Exception):
        return {"ready": False, "error": str(records)}
    if not state:
        return {"ready": True, "started": False, "error": error}
    order = state["order"]
    ratings = state["ratings"]
    current = next((clip for clip in order if clip not in ratings), None)
    return {
        "ready": True, "started": True, "error": error,
        "current": current, "progress": len(ratings), "total": len(order),
        "complete": current is None, "participant_id": state["participant_id"],
    }


@require_http_methods(["GET", "POST"])
def voicerank_study(request):
    records = _manifest()
    if isinstance(records, Exception):
        return render(request, "core/voicerank_study.html", _context(None, records))
    state = request.session.get(KEY)
    if state is not None:
        # Do not trust a forged/stale session to select arbitrary clips or export ratings.
        try:
            required = {"participant_id", "assignment_id", "order", "ratings", "consented"}
            if not isinstance(state, dict) or not required.issubset(state) or state["consented"] is not True:
                raise ValueError("Invalid local study session")
            if state["order"] != counterbalanced_order(records, state["assignment_id"]):
                raise ValueError("Invalid stored study assignment")
            if not isinstance(state["ratings"], dict) or not set(state["ratings"]).issubset(set(state["order"])):
                raise ValueError("Invalid stored study ratings")
        except (TypeError, KeyError, ValueError):
            return HttpResponse("Study session invalid; reset your local browser study data before continuing.", status=409)

    if request.method == "POST":
        command = request.POST.get("command", "")
        if command == "reset":
            request.session.pop(KEY, None)
            return redirect(reverse("voicerank_study"))
        if command == "start" and state is None:
            if request.POST.get("consent") != "yes":
                return render(request, "core/voicerank_study.html",
                              _context(None, records, "Please read the study information and choose whether to participate."),
                              status=400)
            assignment = secrets.randbelow(8)
            new_state = {
                "participant_id": "vr2-" + secrets.token_hex(10),
                "assignment_id": assignment,
                "order": counterbalanced_order(records, assignment),
                "ratings": {}, "consented": True,
            }
            request.session[KEY] = new_state
            return redirect(reverse("voicerank_study"))
        if command == "rate" and state is not None:
            pending = next((clip for clip in state["order"] if clip not in state["ratings"]), None)
            if pending is None or request.POST.get("clip_id") != pending:
                return HttpResponse("Invalid or repeated rating; no data recorded.", status=400)
            try:
                scores = validate_ratings({k: request.POST.get(k) for k in ("authority", "clarity", "urgency")})
            except ValueError:
                return render(request, "core/voicerank_study.html",
                              _context(state, records, "Rate all three dimensions from 1 to 5."), status=400)
            new_state = {**state, "ratings": {**state["ratings"], pending: scores}}
            request.session[KEY] = new_state
            return redirect(reverse("voicerank_study"))
        return HttpResponse("Invalid study command", status=400)

    if request.GET.get("export") == "csv":
        if not state:
            return HttpResponse("You have not begun this study", status=400)
        try:
            rows = export_study_rows(records, state["order"], state["ratings"],
                                     state["participant_id"], state["assignment_id"])
        except ValueError:
            return HttpResponse("Export is available only after eight valid ratings", status=409)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS_V2)
        writer.writeheader()
        writer.writerows(rows)
        result = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
        result["Content-Disposition"] = f'attachment; filename="voicerank_study_{state["participant_id"]}.csv"'
        result["Cache-Control"] = "no-store"
        return result
    return render(request, "core/voicerank_study.html", _context(state, records))
