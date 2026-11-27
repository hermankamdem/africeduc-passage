from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from passages import badges
from passages.models import Badge


class Command(BaseCommand):
    help = "Affiche les codes de badge valides maintenant (démonstration uniquement)."

    def add_arguments(self, parser):
        parser.add_argument("--eleve", help="Prénom ou début du nom de l'élève.")
        parser.add_argument("--brut", action="store_true", help="Affiche seulement le code.")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Réservé à la démonstration (DJANGO_DEBUG=true).")
        qs = Badge.objects.filter(etat=Badge.Etat.ACTIF).select_related("eleve")
        if options["eleve"]:
            qs = qs.filter(eleve__nom__istartswith=options["eleve"])
        trouves = list(qs)
        if not trouves:
            raise CommandError("Aucun badge actif trouvé.")
        for b in trouves:
            code = badges.generer_code(b)
            self.stdout.write(code if options["brut"] else f"{b.eleve.nom} : {code}")