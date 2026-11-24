from django.db import transaction

from .models import Badge, JournalAudit


class TransitionInterdite(Exception):
    pass


# Cycle de vie : un badge révoqué ne revient jamais.
TRANSITIONS = {
    "actif": {"suspendu", "perdu", "revoque"},
    "suspendu": {"actif", "perdu", "revoque"},
    "perdu": {"revoque"},
    "revoque": set(),
}


@transaction.atomic
def emettre_badge(eleve, utilisateur=None):
    """Émet un badge et invalide immédiatement tous les anciens badges de l'élève."""
    ancien = (
        Badge.objects.select_for_update()
        .filter(eleve=eleve)
        .exclude(etat=Badge.Etat.REVOQUE)
        .order_by("-emis_le")
        .first()
    )
    Badge.objects.filter(eleve=eleve).exclude(etat=Badge.Etat.REVOQUE).update(
        etat=Badge.Etat.REVOQUE
    )
    nouveau = Badge.objects.create(eleve=eleve, remplace=ancien)
    JournalAudit.objects.create(
        utilisateur=utilisateur, action="badge_emis", cible=f"eleve:{eleve.pk}"
    )
    return nouveau


@transaction.atomic
def changer_etat(badge, nouvel_etat, utilisateur=None):
    badge = Badge.objects.select_for_update().get(pk=badge.pk)
    if nouvel_etat not in TRANSITIONS.get(badge.etat, set()):
        raise TransitionInterdite(f"{badge.etat} -> {nouvel_etat}")
    badge.etat = nouvel_etat
    badge.save(update_fields=["etat"])
    JournalAudit.objects.create(
        utilisateur=utilisateur, action=f"badge_{nouvel_etat}", cible=f"badge:{badge.pk}"
    )
    return badge