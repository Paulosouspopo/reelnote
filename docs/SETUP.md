# Mise en place

Compte environ 45 minutes. Tu as besoin d'un ordinateur (Windows, Linux ou Mac) pour la configuration et pour faire tourner le worker, et de ton iPhone.

Les intitulés des tableaux de bord (Supabase, Vercel…) évoluent parfois : si un libellé diffère légèrement, cherche l'équivalent le plus proche.

## Vue d'ensemble

| Étape | Où | Durée |
|---|---|---|
| 1. Dépôt GitHub | github.com | 5 min |
| 2. Base de données | supabase.com | 10 min |
| 3. Clés de notification | ton ordinateur | 2 min |
| 4. Web app | vercel.com | 5 min |
| 5. Clé Claude | console.anthropic.com | 3 min |
| 6. Worker | ton ordinateur | 10 min |
| 7. iPhone | ton iPhone | 10 min |

---

## 1. Dépôt GitHub

1. Crée un dépôt **privé** `reelnote` sur GitHub.
2. Envoie-y ce code (`git init`, `git add .`, `git commit`, `git push`).
3. Onglet **Actions** : la CI se lance. Le job « Web app » génère au premier passage les dépendances ; commite ensuite `web/package-lock.json` pour figer les versions (`cd web && npm install`).

## 2. Base de données (Supabase)

