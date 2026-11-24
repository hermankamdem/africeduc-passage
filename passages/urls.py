from django.urls import path

from . import views

urlpatterns = [
    path("parent/enfants/", views.parent_enfants, name="parent_enfants"),
    path("parent/enfants/<int:eleve_id>/", views.parent_enfant_detail, name="parent_enfant_detail"),
    path("responsable/eleves/", views.responsable_eleves, name="responsable_eleves"),
    path("responsable/anomalies/", views.responsable_anomalies, name="responsable_anomalies"),
    path("agent/scan/", views.agent_scan, name="agent_scan"),
]