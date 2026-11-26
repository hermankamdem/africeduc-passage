import json
import uuid
from datetime import datetime, time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from passages import ia
from passages import synthese as S
from passages.models import Anomalie, AppelIA, Badge, JournalAudit, Passage, Synthese
from school.models import Eleve, Etablissement, PointControle

MDP = "Demo-Passage-2026"
CLASSE = "6e A"
BON = json.dumps(
    {"texte": "En 6e A, 3 élèves sur 5 sont passés, 2 sont absents et 4 anomalies ont été relevées."}
)
INVENTE = json.dumps({"texte": "En 6e A, 3 élèves sur 5 sont passés et 9 anomalies ont été relevées."})


@pytest.fixture
def ecole(db, settings):
    settings.ANTHROPIC_API_KEY = "cle-de-test"
    settings.AI_PLAFOND_JOUR_FCFA = 1000.0
    etab = Etablissement.objects.create(nom="Etab")
    point = PointControle.objects.create(etablissement=etab, libelle="Entrée", type="portail")
    jour = timezone.localdate()
    eleves = [
        Eleve.objects.create(nom=f"Eleve{i}", classe=CLASSE, etablissement=etab) for i in range(1, 6)
    ]
    quand = timezone.make_aware(datetime.combine(jour, time(10, 0)))
    for e in eleves[:3]:
        badge = Badge.objects.create(eleve=e)
        for _ in range(2 if e == eleves[0] else 1):  # un élève passe deux fois : compté une fois
            Passage.objects.create(
                badge=badge, eleve=e, point=point, heure_locale=quand, heure_corrigee=quand,
                appareil="tab-test", evenement_local=uuid.uuid4(), etat_sync="valide",
            )
    Anomalie.objects.create(eleve=eleves[3], type="absence_passage", date=jour)
    Anomalie.objects.create(eleve=eleves[0], type="hors_fenetre", date=jour)
    Anomalie.objects.create(eleve=eleves[1], type="hors_fenetre", date=jour)
    Anomalie.objects.create(eleve=eleves[2], type="double_scan", date=jour)
    return SimpleNamespace(etab=etab, jour=jour)


class Faux:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []

    def completer(self, systeme, utilisateur, max_tokens):
        self.appels.append(utilisateur)
        r = self.reponses.pop(0) if len(self.reponses) > 1 else self.reponses[0]
        if isinstance(r, Exception):
            raise r
        return r, 120, 40


def brancher(monkeypatch, *reponses):
    faux = Faux(reponses)
    monkeypatch.setattr(ia, "get_client", lambda: faux)
    return faux


def generer(ecole):
    return S.generer_synthese(ecole.etab, CLASSE, ecole.jour)


# --- Les chiffres sont calculés par le code ---

def test_chiffres_calcules_depuis_la_base(ecole):
    c = S.calculer_chiffres(ecole.etab, CLASSE, ecole.jour)
    assert c["effectif"] == 5 and c["presents"] == 3 and c["absents"] == 2
    assert c["absence_passage"] == 1 and c["hors_fenetre"] == 2 and c["double_scan"] == 1
    assert c["point_hors_itineraire"] == 0 and c["badge_inactif"] == 0
    assert c["anomalies_total"] == 4


def nombres_sans_date_ni_classe(texte, ecole):
    reste = texte.replace(CLASSE, "").replace(ecole.jour.strftime("%d/%m/%Y"), "")
    return sorted(S.extraire_nombres(reste))


def test_les_chiffres_de_la_synthese_sont_ceux_de_la_base(ecole, settings):
    """Sans clé : le gabarit contient exactement les nombres calculés, aucun autre."""
    settings.ANTHROPIC_API_KEY = ""
    synthese = generer(ecole)
    assert nombres_sans_date_ni_classe(synthese.texte, ecole) == sorted([3, 5, 2, 1, 2, 1])


def test_un_texte_du_modele_reste_dans_les_chiffres_de_la_base(ecole, monkeypatch):
    brancher(monkeypatch, BON)
    synthese = generer(ecole)
    autorises = S.nombres_autorises(CLASSE, ecole.jour, S.calculer_chiffres(ecole.etab, CLASSE, ecole.jour))
    assert set(S.extraire_nombres(synthese.texte)) <= autorises


def test_le_modele_ne_recoit_que_des_chiffres_calcules(ecole, monkeypatch):
    faux = brancher(monkeypatch, BON)
    generer(ecole)
    envoye = json.loads(faux.appels[0])
    assert envoye["chiffres"] == S.calculer_chiffres(ecole.etab, CLASSE, ecole.jour)
    assert "Eleve" not in faux.appels[0]  # aucun nom d'élève ne part vers le service


# --- Sortie contrainte ---

def test_sortie_valide_acceptee_et_journalisee(ecole, monkeypatch):
    brancher(monkeypatch, BON)
    synthese = generer(ecole)
    assert synthese.origine == "modele" and synthese.chemin == "modele"
    appel = AppelIA.objects.get()
    assert appel.succes and appel.tokens_entree == 120 and appel.tokens_sortie == 40
    assert appel.cout_estime_fcfa > 0 and appel.modele


def test_json_entoure_de_balises_accepte(ecole):
    c = S.calculer_chiffres(ecole.etab, CLASSE, ecole.jour)
    assert S.valider_sortie("```json\n" + BON + "\n```", CLASSE, ecole.jour, c)


