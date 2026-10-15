"""Interfaces (ports) dont dépend le pipeline.

Le pipeline ne connaît que ces contrats ; les implémentations concrètes
(yt-dlp, ffmpeg, Whisper, Claude, Supabase…) vivent dans `adapters/`.
On peut ainsi tester toute la logique avec des doublures, et remplacer un
fournisseur (ex. un autre moteur de transcription) sans toucher au cœur.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from .models import (
    AnalysisInput,
    AnalysisResult,
    DownloadResult,
    Job,
    MediaAssets,
    PushSubscription,
    ReelSource,
    SourceMetadata,
    Stage,
    Transcript,
)


class Downloader(Protocol):
    def download(self, url: str, workdir: Path) -> DownloadResult: ...


class MediaProcessor(Protocol):
    def extract(
        self, video: Path, workdir: Path, *, keyframes: int, cover: Path | None, duration_hint: float | None
    ) -> MediaAssets: ...


class Transcriber(Protocol):
    def transcribe(self, audio: Path) -> Transcript | None: ...


class Analyzer(Protocol):
    def analyze(self, data: AnalysisInput) -> AnalysisResult: ...


class ObjectStore(Protocol):
    def upload(self, path: str, file: Path, content_type: str) -> str: ...

    def delete(self, paths: list[str]) -> None: ...


class Notifier(Protocol):
    def notify_ready(self, user_id: UUID, reel_id: UUID, title: str, emoji: str) -> None: ...


class ReelRepository(Protocol):
    def get_source(self, reel_id: UUID) -> ReelSource | None: ...

    def set_stage(self, reel_id: UUID, stage: Stage) -> None: ...

    def save_result(
        self,
        reel_id: UUID,
        *,
        metadata: SourceMetadata,
        transcript: Transcript | None,
        analysis: AnalysisResult,
        thumbnail_path: str | None,
    ) -> None: ...

    def mark_failed(self, reel_id: UUID, code: str, message: str) -> None: ...

    def mark_retrying(self, reel_id: UUID) -> None: ...

    def list_push_subscriptions(self, user_id: UUID) -> list[PushSubscription]: ...

    def delete_push_subscription(self, subscription_id: UUID) -> None: ...


class JobQueue(Protocol):
    def claim(self, worker_id: str) -> Job | None: ...

    def complete(self, job_id: int) -> None: ...

    def fail(self, job_id: int, error: str, *, retryable: bool) -> bool: ...

    def requeue_stale(self, timeout_s: int) -> int: ...

    def wait_for_jobs(self, timeout_s: float) -> None: ...

    def pop_storage_garbage(self, limit: int) -> list[tuple[int, str, str]]: ...

    def ack_storage_garbage(self, ids: list[int]) -> None: ...
