import logging
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

from school.models import ParentEleve

from .models import Anomalie, MessageSortant

logger = logging.getLogger(__name__)


class FournisseurSMS(ABC):
    """Interface à implémenter pour brancher un vrai service de SMS."""

    @abstractmethod
    def envoyer(self, parent, texte):
        """Envoie `texte` au parent. Doit lever une exception en cas d'échec."""


class FournisseurConsole(FournisseurSMS):
    """Fournisseur de démonstration : n'envoie rien, écrit dans le journal."""

    def envoyer(self, parent, texte):
        logger.info("SMS simulé pour %s : %s", parent.username, texte)


def get_fournisseur():
    # Le fournisseur se choisit par réglage : aucun autre code à modifier.
    return import_string(settings.SMS_FOURNISSEUR)()


T = Anomalie.Type
PHRASES = {
    T.ABSENCE: "{prenom} n'a pas été enregistré(e) à un passage attendu le {date}.",
    T.HORS_FENETRE: "{prenom} a été enregistré(e) à un passage en dehors des horaires prévus le {date}.",
    T.HORS_ITINERAIRE: "{prenom} a été enregistré(e) à un point qui ne fait pas partie de son parcours habituel le {date}.",
    T.DOUBLE_SCAN: "Le badge de {prenom} a été présenté deux fois de suite le {date}.",
    T.BADGE_INACTIF: "Un badge désactivé de {prenom} a été présenté le {date}.",
}
SUITE = " Si tout est normal, aucune action n'est nécessaire. Détails dans l'application SchoolLogs."


def texte_message(anomalie):
    """Message neutre : prénom, nature de l'écart, date. Ni lieu, ni heure, ni nom de famille."""
    prenom = anomalie.eleve.nom.split()[0]
    phrase = PHRASES[anomalie.type].format(prenom=prenom, date=anomalie.date.strftime("%d/%m/%Y"))
    return "SchoolLogs : " + phrase + SUITE


def creer_messages(anomalie):
    """Crée un message par parent, en respectant le plafond par élève et par jour."""
    texte = texte_message(anomalie)
    aujourdhui = timezone.localdate()
    crees = []
    for lien in ParentEleve.objects.filter(eleve=anomalie.eleve).select_related("parent"):
        deja_emis = (
            MessageSortant.objects.filter(
                parent=lien.parent, anomalie__eleve=anomalie.eleve, cree_le__date=aujourdhui
            )
            .exclude(etat=MessageSortant.Etat.BLOQUE)
            .count()
        )
        if deja_emis >= settings.MESSAGES_MAX_PAR_ELEVE_PAR_JOUR:
            etat, motif = MessageSortant.Etat.BLOQUE, "plafond_quotidien_atteint"
        else:
            etat, motif = MessageSortant.Etat.EN_ATTENTE, ""
        message, cree = MessageSortant.objects.get_or_create(
            parent=lien.parent,
            anomalie=anomalie,
            defaults={"texte": texte, "etat": etat, "motif_non_envoi": motif},
        )
        if cree:
            crees.append(message)
    return crees


def envoyer_en_attente():
    """Envoie les messages en attente. Un échec laisse le message en attente pour un nouvel essai."""
    fournisseur = get_fournisseur()
    envoyes = 0
    for message in MessageSortant.objects.filter(etat=MessageSortant.Etat.EN_ATTENTE).select_related("parent"):
        try:
            fournisseur.envoyer(message.parent, message.texte)
        except Exception:
            logger.exception("Échec d'envoi du message %s", message.pk)
            message.motif_non_envoi = "echec_fournisseur"
            message.save(update_fields=["motif_non_envoi"])
            continue
        message.etat = MessageSortant.Etat.ENVOYE
        message.motif_non_envoi = ""
        message.save(update_fields=["etat", "motif_non_envoi"])
        envoyes += 1
    return envoyes