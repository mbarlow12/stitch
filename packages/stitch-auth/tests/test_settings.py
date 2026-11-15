import pytest
from pydantic import ValidationError

from stitch.auth.settings import OIDCSettings

_ENV_VARS = (
    "AUTH_ISSUER",
    "AUTH_AUDIENCE",
    "AUTH_JWKS_URI",
    "AUTH_ALGORITHMS",
    "AUTH_JWKS_CACHE_TTL",
    "AUTH_CLOCK_SKEW_SECONDS",
)


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestOIDCSettingsValidation:
    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            OIDCSettings(_env_file=None)

    def test_all_required_fields_succeeds(self):
        settings = OIDCSettings(
            issuer="https://auth.example.com/",
            audience="https://api.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
        )

        assert settings.issuer == "https://auth.example.com/"
        assert settings.audience == "https://api.example.com"
        assert settings.jwks_uri == "https://auth.example.com/.well-known/jwks.json"


class TestOIDCSettingsDefaults:
    def test_default_algorithms(self):
        settings = OIDCSettings(
            issuer="https://auth.example.com/",
            audience="aud",
            jwks_uri="https://auth.example.com/jwks",
        )
        assert settings.algorithms == ("RS256",)

    def test_default_cache_ttl(self):
        settings = OIDCSettings(
            issuer="https://auth.example.com/",
            audience="aud",
            jwks_uri="https://auth.example.com/jwks",
        )
        assert settings.jwks_cache_ttl == 600

    def test_default_clock_skew(self):
        settings = OIDCSettings(
            issuer="https://auth.example.com/",
            audience="aud",
            jwks_uri="https://auth.example.com/jwks",
        )
        assert settings.clock_skew_seconds == 30


class TestOIDCSettingsFromEnv:
    def test_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("AUTH_ISSUER", "https://auth.example.com/")
        monkeypatch.setenv("AUTH_AUDIENCE", "https://api.example.com")
        monkeypatch.setenv(
            "AUTH_JWKS_URI", "https://auth.example.com/.well-known/jwks.json"
        )
        monkeypatch.setenv("AUTH_CLOCK_SKEW_SECONDS", "60")

        settings = OIDCSettings()

        assert settings.issuer == "https://auth.example.com/"
        assert settings.audience == "https://api.example.com"
        assert settings.clock_skew_seconds == 60
