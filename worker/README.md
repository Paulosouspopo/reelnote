# Reelnote — worker

Transforme un reel en fiche : téléchargement (yt-dlp) → audio, images clés et
miniature (ffmpeg) → transcription (faster-whisper, local) → analyse
structurée (Claude) → enregistrement (Supabase) → notification push.

```
src/reelnote_worker/
├── __main__.py        assemblage des dépendances, démarrage
├── config.py          configuration validée au démarrage
├── runner.py          boucle : LISTEN/NOTIFY, retries, maintenance, arrêt propre
├── pipeline.py        les étapes d'un reel (ne dépend que des ports)
├── ports.py           interfaces : Downloader, Transcriber, Analyzer…
├── card.py            schéma de la fiche (contrat avec l'app)
├── prompts.py         prompt versionné
└── adapters/          implémentations : yt-dlp, ffmpeg, whisper, claude, postgres, storage, webpush
```

## Lancer

```bash
cp .env.example .env      # remplir
docker compose up -d --build
docker compose logs -f
```

## Développer

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check . && mypy src
```

## Principes

- **Aucune connexion entrante** : le worker va chercher le travail en base. Il peut tourner derrière une box, sans port ouvert.
- **Idempotent** : retraiter un reel réécrit la même fiche. Un worker tué en plein job est récupéré automatiquement.
- **Erreurs typées** : `PermanentError` (inutile de réessayer) ou `TransientError` (backoff exponentiel : 30 s, 2 min, 8 min).
- **Aucune vidéo conservée** : tout passe par un dossier temporaire supprimé à la fin.
- **Prompt versionné** : chaque fiche garde `analysis_version` pour pouvoir être régénérée.
