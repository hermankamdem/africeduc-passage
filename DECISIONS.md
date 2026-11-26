
# DECISIONS

Les quatre questions posées par l'énoncé (section 3.6) :
- Badge inutilisable par un tiers : D4 (et D11 pour la vérification hors ligne)
- Passage enregistré une seule fois : D5 et D13
- Heure locale fausse : D12
- Détection d'une absence et cinquième anomalie : D16 et D6
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
  ## D16 - Détection d'une absence de passage
- Retenu : une commande planifiée (`detecter_absences`), exécutée chaque minute par un
  planificateur (cron, Planificateur de tâches Windows) ou avec `--boucle`. À chaque passe,
  elle cherche les fenêtres closes sans passage validé dans la fenêtre et crée l'anomalie.
  Elle est rejouable : une contrainte d'unicité en base empêche les doublons.
- Écartés : calculer l'absence à l'ouverture d'une page (personne n'ouvre l'application),
  et une file de tâches type Celery (trop lourd pour ce périmètre).
- Limite connue : si le planificateur s'arrête, les absences sont rattrapées avec
  `--rattrapage N`, mais pas automatiquement.

## D17 - Délai de grâce avant de déclarer une absence
- Retenu : 10 minutes après la fin de la fenêtre (réglable), pour laisser arriver les scans
  faits hors ligne.
- Écarté : déclarer l'absence à la seconde où la fenêtre se ferme.
- Raison : sinon un portail sans réseau génèrerait de fausses absences, et donc de faux
  messages aux parents. Limite connue : un lot très tardif peut quand même arriver après.

## D18 - Jours d'exception et badge inactif
- Retenu : une exception suspend toutes les anomalies de la journée, sauf « badge suspendu,
  perdu ou révoqué présenté ».
- Raison : un badge déclaré perdu qui est scanné est un signal de sécurité, pas un écart
  d'horaire. C'est un écart volontaire par rapport à la lettre de l'énoncé.

## D19 - Double scan
- Retenu : deux scans validés du même badge à moins de 60 s ; l'anomalie porte sur le
  deuxième (heure corrigée), même si les lots arrivent dans le désordre.
- Écarté : comparer l'heure d'arrivée au serveur.
- Raison : en mode hors ligne, l'ordre d'arrivée ne reflète pas l'ordre des scans.

## D20 - Élève sans itinéraire
- Retenu : aucun jugement (ni hors fenêtre, ni hors itinéraire) tant qu'aucun itinéraire
  n'est rattaché à l'élève.
- Raison : on ne peut pas dire qu'un écart existe sans référence.
## D21 - Plafond de messages
- Retenu : un maximum de 3 messages émis par élève, par parent et par jour (réglable). Au-delà,
  l'anomalie est enregistrée, le message est créé avec l'état « non émis » et le motif
  « plafond_quotidien_atteint », visible dans l'administration.
- Écarté : supprimer ou ignorer silencieusement les messages en trop.
- Raison : le parent ne doit pas être inondé, et le responsable doit pouvoir voir ce qui n'est pas parti.

## D22 - Fournisseur de SMS
- Retenu : une interface (FournisseurSMS) choisie par réglage (SMS_FOURNISSEUR). La version
  livrée n'envoie rien : elle écrit dans le journal.
- Écarté : appeler un service de SMS directement depuis le code métier.
- Limite connue : le modèle utilisateur n'a pas de numéro de téléphone ; il faudrait l'ajouter
  avant de brancher un vrai service.

## D23 - Contenu du message
- Retenu : prénom de l'enfant, nature de l'écart et date. Ni lieu, ni heure précise, ni nom
  de famille, ni identifiant.
- Raison : un SMS peut être lu par un tiers ; il faut qu'il reste compréhensible sans
  application et sans révéler où se trouve un mineur.
  ## D24 - Qui calcule les chiffres de la synthèse
- Retenu : le code calcule les chiffres (effectif, présents, absents, anomalies par type)
  depuis la base ; le modèle ne reçoit que ces chiffres, sans nom d'élève, et ne fait que rédiger.
- Écarté : donner la liste brute des passages au modèle et lui demander de compter.
- Raison : un modèle de langage compte mal et peut inventer ; un test compare les nombres du texte
  à ceux de la base.

## D25 - Validation de la sortie du modèle
- Retenu : réponse JSON stricte {"texte": ...}, longueur bornée, tout nombre du texte doit
  appartenir aux chiffres calculés (ou à la date et à la classe), et présents et effectif
  doivent apparaître. Une seule nouvelle tentative, puis gabarit. Le chemin pris est stocké.
- Limite connue : un nombre écrit en toutes lettres ("trois") n'est pas contrôlé ; le prompt
  demande des chiffres, mais ce n'est pas une garantie.

## D26 - Coût et plafond
- Retenu : chaque appel est journalisé (modèle, tokens, coût estimé). Avant chaque appel,
  une estimation prudente est ajoutée à la dépense du jour : si elle dépasse le plafond
  configurable, aucun appel n'est fait et le gabarit est utilisé, avec un message clair.
- Limite connue : le coût est estimé avec des tarifs configurés à la main, pas lu depuis
  une facture.

## D27 - Deux demandes identiques
- Retenu : une empreinte (établissement, classe, date, chiffres) ; si une synthèse produite
  par le modèle existe déjà, elle est renvoyée sans nouvel appel.
- Raison : cliquer deux fois ne coûte pas deux fois. Si les chiffres changent, l'empreinte
  change et une nouvelle synthèse est produite.

## D28 - Classes portant le même nom
- Retenu : la synthèse choisit le premier établissement qui possède la classe demandée.
- Limite connue : avec plusieurs établissements, il faudrait choisir l'établissement ; le
  périmètre du test n'en contient qu'un.