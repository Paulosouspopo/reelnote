"""Notifications Web Push (« Ta fiche est prête »)."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric import ec

from ..ports import ReelRepository

log = logging.getLogger(__name__)


def vapid_key_from_raw(raw_b64url: str) -> ec.EllipticCurvePrivateKey:
    """Convertit la clé privée VAPID brute (format de `npx web-push generate-vapid-keys`)."""
    padded = raw_b64url + "=" * (-len(raw_b64url) % 4)
    raw = base64.urlsafe_b64decode(padded)
    if len(raw) != 32:
        raise ValueError("VAPID_PRIVATE_KEY doit être une clé brute de 32 octets encodée en base64url")
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())


def build_payload(reel_id: UUID, title: str, emoji: str) -> dict[str, Any]:
    return {
        "title": f"{emoji} Fiche prête".strip(),
        "body": title,
        "url": f"/r/{reel_id}",
        "tag": f"reel-{reel_id}",
    }


class WebPushNotifier:
    def __init__(self, *, repo: ReelRepository, private_key: str, subject: str) -> None:
        from py_vapid import Vapid

        self._repo = repo
        self._vapid = Vapid(private_key=vapid_key_from_raw(private_key))
        self._claims = {"sub": subject}

    def notify_ready(self, user_id: UUID, reel_id: UUID, title: str, emoji: str) -> None:
        from pywebpush import WebPushException, webpush

        payload = json.dumps(build_payload(reel_id, title, emoji), ensure_ascii=False)
        for sub in self._repo.list_push_subscriptions(user_id):
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=self._vapid,
                    vapid_claims=dict(self._claims),
                    ttl=24 * 3600,
                    timeout=10,
                )
            except WebPushException as exc:
                status = getattr(exc.response, "status_code", None)
                if status in (404, 410):  # abonnement expiré ou révoqué : on nettoie
                    self._repo.delete_push_subscription(sub.id)
                    log.info("abonnement push expiré supprimé", extra={"subscription_id": str(sub.id)})
                else:
                    log.warning("échec d'envoi push", extra={"status": status})
