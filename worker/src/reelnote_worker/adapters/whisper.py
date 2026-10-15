"""Transcription locale avec faster-whisper (gratuit, tourne sur CPU)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from ..errors import TransientError
from ..models import Transcript

log = logging.getLogger(__name__)

_MIN_WORDS = 3


class WhisperTranscriber:
    def __init__(self, *, model_size: str, compute_type: str = "int8", cpu_threads: int = 0) -> None:
        self._model_size = model_size
        self._compute_type = compute_type
        self._cpu_threads = cpu_threads
        self._model: Any = None
        self._lock = threading.Lock()

    def _get_model(self) -> Any:
        # Chargement paresseux : le modèle (≈ 500 Mo pour "small") n'est lu qu'au premier reel
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                log.info("chargement du modèle Whisper", extra={"model": self._model_size})
                self._model = WhisperModel(
                    self._model_size,
                    device="cpu",
                    compute_type=self._compute_type,
                    cpu_threads=self._cpu_threads,
                )
            return self._model

    def transcribe(self, audio: Path) -> Transcript | None:
        try:
            segments, info = self._get_model().transcribe(
                str(audio),
                vad_filter=True,  # ignore la musique et les silences : moins d'hallucinations
                beam_size=5,
                condition_on_previous_text=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except (OSError, RuntimeError) as exc:
            raise TransientError(
                "transcription_failed", "La transcription a échoué.", detail=str(exc)
            ) from exc

        if len(text.split()) < _MIN_WORDS:
            return None
        return Transcript(text=text, language=getattr(info, "language", None))
