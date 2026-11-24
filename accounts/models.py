from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Utilisateur avec un rôle unique, contrôlé côté serveur."""

    class Role(models.TextChoices):
        AGENT = "agent", "Agent de portail"
        MANAGER = "responsable", "Responsable"
        PARENT = "parent", "Parent"

    role = models.CharField(max_length=20, choices=Role.choices)

    def __str__(self):
        return f"{self.username} ({self.role})"