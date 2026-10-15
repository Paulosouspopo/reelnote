"""Point d'entrée : `python -m reelnote_worker` (ou `reelnote-worker`)."""

from __future__ import annotations

import logging
import sys

from .config import ConfigError, Settings
from .logging_setup import configure_logging
from .pipeline import PipelineOptions, ReelPipeline
from .runner import Runner

log = logging.getLogger("reelnote_worker")


def build_runner(settings: Settings) -> Runner:
    # Imports ici : le démarrage échoue proprement si la config est invalide,
    # avant de charger les bibliothèques lourdes.
    from .adapters.claude import ClaudeAnalyzer
    from .adapters.ffmpeg import FfmpegMedia
    from .adapters.postgres import PostgresStore
    from .adapters.supabase_storage import SupabaseStorage
    from .adapters.whisper import WhisperTranscriber
    from .adapters.ytdlp import YtDlpDownloader
    from .ports import Notifier

    db = PostgresStore(settings.database_url.get_secret_value())
    store = SupabaseStorage(
        base_url=settings.supabase_url,
        secret_key=settings.supabase_secret_key.get_secret_value(),
        bucket="thumbnails",
    )

    notifier: Notifier | None = None
    if settings.vapid_private_key is not None and settings.vapid_subject is not None:
        from .adapters.webpush import WebPushNotifier

        notifier = WebPushNotifier(
            repo=db, private_key=settings.vapid_private_key.get_secret_value(), subject=settings.vapid_subject
        )
    else:
        log.warning("notifications push désactivées (VAPID_PRIVATE_KEY / VAPID_SUBJECT absents)")

    pipeline = ReelPipeline(
        repo=db,
        downloader=YtDlpDownloader(
            max_duration_s=settings.max_video_duration_s, cookies_file=settings.ytdlp_cookies_file
        ),
        media=FfmpegMedia(),
        transcriber=WhisperTranscriber(
            model_size=settings.whisper_model,
            compute_type=settings.whisper_compute_type,
            cpu_threads=settings.whisper_cpu_threads,
        ),
        analyzer=ClaudeAnalyzer(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.analysis_model,
            max_tokens=settings.analysis_max_tokens,
        ),
        store=store,
        notifier=notifier,
        options=PipelineOptions(keyframes=settings.keyframes),
    )

    return Runner(
        queue=db,
        repo=db,
        pipeline=pipeline,
        store=store,
        worker_id=settings.worker_id,
        poll_interval_s=settings.poll_interval_s,
        stale_job_timeout_s=settings.stale_job_timeout_s,
        maintenance_interval_s=settings.maintenance_interval_s,
        heartbeat_file=settings.heartbeat_file,
    )


def main() -> int:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        configure_logging()
        log.error(str(exc))
        return 2

    configure_logging(settings.log_level, json_output=settings.log_json)
    runner = build_runner(settings)
    runner.install_signal_handlers()
    runner.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
