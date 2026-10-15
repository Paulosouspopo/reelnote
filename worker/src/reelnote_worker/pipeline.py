"""Pipeline de traitement d'un reel.

    télécharger → extraire (audio, images clés, miniature) → transcrire
    → analyser avec Claude → enregistrer → notifier

Les fichiers temporaires vivent dans un dossier jetable, supprimé à la fin
quoi qu'il arrive : aucune vidéo n'est conservée.
"""

from __future__ import annotations

import logging
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from .models import AnalysisInput, Job, Stage
from .ports import Analyzer, Downloader, MediaProcessor, Notifier, ObjectStore, ReelRepository, Transcriber

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineOptions:
    keyframes: int = 5
    thumbnails_enabled: bool = True


class ReelPipeline:
    def __init__(
        self,
        *,
        repo: ReelRepository,
        downloader: Downloader,
        media: MediaProcessor,
        transcriber: Transcriber,
        analyzer: Analyzer,
        store: ObjectStore,
        notifier: Notifier | None,
        options: PipelineOptions | None = None,
    ) -> None:
        self._repo = repo
        self._downloader = downloader
        self._media = media
        self._transcriber = transcriber
        self._analyzer = analyzer
        self._store = store
        self._notifier = notifier
        self._options = options or PipelineOptions()

    def process(self, job: Job) -> None:
        source = self._repo.get_source(job.reel_id)
        if source is None:
            log.info("reel supprimé avant traitement, job ignoré", extra={"reel_id": str(job.reel_id)})
            return

        ctx = {"reel_id": str(source.id), "job_id": job.id, "attempt": job.attempts}
        started = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="reelnote-") as tmp:
            workdir = Path(tmp)

            self._stage(source.id, "downloading", ctx)
            download = self._downloader.download(source.canonical_url, workdir)

            self._stage(source.id, "extracting", ctx)
            assets = self._media.extract(
                download.video_path,
                workdir,
                keyframes=self._options.keyframes,
                cover=download.cover_path,
                duration_hint=download.metadata.duration_s,
            )
            thumbnail_path = self._upload_thumbnail(source.user_id, source.id, assets.thumbnail_path, ctx)

            self._stage(source.id, "transcribing", ctx)
            transcript = self._transcriber.transcribe(assets.audio_path) if assets.audio_path else None

            self._stage(source.id, "analyzing", ctx)
            analysis = self._analyzer.analyze(
                AnalysisInput(
                    platform=source.platform,
                    metadata=download.metadata,
                    transcript=transcript,
                    keyframes=assets.keyframes,
                )
            )

            self._stage(source.id, "finalizing", ctx)
            self._repo.save_result(
                source.id,
                metadata=download.metadata,
                transcript=transcript,
                analysis=analysis,
                thumbnail_path=thumbnail_path,
            )

        log.info(
            "fiche prête",
            extra={
                **ctx,
                "kind": analysis.card.kind,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "input_tokens": analysis.input_tokens,
                "output_tokens": analysis.output_tokens,
            },
        )
        self._notify(source.user_id, source.id, analysis.card.title, analysis.card.emoji, ctx)

    # -- étapes secondaires : ne doivent jamais faire échouer la fiche ----------

    def _stage(self, reel_id: UUID, stage: Stage, ctx: dict[str, object]) -> None:
        log.info("étape", extra={**ctx, "stage": stage})
        self._repo.set_stage(reel_id, stage)

    def _upload_thumbnail(
        self, user_id: UUID, reel_id: UUID, local: Path | None, ctx: dict[str, object]
    ) -> str | None:
        if local is None or not self._options.thumbnails_enabled:
            return None
        try:
            return self._store.upload(f"{user_id}/{reel_id}.webp", local, "image/webp")
        except Exception:
            log.warning("miniature non envoyée", exc_info=True, extra=ctx)
            return None

    def _notify(self, user_id: UUID, reel_id: UUID, title: str, emoji: str, ctx: dict[str, object]) -> None:
        if self._notifier is None:
            return
        try:
            self._notifier.notify_ready(user_id, reel_id, title, emoji)
        except Exception:
            log.warning("notification non envoyée", exc_info=True, extra=ctx)
