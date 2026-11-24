# DECISIONS

## D1 - Framework serveur
- Retenu : Django (SQLite par défaut, PostgreSQL possible via variable d'environnement)
- Écarté : FastAPI
- Raison : la sécurité (hachage, sessions, CSRF, anti-XSS, ORM) et les migrations
  sont intégrées, ce qui réduit le risque et le volume de code à justifier en 5 jours.
  ## D2 - Utilisateurs et rôles
- Retenu : modèle utilisateur Django personnalisé avec un champ `role` unique
  (agent, responsable, parent), vérifié côté serveur.
- Écarté : groupes et permissions Django.
- Raison : trois rôles fixes et exclusifs, plus simple à tester et à expliquer.

## D3 - Jours d'application des fenêtres
- Retenu : champ texte de numéros de jours ISO ("1,2,3,4,5").
- Écarté : une table de jours séparée.
- Raison : plus simple pour la durée du test ; limite connue : pas de requête SQL sur les jours.
## D4 - Contenu du badge
- Retenu : le badge ne contient qu'un identifiant aléatoire (UUID) ; le secret de
  signature reste côté serveur. Le code affiché sera dérivé du secret et du temps
  (détail à l'étape badges).
- Écarté : un code statique contenant l'identifiant de l'élève.
- Raison : un badge photographié ne doit pas permettre de se faire passer pour l'élève.

## D5 - Anti-doublon de synchronisation
- Retenu : identifiant d'événement généré par l'appareil, avec contrainte d'unicité
  (appareil, événement) en base.
- Écarté : comparer l'heure et le point pour deviner les doublons.
- Raison : la base garantit l'unicité même si le lot est renvoyé ou interrompu en cours.

## D6 - Cinquième anomalie
- Retenu : « badge suspendu, perdu ou révoqué présenté ».
- Écarté : « retard » (déjà couvert par « hors fenêtre »).
- Raison : c'est le signal le plus utile pour la sécurité (badge volé ou perdu en usage).

## D7 - Un seul badge actif par élève
- Retenu : contrainte d'unicité conditionnelle en base.
- Raison : une réémission invalide l'ancien badge, garanti par la base et non par le code seul.