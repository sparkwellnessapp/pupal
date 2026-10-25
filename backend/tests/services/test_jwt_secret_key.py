"""The JWT signing key has no production fallback (2026-10-25).

Production never set JWT_SECRET_KEY, so every session was signed with a literal that
sits in a public repo — anyone could mint a token for any teacher. Outside development
a missing, published or short key must stop the service, never fall back.
"""
import pytest
from pydantic import SecretStr

from app.config import settings
from app.services import auth_service


def _resolve(monkeypatch, app_env, key):
    monkeypatch.setattr(settings, "app_env", app_env)
    monkeypatch.setattr(settings, "jwt_secret_key", SecretStr(key) if key is not None else None)
    return auth_service._resolve_secret_key()


@pytest.mark.parametrize("key", [None, "", "your-super-secret-key-change-in-production", "short"])
def test_production_refuses_a_missing_published_or_short_key(monkeypatch, key):
    with pytest.raises(RuntimeError):
        _resolve(monkeypatch, "production", key)


def test_an_unknown_app_env_is_production(monkeypatch):
    with pytest.raises(RuntimeError):
        _resolve(monkeypatch, "staging", None)


def test_production_uses_a_real_key(monkeypatch):
    key = "x" * 64
    assert _resolve(monkeypatch, "production", key) == key


def test_development_may_fall_back_but_never_to_the_published_literal(monkeypatch):
    got = _resolve(monkeypatch, "development", None)
    assert got and got not in auth_service._PUBLISHED_SECRETS
