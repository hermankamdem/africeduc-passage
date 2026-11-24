import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from school.models import Eleve, Etablissement, ParentEleve

MDP = "Demo-Passage-2026"


@pytest.fixture
def donnees(db):
    call_command("seed_demo")


def connecte(client, username, mdp=MDP):
    return client.post(reverse("connexion"), {"username": username, "password": mdp})


def test_message_identique_que_l_identifiant_existe_ou_non(client, donnees):
    r1 = connecte(client, "parent1", "mauvais-mot-de-passe")
    r2 = connecte(client, "inconnu", "mauvais-mot-de-passe")
    assert r1.status_code == r2.status_code == 200
    assert r1.context["erreur"] == r2.context["erreur"]


def test_blocage_apres_trop_d_echecs(client, donnees):
    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        connecte(client, "parent1", "faux-faux-faux")
    reponse = connecte(client, "parent1", MDP)  # même le bon mot de passe est refusé
    assert reponse.status_code == 429
    assert "_auth_user_id" not in client.session


def test_mot_de_passe_trop_court_refuse():
    with pytest.raises(ValidationError):
        validate_password("Ab1!xyz")  # 7 caractères


def test_deconnexion_effective(client, donnees):
    connecte(client, "parent1")
    assert client.get(reverse("parent_enfants")).status_code == 200
    ancien_cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
    client.post(reverse("deconnexion"))
    client.cookies[settings.SESSION_COOKIE_NAME] = ancien_cookie  # on rejoue l'ancienne session
    assert client.get(reverse("parent_enfants")).status_code == 302


@pytest.mark.parametrize(
    "username,vue,attendu",
    [
        ("agent1", "responsable_anomalies", 403),
        ("agent1", "responsable_eleves", 403),
        ("agent1", "parent_enfants", 403),
        ("parent1", "responsable_anomalies", 403),
        ("parent1", "agent_scan", 403),
        ("responsable1", "agent_scan", 403),
        ("agent1", "agent_scan", 200),
        ("responsable1", "responsable_anomalies", 200),
    ],
)
def test_controle_des_roles_cote_serveur(client, donnees, username, vue, attendu):
    connecte(client, username)
    assert client.get(reverse(vue)).status_code == attendu


def test_anonyme_redirige_vers_la_connexion(client, donnees):
    reponse = client.get(reverse("responsable_anomalies"))
    assert reponse.status_code == 302
    assert "/connexion/" in reponse["Location"]


def test_parent_ne_voit_pas_l_enfant_d_un_autre(client, donnees):
    connecte(client, "parent1")
    mon_enfant = Eleve.objects.get(nom="Awa Ndongo")
    enfant_d_un_autre = Eleve.objects.get(nom="Carine Etoga")  # rattachée à parent2
    assert client.get(reverse("parent_enfant_detail", args=[mon_enfant.id])).status_code == 200
    assert client.get(reverse("parent_enfant_detail", args=[enfant_d_un_autre.id])).status_code == 404
    assert "Carine" not in client.get(reverse("parent_enfants")).content.decode()


def test_texte_saisi_est_echappe(client, donnees):
    parent = get_user_model().objects.get(username="parent1")
    mechant = Eleve.objects.create(
        nom="<script>alert(1)</script>", classe="6e A", etablissement=Etablissement.objects.first()
    )
    ParentEleve.objects.create(parent=parent, eleve=mechant)
    connecte(client, "parent1")
    html = client.get(reverse("parent_enfants")).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html