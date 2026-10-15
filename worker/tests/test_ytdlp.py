from datetime import UTC, datetime

import pytest

from reelnote_worker.adapters.ytdlp import classify_download_error, metadata_from_info
from reelnote_worker.errors import PermanentError, TransientError


@pytest.mark.parametrize(
    ("message", "code", "kind"),
    [
        (
            "ERROR: [Instagram] C1abc: Requested content is not available, "
            "rate-limit reached or login required",
            "blocked",
            TransientError,
        ),
        ("ERROR: [Instagram] C1abc: This content is private", "auth_required", PermanentError),
        ("ERROR: Unsupported URL: https://example.com", "unsupported", PermanentError),
        (
            "ERROR: [youtube] abc: Video unavailable. This video has been removed",
            "unavailable",
            PermanentError,
        ),
        ("ERROR: Connection reset by peer", "download_failed", TransientError),
    ],
)
def test_classify_download_error(message: str, code: str, kind: type) -> None:
    error = classify_download_error(message)
    assert isinstance(error, kind)
    assert error.code == code
    assert error.detail == message


def test_instagram_metadata() -> None:
    meta = metadata_from_info(
        {
            "extractor_key": "Instagram",
            "channel": "chef.paul",
            "uploader_id": "123456",
            "uploader": "Paul en cuisine",
            "description": "Recette du cold brew #cafe",
            "duration": 42,
            "timestamp": 1760000000,
        }
    )
    assert meta.author_handle == "chef.paul"
    assert meta.author_name == "Paul en cuisine"
    assert meta.duration_s == 42.0
    assert meta.posted_at == datetime.fromtimestamp(1760000000, tz=UTC)


def test_numeric_handles_are_dropped() -> None:
    meta = metadata_from_info({"extractor_key": "Instagram", "uploader_id": "123456"})
    assert meta.author_handle is None


def test_youtube_metadata() -> None:
    meta = metadata_from_info({"extractor_key": "Youtube", "uploader_id": "@chef", "channel": "Chef TV"})
    assert (meta.author_handle, meta.author_name) == ("chef", "Chef TV")
