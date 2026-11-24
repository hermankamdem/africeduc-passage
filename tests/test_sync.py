import json
import time
import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from passages import badges, sync
from passages.models import Passage
from school.models import Eleve, Etablissement, PointControle

MDP = "Demo-Passage-2026"
APPAREIL = "tab-test"


@pytest.fixture
def monde(db):
    call_command("seed_demo")
    badge = Eleve.objects.get(nom="Awa Ndongo").badges.get(etat="actif")
    point = PointControle.objects.get(libelle="Portail d'entrée")
    return badge, point


def scan(badge, point, instant_s, decalage_s=0):
    """Scan fait à `instant_s` sur un appareil dont l'horloge a `decalage_s` d'écart."""
    return {
        "evenement_local": str(uuid.uuid4()),
        "code": badges.generer_code(badge, instant_s),
        "point_id": point.id,
        "heure_locale_ms": int((instant_s + decalage_s) * 1000),
    }


def lot(scans, instant_s, decalage_s=0):
    return {
        "appareil": APPAREIL,
        "appareil_envoye_ms": int((instant_s + decalage_s) * 1000),
        "scans": scans,
    }


def passages():
    return Passage.objects.filter(appareil=APPAREIL)


def test_vingt_scans_donnent_vingt_passages(monde):
    badge, point = monde
    t = time.time()
    resultats = sync.traiter_lot(lot([scan(badge, point, t) for _ in range(20)], t))
    assert [r["statut"] for r in resultats] == ["accepte"] * 20
    assert set(resultats[0]) == {"evenement_local", "statut"}  # aucun motif révélé à l'agent
    assert passages().count() == 20


def test_renvoyer_le_meme_lot_ne_cree_pas_de_doublon(monde):
    badge, point = monde
    t = time.time()
    donnees = lot([scan(badge, point, t) for _ in range(20)], t)
    sync.traiter_lot(donnees)
    sync.traiter_lot(donnees)
    sync.traiter_lot(donnees)
    assert passages().count() == 20


def test_synchronisation_interrompue_puis_relancee(monde):
    badge, point = monde
    t = time.time()
    scans = [scan(badge, point, t) for _ in range(20)]
    sync.traiter_lot(lot(scans[:7], t))      # le serveur traite 7 scans, la réponse est perdue
    sync.traiter_lot(lot(scans, t))          # la tablette renvoie tout
    assert passages().count() == 20


def test_horloge_en_avance_de_deux_heures_est_corrigee(monde):
    badge, point = monde
    t = time.time()
    resultats = sync.traiter_lot(lot([scan(badge, point, t, 7200)], t, 7200))
    p = passages().get()
    assert resultats[0]["statut"] == "accepte"
    assert abs(p.ecart_horloge_s + 7200) <= 2                  # écart enregistré
    assert abs(p.heure_corrigee.timestamp() - t) <= 2          # heure ramenée à la réalité
    assert p.heure_locale.timestamp() == pytest.approx(t + 7200, abs=1)  # l'heure brute est conservée


def test_horloge_inexploitable_est_refusee(monde):
    badge, point = monde
    t = time.time()
    decalage = 3 * 86400
    resultats = sync.traiter_lot(lot([scan(badge, point, t, decalage)], t, decalage))
    assert resultats[0]["statut"] == "refuse"
    p = passages().get()
    assert p.etat_sync == "rejete" and p.motif_rejet == "horloge_inexploitable"


def test_code_photographie_puis_presente_plus_tard_est_refuse(monde):
    badge, point = monde
    t = time.time()
    s = scan(badge, point, t)
    s["code"] = badges.generer_code(badge, t - 600)  # code vu il y a 10 minutes
    resultats = sync.traiter_lot(lot([s], t))
    assert resultats[0]["statut"] == "refuse"
    assert passages().get().motif_rejet == "expire"


