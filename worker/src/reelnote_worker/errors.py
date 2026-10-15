"""Erreurs du pipeline.

Chaque erreur porte :
  * un code stable (stocké en base, utilisable par l'app),
  * un message lisible par l'utilisateur (en français),
  * le fait qu'une nouvelle tentative a du sens ou non.
"""

from __future__ import annotations


class PipelineError(Exception):
    retryable: bool = True

    def __init__(self, code: str, user_message: str, *, detail: str | None = None) -> None:
        super().__init__(detail or user_message)
        self.code = code
        self.user_message = user_message
        self.detail = detail or user_message


class TransientError(PipelineError):
    """Problème temporaire (réseau, limite de débit…) : on réessaie plus tard."""

    retryable = True


class PermanentError(PipelineError):
    """Réessayer ne changera rien (reel privé, supprimé, trop long…)."""

    retryable = False
