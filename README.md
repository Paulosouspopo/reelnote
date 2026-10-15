# Reelnote

Tu vois un reel intéressant, tu le partages au Raccourci « Reelnote » depuis Instagram, et une minute plus tard tu reçois une **fiche claire et actionnable** : une recette avec sa liste de courses, une séance de sport, une adresse à ouvrir dans Plans, des livres à lire, des cartes de révision…

```
Instagram ─► Raccourci iOS ─► /api/ingest (Vercel) ─► Supabase (Postgres) ◄─► Worker (Docker)
                                                           │                  yt-dlp · ffmpeg
                                    PWA sur l'iPhone ◄─────┘                  Whisper · Claude
                                    (temps réel + notifications push)
```

## Contenu du dépôt

| Dossier | Rôle |
|---|---|
| [`supabase/`](supabase) | Schéma, sécurité (RLS), file de jobs, RPC, et tests SQL |
| [`worker/`](worker) | Traitement des reels : téléchargement, transcription, analyse par Claude, notifications |
| [`web/`](web) | Application installable (PWA) en Next.js : fiches, recherche, réglages, API d'ingestion |
| [`docs/`](docs) | Architecture, mise en place pas à pas, Raccourci iOS, feuille de route |

## Documentation

1. **[Architecture](docs/ARCHITECTURE.md)** : comment tout s'emboîte, et pourquoi.
2. **[Mise en place](docs/SETUP.md)** : de zéro à la première fiche, environ 45 minutes.
3. **[Raccourci iOS](docs/SHORTCUT.md)** : le partage depuis Instagram.
4. **[Feuille de route](docs/ROADMAP.md)** : toutes les fonctionnalités prévues, phase par phase.

## Coût

0 € de frais fixes si le worker tourne sur ton ordinateur (environ 5 €/mois sur un petit VPS), plus l'analyse par Claude Haiku : de l'ordre d'un centime ou moins par reel. Détail dans [ARCHITECTURE.md](docs/ARCHITECTURE.md#coûts).

## Commandes utiles

```bash
# Base de données : migrations + tests de sécurité sur un Postgres local
PGURL=postgres://postgres:postgres@localhost:5432/postgres ./supabase/tests/run.sh

# Worker
cd worker && pip install -e ".[dev]" && pytest && ruff check . && mypy src
cd worker && docker compose up -d --build

# Web
cd web && npm install && npm run dev
cd web && npm run lint && npm run typecheck && npm test && npm run build
```
