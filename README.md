# Passage — suivi des passages d'élèves par badge

Test technique Afric'Éduc, sujet B. Version réduite d'un module SchoolLogs : enregistrer les
passages d'élèves à des points de contrôle, même sans réseau, détecter les anomalies, prévenir
les parents et produire une synthèse du jour.

## Technologies et justification

- **Django 6 (Python 3.12+)** : sécurité intégrée (hachage, sessions, CSRF, échappement HTML,
  ORM) et migrations. Voir DECISIONS.md (D1).
- **SQLite** par défaut, **PostgreSQL** possible avec la variable `DATABASE_URL`.
- **Argon2** pour les mots de passe.
- **Interface** : pages Django simples + JavaScript. L'écran de scan fonctionne hors ligne
  grâce à un service worker et à IndexedDB.
- **pytest** et **GitHub Actions** pour les tests.
- **IA** : appel HTTP au service Anthropic, optionnel (voir « Mode dégradé »).

## Installation et lancement

Windows :

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Linux / macOS :

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Puis, dans `.env`, renseigner `DJANGO_SECRET_KEY` avec une valeur générée par :

```
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

et mettre `DJANGO_DEBUG=true` pour un essai en local (nécessaire pour voir le style de
l'administration et pour la commande `codes_demo`). Ensuite :

```
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

Ouvrir http://127.0.0.1:8000/. La base est entièrement recréée par les migrations, puis
remplie par `seed_demo` (rejouable sans doublon).

Deux tâches sont à lancer à part (cron, planificateur Windows, ou en continu) :

```
python manage.py detecter_absences --boucle --intervalle 60
python manage.py envoyer_messages --boucle --intervalle 30
```

## Comptes de test (démonstration uniquement)

| Identifiant | Rôle | Mot de passe |
|---|---|---|
| `responsable1` | Responsable | `Demo-Passage-2026` |
| `agent1` | Agent de portail | `Demo-Passage-2026` |
| `parent1` | Parent (2 enfants : Awa et Bryan) | `Demo-Passage-2026` |
| `parent2` | Parent (3 enfants) | `Demo-Passage-2026` |

Le superutilisateur de l'administration (`/admin/`) se crée avec `createsuperuser`.
Pour obtenir des codes de badge valides pendant une démonstration : `python manage.py codes_demo`.

## Lancer les tests

```
pytest
```

Les mêmes tests s'exécutent à chaque envoi via GitHub Actions
(`.github/workflows/ci.yml`).

## Ce que fait l'application

- **Badges** : code tournant `uid.pas.signature` (HMAC-SHA256, validité 30 s). Aucune donnée
  nominative. Cycle de vie : actif, suspendu, perdu, révoqué. Une réémission révoque
  immédiatement l'ancien badge.
- **Scan hors ligne** : chaque scan est écrit dans IndexedDB avec un identifiant unique, puis
  envoyé par lots. La base refuse un second passage avec le même (appareil, identifiant).
- **Horloge fausse** : le serveur mesure l'écart à chaque lot, corrige l'heure et enregistre
  l'heure brute, l'heure corrigée et l'écart. Au-delà de 24 h, le passage est refusé.
- **Anomalies** : absence à la clôture d'une fenêtre (détectée par une tâche planifiée),
  passage hors fenêtre, point absent de l'itinéraire, double scan à moins de 60 s, et une
  cinquième : badge suspendu, perdu ou révoqué présenté.
- **Messages aux parents** : table de messages sortants, interface de fournisseur SMS
  isolée, plafond par élève et par jour.
- **Synthèse du jour** : chiffres calculés par le code, texte rédigé par un modèle ou par un
  gabarit.

## Sécurité

| Point | Traitement |
|---|---|
| Mots de passe | Argon2, minimum 8 caractères. Test dédié. |
| Tentatives de connexion | 5 échecs par couple (identifiant, adresse IP) : blocage de 15 min. Message d'erreur identique que l'identifiant existe ou non. |
| Session | Durée de 1 h, cookie inaccessible au JavaScript. La déconnexion détruit la session côté serveur ; un test rejoue l'ancien cookie. |
| Rôles | Décorateur `role_requis` sur chaque vue, vérifié par le serveur (403). Tests pour chaque couple rôle / page. |
| Cloisonnement | Un parent ne trouve un élève que parmi ses enfants : un identifiant étranger donne 404. Testé, y compris pour le code du badge. |
| Entrées | Lots de synchronisation validés champ par champ (types, bornes, taille). ORM partout, aucune requête construite à la main. |
| XSS | Échappement automatique des gabarits, jamais de `|safe`. Test avec un nom contenant `<script>`. |
| CSRF | Jeton exigé, y compris sur l'envoi des scans (testé). |
| Secrets | Variables d'environnement, `.env` ignoré par Git, `.env.example` sans valeur. |
| Badge | Code signé qui expire, secret côté serveur seulement. Une photo ne sert plus après environ 1 minute. |

**Ce que je ferais avec plus de temps** : chiffrer les secrets de badge en base ; stocker la
limitation de tentatives dans Redis (le cache en mémoire est propre à un processus) ;
activer les cookies `Secure` et HSTS derrière HTTPS ; limiter le débit de l'endpoint de
synchronisation ; double authentification pour le responsable ; lecture du code par la caméra.

## Mode dégradé

- **Sans clé d'IA** (`ANTHROPIC_API_KEY` vide) ou **service en erreur** : la synthèse reste
  produite par un gabarit, exact mais sec. Le chemin emprunté est enregistré en base
  (champ `chemin`) et affiché au responsable.
- **Plafond de dépense atteint** : plus aucun appel, gabarit utilisé, message clair.
- **Réponse du modèle non conforme** (JSON invalide, nombre inventé) : une seule nouvelle
  tentative, puis gabarit.
- **Sans réseau au portail** : les scans restent sur l'appareil et partent au retour du réseau.
- **Sans fournisseur de SMS** : les messages sont enregistrés avec leur état.

## Ce que je n'ai pas terminé

- Lecture du code par la caméra et affichage du code sous forme de QR Code : le code est saisi
  ou collé (compatible avec un lecteur qui « tape » le code).
- Envoi réel de SMS : le fournisseur livré écrit dans le journal, et le modèle utilisateur
  n'a pas de numéro de téléphone.
- Gestion par le responsable des points de contrôle, itinéraires, fenêtres et jours
  d'exception : possible uniquement par l'administration Django, pas par un écran dédié.
- Le responsable ne peut pas créer d'élève depuis son écran.
- La tâche de détection d'absence doit être planifiée à l'extérieur (cron).
- Correction d'horloge : mal corrigée si l'agent change l'horloge pendant que des scans
  attendent dans la file.
- Un seul établissement est géré de bout en bout pour la synthèse.
- Pas de test automatique du comportement hors ligne dans le navigateur : ce scénario est
  vérifié à la main (voir la vidéo de démonstration).

## Structure

```
accounts/    utilisateurs, connexion, limitation des tentatives, rôles
school/      établissements, élèves, parents, itinéraires, fenêtres, exceptions
passages/    badges, synchronisation, anomalies, messages, synthèse, IA
tests/       tests automatisés
DECISIONS.md décisions prises, option écartée et raison
JOURNAL-IA.md usage des outils d'IA
```