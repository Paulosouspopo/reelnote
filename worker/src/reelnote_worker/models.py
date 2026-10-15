"""Objets de données échangés entre les étapes du pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from .card import ReelCard

Stage = Literal["downloading", "extracting", "transcribing", "analyzing", "finalizing"]


@dataclass(frozen=True, slots=True)
class Job:
    id: int
    reel_id: UUID
    attempts: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class ReelSource:
    id: UUID
    user_id: UUID
    platform: str
    external_id: str
    canonical_url: str


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    author_handle: str | None = None
    author_name: str | None = None
    caption: str | None = None
    duration_s: float | None = None
    posted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DownloadResult:
    video_path: Path
    metadata: SourceMetadata
    cover_path: Path | None = None


@dataclass(frozen=True, slots=True)
class MediaAssets:
    audio_path: Path | None
    keyframes: list[Path] = field(default_factory=list)
    thumbnail_path: Path | None = None


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: str | None


@dataclass(frozen=True, slots=True)
class AnalysisInput:
    platform: str
    metadata: SourceMetadata
    transcript: Transcript | None
    keyframes: list[Path]


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    card: ReelCard
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class PushSubscription:
    id: UUID
    endpoint: str
    p256dh: str
    auth: str
