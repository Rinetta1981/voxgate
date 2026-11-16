"""Local VOXGATE research routes. No route performs a real-world action."""
from django.contrib import admin
from django.urls import path

from core.views import home
from core.web_views import gate_lab
from core.voicerank_views import voicerank_lab, voicerank_audio
from core.voicerank_study_views import voicerank_study
from core.results_dashboard_views import results_dashboard

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("lab/", gate_lab, name="gate_lab"),
    path("voice/", voicerank_lab, name="voicerank_lab"),
    path("voice/audio/<str:clip_id>/", voicerank_audio, name="voicerank_audio"),
    path("voice/study/", voicerank_study, name="voicerank_study"),
    # VOXGATE_READONLY_RESULTS_ROUTE: keep installer idempotent.
    path("results/", results_dashboard, name="results_dashboard"),
]
