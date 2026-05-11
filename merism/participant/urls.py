"""``/i/<slug>/`` URL configuration."""
from __future__ import annotations

from django.urls import path

from merism.participant import views

urlpatterns = [
    path("<slug:slug>/", views.resolve_link, name="participant-resolve"),
    path("<slug:slug>/consent/", views.post_consent, name="participant-consent"),
    path("<slug:slug>/screener/", views.screener, name="participant-screener"),
    path("<slug:slug>/start/", views.start_session, name="participant-start"),
]
