"""Doublures des ports, partagées par les tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from reelnote_worker.card import ReelCard
from reelnote_worker.models import (
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

SAMPLE_CARD: dict[str, Any] = {
    "title": "Cold brew maison en 3 étapes",
    "emoji": "☕",
    "tldr": "Un café infusé à froid, doux et peu acide, prêt en 12 heures.",
    "key_points": ["Mouture grossière", "Ratio 1:8", "12 h au frigo"],
    "action": "Lancer une infusion ce soir pour demain matin",
    "tags": ["café", "boisson"],
    "source_language": "fr",
    "caution": None,
    "details": {
        "kind": "recipe",
        "servings": 4,
        "prep_minutes": 5,
        "ingredients": [
            {"name": "café moulu grossièrement", "quantity": "100 g"},
            {"name": "eau froide", "quantity": "800 ml"},
        ],
        "steps": ["Mélanger le café et l'eau", "Laisser infuser 12 h au frigo", "Filtrer"],
    },
}


def make_card(**overrides: Any) -> ReelCard:
    return ReelCard.model_validate({**SAMPLE_CARD, **overrides})


def make_job(reel_id: UUID | None = None) -> Job:
    return Job(id=1, reel_id=reel_id or uuid4(), attempts=1, max_attempts=4)


@dataclass
class FakeRepo:
    source: ReelSource | None = None
    stages: list[Stage] = field(default_factory=list)
    saved: dict[str, Any] | None = None
    failed: tuple[str, str] | None = None
    retrying: bool = False
    subscriptions: list[PushSubscription] = field(default_factory=list)
    deleted_subscriptions: list[UUID] = field(default_factory=list)

    def get_source(self, reel_id: UUID) -> ReelSource | None:
        return self.source

    def set_stage(self, reel_id: UUID, stage: Stage) -> None:
        self.stages.append(stage)

    def save_result(self, reel_id: UUID, **kwargs: Any) -> None:
        self.saved = {"reel_id": reel_id, **kwargs}

    def mark_failed(self, reel_id: UUID, code: str, message: str) -> None:
        self.failed = (code, message)

    def mark_retrying(self, reel_id: UUID) -> None:
        self.retrying = True

    def list_push_subscriptions(self, user_id: UUID) -> list[PushSubscription]:
        return self.subscriptions

    def delete_push_subscription(self, subscription_id: UUID) -> None:
        self.deleted_subscriptions.append(subscription_id)


@dataclass
class FakeDownloader:
    error: Exception | None = None
    calls: list[str] = field(default_factory=list)

    def download(self, url: str, workdir: Path) -> DownloadResult:
        self.calls.append(url)
        if self.error:
            raise self.error
        video = workdir / "video.mp4"
        video.write_bytes(b"fake")
        return DownloadResult(
            video_path=video,
            metadata=SourceMetadata(author_handle="chef", caption="Le meilleur cold brew", duration_s=42.0),
        )


@dataclass
class FakeMedia:
    with_audio: bool = True

    def extract(
        self, video: Path, workdir: Path, *, keyframes: int, cover: Path | None, duration_hint: float | None
    ) -> MediaAssets:
        thumb = workdir / "thumbnail.webp"
        thumb.write_bytes(b"img")
        frames = []
        for i in range(keyframes):
            frame = workdir / f"frame_{i}.jpg"
            frame.write_bytes(b"jpg")
            frames.append(frame)
        audio = workdir / "audio.wav" if self.with_audio else None
        return MediaAssets(audio_path=audio, keyframes=frames, thumbnail_path=thumb)


@dataclass
class FakeTranscriber:
    calls: int = 0

    def transcribe(self, audio: Path) -> Transcript | None:
        self.calls += 1
        return Transcript(text="Aujourd'hui je vous montre mon cold brew", language="fr")


@dataclass
class FakeAnalyzer:
    error: Exception | None = None
    received: AnalysisInput | None = None

    def analyze(self, data: AnalysisInput) -> AnalysisResult:
        self.received = data
        if self.error:
            raise self.error
        return AnalysisResult(
            card=make_card(), model="fake-model", prompt_version="test", input_tokens=1000, output_tokens=300
        )


@dataclass
class FakeStore:
    fail: bool = False
    uploaded: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def upload(self, path: str, file: Path, content_type: str) -> str:
        if self.fail:
            raise RuntimeError("storage down")
        self.uploaded.append(path)
        return path

    def delete(self, paths: list[str]) -> None:
        self.deleted.extend(paths)


@dataclass
class FakeNotifier:
    fail: bool = False
    sent: list[tuple[UUID, UUID, str]] = field(default_factory=list)

    def notify_ready(self, user_id: UUID, reel_id: UUID, title: str, emoji: str) -> None:
        if self.fail:
            raise RuntimeError("push down")
        self.sent.append((user_id, reel_id, title))


@dataclass
class FakeQueue:
    jobs: list[Job] = field(default_factory=list)
    completed: list[int] = field(default_factory=list)
    failures: list[tuple[int, str, bool]] = field(default_factory=list)
    retry_on_fail: bool = True
    garbage: list[tuple[int, str, str]] = field(default_factory=list)
    acked: list[int] = field(default_factory=list)

    def claim(self, worker_id: str) -> Job | None:
        return self.jobs.pop(0) if self.jobs else None

    def complete(self, job_id: int) -> None:
        self.completed.append(job_id)

    def fail(self, job_id: int, error: str, *, retryable: bool) -> bool:
        self.failures.append((job_id, error, retryable))
        return retryable and self.retry_on_fail

    def requeue_stale(self, timeout_s: int) -> int:
        return 0

    def wait_for_jobs(self, timeout_s: float) -> None:
        return None

    def pop_storage_garbage(self, limit: int) -> list[tuple[int, str, str]]:
        return list(self.garbage)

    def ack_storage_garbage(self, ids: list[int]) -> None:
        self.acked.extend(ids)
