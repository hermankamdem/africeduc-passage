from django.urls import path

from . import views

urlpatterns = [
    path("parent/enfants/", views.parent_enfants, name="parent_enfants"),
    path("parent/enfants/<int:eleve_id>/", views.parent_enfant_detail, name="parent_enfant_detail"),
    path("responsable/eleves/", views.responsable_eleves, name="responsable_eleves"),
    path("responsable/anomalies/", views.responsable_anomalies, name="responsable_anomalies"),
    path("agent/scan/", views.agent_scan, name="agent_scan"),
        path("parent/enfants/<int:eleve_id>/badge/", views.parent_badge, name="parent_badge"),
    path("parent/enfants/<int:eleve_id>/badge/code/", views.parent_badge_code, name="parent_badge_code"),
    path("responsable/eleves/<int:eleve_id>/badge/emettre/", views.responsable_emettre_badge, name="responsable_emettre_badge"),
    path("responsable/badges/<int:badge_id>/etat/", views.responsable_changer_etat_badge, name="responsable_changer_etat_badge"),
]