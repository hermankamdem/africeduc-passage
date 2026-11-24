import uuid

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone

from passages.models import Anomalie, Badge, Passage
from school.models import Eleve, Etablissement, PointControle


@pytest.fixture
def contexte(db):
    etab = Etablissement.objects.create(nom="Etab test")
    eleve = Eleve.objects.create(nom="Eleve test", classe="6e A", etablissement=etab)
    point = PointControle.objects.create(etablissement=etab, libelle="Portail", type="portail")
    return eleve, point


def test_un_seul_badge_actif_par_eleve(contexte):
    eleve, _ = contexte
    Badge.objects.create(eleve=eleve)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Badge.objects.create(eleve=eleve)


def test_un_passage_renvoye_n_est_enregistre_qu_une_fois(contexte):
    eleve, point = contexte
    badge = Badge.objects.create(eleve=eleve)
    donnees = dict(
        badge=badge, eleve=eleve, point=point, heure_locale=timezone.now(),
        appareil="tablette-1", evenement_local=uuid.uuid4(),
    )
    Passage.objects.create(**donnees)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Passage.objects.create(**donnees)


def test_seed_cree_trois_types_d_anomalies(db):
    call_command("seed_demo")
    assert Anomalie.objects.values("type").distinct().count() >= 3
    call_command("seed_demo")  # relancé : aucune erreur, aucun doublon
    assert Anomalie.objects.count() == 3