1. Crée un compte sur [supabase.com](https://supabase.com), puis un projet :
   - région **West EU (Paris)** ;
   - un mot de passe de base de données long, à garder dans ton gestionnaire de mots de passe.
2. **Appliquer le schéma** : *SQL Editor* → colle et exécute, **dans l'ordre** :
   1. `supabase/migrations/20261015000100_init.sql`
   2. `supabase/migrations/20261015000200_storage.sql`

   > Pour les migrations suivantes, la CLI est plus pratique : `npx supabase login`, `npx supabase link --project-ref <id>`, puis `npx supabase db push`.
3. **Connexion par code** : *Authentication → Emails → Magic Link* : remplace le contenu du modèle par :
   ```html
   <h2>Ton code Reelnote</h2>
   <p>Saisis ce code dans l'app : <strong>{{ .Token }}</strong></p>
   <p>Il expire dans une heure. Si tu n'as rien demandé, ignore cet e-mail.</p>
   ```
4. **Récupère** :
   - *Project Settings → API Keys* : l'URL du projet, la clé **publishable** (`sb_publishable_…`) et une clé **secret** (`sb_secret_…`) ;
   - bouton **Connect** en haut du projet → **Session pooler** : la chaîne de connexion (port 5432). C'est elle qu'utilise le worker : compatible IPv4 et avec les notifications temps réel de la file (contrairement au *Transaction pooler*, port 6543).

> ⚠️ La clé **secret** et la chaîne de connexion donnent un accès total : elles ne vont **que** dans le `.env` du worker, jamais dans Vercel ni dans Git.

## 3. Clés de notification (VAPID)

Sur ton ordinateur, avec Node.js ou Docker :

```bash
npx web-push generate-vapid-keys
# ou, sans Node : docker run --rm node:22-alpine npx -y web-push generate-vapid-keys
```

Tu obtiens une clé **publique** (pour Vercel) et une clé **privée** (pour le worker).

## 4. Web app (Vercel)

1. Crée un compte sur [vercel.com](https://vercel.com) avec ton compte GitHub.
2. *Add New → Project* → importe le dépôt `reelnote`.
3. **Root Directory** : `web`. Le framework Next.js est détecté automatiquement.
4. **Environment Variables** :

   | Nom | Valeur |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | URL du projet Supabase |
   | `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | clé `sb_publishable_…` |
   | `NEXT_PUBLIC_VAPID_PUBLIC_KEY` | clé VAPID publique |

5. **Deploy**. Note l'adresse obtenue, par exemple `https://reelnote-xxx.vercel.app`.
6. Retour dans Supabase : *Authentication → URL Configuration* → **Site URL** = cette adresse.

## 5. Clé Claude

1. Sur [console.anthropic.com](https://console.anthropic.com) : ajoute quelques euros de crédit, puis crée une clé API.
2. **Fixe un plafond de dépenses mensuel** (par exemple 5 €) dans les réglages de facturation : c'est ton filet de sécurité.

## 6. Worker

Prérequis : [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows ou Mac) ou Docker Engine (Linux).

```bash
cd worker
cp .env.example .env
# Remplis .env : DATABASE_URL, SUPABASE_URL, SUPABASE_SECRET_KEY, ANTHROPIC_API_KEY,
#                VAPID_PRIVATE_KEY, VAPID_SUBJECT (mailto:ton@email)
docker compose up -d --build
docker compose logs -f
```

Tu dois voir `worker démarré`. Au premier reel, le modèle Whisper (≈ 500 Mo) est téléchargé une seule fois, dans un volume Docker.

**Sur ton PC** : Docker Desktop peut se lancer au démarrage de l'ordinateur. Les reels partagés quand le PC est éteint attendent dans la file et sont traités à son réveil.

**Sur un VPS** (≈ 4 à 5 €/mois, 2 vCPU, 4 Go de RAM) : installe Docker, copie le dossier `worker` et le fichier `.env`, et lance les mêmes commandes. Aucun port à ouvrir.

**Mettre à jour yt-dlp** quand Instagram change quelque chose :

```bash
docker compose build --pull --no-cache && docker compose up -d
```

## 7. iPhone

1. **Installer l'app** : ouvre l'adresse Vercel dans **Safari** → bouton Partager → **Sur l'écran d'accueil**.
2. Ouvre Reelnote **depuis l'icône**, connecte-toi avec ton e-mail et le code reçu.
3. **Ferme les inscriptions** : dans Supabase, *Authentication → Sign In / Providers* → désactive **Allow new users to sign up**. Ton compte existe, plus personne d'autre ne peut en créer.
4. *Réglages* → **Activer les notifications**.
5. *Réglages* → **Créer un jeton**, copie-le, puis crée le Raccourci en suivant [SHORTCUT.md](SHORTCUT.md).
6. **Test** : dans Instagram, sur un reel → Partager → **Reelnote**. Tu dois voir « Ajouté ✓ », puis la fiche apparaît dans l'app et une notification arrive.

---

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| « Jeton manquant ou mal copié » | En-tête du Raccourci incorrect | Format exact : `Bearer rn_…` (avec l'espace) |
| La fiche reste « En attente » | Worker arrêté | `docker compose ps`, puis `docker compose logs -f` |
| Erreur `auth_required` ou `blocked` qui persiste | Instagram exige une connexion | Voir « Cookies Instagram » ci-dessous |
| Pas de notification | App ouverte depuis Safari, pas depuis l'icône | Réinstalle sur l'écran d'accueil, réactive dans Réglages |
| Le code de connexion n'arrive pas | Limite d'e-mails de l'offre gratuite Supabase | Attends quelques minutes, regarde les spams |
| « Service momentanément indisponible » | Projet Supabase en pause | Réactive-le depuis le tableau de bord Supabase |

### Cookies Instagram (seulement si nécessaire)

Certains reels ne se téléchargent qu'avec une session Instagram.

1. Idéalement avec un **compte Instagram secondaire**, connecte-toi sur instagram.com dans un navigateur d'ordinateur.
2. Exporte les cookies au format **Netscape (`cookies.txt`)** avec une extension d'export de cookies.
3. Place le fichier dans `worker/cookies.txt` (il est ignoré par Git).
4. Dans `docker-compose.yml`, décommente la ligne du volume `cookies.txt`, et dans `.env` : `YTDLP_COOKIES_FILE=/run/secrets/cookies.txt`.
5. `docker compose up -d`.

Les cookies expirent au bout de quelques semaines ; refais l'export si l'erreur revient.
