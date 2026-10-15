from uuid import uuid4

from reelnote_worker.errors import PermanentError, TransientError
from reelnote_worker.models import ReelSource
from reelnote_worker.pipeline import ReelPipeline
from reelnote_worker.runner import GENERIC_ERROR_MESSAGE, Runner

from .fakes import (
    FakeAnalyzer,
    FakeDownloader,
    FakeMedia,
    FakeQueue,
    FakeRepo,
    FakeStore,
    FakeTranscriber,
    make_job,
)


def build(downloader=None, retry_on_fail=True):
    job = make_job()
    repo = FakeRepo(
        source=ReelSource(
            id=job.reel_id,
            user_id=uuid4(),
            platform="instagram",
            external_id="C1abcDEF",
            canonical_url="https://x",
        )
    )
    queue = FakeQueue(jobs=[job], retry_on_fail=retry_on_fail)
    store = FakeStore()
    pipeline = ReelPipeline(
        repo=repo,
        downloader=downloader or FakeDownloader(),
        media=FakeMedia(),
        transcriber=FakeTranscriber(),
        analyzer=FakeAnalyzer(),
        store=store,
        notifier=None,
    )
    runner = Runner(
        queue=queue,
        repo=repo,
        pipeline=pipeline,
        store=store,
        worker_id="test",
        poll_interval_s=1,
        stale_job_timeout_s=900,
        maintenance_interval_s=300,
    )
    return runner, queue, repo, store, job


def test_success_completes_the_job() -> None:
    runner, queue, repo, _, job = build()
    assert runner.run_once() is True
    assert queue.completed == [job.id]
    assert repo.failed is None


def test_no_job_returns_false() -> None:
    runner, queue, *_ = build()
    queue.jobs.clear()
    assert runner.run_once() is False


def test_permanent_error_marks_reel_failed_with_user_message() -> None:
    error = PermanentError("too_long", "Vidéo trop longue.")
    runner, queue, repo, _, job = build(downloader=FakeDownloader(error=error))
    runner.run_once()
    assert queue.failures == [(job.id, "too_long: Vidéo trop longue.", False)]
    assert repo.failed == ("too_long", "Vidéo trop longue.")
    assert not repo.retrying


def test_transient_error_is_retried() -> None:
    error = TransientError("blocked", "Instagram bloque.")
    runner, queue, repo, *_ = build(downloader=FakeDownloader(error=error))
    runner.run_once()
    assert queue.failures[0][2] is True
    assert repo.retrying
    assert repo.failed is None


def test_transient_error_after_last_attempt_fails_the_reel() -> None:
    error = TransientError("blocked", "Instagram bloque.")
    runner, _, repo, *_ = build(downloader=FakeDownloader(error=error), retry_on_fail=False)
    runner.run_once()
    assert repo.failed == ("blocked", "Instagram bloque.")


def test_unexpected_error_never_leaks_internals_to_the_user() -> None:
    runner, _, repo, *_ = build(
        downloader=FakeDownloader(error=KeyError("secret internals")), retry_on_fail=False
    )
    runner.run_once()
    assert repo.failed == ("unexpected", GENERIC_ERROR_MESSAGE)


def test_maintenance_deletes_orphan_thumbnails() -> None:
    runner, queue, _, store, _ = build()
    queue.garbage = [(7, "thumbnails", "u/r.webp")]
    runner._maybe_maintenance()
    assert store.deleted == ["u/r.webp"]
    assert queue.acked == [7]
