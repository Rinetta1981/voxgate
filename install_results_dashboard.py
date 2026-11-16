"""Add one idempotent results route to an existing VOXGATE Django URL file.

Makes a local backup and preserves existing routes. Does not edit settings.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
URLS = ROOT / "config" / "urls.py"
MARKER = "# VOXGATE_READONLY_RESULTS_ROUTE"
APPEND = '''\n\n# VOXGATE_READONLY_RESULTS_ROUTE\nfrom core.results_dashboard_views import results_dashboard\nurlpatterns += [path("results/", results_dashboard, name="results_dashboard")]\n'''


def install(path=URLS):
    path = Path(path)
    original = path.read_text(encoding="utf-8")
    if MARKER in original:
        return "Results route already installed; no changes needed."
    if 'urlpatterns' not in original or 'from django.urls import path' not in original:
        raise ValueError("Unexpected URL configuration; cannot safely add results route")
    if 'path("results/"' in original or "path('results/'" in original:
        raise ValueError("A results route already exists; no changes made")
    backup = path.with_name("urls.before_results_dashboard.py")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
    path.write_text(original.rstrip() + APPEND, encoding="utf-8")
    return f"Results route installed. Backup: {backup}"


if __name__ == "__main__":
    try:
        print(install())
    except (OSError, ValueError) as exc:
        print(f"Installation stopped: {exc}", file=sys.stderr)
        raise SystemExit(2)
