import time

import pytest
from django.conf import settings
from django.core.management import call_command
from django.urls import reverse

from passages import badges, services
from passages.models import Badge
from school.models import Eleve

MDP = "Demo-Passage-2026"


@pytest.fixture
def awa(db):
    call_command("seed_demo")
    eleve = Eleve.objects.get(nom="Awa Ndongo")
    return eleve, eleve.badges.get(etat="actif")


def connecte(client, username):
    client.post(reverse("connexion"), {"username": username, "password": MDP})


def test_le_code_ne_contient_aucune_donnee_nominative(awa):
    _, badge = awa
    code = badges.generer_code(badge)
    assert "Awa" not in code and "Ndongo" not in code
    assert code.split(".")[0] == str(badge.uid)


def test_code_valide_au_moment_de_sa_generation(awa):
    _, badge = awa
    t = time.time()
    resultat = badges.verifier_code(badges.generer_code(badge, t), t)
    assert resultat.ok and resultat.badge == badge


def test_le_code_change_a_chaque_pas(awa):
    _, badge = awa
    t = time.time()
    assert badges.generer_code(badge, t) != badges.generer_code(
        badge, t + settings.BADGE_PAS_SECONDES
    )


def test_code_photographie_refuse_plus_tard(awa):
    _, badge = awa
    t = time.time()
    code = badges.generer_code(badge, t)
    resultat = badges.verifier_code(code, t + 600)
    assert not resultat.ok and resultat.raison == "expire"


def test_signature_alteree_refusee(awa):
    _, badge = awa
    t = time.time()
    uid, pas, signature = badges.generer_code(badge, t).split(".")
    resultat = badges.verifier_code(f"{uid}.{pas}.{'0' * len(signature)}", t)
    assert resultat.raison == "invalide"


def test_signature_d_un_autre_badge_refusee(awa):
    _, badge = awa
    autre = Badge.objects.exclude(pk=badge.pk).first()
    t = time.time()
    _, pas, signature = badges.generer_code(autre, t).split(".")
    assert not badges.verifier_code(f"{badge.uid}.{pas}.{signature}", t).ok


@pytest.mark.parametrize("code", ["", "n'importe quoi", "a.b.c", "é.1.é"])
def test_codes_mal_formes_refuses(awa, code):
    assert badges.verifier_code(code, time.time()).raison == "invalide"


def test_badge_suspendu_refuse(awa):
    _, badge = awa
    services.changer_etat(badge, "suspendu")
    t = time.time()
    assert badges.verifier_code(badges.generer_code(badge, t), t).raison == "badge_inactif"


def test_reemission_invalide_immediatement_l_ancien_badge(awa):
    eleve, ancien = awa
    t = time.time()
    ancien_code = badges.generer_code(ancien, t)
    nouveau = services.emettre_badge(eleve)
    assert badges.verifier_code(ancien_code, t).raison == "badge_inactif"
    assert badges.verifier_code(badges.generer_code(nouveau, t), t).ok
    ancien.refresh_from_db()
    assert ancien.etat == "revoque"
    assert nouveau.remplace == ancien
    assert eleve.badges.filter(etat="actif").count() == 1


def test_badge_revoque_ne_peut_pas_etre_reactive(awa):
    _, badge = awa
    services.changer_etat(badge, "revoque")
    with pytest.raises(services.TransitionInterdite):
        services.changer_etat(badge, "actif")


def test_parent_obtient_le_code_de_son_enfant(client, awa):
    eleve, _ = awa
    connecte(client, "parent1")
    reponse = client.get(reverse("parent_badge_code", args=[eleve.id]))
    assert reponse.status_code == 200
    assert "no-store" in reponse["Cache-Control"]
    assert badges.verifier_code(reponse.json()["code"], time.time()).ok


def test_parent_ne_peut_pas_obtenir_le_code_d_un_autre_enfant(client, awa):
    connecte(client, "parent1")
    autre = Eleve.objects.get(nom="Carine Etoga")  # rattachée à parent2
    assert client.get(reverse("parent_badge_code", args=[autre.id])).status_code == 404


def test_seul_le_responsable_emet_un_badge(client, awa):
    eleve, _ = awa
    url = reverse("responsable_emettre_badge", args=[eleve.id])
    for utilisateur in ("agent1", "parent1"):
        client.logout()
        connecte(client, utilisateur)
        assert client.post(url).status_code == 403
    client.logout()
    connecte(client, "responsable1")
    assert client.post(url).status_code == 302
    assert eleve.badges.count() == 2