@pytest.mark.parametrize(
    "brut",
    [
        "pas du json",
        "",
        '{"texte": "court"}',
        json.dumps({"texte": "3 élèves sur 5 sont passés ici", "extra": 1}),
        '["a"]',
        '{"texte": 12}',
        INVENTE,
    ],
)
def test_sortie_non_conforme_refusee(ecole, brut):
    c = S.calculer_chiffres(ecole.etab, CLASSE, ecole.jour)
    with pytest.raises(S.SortieInvalide):
        S.valider_sortie(brut, CLASSE, ecole.jour, c)


def test_un_chiffre_invente_donne_une_seule_nouvelle_tentative_puis_le_gabarit(ecole, monkeypatch):
    faux = brancher(monkeypatch, INVENTE)
    synthese = generer(ecole)
    assert len(faux.appels) == 2  # un appel et une seule nouvelle tentative
    assert synthese.origine == "gabarit" and synthese.chemin == "gabarit_sortie_invalide"
    assert nombres_sans_date_ni_classe(synthese.texte, ecole) == sorted([3, 5, 2, 1, 2, 1])
    assert AppelIA.objects.count() == 2


def test_premiere_reponse_invalide_puis_valide(ecole, monkeypatch):
    faux = brancher(monkeypatch, "pas du json", BON)
    synthese = generer(ecole)
    assert len(faux.appels) == 2
    assert synthese.origine == "modele" and synthese.chemin == "modele_apres_nouvel_essai"


# --- Mode dégradé ---

def test_sans_cle_la_synthese_est_produite_sans_appel(ecole, settings, monkeypatch):
    settings.ANTHROPIC_API_KEY = ""

    def interdit():
        raise AssertionError("aucun appel sans clé")

    monkeypatch.setattr(ia, "get_client", interdit)
    synthese = generer(ecole)
    assert synthese.origine == "gabarit" and synthese.chemin == "gabarit_sans_cle"
    assert AppelIA.objects.count() == 0


def test_service_en_erreur_bascule_sur_le_gabarit(ecole, monkeypatch):
    brancher(monkeypatch, ia.ErreurIA("URLError"))
    synthese = generer(ecole)
    assert synthese.chemin == "gabarit_erreur_service" and synthese.origine == "gabarit"
    appel = AppelIA.objects.get()
    assert appel.succes is False and appel.cout_estime_fcfa == 0


# --- Coût plafonné et pas de double facturation ---

def test_plafond_a_zero_bloque_les_appels(ecole, settings, monkeypatch):
    settings.AI_PLAFOND_JOUR_FCFA = 0.0
    faux = brancher(monkeypatch, BON)
    synthese = generer(ecole)
    assert faux.appels == []
    assert synthese.chemin == "gabarit_plafond" and synthese.origine == "gabarit"


def test_plafond_atteint_apres_les_depenses_du_jour(ecole, monkeypatch):
    AppelIA.objects.create(modele="m", cout_estime_fcfa=Decimal("999.9999"))
    faux = brancher(monkeypatch, BON)
    assert generer(ecole).chemin == "gabarit_plafond"
    assert faux.appels == []


def test_deux_demandes_identiques_ne_sont_pas_facturees_deux_fois(ecole, monkeypatch):
    faux = brancher(monkeypatch, BON)
    premiere = generer(ecole)
    seconde = generer(ecole)
    assert len(faux.appels) == 1
    assert premiere.pk == seconde.pk
    assert Synthese.objects.count() == 1 and AppelIA.objects.count() == 1


# --- Écran du responsable ---

@pytest.fixture
def responsable(ecole):
    get_user_model().objects.create_user("resp", password=MDP, role="responsable")


def connecte(client, username):
    client.post(reverse("connexion"), {"username": username, "password": MDP})


def test_le_responsable_obtient_la_synthese_et_la_consultation_est_journalisee(client, responsable, ecole):
    connecte(client, "resp")
    r = client.post(reverse("responsable_synthese"), {"classe": CLASSE, "date": ecole.jour.isoformat()})
    assert r.status_code == 200
    assert r.context["synthese"].origine == "gabarit"
    assert JournalAudit.objects.filter(action="synthese_consultee").count() == 1


def test_la_synthese_reste_exacte_sans_cle(client, responsable, ecole, settings):
    settings.ANTHROPIC_API_KEY = ""
    connecte(client, "resp")
    r = client.post(reverse("responsable_synthese"), {"classe": CLASSE, "date": ecole.jour.isoformat()})
    assert r.status_code == 200
    assert nombres_sans_date_ni_classe(r.context["synthese"].texte, ecole) == sorted([3, 5, 2, 1, 2, 1])


@pytest.mark.parametrize("utilisateur", ["agent1", "parent1"])
def test_seul_le_responsable_voit_la_synthese(client, ecole, utilisateur):
    get_user_model().objects.create_user("agent1", password=MDP, role="agent")
    get_user_model().objects.create_user("parent1", password=MDP, role="parent")
    connecte(client, utilisateur)
    assert client.get(reverse("responsable_synthese")).status_code == 403


def test_entrees_invalides_refusees(client, responsable, ecole):
    connecte(client, "resp")
    url = reverse("responsable_synthese")
    assert client.post(url, {"classe": CLASSE, "date": "pas-une-date"}).status_code == 400
    assert client.post(url, {"classe": "classe-inconnue", "date": ecole.jour.isoformat()}).status_code == 400