"""Téléchargement via yt-dlp (Instagram, YouTube Shorts…).

Isolé derrière le port `Downloader` : c'est la brique la plus fragile
(Instagram change souvent), elle doit pouvoir être remplacée sans impact.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..errors import PermanentError, PipelineError, TransientError
from ..models import DownloadResult, SourceMetadata

_MAX_FILESIZE = 250 * 1024 * 1024
_COVER_EXTENSIONS = (".jpg", ".jpeg", ".webp", ".png")


def classify_download_error(message: str) -> PipelineError:
    """Traduit un message d'erreur yt-dlp en erreur métier."""
    text = message.lower()
    # Instagram renvoie souvent un message ambigu « rate-limit reached or login required » :
    # on réessaie d'abord (souvent temporaire), en indiquant la solution si ça persiste.
    if any(k in text for k in ("rate-limit", "rate limit", "429", "too many requests")):
        return TransientError(
            "blocked",
            "Instagram bloque temporairement l'accès. Nouvelle tentative automatique ; "
            "si ça persiste, ajoute des cookies au worker (voir docs/SETUP.md).",
            detail=message,
        )
    if any(k in text for k in ("private", "login required", "log in to", "requires authentication")):
        return PermanentError(
            "auth_required",
            "Ce reel est privé ou Instagram demande une connexion. "
            "Ajoute des cookies au worker (voir docs/SETUP.md).",
            detail=message,
        )
    if "unsupported url" in text:
        return PermanentError("unsupported", "Ce lien n'est pas pris en charge.", detail=message)
    if any(
        k in text for k in ("not available", "removed", "404", "does not exist", "unavailable", "deleted")
    ):
        return PermanentError(
            "unavailable", "Ce reel n'est plus disponible (supprimé ou restreint).", detail=message
        )
    return TransientError(
        "download_failed", "Le téléchargement a échoué, nouvelle tentative bientôt.", detail=message
    )


def _author(info: dict[str, Any], platform_hint: str) -> tuple[str | None, str | None]:
    if platform_hint == "instagram":
        handle = info.get("channel") or info.get("uploader_id")
        name = info.get("uploader")
    else:
        handle = info.get("uploader_id") or info.get("channel_id")
        name = info.get("channel") or info.get("uploader")
    handle = str(handle).lstrip("@") if handle else None
    if handle and handle.isdigit():  # identifiant numérique, inutile à l'écran
        handle = None
    return handle, (str(name) if name else None)


def metadata_from_info(info: dict[str, Any]) -> SourceMetadata:
    extractor = str(info.get("extractor_key") or info.get("extractor") or "").lower()
    platform_hint = "instagram" if "instagram" in extractor else "youtube"
    handle, name = _author(info, platform_hint)
    timestamp = info.get("timestamp")
    posted_at = datetime.fromtimestamp(timestamp, tz=UTC) if isinstance(timestamp, int | float) else None
    duration = info.get("duration")
    return SourceMetadata(
        author_handle=handle,
        author_name=name,
        caption=(info.get("description") or None),
        duration_s=float(duration) if isinstance(duration, int | float) else None,
        posted_at=posted_at,
    )


class YtDlpDownloader:
    def __init__(self, *, max_duration_s: int, cookies_file: Path | None = None) -> None:
        self._max_duration_s = max_duration_s
        self._cookies_file = cookies_file

    def _options(self, workdir: Path) -> dict[str, Any]:
        options: dict[str, Any] = {
            "outtmpl": str(workdir / "video.%(ext)s"),
            # 720p suffit largement pour quelques images clés ; économise bande passante et CPU
            "format": "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "playlist_items": "1",
            "writethumbnail": True,
            "max_filesize": _MAX_FILESIZE,
            "socket_timeout": 30,
            "retries": 3,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
        if self._cookies_file is not None:
            options["cookiefile"] = str(self._cookies_file)
        return options

    def download(self, url: str, workdir: Path) -> DownloadResult:
        import yt_dlp

        try:
            with yt_dlp.YoutubeDL(self._options(workdir)) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise PermanentError("unavailable", "Ce reel est introuvable.")
                if info.get("_type") == "playlist":  # carrousel : on prend la première vidéo
                    entries = [e for e in info.get("entries") or [] if e]
                    if not entries:
                        raise PermanentError("no_video", "Cette publication ne contient pas de vidéo.")
                    info = entries[0]

                duration = info.get("duration")
                if isinstance(duration, int | float) and duration > self._max_duration_s:
                    minutes, limit = round(duration / 60), self._max_duration_s // 60
                    raise PermanentError(
                        "too_long", f"Vidéo trop longue ({minutes} min). Limite : {limit} min."
                    )
                info = ydl.process_ie_result(info, download=True)
        except PipelineError:
            raise
        except yt_dlp.utils.DownloadError as exc:
            raise classify_download_error(str(exc)) from exc

        video = self._find_video(info, workdir)
        cover = next((p for p in sorted(workdir.iterdir()) if p.suffix.lower() in _COVER_EXTENSIONS), None)
        return DownloadResult(video_path=video, metadata=metadata_from_info(info), cover_path=cover)

    @staticmethod
    def _find_video(info: dict[str, Any], workdir: Path) -> Path:
        for item in info.get("requested_downloads") or []:
            path = item.get("filepath")
            if path and Path(path).exists():
                return Path(path)
        candidates = [
            p for p in workdir.glob("video.*") if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")
        ]
        if not candidates:
            raise PermanentError("no_video", "Aucune vidéo n'a pu être récupérée pour ce reel.")
        return max(candidates, key=lambda p: p.stat().st_size)
