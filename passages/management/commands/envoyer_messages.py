import time

from django.core.management.base import BaseCommand

from passages.notifications import envoyer_en_attente


class Command(BaseCommand):
    help = "Envoie les messages aux parents qui sont en attente."

    def add_arguments(self, parser):
        parser.add_argument("--boucle", action="store_true", help="Tourne en continu.")
        parser.add_argument("--intervalle", type=int, default=30, help="Secondes entre deux passes.")

    def handle(self, *args, **options):
        while True:
            n = envoyer_en_attente()
            if n:
                self.stdout.write(f"{n} message(s) envoyé(s).")
            if not options["boucle"]:
                break
            try:
                time.sleep(max(options["intervalle"], 1))
            except KeyboardInterrupt:
                break