import time as horloge
import uuid
from datetime import date, datetime, time
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.utils import timezone

from passages import anomalies, badges, sync
from passages.models import Anomalie, Badge, Passage
from school.models import (
    Eleve, Etablissement, ExceptionJour, Fenetre, Itineraire, PointControle,
)

LUNDI = date(2026, 11, 23)
SAMEDI = date(2026, 11, 28)
T = Anomalie.Type


def instant(jour, h, m, s=0):
    return timezone.make_aware(datetime.combine(jour, time(h, m, s)))


@pytest.fixture
def ecole(db, settings):
    settings.ABSENCE_DELAI_GRACE_S = 0
    etab = Etablissement.objects.create(nom="Etab")
    entree = PointControle.objects.create(etablissement=etab, libelle="Entrée", type="portail")
    sortie = PointControle.objects.create(etablissement=etab, libelle="Sortie", type="portail")
    bus = PointControle.objects.create(etablissement=etab, libelle="Bus", type="autobus")
    itineraire = Itineraire.objects.create(etablissement=etab, nom="Journée")
    f_entree = Fenetre.objects.create(
        itineraire=itineraire, point=entree, ordre=1,
        heure_debut=time(7, 0), heure_fin=time(7, 45), jours="1,2,3,4,5",
    )
    f_sortie = Fenetre.objects.create(
        itineraire=itineraire, point=sortie, ordre=2,
        heure_debut=time(15, 30), heure_fin=time(16, 15), jours="1,2,3,4,5",
    )
    eleve = Eleve.objects.create(
        nom="E1", classe="6e A", etablissement=etab, itineraire=itineraire
    )
    badge = Badge.objects.create(eleve=eleve)
    return SimpleNamespace(
        etab=etab, entree=entree, sortie=sortie, bus=bus, eleve=eleve, badge=badge,
        f_entree=f_entree, f_sortie=f_sortie,
    )


def faire_passage(e, point, quand, etat=Passage.EtatSync.VALIDE, motif=""):
    return Passage.objects.create(
        badge=e.badge, eleve=e.eleve, point=point, heure_locale=quand, heure_corrigee=quand,
        appareil="tab-test", evenement_local=uuid.uuid4(), etat_sync=etat, motif_rejet=motif,
    )


def types():
    return set(Anomalie.objects.values_list("type", flat=True))


# --- Anomalies liées à un scan ---

def test_passage_dans_la_fenetre_ne_cree_aucune_anomalie(ecole):
    anomalies.evaluer_passage(faire_passage(ecole, ecole.entree, instant(LUNDI, 7, 10)))
    assert Anomalie.objects.count() == 0


def test_passage_hors_fenetre(ecole):
    anomalies.evaluer_passage(faire_passage(ecole, ecole.entree, instant(LUNDI, 9, 0)))
    assert types() == {T.HORS_FENETRE}


def test_passage_un_jour_non_applicable_est_hors_fenetre(ecole):
    anomalies.evaluer_passage(faire_passage(ecole, ecole.entree, instant(SAMEDI, 7, 10)))
    assert types() == {T.HORS_FENETRE}


def test_point_absent_de_l_itineraire(ecole):
    anomalies.evaluer_passage(faire_passage(ecole, ecole.bus, instant(LUNDI, 7, 10)))
    assert types() == {T.HORS_ITINERAIRE}


def test_double_scan_sous_60_secondes(ecole):
    p1 = faire_passage(ecole, ecole.entree, instant(LUNDI, 7, 10, 0))
    p2 = faire_passage(ecole, ecole.entree, instant(LUNDI, 7, 10, 30))
    anomalies.evaluer_passage(p1)
    anomalies.evaluer_passage(p2)
    assert Anomalie.objects.get(type=T.DOUBLE_SCAN).passage == p2  # le deuxième scan


def test_deux_scans_espaces_de_70_secondes_ne_sont_pas_un_double_scan(ecole):
    p1 = faire_passage(ecole, ecole.entree, instant(LUNDI, 7, 10, 0))
    p2 = faire_passage(ecole, ecole.entree, instant(LUNDI, 7, 11, 10))
    anomalies.evaluer_passage(p1)
    anomalies.evaluer_passage(p2)
    assert Anomalie.objects.filter(type=T.DOUBLE_SCAN).count() == 0


def test_double_scan_detecte_meme_si_les_lots_arrivent_dans_le_desordre(ecole):
    p1 = faire_passage(ecole, ecole.entree, instant(LUNDI, 7, 10, 0))
    p2 = faire_passage(ecole, ecole.entree, instant(LUNDI, 7, 10, 30))
    anomalies.evaluer_passage(p2)  # le plus récent est évalué en premier
    anomalies.evaluer_passage(p1)
    assert Anomalie.objects.filter(type=T.DOUBLE_SCAN).count() == 1
    assert Anomalie.objects.get(type=T.DOUBLE_SCAN).passage == p2


