"""Configuration lue depuis l'environnement, validée au démarrage (fail fast)."""

from __future__ import annotations

import os
import socket
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator


class ConfigError(RuntimeError):
    pass


class Settings(BaseModel):
    model_config = {"frozen": True}

    # Connexions
    database_url: SecretStr
    supabase_url: str
    supabase_secret_key: SecretStr
    anthropic_api_key: SecretStr

    # Analyse
    analysis_model: str = "claude-haiku-5-5"
    analysis_max_tokens: int = Field(default=2500, ge=500, le=8000)
    keyframes: int = Field(default=5, ge=0, le=10)

    # Transcription
    whisper_model: str = "small"
    whisper_compute_type: str = "int8"
    whisper_cpu_threads: int = Field(default=0, ge=0)

    # Téléchargement
    max_video_duration_s: int = Field(default=900, ge=10)
    ytdlp_cookies_file: Path | None = None

    # Notifications Web Push (optionnel)
    vapid_private_key: SecretStr | None = None
    vapid_subject: str | None = None

    # Boucle
    worker_id: str = Field(default_factory=lambda: f"{socket.gethostname()}-{os.getpid()}")
    poll_interval_s: float = Field(default=30.0, gt=0)
    stale_job_timeout_s: int = Field(default=900, ge=60)
    maintenance_interval_s: int = Field(default=300, ge=30)
    heartbeat_file: Path = Path("/tmp/reelnote-heartbeat")  # noqa: S108 - fichier local au conteneur

    # Logs
    log_level: str = "INFO"
    log_json: bool = True

    @field_validator("supabase_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        if not value.startswith("https://") and not value.startswith("http://localhost"):
            raise ValueError("SUPABASE_URL doit commencer par https://")
        return value.rstrip("/")

    @field_validator("vapid_subject")
    @classmethod
    def _check_subject(cls, value: str | None) -> str | None:
        if value and not value.startswith(("mailto:", "https://")):
            raise ValueError("VAPID_SUBJECT doit être 'mailto:toi@exemple.com' ou une URL https")
        return value

    @property
    def push_enabled(self) -> bool:
        return self.vapid_private_key is not None and self.vapid_subject is not None

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if environ is None else environ)
        values: dict[str, object] = {}
        for name in cls.model_fields:
            raw = env.get(name.upper())
            if raw is not None and raw != "":
                values[name] = raw
        try:
            return cls.model_validate(values)
        except ValidationError as exc:
            problems = ", ".join(f"{'.'.join(map(str, e['loc'])).upper()}: {e['msg']}" for e in exc.errors())
            raise ConfigError(f"Configuration invalide — {problems}") from None
