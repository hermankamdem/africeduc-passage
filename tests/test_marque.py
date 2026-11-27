from django.urls import reverse


def test_la_page_de_connexion_affiche_le_nom(client):
    html = client.get(reverse("connexion")).content.decode()
    assert "<title>Connexion - HK_checking</title>" in html
    assert "<strong>HK_checking</strong>" in html


def test_le_nom_vient_du_reglage(client, settings):
    settings.APP_NAME = "AutreNom"
    html = client.get(reverse("connexion")).content.decode()
    assert "AutreNom" in html and "HK_checking" not in html


def test_l_administration_affiche_aussi_le_nom(client):
    html = client.get("/admin/login/").content.decode()
    assert "HK_checking" in html