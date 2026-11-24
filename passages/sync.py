import re
import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from school.models import PointControle

import logging

from . import anomalies, badges
from .models import Passage
logger = logging.getLogger(__name__)

TAILLE_MAX_LOT = 200
AGE_MAX = timedelta(days=7)
MS_MAX = 4_102_444_800_000  # an 2100 : borne contre les valeurs absurdes
APPAREIL_VALIDE = re.compile(r"[A-Za-z0-9_-]{3,64}")


class LotInvalide(Exception):
    pass


def _entier(valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        raise LotInvalide("entier attendu")
    return valeur


def _horodatage_ms(valeur):
    valeur = _entier(valeur)
    if not 0 < valeur < MS_MAX:
        raise LotInvalide("horodatage hors limites")
    return valeur


def _uuid(valeur):
    try:
        return uuid.UUID(str(valeur))
    except ValueError:
        raise LotInvalide("uuid invalide")


def _valider(donnees):
    """Toute entrée est validée côté serveur avant usage."""
    if not isinstance(donnees, dict):
        raise LotInvalide("objet attendu")
    appareil = donnees.get("appareil")
    if not isinstance(appareil, str) or not APPAREIL_VALIDE.fullmatch(appareil):
        raise LotInvalide("appareil invalide")
    envoye_ms = _horodatage_ms(donnees.get("appareil_envoye_ms"))
    scans = donnees.get("scans")
    if not isinstance(scans, list) or not 0 < len(scans) <= TAILLE_MAX_LOT:
        raise LotInvalide("liste de scans invalide")
    propres = []
    for s in scans:
        if not isinstance(s, dict):
            raise LotInvalide("scan invalide")
        code = s.get("code")
        if not isinstance(code, str) or len(code) > 200:
            raise LotInvalide("code invalide")
        propres.append(
            {
                "evenement_local": _uuid(s.get("evenement_local")),
                "code": code,
                "point_id": _entier(s.get("point_id")),
                "heure_locale_ms": _horodatage_ms(s.get("heure_locale_ms")),
            }
        )
    return appareil, envoye_ms, propres


def _statut(passage):
    return "accepte" if passage.etat_sync == Passage.EtatSync.VALIDE else "refuse"


def _traiter_scan(s, appareil, ecart_s, maintenant):
    ev = s["evenement_local"]

    def resultat(statut):
        # L'agent ne reçoit que « accepté » ou « refusé », jamais le motif.
        return {"evenement_local": str(ev), "statut": statut}

    # Idempotence : un scan déjà reçu n'est jamais réenregistré.
    deja = Passage.objects.filter(appareil=appareil, evenement_local=ev).first()
    if deja:
        return resultat(_statut(deja))

    instant_corrige = s["heure_locale_ms"] / 1000 + ecart_s
    verif = badges.verifier_code(s["code"], instant_corrige)
    if verif.badge is None:
        return resultat("refuse")  # code inconnu ou falsifié : rien à rattacher

    point = PointControle.objects.filter(pk=s["point_id"]).first()
    if point is None:
        return resultat("refuse")

    motif, corrigee = "", None
    if abs(ecart_s) > settings.HORLOGE_ECART_MAX_S or instant_corrige <= 0:
        motif = "horloge_inexploitable"
    else:
        corrigee = datetime.fromtimestamp(instant_corrige, tz=dt_timezone.utc)
        if not verif.ok:
            motif = verif.raison  # expire | badge_inactif
        elif verif.badge.eleve.etablissement_id != point.etablissement_id:
            motif = "point_autre_etablissement"
        elif corrigee > maintenant + timedelta(seconds=60):
            motif = "heure_future"
        elif corrigee < maintenant - AGE_MAX:
            motif = "trop_ancien"

    heure_locale = datetime.fromtimestamp(s["heure_locale_ms"] / 1000, tz=dt_timezone.utc)
    cree = True
    try:
        with transaction.atomic():
            passage = Passage.objects.create(
                badge=verif.badge,
                eleve=verif.badge.eleve,
                point=point,
                heure_locale=heure_locale,
                heure_corrigee=corrigee,
                ecart_horloge_s=round(ecart_s),
                appareil=appareil,
                evenement_local=ev,
                etat_sync=Passage.EtatSync.REJETE if motif else Passage.EtatSync.VALIDE,
                motif_rejet=motif,
            )
    except IntegrityError:  # deux envois simultanés du même scan
        cree = False
        passage = Passage.objects.get(appareil=appareil, evenement_local=ev)

    if cree:
        try:
            with transaction.atomic():
                anomalies.evaluer_passage(passage)
        except Exception:  # un défaut de détection ne doit jamais faire perdre un passage
            logger.exception("Détection d'anomalies en échec pour le passage %s", passage.pk)
    return resultat(_statut(passage))

def traiter_lot(donnees, maintenant=None):
    appareil, envoye_ms, scans = _valider(donnees)
    maintenant = maintenant or timezone.now()
    # Écart d'horloge mesuré à l'envoi : positif = appareil en retard, négatif = en avance.
    ecart_s = maintenant.timestamp() - envoye_ms / 1000
    return [_traiter_scan(s, appareil, ecart_s, maintenant) for s in scans]