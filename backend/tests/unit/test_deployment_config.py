"""Behaviour needed for hosted deployments (e.g. Render): URL schemes, demo mode, key handling."""

import sys

import pytest
from pydantic import ValidationError

from app.core import identifiers
from app.core.config import Settings, get_settings

STRONG = {
    "identifier_hmac_key": "h" * 48,
    "identifier_encryption_key": "Zm9vYmFy+/base64-with/slashes=",  # not a Fernet key
    "cookie_secure": True,
}


def make(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite:///./x.db", "sqlite:///./x.db"),
    ],
)
def test_database_url_scheme_is_normalised(given: str, expected: str):
    assert make(database_url=given).database_url == expected


def test_demo_mode_defaults_and_override():
    assert make(app_env="development").is_demo is True
    assert make(app_env="production", **STRONG).is_demo is False
    assert make(app_env="production", demo_mode=True, **STRONG).is_demo is True


def test_production_still_requires_real_keys_and_secure_cookies():
    with pytest.raises(ValidationError):
        make(app_env="production", demo_mode=True)
    with pytest.raises(ValidationError):
        make(app_env="production", **{**STRONG, "cookie_secure": False})


def test_any_secret_works_as_encryption_key(monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "identifier_encryption_key", STRONG["identifier_encryption_key"])
    token = identifiers.encrypt_identifier("DEMO-APAAR-000123")
    assert identifiers.decrypt_identifier(token) == "DEMO-APAAR-000123"
    monkeypatch.setattr(settings, "identifier_encryption_key", "a different secret")
    assert identifiers.decrypt_identifier(token) is None


def test_seed_if_empty_skips_existing_data(monkeypatch, capsys):
    from app import seed

    monkeypatch.setattr(sys, "argv", ["seed", "--if-empty"])
    seed.main()
    assert "skipping" in capsys.readouterr().out


def test_seed_refuses_without_demo_mode(monkeypatch):
    from app import seed

    monkeypatch.setattr(get_settings(), "demo_mode", False)
    monkeypatch.setattr(sys, "argv", ["seed", "--reset"])
    with pytest.raises(SystemExit):
        seed.main()
