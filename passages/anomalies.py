import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from school.models import Eleve, ExceptionJour, Fenetre

from . import notifications
from .models import Anomalie, Passage

logger = logging.getLogger(__name__)
DOUBLE_SCAN_S = 60


def _jours(fenetre):
    return {int(j) for j in fenetre.jours.split(",") if j.strip().isdigit()}


def _instant(passage):
    return passage.heure_corrigee or passage.heure_locale


def _aware(jour, heure):
    return timezone.make_aware(datetime.combine(jour, heure))


def _a_exception(eleve, jour):
    """Jour férié, absence justifiée ou sortie anticipée : la détection est suspendue."""
    return (
        ExceptionJour.objects.filter(etablissement=eleve.etablissement, date=jour)
        .filter(Q(eleve=eleve) | Q(eleve__isnull=True))
        .exists()
    )

def creer_anomalie(eleve, type_, jour, passage=None, fenetre=None):
    """Point d'entrée unique de création d'une anomalie. Idempotent."""
    try:
        with transaction.atomic():
            anomalie, creee = Anomalie.objects.get_or_create(
                eleve=eleve, type=type_, date=jour, passage=passage, fenetre=fenetre
            )
    except IntegrityError:
        return None, False
    if creee:
        try:
            with transaction.atomic():
                notifications.creer_messages(anomalie)
        except Exception:  # un souci de message ne doit jamais faire perdre l'anomalie
            logger.exception("Création des messages en échec pour l'anomalie %s", anomalie.pk)
    return anomalie, creee


def evaluer_passage(passage):
    """Détecte les anomalies d'un passage qui vient d'être enregistré."""
    eleve = passage.eleve
    instant = _instant(passage)
    local = timezone.localtime(instant)
    jour = local.date()

    if passage.etat_sync == Passage.EtatSync.REJETE:
        # Seul le badge inactif est une anomalie : c'est un signal de sécurité, il n'est donc
        # jamais suspendu par un jour d'exception.
        if passage.motif_rejet == "badge_inactif":
            creer_anomalie(eleve, Anomalie.Type.BADGE_INACTIF, jour, passage=passage)
        return

    if _a_exception(eleve, jour):
        return

    _verifier_itineraire(passage, eleve, local, jour)
    _verifier_double_scan(passage)


def _verifier_itineraire(passage, eleve, local, jour):
    if not eleve.itineraire_id:
        return  # sans itinéraire, on ne peut rien juger
    fenetres = list(
        Fenetre.objects.filter(itineraire_id=eleve.itineraire_id, point=passage.point)
    )
    if not fenetres:
        creer_anomalie(eleve, Anomalie.Type.HORS_ITINERAIRE, jour, passage=passage)
        return
    heure = local.time()
    dans_une_fenetre = any(
        local.isoweekday() in _jours(f) and f.heure_debut <= heure <= f.heure_fin
        for f in fenetres
    )
    if not dans_une_fenetre:
        creer_anomalie(eleve, Anomalie.Type.HORS_FENETRE, jour, passage=passage)


def _verifier_double_scan(passage):
    instant = passage.heure_corrigee
    if instant is None:
        return
    ecart = timedelta(seconds=DOUBLE_SCAN_S)
    voisins = (
        Passage.objects.filter(badge=passage.badge, etat_sync=Passage.EtatSync.VALIDE)
        .exclude(pk=passage.pk)
        .filter(heure_corrigee__gt=instant - ecart, heure_corrigee__lt=instant + ecart)
    )
    for voisin in voisins:
        # L'anomalie porte toujours sur le deuxième scan, même si les lots arrivent dans le désordre.
        plus_tard = max((passage, voisin), key=lambda p: (p.heure_corrigee, p.pk))
        creer_anomalie(
            plus_tard.eleve,
            Anomalie.Type.DOUBLE_SCAN,
            timezone.localdate(plus_tard.heure_corrigee),
            passage=plus_tard,
        )


def detecter_absences(maintenant=None, rattrapage_jours=0):
    """Crée une anomalie pour chaque passage attendu et non validé à la clôture de sa fenêtre.

    À exécuter régulièrement par un planificateur : personne n'a besoin d'ouvrir l'application.
    Retourne le nombre d'anomalies créées.
    """
    maintenant = maintenant or timezone.now()
    grace = timedelta(seconds=settings.ABSENCE_DELAI_GRACE_S)
    aujourdhui = timezone.localdate(maintenant)
    crees = 0

    for decalage in range(rattrapage_jours + 1):
        jour = aujourdhui - timedelta(days=decalage)
        for fenetre in Fenetre.objects.select_related("itineraire", "point"):
            if jour.isoweekday() not in _jours(fenetre):
                continue
            debut = _aware(jour, fenetre.heure_debut)
            fin = _aware(jour, fenetre.heure_fin)
            if maintenant < fin + grace:
                continue  # fenêtre pas encore close

            exceptions = ExceptionJour.objects.filter(
                date=jour, etablissement=fenetre.itineraire.etablissement
            )
            if exceptions.filter(eleve__isnull=True).exists():
                continue  # jour férié pour tout l'établissement
            exclus = set(
                exceptions.filter(eleve__isnull=False).values_list("eleve_id", flat=True)
            )

            eleves = Eleve.objects.filter(
                itineraire=fenetre.itineraire, etat=Eleve.Etat.ACTIF
            )
            # Seul un passage validé DANS la fenêtre compte : un scan hors fenêtre ne comble pas l'absence.
            presents = set(
                Passage.objects.filter(
                    point=fenetre.point,
                    etat_sync=Passage.EtatSync.VALIDE,
                    heure_corrigee__gte=debut,
                    heure_corrigee__lte=fin,
                    eleve__in=eleves,
                ).values_list("eleve_id", flat=True)
            )
            for eleve in eleves.exclude(pk__in=presents | exclus):
                _, creee = creer_anomalie(
                    eleve, Anomalie.Type.ABSENCE, jour, fenetre=fenetre
                )
                crees += int(creee)
    return crees