# Le Raccourci iOS « Reelnote »

Il remplace l'extension de partage d'une app native : il apparaît dans le menu Partager d'Instagram et envoie le reel à ton serveur.

Avant de commencer, dans l'app Reelnote : *Réglages* → **Créer un jeton** → copie le jeton. L'adresse d'envoi est affichée juste en dessous (`https://…vercel.app/api/ingest`).

## Création (5 minutes)

1. Ouvre l'app **Raccourcis** → **+** en haut à droite.
2. Renomme le raccourci **Reelnote** (touche le nom en haut). Choisis une icône si tu veux.
3. Touche **ⓘ** en bas → active **Afficher dans la feuille de partage**. Ferme.
4. En haut du raccourci, le bloc « Recevoir … de Feuille de partage » apparaît :
   - types acceptés : garde seulement **URL** et **Texte** ;
   - **En l'absence d'entrée** : choisis **Obtenir le presse-papiers**. Ainsi, le raccourci marche aussi après avoir *copié* un lien.
5. Ajoute l'action **Obtenir le contenu de l'URL** :
   - URL : colle l'adresse d'envoi ;
   - touche **Afficher plus** :
     - **Méthode** : `POST`
     - **En-têtes** → *Ajouter un nouvel en-tête* : clé `Authorization`, valeur `Bearer ` suivi de ton jeton (avec l'espace après Bearer) ;
     - **Corps de la requête** : `JSON` → *Ajouter un nouveau champ* → **Texte** : clé `url`, valeur : la variable **Entrée du raccourci**.
6. Ajoute l'action **Obtenir la valeur du dictionnaire** : clé `message`, dans **Contenu de l'URL**.
7. Ajoute l'action **Afficher la notification** avec la variable **Valeur du dictionnaire**.
8. Touche **OK**.

## Utilisation

- **Depuis Instagram** : sur un reel → bouton Partager (avion en papier) → fais défiler vers **Plus** si besoin → **Reelnote**. Tu peux l'épingler en tête de liste.
- **Après avoir copié un lien** : lance le raccourci depuis l'app Raccourcis ou un widget.
- **Encore plus rapide** : *Réglages iOS → Accessibilité → Toucher → Toucher le dos → Toucher deux fois → Reelnote*. Copie un lien, tape deux fois au dos de l'iPhone, c'est envoyé.
- **Importer d'anciens reels** : copie plusieurs liens à la suite (dans Notes par exemple), puis lance le raccourci : jusqu'à 25 liens d'un coup. Ou utilise le bouton **+** de l'app, qui accepte aussi plusieurs liens.

## Messages possibles

| Message | Signification |
|---|---|
| Ajouté ✓ Ta fiche sera prête dans une minute environ. | Tout va bien |
| Déjà dans ta liste : … | Ce reel a déjà une fiche |
| Jeton manquant ou mal copié… | Vérifie l'en-tête `Authorization` |
| Jeton invalide ou révoqué… | Crée un nouveau jeton dans les Réglages de l'app |
| Aucun lien de reel reconnu… | Le contenu partagé n'est pas un reel Instagram ou un YouTube Short |
| Beaucoup de reels en peu de temps… | Limite de 60 reels par heure, qui protège ton budget |

## Sécurité

Le raccourci contient ton jeton : **ne le partage pas** via un lien iCloud. Si tu perds ton iPhone, révoque le jeton dans *Réglages* depuis un autre appareil. Un jeton ne permet que d'ajouter des reels, jamais de lire tes fiches.
