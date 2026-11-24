import time

from django.core.management.base import BaseCommand

from passages.anomalies import detecter_absences


class Command(BaseCommand):
    help = "Détecte les passages attendus et non effectués à la clôture des fenêtres."

    def add_arguments(self, parser):
        parser.add_argument("--boucle", action="store_true", help="Tourne en continu.")
        parser.add_argument("--intervalle", type=int, default=60, help="Secondes entre deux passes.")
        parser.add_argument("--rattrapage", type=int, default=0, help="Jours passés à revérifier.")

    def handle(self, *args, **options):
        while True:
            n = detecter_absences(rattrapage_jours=options["rattrapage"])
            if n:
                self.stdout.write(f"{n} absence(s) détectée(s).")
            if not options["boucle"]:
                break
            try:
                time.sleep(max(options["intervalle"], 1))
            except KeyboardInterrupt:
                break