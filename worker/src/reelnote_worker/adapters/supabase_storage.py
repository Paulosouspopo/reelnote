"""Envoi et suppression des miniatures dans Supabase Storage (API HTTP)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import httpx

from ..errors import TransientError


class SupabaseStorage:
    def __init__(
        self, *, base_url: str, secret_key: str, bucket: str, client: httpx.Client | None = None
    ) -> None:
        self._base = f"{base_url.rstrip('/')}/storage/v1/object"
        self._bucket = bucket
        self._client = client or httpx.Client(timeout=30.0)
        self._headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}

    def upload(self, path: str, file: Path, content_type: str) -> str:
        url = f"{self._base}/{self._bucket}/{quote(path)}"
        try:
            response = self._client.post(
                url,
                content=file.read_bytes(),
                headers={
                    **self._headers,
                    "Content-Type": content_type,
                    "x-upsert": "true",
                    "Cache-Control": "max-age=31536000",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TransientError(
                "storage_failed", "Envoi de la miniature impossible.", detail=str(exc)
            ) from exc
        return path

    def delete(self, paths: list[str]) -> None:
        if not paths:
            return
        response = self._client.request(
            "DELETE", f"{self._base}/{self._bucket}", json={"prefixes": paths}, headers=self._headers
        )
        response.raise_for_status()
