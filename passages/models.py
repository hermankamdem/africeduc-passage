import secrets
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


def nouveau_secret():
    return secrets.token_hex(32)


class Badge(models.Model):
    class Etat(models.TextChoices):
        ACTIF = "actif", "Actif"
        SUSPENDU = "suspendu", "Suspendu"
        PERDU = "perdu", "Perdu"
        REVOQUE = "revoque", "Révoqué"

    # Seul identifiant visible sur le support : aléatoire, sans donnée nominative.
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    eleve = models.ForeignKey("school.Eleve", on_delete=models.CASCADE, related_name="badges")
    # Clé de signature, gardée côté serveur, jamais affichée sur le badge.
    secret = models.CharField(max_length=64, default=nouveau_secret, editable=False)
    etat = models.CharField(max_length=10, choices=Etat.choices, default=Etat.ACTIF)
    emis_le = models.DateTimeField(auto_now_add=True)
    remplace = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="remplace_par"
    )

    class Meta:
        constraints = [
            # Un élève ne peut avoir qu'un seul badge actif à la fois.
            models.UniqueConstraint(
                fields=["eleve"], condition=Q(etat="actif"), name="un_seul_badge_actif_par_eleve"
            ),
        ]


class Passage(models.Model):
    class EtatSync(models.TextChoices):
        RECU = "recu", "Reçu"
        VALIDE = "valide", "Validé"
        REJETE = "rejete", "Rejeté"

    badge = models.ForeignKey(Badge, on_delete=models.PROTECT)
    eleve = models.ForeignKey("school.Eleve", on_delete=models.PROTECT, related_name="passages")
    point = models.ForeignKey("school.PointControle", on_delete=models.PROTECT)
    heure_locale = models.DateTimeField()                      # horloge de l'appareil
    heure_serveur = models.DateTimeField(auto_now_add=True)    # réception par le serveur
    appareil = models.CharField(max_length=64)
    evenement_local = models.UUIDField()                       # identifiant généré par l'appareil
    etat_sync = models.CharField(max_length=10, choices=EtatSync.choices, default=EtatSync.RECU)
    motif_rejet = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            # Anti-doublon : le même scan renvoyé plusieurs fois n'est enregistré qu'une fois.
            models.UniqueConstraint(
                fields=["appareil", "evenement_local"], name="passage_unique_par_evenement"
            ),
        ]
        indexes = [models.Index(fields=["eleve", "heure_serveur"])]


class Anomalie(models.Model):
    class Type(models.TextChoices):
        ABSENCE = "absence_passage", "Passage attendu non effectué"
        HORS_FENETRE = "hors_fenetre", "Passage hors fenêtre"
        HORS_ITINERAIRE = "point_hors_itineraire", "Point absent de l'itinéraire"
        DOUBLE_SCAN = "double_scan", "Double scan en moins de 60 s"
        BADGE_INACTIF = "badge_inactif", "Badge suspendu, perdu ou révoqué présenté"

    class Traitement(models.TextChoices):
        NOUVELLE = "nouvelle", "Nouvelle"
        TRAITEE = "traitee", "Traitée"

    eleve = models.ForeignKey("school.Eleve", on_delete=models.CASCADE, related_name="anomalies")
    type = models.CharField(max_length=30, choices=Type.choices)
    date = models.DateField()
    passage = models.ForeignKey(Passage, null=True, blank=True, on_delete=models.SET_NULL)
    fenetre = models.ForeignKey("school.Fenetre", null=True, blank=True, on_delete=models.SET_NULL)
    etat_traitement = models.CharField(
        max_length=10, choices=Traitement.choices, default=Traitement.NOUVELLE
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # La détection d'absence peut être relancée sans créer de doublon.
            models.UniqueConstraint(
                fields=["eleve", "fenetre", "date"],
                condition=Q(type="absence_passage"),
                name="absence_unique_par_fenetre_et_jour",
            ),
        ]


class MessageSortant(models.Model):
    class Etat(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        ENVOYE = "envoye", "Envoyé"
        BLOQUE = "bloque_plafond", "Non émis (plafond atteint)"

    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    anomalie = models.ForeignKey(Anomalie, on_delete=models.CASCADE)
    texte = models.TextField()
    etat = models.CharField(max_length=20, choices=Etat.choices, default=Etat.EN_ATTENTE)
    cree_le = models.DateTimeField(auto_now_add=True)
    motif_non_envoi = models.CharField(max_length=200, blank=True)


class Synthese(models.Model):
    class Origine(models.TextChoices):
        MODELE = "modele", "Modèle de langage"
        GABARIT = "gabarit", "Gabarit (mode dégradé)"

    etablissement = models.ForeignKey("school.Etablissement", on_delete=models.CASCADE)
    classe = models.CharField(max_length=50)
    date = models.DateField()
    chiffres = models.JSONField()        # calculés par le code, jamais par le modèle
    empreinte = models.CharField(max_length=64)   # hash des chiffres : évite de refacturer
    texte = models.TextField()
    origine = models.CharField(max_length=10, choices=Origine.choices)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["etablissement", "classe", "date", "empreinte"], name="synthese_unique"
            ),
        ]


class JournalAudit(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=50)
    cible = models.CharField(max_length=100, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)