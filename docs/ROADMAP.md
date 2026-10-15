# Feuille de route

Chaque fonctionnalité est rattachée à ce qui existe déjà, pour savoir comment la construire sans rien casser.

## ✅ MVP (ce dépôt)

**Capturer**
- Partage depuis Instagram via le Raccourci iOS, ou après avoir copié un lien (presse-papiers, « Toucher le dos »)
- Ajout manuel dans l'app, y compris plusieurs liens d'un coup pour importer d'anciens reels
- Instagram (reels, publications vidéo) et YouTube Shorts
- Déduplication : repartager un reel ne crée pas de doublon ; repartager un reel en échec le relance

**Comprendre**
- Transcription locale + lecture de 5 images clés (le texte affiché à l'écran compte souvent plus que l'audio)
- Fiche typée : 🍳 recette · 💪 sport · 📍 lieu · 📚 à voir/à lire · 🛍️ produit · 💡 astuce · 🧠 apprendre · ✨ autre
- Résumé, points clés, **une action à essayer**, mots-clés
- Avertissement « À vérifier » sur les affirmations santé, nutrition ou finance discutables

**Agir**
- Statuts façon « inbox zero » : Nouveaux → À tester → Faits → Archivés
- Recette : ingrédients à cocher, **liste de courses envoyée vers Rappels** (feuille de partage iOS)
- Sport : séance prête à suivre, envoyable
- Lieu : bouton **Ouvrir dans Plans**
- Apprendre : **cartes de révision** à retourner
- Note personnelle, favoris, régénération de la fiche

**Retrouver**
- Recherche plein texte en français, insensible aux accents, sur titre, résumé, tags, légende et transcription
- Filtres par type et par statut

**Expérience**
- PWA installable, notifications push « Fiche prête », progression en temps réel, page hors ligne, mode sombre

---

## V1 : Retrouver et importer

| Fonctionnalité | Comment |
|---|---|
| **Import de l'historique Instagram** | Page « Importer » : tu déposes le fichier des enregistrements de l'export de données Instagram ; il est lu dans le navigateur, les liens partent par lots via `add_reels`. Une priorité basse dans `internal.jobs` (colonne `priority`) évite de bloquer les nouveaux partages. |
| **Collections** | Tables `collections` + `collection_reels` avec RLS ; suggestion automatique de collection par Claude à partir des tags. |
| **Recherche sémantique** | Colonne `embedding vector` (pgvector) calculée par le worker ; « le truc sur le café froid » retrouve la bonne fiche sans les bons mots. Recherche hybride : plein texte + vecteurs. |
| **Modifier les tags** | Déjà autorisé par la base (privilège par colonne), il manque l'interface. |
| **Types générés** | `supabase gen types` → clients Supabase entièrement typés dans l'app. |
| **Suivi des coûts** | Tokens déjà enregistrés par fiche → page « Ce mois-ci : 43 fiches, 0,31 € ». |
| **Supervision** | Ping du worker vers un service gratuit de surveillance (healthchecks.io) : alerte si le worker est arrêté depuis une heure. |

## V2 : Passer à l'action

| Fonctionnalité | Comment |
|---|---|
| **Carte de tes lieux** | Géocodage des lieux par le worker (OpenStreetMap / Nominatim, gratuit), colonnes `lat`/`lng`, carte Leaflet dans l'app. « Tes restos à tester autour de toi ». |
| **Digest du dimanche** | Table `user_settings` (jour, heure) ; tâche planifiée qui envoie une notification : « 5 reels cette semaine, dont 2 recettes. Tu testes laquelle ? » |
| **Le reel du jour** | Remontée d'une vieille fiche « À tester » selon un espacement croissant (répétition espacée), en notification. |
| **Widget sur l'écran d'accueil** | Sans app native : l'app gratuite **Scriptable** peut afficher un widget à partir d'une petite API JSON (`/api/widget?token=…`, jeton en lecture seule). |
| **Ajouter au calendrier** | Fichier `.ics` généré pour « planifier cette séance samedi 10 h ». |
| **Rappels en un geste** | Lien `shortcuts://run-shortcut?name=…` vers un second Raccourci qui crée directement les rappels, sans passer par la feuille de partage. |
| **Export** | Markdown, Notion, ou PDF mensuel pour ceux qui aiment le papier. |

## V3 : Partager et étendre

| Fonctionnalité | Comment |
|---|---|
| **Discuter avec sa collection** | « Qu'est-ce que j'ai sauvegardé pour un dîner végé rapide ? » : recherche vectorielle + Claude, avec citations des fiches. |
| **TikTok** | Ajout de la plateforme : résolution des liens courts côté worker, extension de `internal.canonical_url`. |
| **Collections partagées** | « Nos restos à tester » avec ton entourage : table de membres + politiques RLS associées. |
| **Créateurs** | « Tu sauvegardes souvent @untel » ; regroupement par auteur, déjà stocké (`author_handle`). |
| **Siri** | Raccourci « Qu'est-ce que j'ai à tester ? » qui interroge une petite API en lecture seule. |

## Robustesse (au fil de l'eau)

- **Rôle de base dédié au worker** avec le strict nécessaire, et clés de stockage S3 limitées au bucket des miniatures, à la place de la clé secrète.
- **Évaluations du prompt** : un jeu de 20 reels de référence avec le type attendu, rejoué à chaque changement de `PROMPT_VERSION`.
- **Sauvegardes** : export `pg_dump` hebdomadaire par GitHub Actions vers un stockage privé (l'offre gratuite Supabase n'a pas de restauration à un instant donné).
- **Limite de débit en amont** de `/api/ingest` (pare-feu Vercel) en plus de celle de la base.
- **Analyse par lots** (Batch API d'Anthropic, moins chère) pour les gros imports qui ne sont pas urgents.
