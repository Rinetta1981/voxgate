"""Local-only, GET-only research audit dashboard. Never executes actions."""
from pathlib import Path

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .results_dashboard import AuditReadError, load_dashboard

AUDIT_DIR = Path.home() / "Desktop" / "voxgate-spoken-action-audit"


@require_GET
def results_dashboard(request):
    # Unlike an auth system, this guard is intentionally only for local research.
    if not settings.DEBUG or request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}:
        raise Http404("Local development dashboard only")
    try:
        data = load_dashboard(AUDIT_DIR)
        return render(request, "core/results_dashboard.html", {"ready": True, **data})
    except AuditReadError as error:
        return render(request, "core/results_dashboard.html", {"ready": False, "message": str(error)})
