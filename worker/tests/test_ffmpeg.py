"""Test d'intégration : vraie vidéo générée par ffmpeg (ignoré si ffmpeg absent)."""

import shutil
import subprocess

import pytest

from reelnote_worker.adapters.ffmpeg import FfmpegMedia
from reelnote_worker.errors import PermanentError

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg non installé")


def make_video(path, *, audio: bool) -> None:
    args = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=4:size=640x1136:rate=24",
    ]
    if audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-shortest"]
    args += ["-pix_fmt", "yuv420p", str(path)]
    subprocess.run(args, check=True)


def test_extracts_audio_keyframes_and_thumbnail(tmp_path) -> None:
    video = tmp_path / "video.mp4"
    make_video(video, audio=True)

    assets = FfmpegMedia().extract(video, tmp_path, keyframes=3, cover=None, duration_hint=None)

    assert assets.audio_path is not None and assets.audio_path.stat().st_size > 0
    assert len(assets.keyframes) == 3
    assert all(frame.stat().st_size > 0 for frame in assets.keyframes)
    assert assets.thumbnail_path is not None
    assert assets.thumbnail_path.read_bytes()[8:12] == b"WEBP"


def test_silent_video_has_no_audio(tmp_path) -> None:
    video = tmp_path / "video.mp4"
    make_video(video, audio=False)
    assets = FfmpegMedia().extract(video, tmp_path, keyframes=2, cover=None, duration_hint=None)
    assert assets.audio_path is None
    assert len(assets.keyframes) == 2


def test_corrupted_file_is_a_permanent_error(tmp_path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"not a video at all")
    with pytest.raises(PermanentError):
        FfmpegMedia().extract(video, tmp_path, keyframes=2, cover=None, duration_hint=None)
