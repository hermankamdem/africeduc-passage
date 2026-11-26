# Journal d'usage de l'IA

## Outils utilisés

- **Claude (assistant conversationnel d'Anthropic)** : conception, écriture du code, des
  tests, de la documentation et préparation du plan. Je l'ai utilisé pour presque toutes les
  parties du dépôt.
- **Dans le produit** : appel optionnel à l'API Anthropic pour la synthèse du jour
  (voir le README).
- **Outils vidéo** : [à renseigner : outil de voix off, sous-titres, montage...].

## Ce que je leur ai confié

[À écrire avec tes mots : architecture, modèles de données, vérification des badges,
synchronisation, anomalies, tests, rédaction. Précise ce que TOI tu as fait : choix de
Django, exécution, vérification, lecture et compréhension du code, tests à la main.]

## Ce que j'ai fait moi-même

[À écrire : par exemple, tout lancer en local, lire chaque fichier, tester les scénarios à la
main avec le navigateur coupé du réseau, changer l'heure de ma machine, etc. Ne
mentionne que ce qui est vrai.]

## Cas où j'ai refusé ou corrigé ce que l'assistant proposait

1. **Version de Django dans `requirements.txt`.** L'assistant avait écrit `django>=5.0,<6`,
   mais `pip` avait installé Django 6.1.3. Avec cette contrainte, la CI aurait installé une
   autre version que la mienne. J'ai corrigé en `django>=6.1,<7`.
2. **Commande d'activation de l'environnement virtuel.** L'assistant avait donné une commande
   Linux (`source .venv/bin/activate`) alors que je suis sur Windows : les paquets ont été
   installés globalement. J'ai réactivé avec `.venv\Scripts\activate` et réinstallé.
3. **Réglage manquant `HORLOGE_ECART_MAX_S`.** Le code de synchronisation l'utilisait, mais
   l'instruction n'avait pas fait ajouter ce réglage : 10 tests échouaient. Je l'ai ajouté à
   `settings.py` et les tests sont repassés.
4. **Indentation fausse dans `sync.py`.** Après l'intégration d'un correctif, une ligne
   était décalée : un scan avec une horloge inexploitable faisait planter la synchronisation
   au lieu d'être refusé. Le test `test_horloge_inexploitable_est_refusee` l'a détecté ; j'ai
   corrigé l'indentation.
5. **Champ placé dans la mauvaise classe.** Le champ `chemin` a été placé dans la classe des
   choix `Origine` au lieu de `Synthese`, ce qui bloquait toutes les commandes. J'ai lu
   l'erreur, compris que l'énumération n'accepte que du texte, et déplacé le champ.
6. **Gabarit collé en double.** Le gabarit de connexion avait été collé deux fois ; Django a
   signalé un bloc défini deux fois et j'ai nettoyé le fichier.

[Ajoute ici tes propres refus ou corrections de conception, s'il y en a : une proposition
que tu as changée parce qu'elle ne te convenait pas, et pourquoi. C'est ce que le jury
cherche en priorité.]

## Ce que j'ai compris et que je peux expliquer

[Une phrase par partie, avec tes mots : badge tournant, idempotence de la synchronisation,
correction d'horloge, détection d'absence, garde-fous de l'IA.]

## Production vidéo

[Outils utilisés pour la voix off, les sous-titres, le montage, la transition et l'image de
fin de la capsule.]