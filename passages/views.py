from django.shortcuts import get_object_or_404, render

from accounts.permissions import role_requis
from passages.models import Anomalie
from school.models import Eleve


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