import hashlib
import hmac
import time
import uuid
from typing import NamedTuple

from django.conf import settings

from .models import Badge


class Verification(NamedTuple):
    ok: bool
    raison: str            # ok | invalide | expire | badge_inactif
    badge: "Badge | None" = None
    pas: "int | None" = None


def _signature(secret, uid, pas):
    message = f"{uid}.{pas}".encode()
    return hmac.new(bytes.fromhex(secret), message, hashlib.sha256).hexdigest()[:24]


def generer_code(badge, instant=None):
    instant = time.time() if instant is None else instant
    pas = int(instant // settings.BADGE_PAS_SECONDES)
    return f"{badge.uid}.{pas}.{_signature(badge.secret, badge.uid, pas)}"


def secondes_restantes(instant=None):
    instant = time.time() if instant is None else instant
    return settings.BADGE_PAS_SECONDES - int(instant % settings.BADGE_PAS_SECONDES)


def verifier_code(code, instant):
    """Vérifie un code scanné. `instant` = heure (en secondes) du scan."""
    invalide = Verification(False, "invalide")
    parties = str(code).strip().split(".")
    if len(parties) != 3:
        return invalide
    try:
        uid = uuid.UUID(parties[0])
        pas = int(parties[1])
    except ValueError:
        return invalide

    badge = Badge.objects.filter(uid=uid).first()
    if badge is None:
        return invalide
    attendu = _signature(badge.secret, badge.uid, pas)
    # Comparaison en temps constant, sur des octets (évite une erreur sur du texte exotique).
    if not hmac.compare_digest(attendu.encode(), parties[2].encode()):
        return invalide

    # Fraîcheur : le code doit dater de sa tranche de 30 s, à la tolérance d'horloge près.
    ecart = instant - pas * settings.BADGE_PAS_SECONDES
    if ecart < -settings.BADGE_TOLERANCE_SECONDES or ecart > (
        settings.BADGE_PAS_SECONDES + settings.BADGE_TOLERANCE_SECONDES
    ):
        return Verification(False, "expire", badge, pas)

    if badge.etat != Badge.Etat.ACTIF:
        return Verification(False, "badge_inactif", badge, pas)
    return Verification(True, "ok", badge, pas)