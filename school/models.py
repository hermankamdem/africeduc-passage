from django.conf import settings
from django.db import models


class Etablissement(models.Model):
    nom = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.nom


class Itineraire(models.Model):
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE)
    nom = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["etablissement", "nom"], name="itineraire_unique"),
        ]

    def __str__(self):
        return self.nom


class Eleve(models.Model):
    class Etat(models.TextChoices):
        ACTIF = "actif", "Actif"
        INACTIF = "inactif", "Inactif"

    nom = models.CharField(max_length=150)
    classe = models.CharField(max_length=50)
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE)
    itineraire = models.ForeignKey(Itineraire, null=True, blank=True, on_delete=models.SET_NULL)
    etat = models.CharField(max_length=10, choices=Etat.choices, default=Etat.ACTIF)

    def __str__(self):
        return f"{self.nom} ({self.classe})"


class ParentEleve(models.Model):
    """Un parent peut avoir plusieurs enfants, un enfant plusieurs parents."""

    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "parent"},
    )
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["parent", "eleve"], name="parent_eleve_unique"),
        ]


class PointControle(models.Model):
    class Type(models.TextChoices):
        PORTAIL = "portail", "Portail"
        AUTOBUS = "autobus", "Autobus"

    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE)
    libelle = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=Type.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["etablissement", "libelle"], name="point_unique"),
        ]

    def __str__(self):
        return self.libelle


class Fenetre(models.Model):
    """Un point de contrôle attendu dans un itinéraire, avec sa fenêtre horaire."""

    itineraire = models.ForeignKey(Itineraire, on_delete=models.CASCADE, related_name="fenetres")
    point = models.ForeignKey(PointControle, on_delete=models.CASCADE)
    ordre = models.PositiveSmallIntegerField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    # Jours d'application : numéros ISO séparés par des virgules (1 = lundi ... 7 = dimanche).
    jours = models.CharField(max_length=20, default="1,2,3,4,5")

    class Meta:
        ordering = ["itineraire", "ordre"]
        constraints = [
            models.UniqueConstraint(fields=["itineraire", "ordre"], name="fenetre_ordre_unique"),
            models.CheckConstraint(
                condition=models.Q(heure_debut__lt=models.F("heure_fin")),
                name="fenetre_debut_avant_fin",
            ),
        ]


class ExceptionJour(models.Model):
    """Jour férié, absence justifiée, sortie anticipée : suspend la détection d'anomalie."""

    class Type(models.TextChoices):
        FERIE = "ferie", "Jour férié"
        ABSENCE = "absence", "Absence justifiée"
        SORTIE_ANTICIPEE = "sortie_anticipee", "Sortie anticipée autorisée"

    # eleve vide = valable pour tout l'établissement (jour férié)
    eleve = models.ForeignKey(Eleve, null=True, blank=True, on_delete=models.CASCADE)
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE)
    date = models.DateField()
    type = models.CharField(max_length=20, choices=Type.choices)