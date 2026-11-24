from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from . import throttle

MESSAGE_ERREUR = "Identifiant ou mot de passe incorrect."
MESSAGE_BLOQUE = "Trop de tentatives. Réessayez plus tard."

DESTINATIONS = {
    "parent": "parent_enfants",
    "responsable": "responsable_eleves",
    "agent": "agent_scan",
}


@require_http_methods(["GET", "POST"])
def connexion(request):
    erreur, statut = None, 200
    if request.method == "POST":
        identifiant = request.POST.get("username", "")[:150]
        mot_de_passe = request.POST.get("password", "")
        ip = request.META.get("REMOTE_ADDR", "")

        if throttle.est_bloque(identifiant, ip):
            erreur, statut = MESSAGE_BLOQUE, 429
        else:
            user = authenticate(request, username=identifiant, password=mot_de_passe)
            if user is not None and user.is_active:
                throttle.reinitialiser(identifiant, ip)
                login(request, user)
                return redirect("accueil")
            throttle.enregistrer_echec(identifiant, ip)
            erreur = MESSAGE_ERREUR  # identique que l'identifiant existe ou non
    return render(request, "accounts/connexion.html", {"erreur": erreur}, status=statut)


@require_POST
def deconnexion(request):
    logout(request)  # supprime la session côté serveur
    return redirect("connexion")


@login_required
def accueil(request):
    cible = DESTINATIONS.get(request.user.role)
    if cible is None:
        raise PermissionDenied
    return redirect(cible)