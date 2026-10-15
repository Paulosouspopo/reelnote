"""Extraction audio, images clés et miniature avec ffmpeg/ffprobe."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..errors import PermanentError, TransientError
from ..models import MediaAssets

log = logging.getLogger(__name__)

_TIMEOUT_S = 120


@dataclass(frozen=True, slots=True)
class Probe:
    duration_s: float | None
    has_audio: bool
    has_video: bool


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True, timeout=_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise TransientError(
            "media_timeout", "Le traitement vidéo a pris trop de temps.", detail=str(exc)
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise PermanentError(
            "media_invalid", "La vidéo semble corrompue ou illisible.", detail=(exc.stderr or "")[-500:]
        ) from exc


class FfmpegMedia:
    def __init__(self, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> None:
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe

    def _cmd(self) -> list[str]:
        return [self._ffmpeg, "-nostdin", "-v", "error", "-y"]

    def probe(self, video: Path) -> Probe:
        out = _run(
            [
                self._ffprobe,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video),
            ]
        )
        data = json.loads(out.stdout or "{}")
        streams = data.get("streams", [])
        duration = data.get("format", {}).get("duration")
        return Probe(
            duration_s=float(duration) if duration not in (None, "N/A") else None,
            has_audio=any(s.get("codec_type") == "audio" for s in streams),
            has_video=any(s.get("codec_type") == "video" for s in streams),
        )

    def extract(
        self, video: Path, workdir: Path, *, keyframes: int, cover: Path | None, duration_hint: float | None
    ) -> MediaAssets:
        info = self.probe(video)
        if not info.has_video:
            raise PermanentError("no_video", "Ce contenu ne contient pas de vidéo.")
        duration = info.duration_s or duration_hint or 0.0

        audio = self._extract_audio(video, workdir) if info.has_audio else None
        frames = self._extract_keyframes(video, workdir, duration, keyframes)
        thumbnail = self._make_thumbnail(cover, video, workdir, duration)
        return MediaAssets(audio_path=audio, keyframes=frames, thumbnail_path=thumbnail)

    def _extract_audio(self, video: Path, workdir: Path) -> Path:
        out = workdir / "audio.wav"
        # Mono 16 kHz : le format attendu par Whisper
        _run(
            [*self._cmd(), "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out)]
        )
        return out

    def _extract_keyframes(self, video: Path, workdir: Path, duration: float, count: int) -> list[Path]:
        if count <= 0 or duration <= 0:
            return []
        frames: list[Path] = []
        for index in range(count):
            timestamp = duration * (index + 0.5) / count
            out = workdir / f"frame_{index:02d}.jpg"
            try:
                args = [*self._cmd(), "-ss", f"{timestamp:.2f}", "-i", str(video), "-frames:v", "1"]
                _run([*args, "-vf", "scale='min(768,iw)':-2", "-q:v", "4", str(out)])
            except PermanentError:
                log.debug("image clé ignorée", extra={"timestamp": timestamp})
                continue
            if out.exists() and out.stat().st_size > 0:
                frames.append(out)
        return frames

    def _make_thumbnail(self, cover: Path | None, video: Path, workdir: Path, duration: float) -> Path | None:
        out = workdir / "thumbnail.webp"
        sources: list[list[str]] = []
        if cover is not None:
            sources.append(["-i", str(cover)])  # la couverture choisie par l'auteur, si disponible
        sources.append(["-ss", f"{min(1.0, duration / 2):.2f}", "-i", str(video)])
        for source in sources:
            try:
                args = [*self._cmd(), *source, "-frames:v", "1", "-vf", "scale='min(480,iw)':-2"]
                _run([*args, "-c:v", "libwebp", "-quality", "80", str(out)])
            except PermanentError:
                continue
            if out.exists() and out.stat().st_size > 0:
                return out
        return None