def test_code_falsifie_est_refuse_sans_rien_enregistrer(monde):
    badge, point = monde
    t = time.time()
    s = scan(badge, point, t)
    s["code"] = "n'importe.quoi"
    assert sync.traiter_lot(lot([s], t))[0]["statut"] == "refuse"
    assert passages().count() == 0


def test_point_d_un_autre_etablissement_est_refuse(monde):
    badge, _ = monde
    autre = Etablissement.objects.create(nom="Autre école")
    point = PointControle.objects.create(etablissement=autre, libelle="Portail", type="portail")
    t = time.time()
    assert sync.traiter_lot(lot([scan(badge, point, t)], t))[0]["statut"] == "refuse"
    assert passages().get().motif_rejet == "point_autre_etablissement"


def test_heure_future_est_refusee(monde):
    badge, point = monde
    t = time.time()
    resultats = sync.traiter_lot(lot([scan(badge, point, t + 600)], t))
    assert resultats[0]["statut"] == "refuse"
    assert passages().get().motif_rejet == "heure_future"


def test_scan_trop_ancien_est_refuse(monde):
    badge, point = monde
    t = time.time()
    resultats = sync.traiter_lot(lot([scan(badge, point, t - 8 * 86400)], t))
    assert resultats[0]["statut"] == "refuse"
    assert passages().get().motif_rejet == "trop_ancien"


UN_SCAN = {
    "evenement_local": str(uuid.uuid4()),
    "code": "x",
    "point_id": 1,
    "heure_locale_ms": 1_700_000_000_000,
}
BASE = {"appareil": APPAREIL, "appareil_envoye_ms": 1_700_000_000_000, "scans": [UN_SCAN]}


@pytest.mark.parametrize(
    "donnees",
    [
        "pas un objet",
        {**BASE, "appareil": "../etc"},
        {**BASE, "appareil_envoye_ms": "x"},
        {**BASE, "scans": []},
        {**BASE, "scans": [UN_SCAN] * 201},
        {**BASE, "scans": [{**UN_SCAN, "evenement_local": "pas-un-uuid"}]},
        {**BASE, "scans": [{**UN_SCAN, "point_id": True}]},
        {**BASE, "appareil_envoye_ms": 10**30},
    ],
)
def test_lots_invalides_refuses(donnees):
    with pytest.raises(sync.LotInvalide):
        sync.traiter_lot(donnees)


# --- Endpoint HTTP ---

def connecte(client, username):
    client.post(reverse("connexion"), {"username": username, "password": MDP})


def post_sync(client, donnees):
    return client.post(reverse("agent_sync"), json.dumps(donnees), content_type="application/json")


def test_agent_peut_synchroniser(client, monde):
    badge, point = monde
    connecte(client, "agent1")
    t = time.time()
    reponse = post_sync(client, lot([scan(badge, point, t)], t))
    assert reponse.status_code == 200
    assert reponse.json()["resultats"][0]["statut"] == "accepte"


@pytest.mark.parametrize("utilisateur", ["parent1", "responsable1"])
def test_seul_l_agent_peut_synchroniser(client, monde, utilisateur):
    connecte(client, utilisateur)
    assert post_sync(client, BASE).status_code == 403


def test_synchronisation_anonyme_redirigee(client, monde):
    assert post_sync(client, BASE).status_code == 302


def test_synchronisation_refuse_get(client, monde):
    connecte(client, "agent1")
    assert client.get(reverse("agent_sync")).status_code == 405


def test_json_invalide_donne_400(client, monde):
    connecte(client, "agent1")
    reponse = client.post(reverse("agent_sync"), "pas du json", content_type="application/json")
    assert reponse.status_code == 400


def test_la_synchronisation_exige_le_jeton_csrf(monde):
    c = Client(enforce_csrf_checks=True)
    c.force_login(get_user_model().objects.get(username="agent1"))
    reponse = c.post(reverse("agent_sync"), "{}", content_type="application/json")
    assert reponse.status_code == 403