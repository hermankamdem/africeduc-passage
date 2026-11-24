import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from passages import anomalies, notifications
from passages.models import Anomalie, MessageSortant
from school.models import Eleve, Etablissement, ParentEleve

T = Anomalie.Type
E = MessageSortant.Etat


@pytest.fixture
def famille(db, settings):
    settings.MESSAGES_MAX_PAR_ELEVE_PAR_JOUR = 2
    etab = Etablissement.objects.create(nom="Etab")
    User = get_user_model()
    p1 = User.objects.create_user("p1", password="Motdepasse-42x", role="parent")
    p2 = User.objects.create_user("p2", password="Motdepasse-42x", role="parent")
    eleve = Eleve.objects.create(nom="Awa Ndongo", classe="6e A", etablissement=etab)
    autre = Eleve.objects.create(nom="Bob Etoga", classe="6e A", etablissement=etab)
    ParentEleve.objects.create(parent=p1, eleve=eleve)
    ParentEleve.objects.create(parent=p2, eleve=eleve)
    ParentEleve.objects.create(parent=p1, eleve=autre)
    return eleve, autre, p1, p2


def anomalie(eleve, type_):
    return Anomalie.objects.create(eleve=eleve, type=type_, date=timezone.localdate())


def test_un_message_par_parent_de_l_eleve(famille):
    eleve, autre, p1, p2 = famille
    notifications.creer_messages(anomalie(eleve, T.ABSENCE))
    assert set(MessageSortant.objects.values_list("parent__username", flat=True)) == {"p1", "p2"}


def test_le_message_est_neutre_et_comprehensible(famille):
    eleve, *_ = famille
    for type_ in T.values:
        texte = notifications.texte_message(anomalie(eleve, type_))
        assert "Awa" in texte and "Ndongo" not in texte  # prénom seulement
        assert str(timezone.localdate().year) in texte
        assert "Entrée" not in texte and "Portail" not in texte and "Bus" not in texte
        assert "application" in texte


def test_plafond_par_eleve_et_par_jour(famille):
    eleve, autre, p1, p2 = famille
    for type_ in (T.ABSENCE, T.HORS_FENETRE, T.DOUBLE_SCAN):
        notifications.creer_messages(anomalie(eleve, type_))
    assert MessageSortant.objects.filter(parent=p1, anomalie__eleve=eleve, etat=E.EN_ATTENTE).count() == 2
    bloques = MessageSortant.objects.filter(parent=p1, anomalie__eleve=eleve, etat=E.BLOQUE)
    assert bloques.count() == 1
    assert bloques.get().motif_non_envoi == "plafond_quotidien_atteint"  # et cela se voit


def test_le_plafond_d_un_eleve_ne_bloque_pas_un_autre(famille):
    eleve, autre, p1, p2 = famille
    for type_ in (T.ABSENCE, T.HORS_FENETRE, T.DOUBLE_SCAN):
        notifications.creer_messages(anomalie(eleve, type_))
    notifications.creer_messages(anomalie(autre, T.ABSENCE))
    assert MessageSortant.objects.get(parent=p1, anomalie__eleve=autre).etat == E.EN_ATTENTE


def test_les_messages_ne_sont_pas_dupliques(famille):
    eleve, *_ = famille
    a = anomalie(eleve, T.ABSENCE)
    notifications.creer_messages(a)
    notifications.creer_messages(a)
    assert MessageSortant.objects.count() == 2  # un par parent


def test_envoi_marque_envoye_mais_jamais_les_messages_bloques(famille):
    eleve, *_ = famille
    for type_ in (T.ABSENCE, T.HORS_FENETRE, T.DOUBLE_SCAN):
        notifications.creer_messages(anomalie(eleve, type_))
    assert notifications.envoyer_en_attente() == 4  # 2 parents x 2 messages
    assert MessageSortant.objects.filter(etat=E.BLOQUE).count() == 2
    assert MessageSortant.objects.filter(etat=E.EN_ATTENTE).count() == 0


def test_echec_du_fournisseur_laisse_le_message_en_attente(famille, monkeypatch):
    eleve, *_ = famille
    notifications.creer_messages(anomalie(eleve, T.ABSENCE))

    class EnPanne(notifications.FournisseurSMS):
        def envoyer(self, parent, texte):
            raise RuntimeError("réseau coupé")

    monkeypatch.setattr(notifications, "get_fournisseur", lambda: EnPanne())
    assert notifications.envoyer_en_attente() == 0
    messages = MessageSortant.objects.all()
    assert {m.etat for m in messages} == {E.EN_ATTENTE}
    assert {m.motif_non_envoi for m in messages} == {"echec_fournisseur"}


def test_un_autre_fournisseur_se_branche_sans_toucher_au_reste(famille, monkeypatch):
    recus = []

    class Spy(notifications.FournisseurSMS):
        def envoyer(self, parent, texte):
            recus.append((parent.username, texte))

    monkeypatch.setattr(notifications, "get_fournisseur", lambda: Spy())
    eleve, *_ = famille
    notifications.creer_messages(anomalie(eleve, T.ABSENCE))
    notifications.envoyer_en_attente()
    assert {u for u, _ in recus} == {"p1", "p2"}


def test_le_fournisseur_par_defaut_est_simule(settings):
    assert isinstance(notifications.get_fournisseur(), notifications.FournisseurConsole)


def test_une_nouvelle_anomalie_produit_ses_messages(famille):
    eleve, *_ = famille
    anomalies.creer_anomalie(eleve, T.HORS_FENETRE, timezone.localdate())
    assert MessageSortant.objects.filter(anomalie__eleve=eleve).count() == 2


def test_un_defaut_de_message_ne_fait_pas_perdre_l_anomalie(famille, monkeypatch):
    def panne(anomalie):
        raise RuntimeError("panne")

    monkeypatch.setattr(notifications, "creer_messages", panne)
    eleve, *_ = famille
    anomalies.creer_anomalie(eleve, T.HORS_FENETRE, timezone.localdate())
    assert Anomalie.objects.count() == 1