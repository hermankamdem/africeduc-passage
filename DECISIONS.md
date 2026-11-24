# DECISIONS

## D1 - Framework serveur
- Retenu : Django (SQLite par défaut, PostgreSQL possible via variable d'environnement)
- Écarté : FastAPI
- Raison : la sécurité (hachage, sessions, CSRF, anti-XSS, ORM) et les migrations
  sont intégrées, ce qui réduit le risque et le volume de code à justifier en 5 jours.