def test_badge_inactif_est_signale_meme_un_jour_d_exception(ecole):
    ExceptionJour.objects.create(etablissement=ecole.etab, date=LUNDI, type="ferie")
    p = faire_passage(
        ecole, ecole.entree, instant(LUNDI, 7, 10),
        etat=Passage.EtatSync.REJETE, motif="badge_inactif",
    )
    anomalies.evaluer_passage(p)
    assert types() == {T.BADGE_INACTIF}


def test_passage_rejete_pour_un_autre_motif_ne_cree_pas_d_anomalie(ecole):
    p = faire_passage(
        ecole, ecole.entree, instant(LUNDI, 7, 10),
        etat=Passage.EtatSync.REJETE, motif="expire",
    )
    anomalies.evaluer_passage(p)
    assert Anomalie.objects.count() == 0


def test_jour_ferie_suspend_la_detection(ecole):
    ExceptionJour.objects.create(etablissement=ecole.etab, date=LUNDI, type="ferie")
    anomalies.evaluer_passage(faire_passage(ecole, ecole.entree, instant(LUNDI, 9, 0)))
    assert Anomalie.objects.count() == 0


# --- Détection d'absence ---

def test_absence_detectee_a_la_cloture_de_la_fenetre(ecole):
    assert anomalies.detecter_absences(instant(LUNDI, 7, 44)) == 0  # fenêtre encore ouverte
    assert anomalies.detecter_absences(instant(LUNDI, 7, 46)) == 1
    a = Anomalie.objects.get()
    assert (a.type, a.eleve, a.fenetre, a.date) == (T.ABSENCE, ecole.eleve, ecole.f_entree, LUNDI)


def test_la_detection_d_absence_est_rejouable_sans_doublon(ecole):
    for _ in range(3):
        anomalies.detecter_absences(instant(LUNDI, 7, 46))
    assert Anomalie.objects.filter(type=T.ABSENCE).count() == 1


def test_pas_d_absence_si_le_passage_a_eu_lieu_dans_la_fenetre(ecole):
    faire_passage(ecole, ecole.entree, instant(LUNDI, 7, 10))
    assert anomalies.detecter_absences(instant(LUNDI, 7, 46)) == 0


def test_un_scan_hors_fenetre_ne_comble_pas_l_absence(ecole):
    faire_passage(ecole, ecole.entree, instant(LUNDI, 7, 50))
    assert anomalies.detecter_absences(instant(LUNDI, 8, 0)) == 1


def test_pas_d_absence_avec_une_exception_de_l_eleve(ecole):
    ExceptionJour.objects.create(
        eleve=ecole.eleve, etablissement=ecole.etab, date=LUNDI, type="absence"
    )
    assert anomalies.detecter_absences(instant(LUNDI, 7, 46)) == 0


def test_pas_d_absence_un_jour_ferie_pour_l_etablissement(ecole):
    ExceptionJour.objects.create(etablissement=ecole.etab, date=LUNDI, type="ferie")
    assert anomalies.detecter_absences(instant(LUNDI, 7, 46)) == 0


def test_pas_d_absence_un_jour_non_applicable(ecole):
    assert anomalies.detecter_absences(instant(SAMEDI, 17, 0)) == 0


def test_pas_d_absence_pour_un_eleve_inactif(ecole):
    ecole.eleve.etat = "inactif"
    ecole.eleve.save()
    assert anomalies.detecter_absences(instant(LUNDI, 7, 46)) == 0


def test_delai_de_grace_avant_de_declarer_l_absence(ecole, settings):
    settings.ABSENCE_DELAI_GRACE_S = 600
    assert anomalies.detecter_absences(instant(LUNDI, 7, 50)) == 0
    assert anomalies.detecter_absences(instant(LUNDI, 7, 56)) == 1


def test_la_commande_s_execute_sans_intervention(ecole):
    call_command("detecter_absences")


# --- Branchement sur la synchronisation ---

def lot_pour(ecole, point, t):
    return {
        "appareil": "tab-test",
        "appareil_envoye_ms": int(t * 1000),
        "scans": [
            {
                "evenement_local": str(uuid.uuid4()),
                "code": badges.generer_code(ecole.badge, t),
                "point_id": point.id,
                "heure_locale_ms": int(t * 1000),
            }
        ],
    }


def test_un_scan_synchronise_declenche_la_detection_une_seule_fois(ecole):
    donnees = lot_pour(ecole, ecole.bus, horloge.time())
    sync.traiter_lot(donnees)
    sync.traiter_lot(donnees)  # lot renvoyé
    assert Passage.objects.count() == 1
    assert Anomalie.objects.filter(type=T.HORS_ITINERAIRE).count() == 1


def test_un_defaut_de_detection_ne_fait_pas_perdre_le_passage(ecole, monkeypatch):
    def panne(passage):
        raise RuntimeError("panne")

    monkeypatch.setattr(anomalies, "evaluer_passage", panne)
    resultats = sync.traiter_lot(lot_pour(ecole, ecole.entree, horloge.time()))
    assert resultats[0]["statut"] == "accepte"
    assert Passage.objects.count() == 1