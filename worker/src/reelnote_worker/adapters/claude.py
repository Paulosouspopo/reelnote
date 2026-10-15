"""Analyse d'un reel par Claude, en sortie structurée.

On force l'appel d'un outil dont le schéma est celui de ReelCard : la réponse
est toujours du JSON exploitable. Si la validation échoue malgré tout, on
renvoie l'erreur au modèle une fois pour qu'il corrige (boucle de réparation).
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..card import ReelCard, card_json_schema
from ..errors import PermanentError, TransientError
from ..models import AnalysisInput, AnalysisResult
from ..prompts import PROMPT_VERSION, SYSTEM_PROMPT, TOOL_NAME, build_user_text

log = logging.getLogger(__name__)

_MAX_REPAIRS = 1
_MAX_IMAGE_BYTES = 1_500_000


def _image_block(path: Path) -> dict[str, Any] | None:
    data = path.read_bytes()
    if not data or len(data) > _MAX_IMAGE_BYTES:
        return None
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.b64encode(data).decode("ascii"),
        },
    }


def build_tool() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": "Enregistre la fiche résumée du reel.",
        "input_schema": card_json_schema(),
    }


def _validation_feedback(error: ValidationError) -> str:
    problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()[:10])
    return f"La fiche ne respecte pas le schéma ({problems}). Rappelle l'outil avec une fiche corrigée."


class ClaudeAnalyzer:
    def __init__(self, *, api_key: str, model: str, max_tokens: int, client: Any = None) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=90.0)
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._tool = build_tool()

    def analyze(self, data: AnalysisInput) -> AnalysisResult:
        content: list[dict[str, Any]] = [
            block for block in (_image_block(p) for p in data.keyframes) if block is not None
        ]
        content.append({"type": "text", "text": build_user_text(data)})
        messages: list[dict[str, Any]] = [{"role": "user", "content": content}]

        input_tokens = output_tokens = 0
        for attempt in range(_MAX_REPAIRS + 1):
            response = self._call(messages)
            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens

            tool_use = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
            if tool_use is None:
                raise TransientError(
                    "analysis_failed", "L'analyse n'a pas abouti.", detail="no tool_use block"
                )

            try:
                card = ReelCard.model_validate(tool_use.input)
            except ValidationError as exc:
                if attempt >= _MAX_REPAIRS:
                    raise TransientError(
                        "analysis_invalid", "L'analyse a produit une fiche invalide.", detail=str(exc)[:500]
                    ) from exc
                log.info("fiche invalide, demande de correction", extra={"errors": exc.error_count()})
                messages.append({"role": "assistant", "content": response.content})
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "is_error": True,
                                "content": _validation_feedback(exc),
                            }
                        ],
                    }
                )
                continue

            return AnalysisResult(
                card=card,
                model=self._model,
                prompt_version=PROMPT_VERSION,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        raise AssertionError("unreachable")  # pragma: no cover

    def _call(self, messages: list[dict[str, Any]]) -> Any:
        import anthropic

        try:
            return self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=[self._tool],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=messages,
            )
        except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError) as exc:
            raise TransientError(
                "analysis_unavailable", "Le service d'analyse est indisponible.", detail=str(exc)
            ) from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise PermanentError(
                "analysis_config",
                "La clé API Claude du worker est invalide. Vérifie sa configuration.",
                detail=str(exc),
            ) from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise TransientError(
                    "analysis_unavailable", "Le service d'analyse est surchargé.", detail=str(exc)
                ) from exc
            raise PermanentError(
                "analysis_rejected", "L'analyse de ce reel a été refusée.", detail=str(exc)
            ) from exc
