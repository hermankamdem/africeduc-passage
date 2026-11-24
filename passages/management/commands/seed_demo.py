import uuid
from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from passages.models import Anomalie, Badge, Passage
from school.models import Eleve, Etablissement, Fenetre, Itineraire, ParentEleve, PointControle

NOM_ETAB = "Collège Démo de Yaoundé"
# Mots de passe de démonstration uniquement (comptes de test du README).
MOT_DE_PASSE_DEMO = "Demo-Passage-2026"
APPAREIL = "tablette-portail-1"


class Command(BaseCommand):
    help = "Crée les données de départ (comptes de test, élèves, itinéraires, anomalies)."

    @transaction.atomic
    def handle(self, *args, **options):
        if Etablissement.objects.filter(nom=NOM_ETAB).exists():
            self.stdout.write("Données de départ déjà présentes : rien à faire.")
            return

        User = get_user_model()
        for username, role in [
            ("responsable1", "responsable"),
            ("agent1", "agent"),
            ("parent1", "parent"),
            ("parent2", "parent"),
        ]:
            User.objects.create_user(username=username, password=MOT_DE_PASSE_DEMO, role=role)
        parent1 = User.objects.get(username="parent1")
        parent2 = User.objects.get(username="parent2")

        etab = Etablissement.objects.create(nom=NOM_ETAB)
        entree = PointControle.objects.create(etablissement=etab, libelle="Portail d'entrée", type="portail")
        sortie = PointControle.objects.create(etablissement=etab, libelle="Portail de sortie", type="portail")

        itineraire = Itineraire.objects.create(etablissement=etab, nom="Journée standard")
        Fenetre.objects.create(
            itineraire=itineraire, point=entree, ordre=1, heure_debut=time(7, 0), heure_fin=time(7, 45)
        )
        fenetre_sortie = Fenetre.objects.create(
            itineraire=itineraire, point=sortie, ordre=2, heure_debut=time(15, 30), heure_fin=time(16, 15)
        )

        eleves = {}
        for nom, parent in [
            ("Awa Ndongo", parent1), ("Bryan Ndongo", parent1),   # deux enfants, même parent
            ("Carine Etoga", parent2), ("Daniel Fouda", parent2), ("Estelle Mballa", parent2),
        ]:
            eleve = Eleve.objects.create(
                nom=nom, classe="6e A", etablissement=etab, itineraire=itineraire
            )
            ParentEleve.objects.create(parent=parent, eleve=eleve)
            eleves[nom.split()[0]] = (eleve, Badge.objects.create(eleve=eleve))

        jour = timezone.localdate()

        def scan(prenom, point, heure, minute, seconde=0):
            eleve, badge = eleves[prenom]
            heure_locale = timezone.make_aware(datetime.combine(jour, time(heure, minute, seconde)))
            return Passage.objects.create(
                badge=badge, eleve=eleve, point=point, heure_locale=heure_locale,
                heure_corrigee=heure_locale,
                appareil=APPAREIL, evenement_local=uuid.uuid4(),
                etat_sync=Passage.EtatSync.VALIDE,
            )

        scan("Awa", entree, 7, 10)
        scan("Awa", sortie, 15, 45)
        scan("Bryan", entree, 7, 20)                  # Bryan ne passe jamais à la sortie
        scan("Carine", entree, 7, 5)
        double = scan("Carine", entree, 7, 5, 30)     # deuxième scan à 30 s d'écart
        hors = scan("Daniel", entree, 9, 0)           # passage à 9 h, hors fenêtre
        scan("Estelle", entree, 7, 30)
        scan("Estelle", sortie, 15, 40)

        # Trois anomalies de types différents (le moteur de détection viendra à l'étape 6).
        Anomalie.objects.create(
            eleve=eleves["Bryan"][0], type=Anomalie.Type.ABSENCE, date=jour, fenetre=fenetre_sortie
        )
        Anomalie.objects.create(
            eleve=eleves["Carine"][0], type=Anomalie.Type.DOUBLE_SCAN, date=jour, passage=double
        )
        Anomalie.objects.create(
            eleve=eleves["Daniel"][0], type=Anomalie.Type.HORS_FENETRE, date=jour, passage=hors
        )

        self.stdout.write(self.style.SUCCESS("Données de départ créées."))