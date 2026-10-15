import base64

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from reelnote_worker.adapters.webpush import build_payload, vapid_key_from_raw
from reelnote_worker.config import ConfigError, Settings

BASE_ENV = {
    "DATABASE_URL": "postgresql://u:p@host:5432/postgres",
    "SUPABASE_URL": "https://abc.supabase.co/",
    "SUPABASE_SECRET_KEY": "sb_secret_x",
    "ANTHROPIC_API_KEY": "sk-ant-x",
}


def test_settings_from_env() -> None:
    settings = Settings.from_env({**BASE_ENV, "KEYFRAMES": "3"})
    assert settings.supabase_url == "https://abc.supabase.co"
    assert settings.keyframes == 3
    assert settings.push_enabled is False
    assert "sk-ant-x" not in repr(settings)  # les secrets ne fuient pas dans les logs


def test_missing_required_settings_fail_fast() -> None:
    with pytest.raises(ConfigError) as info:
        Settings.from_env({"SUPABASE_URL": "https://abc.supabase.co"})
    assert "DATABASE_URL" in str(info.value)


def test_push_enabled_with_vapid() -> None:
    settings = Settings.from_env(
        {**BASE_ENV, "VAPID_PRIVATE_KEY": "x", "VAPID_SUBJECT": "mailto:moi@example.com"}
    )
    assert settings.push_enabled


def test_vapid_raw_key_roundtrip() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    raw = key.private_numbers().private_value.to_bytes(32, "big")
    encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    restored = vapid_key_from_raw(encoded)
    assert restored.private_numbers().private_value == key.private_numbers().private_value


def test_vapid_rejects_wrong_length() -> None:
    with pytest.raises(ValueError):
        vapid_key_from_raw(base64.urlsafe_b64encode(b"short").decode())


def test_push_payload_points_to_the_card() -> None:
    payload = build_payload("1234", "Cold brew maison", "☕")  # type: ignore[arg-type]
    assert payload == {
        "title": "☕ Fiche prête",
        "body": "Cold brew maison",
        "url": "/r/1234",
        "tag": "reel-1234",
    }
