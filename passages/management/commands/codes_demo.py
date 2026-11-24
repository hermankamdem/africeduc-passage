from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from passages import badges
from passages.models import Badge


class Command(BaseCommand):
    help = "Affiche les codes de badge valides maintenant (démonstration uniquement)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Réservé à la démonstration (DJANGO_DEBUG=true).")
        for b in Badge.objects.filter(etat=Badge.Etat.ACTIF).select_related("eleve"):
            self.stdout.write(f"{b.eleve.nom} : {badges.generer_code(b)}")
        self.stdout.write(f"(valides encore environ {badges.secondes_restantes()} s, plus la tolérance)")