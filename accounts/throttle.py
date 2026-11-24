import hashlib

from django.conf import settings
from django.core.cache import cache


def _cle(identifiant, ip):
    brut = f"{identifiant.strip().lower()}|{ip}"
    return "echec_connexion:" + hashlib.sha256(brut.encode()).hexdigest()


def est_bloque(identifiant, ip):
    return cache.get(_cle(identifiant, ip), 0) >= settings.LOGIN_MAX_ATTEMPTS


def enregistrer_echec(identifiant, ip):
    cle = _cle(identifiant, ip)
    cache.add(cle, 0, settings.LOGIN_LOCKOUT_SECONDS)
    cache.incr(cle)


def reinitialiser(identifiant, ip):
    cache.delete(_cle(identifiant, ip))