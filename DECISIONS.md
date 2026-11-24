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