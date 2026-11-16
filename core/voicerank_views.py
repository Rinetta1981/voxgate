"""Local-only, session-based, blinded VoiceRank perception pilot.

No model inference or access to actual actions. Ratings live only in a Django
browser session until voluntarily exported to CSV by the researcher.
"""
from __future__ import annotations

import csv
import io
import secrets
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from .voicerank import VOICE_DIR, EXPORT_FIELDS, export_rows, validate_manifest, validate_ratings

ORDER_KEY = "voicerank_trial_order_v1"
RATINGS_KEY = "voicerank_ratings_v1"


def _local_only() -> None:
    if not settings.DEBUG:
        raise Http404("The perception pilot is disabled outside local development")


def _manifest():
    _local_only()
    try:
        return validate_manifest(VOICE_DIR)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return exc


def _session_data(request, records):
    clip_ids = [str(row["clip_id"]) for row in records]
    order = request.session.get(ORDER_KEY)
    if (not isinstance(order, list) or len(order) != len(clip_ids)
            or set(order) != set(clip_ids)):
        order = secrets.SystemRandom().sample(clip_ids, len(clip_ids))
        request.session[ORDER_KEY] = order
        request.session[RATINGS_KEY] = {}
    ratings = request.session.get(RATINGS_KEY, {})
    if not isinstance(ratings, dict) or not set(ratings).issubset(set(clip_ids)):
        ratings = {}
        request.session[RATINGS_KEY] = ratings
    return order, ratings


@require_http_methods(["GET", "POST"])
def voicerank_lab(request):
    records = _manifest()
    if isinstance(records, Exception):
        return render(request, "core/voicerank_lab.html", {
            "ready": False, "error": str(records),
        })
    order, ratings = _session_data(request, records)
    clip_map = {str(row["clip_id"]): row for row in records}
    pending = next((clip_id for clip_id in order if clip_id not in ratings), None)

    if request.method == "POST":
        command = request.POST.get("command", "")
        if command == "reset":
            request.session.pop(ORDER_KEY, None)
            request.session.pop(RATINGS_KEY, None)
            return redirect(reverse("voicerank_lab"))
        if command == "rate" and pending is not None and request.POST.get("clip_id") == pending:
            try:
                scores = validate_ratings({key: request.POST.get(key) for key in ("authority", "clarity", "urgency")})
            except ValueError:
                # Do not record invalid scores or advance to another clip.
                return render(request, "core/voicerank_lab.html", {
                    "ready": True, "error": "Please select a number from 1 to 5 for every question.",
                    "current": pending, "progress": len(ratings), "total": len(order), "complete": False,
                }, status=400)
            new_ratings = dict(ratings)
            new_ratings[pending] = scores
            request.session[RATINGS_KEY] = new_ratings
            return redirect(reverse("voicerank_lab"))
        return HttpResponse("Invalid or repeated rating; no data recorded.", status=400)

    if request.GET.get("export") == "csv":
        rows = export_rows(records, order, ratings)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="voicerank_pilot.csv"'
        response["Cache-Control"] = "no-store"
        return response
    return render(request, "core/voicerank_lab.html", {
        "ready": True, "current": pending, "progress": len(ratings),
        "total": len(order), "complete": pending is None,
    })


@require_GET
def voicerank_audio(request, clip_id: str):
    records = _manifest()
    if isinstance(records, Exception):
        raise Http404("VoiceRank stimuli unavailable")
    item = next((entry for entry in records if entry["clip_id"] == clip_id), None)
    if item is None:
        raise Http404("Unknown audio clip")
    filename = str(item["file_name"])
    # The validated manifest contains only generated opaque audio basenames.
    path = Path(VOICE_DIR) / filename
    try:
        response = FileResponse(path.open("rb"), content_type="audio/wav", as_attachment=False)
    except OSError as exc:
        raise Http404("Audio file unavailable") from exc
    response["Cache-Control"] = "no-store"
    return response
