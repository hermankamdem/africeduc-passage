import json

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.permissions import role_requis
from passages import badges, services, sync
from passages.models import Anomalie, Badge
from school.models import Eleve, PointControle


@role_requis("parent")
def parent_enfants(request):
    enfants = Eleve.objects.filter(parenteleve__parent=request.user).order_by("nom")
    return render(request, "passages/parent_enfants.html", {"enfants": enfants})


@role_requis("parent")
def parent_enfant_detail(request, eleve_id):
    # Cloisonnement : on cherche l'élève UNIQUEMENT parmi les enfants de ce parent.
    # Un identifiant étranger donne 404, sans révéler que l'élève existe.
    eleve = get_object_or_404(
        Eleve.objects.filter(parenteleve__parent=request.user), pk=eleve_id
    )
    passages = eleve.passages.select_related("point").order_by("-heure_serveur")[:50]
    anomalies = eleve.anomalies.order_by("-cree_le")[:50]
    return render(
        request,
        "passages/parent_enfant_detail.html",
        {"eleve": eleve, "passages": passages, "anomalies": anomalies},
    )


@role_requis("responsable")
def responsable_eleves(request):
    eleves = Eleve.objects.select_related("etablissement").order_by("classe", "nom")
    return render(request, "passages/responsable_eleves.html", {"eleves": eleves})


@role_requis("responsable")
def responsable_anomalies(request):
    anomalies = Anomalie.objects.select_related("eleve").order_by("-cree_le")[:100]
    return render(request, "passages/responsable_anomalies.html", {"anomalies": anomalies})


@role_requis("agent")
def agent_scan(request):
    return render(request, "passages/agent_scan.html")

@role_requis("responsable")
def responsable_eleves(request):
    eleves = (
        Eleve.objects.select_related("etablissement")
        .prefetch_related("badges")
        .order_by("classe", "nom")
    )
    return render(request, "passages/responsable_eleves.html", {"eleves": eleves})


def _enfant_du_parent(request, eleve_id):
    # Même cloisonnement que le détail : seuls les enfants du parent connecté existent.
    return get_object_or_404(Eleve.objects.filter(parenteleve__parent=request.user), pk=eleve_id)


@role_requis("parent")
def parent_badge(request, eleve_id):
    eleve = _enfant_du_parent(request, eleve_id)
    return render(request, "passages/parent_badge.html", {"eleve": eleve})


@role_requis("parent")
@never_cache
def parent_badge_code(request, eleve_id):
    eleve = _enfant_du_parent(request, eleve_id)
    badge = eleve.badges.filter(etat=Badge.Etat.ACTIF).first()
    if badge is None:
        return JsonResponse({"erreur": "Aucun badge actif."}, status=404)
    return JsonResponse(
        {"code": badges.generer_code(badge), "valide_secondes": badges.secondes_restantes()}
    )


@role_requis("responsable")
@require_POST
def responsable_emettre_badge(request, eleve_id):
    eleve = get_object_or_404(Eleve, pk=eleve_id)
    services.emettre_badge(eleve, request.user)
    return redirect("responsable_eleves")


@role_requis("responsable")
@require_POST
def responsable_changer_etat_badge(request, badge_id):
    badge = get_object_or_404(Badge, pk=badge_id)
    try:
        services.changer_etat(badge, request.POST.get("etat", ""), request.user)
    except services.TransitionInterdite:
        return HttpResponseBadRequest("Changement d'état interdit.")
    return redirect("responsable_eleves")
@role_requis("agent")
def agent_scan(request):
    points = PointControle.objects.select_related("etablissement").order_by(
        "etablissement__nom", "libelle"
    )
    return render(request, "passages/agent_scan.html", {"points": points})


@role_requis("agent")
@require_POST
def agent_sync(request):
    try:
        resultats = sync.traiter_lot(json.loads(request.body))
    except (ValueError, sync.LotInvalide):
        return JsonResponse({"erreur": "Lot invalide."}, status=400)
    return JsonResponse({"resultats": resultats})


def service_worker(request):
    reponse = render(request, "passages/sw.js", content_type="application/javascript")
    reponse["Cache-Control"] = "no-cache"
    return reponse