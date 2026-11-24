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
## D8 - Limitation des tentatives de connexion
- Retenu : compteur d'échecs par couple (identifiant, adresse IP) dans le cache, blocage
  après 5 échecs pendant 15 minutes, paramétrable par variables d'environnement.
- Écarté : blocage par identifiant seul.
- Raison : un attaquant pourrait verrouiller le compte de n'importe quel parent.
  Limite connue : le cache en mémoire est propre à un processus ; en production il faudrait
  Redis ou la base.

## D9 - Accès à l'élève d'un autre parent
- Retenu : réponse 404 (l'élève est cherché uniquement parmi les enfants du parent connecté).
- Écarté : réponse 403.
- Raison : un 403 confirmerait à un curieux que cet identifiant existe.

## D10 - Contrôle des rôles
- Retenu : un décorateur unique `role_requis` appliqué à chaque vue, côté serveur.
- Écarté : masquer des boutons dans l'interface.
- Raison : l'interface n'est pas une barrière ; chaque vue vérifie le rôle elle-même.
## D12 - Horloge fausse sur l'appareil
- Retenu : la tablette envoie son heure à chaque lot ; le serveur calcule l'écart,
  corrige l'heure du scan, enregistre l'heure brute, l'heure corrigée et l'écart. Si
  l'écart dépasse 24 h, le passage est enregistré comme refusé (horloge_inexploitable).
- Écartés : rejeter dès que l'horloge est fausse (on perdrait de vrais passages et on
  punirait l'agent), et faire confiance à l'heure locale (données corrompues).
- Limite connue : si l'agent change l'horloge pendant que des scans sont en file, ces scans
  sont mal corrigés. Une horloge monotone serait la suite.

## D13 - Confirmation de synchronisation
- Retenu : la tablette ne retire de sa file que les scans confirmés par le serveur, par
  lots de 5. Un lot renvoyé est reconnu par (appareil, identifiant d'événement).
- Écarté : vider la file après l'envoi.
- Raison : une réponse perdue ne doit ni perdre ni dupliquer de passage.

## D14 - Refus différé et information de l'agent
- Retenu : le code est vérifié par le serveur, donc un refus n'est connu qu'à la
  synchronisation. L'agent voit seulement « accepté » ou « refusé », jamais le motif.
- Écarté : stocker les secrets sur les tablettes pour vérifier hors ligne.
- Raison : un secret volé sur une tablette permettrait de fabriquer des codes. L'agent ne
  voit pas les anomalies (règle du sujet).

## D15 - Saisie du code
- Retenu : champ texte, compatible avec un lecteur de codes qui « tape » le code.
- Non fait : lecture par la caméra et affichage d'un QR Code côté parent (à documenter
  dans le README).