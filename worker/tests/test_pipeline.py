from uuid import uuid4

import pytest

from reelnote_worker.errors import PermanentError
from reelnote_worker.models import ReelSource
from reelnote_worker.pipeline import PipelineOptions, ReelPipeline

from .fakes import (
    FakeAnalyzer,
    FakeDownloader,
    FakeMedia,
    FakeNotifier,
    FakeRepo,
    FakeStore,
    FakeTranscriber,
    make_job,
)


def build(**overrides):
    reel_id, user_id = uuid4(), uuid4()
    parts = {
        "repo": FakeRepo(
            source=ReelSource(
                id=reel_id,
                user_id=user_id,
                platform="instagram",
                external_id="C1abcDEF",
                canonical_url="https://www.instagram.com/reel/C1abcDEF/",
            )
        ),
        "downloader": FakeDownloader(),
        "media": FakeMedia(),
        "transcriber": FakeTranscriber(),
        "analyzer": FakeAnalyzer(),
        "store": FakeStore(),
        "notifier": FakeNotifier(),
    }
    parts.update(overrides)
    pipeline = ReelPipeline(**parts, options=PipelineOptions(keyframes=3))
    return pipeline, parts, make_job(reel_id)


def test_happy_path_runs_every_stage_in_order() -> None:
    pipeline, parts, job = build()
    pipeline.process(job)

    assert parts["repo"].stages == ["downloading", "extracting", "transcribing", "analyzing", "finalizing"]
    assert parts["downloader"].calls == ["https://www.instagram.com/reel/C1abcDEF/"]
    saved = parts["repo"].saved
    assert saved["analysis"].card.kind == "recipe"
    assert saved["transcript"].language == "fr"
    assert saved["thumbnail_path"] == f"{parts['repo'].source.user_id}/{job.reel_id}.webp"
    assert len(parts["analyzer"].received.keyframes) == 3
    assert parts["notifier"].sent[0][2] == "Cold brew maison en 3 étapes"


def test_video_without_audio_skips_transcription() -> None:
    pipeline, parts, job = build(media=FakeMedia(with_audio=False))
    pipeline.process(job)
    assert parts["transcriber"].calls == 0
    assert parts["repo"].saved["transcript"] is None
    assert parts["analyzer"].received.transcript is None


def test_thumbnail_failure_does_not_fail_the_card() -> None:
    pipeline, parts, job = build(store=FakeStore(fail=True))
    pipeline.process(job)
    assert parts["repo"].saved["thumbnail_path"] is None


def test_notification_failure_does_not_fail_the_card() -> None:
    pipeline, parts, job = build(notifier=FakeNotifier(fail=True))
    pipeline.process(job)
    assert parts["repo"].saved is not None


def test_deleted_reel_is_skipped() -> None:
    pipeline, parts, job = build(repo=FakeRepo(source=None))
    pipeline.process(job)
    assert parts["downloader"].calls == []


def test_errors_propagate_to_the_runner() -> None:
    error = PermanentError("unavailable", "Ce reel n'est plus disponible.")
    pipeline, parts, job = build(downloader=FakeDownloader(error=error))
    with pytest.raises(PermanentError):
        pipeline.process(job)
    assert parts["repo"].saved is None
