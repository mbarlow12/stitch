from pathlib import Path

import pytest
from pydantic import SecretStr, TypeAdapter, ValidationError

from stitch.api.settings import OriginUrl, PostgresConfig, Settings, SqliteConfig


class TestPostgresConfig:
    def test_to_url_format(self):
        config = PostgresConfig(
            host="localhost",
            port=5432,
            db="testdb",
            user="testuser",
            password=SecretStr("testpass"),
        )

        url = config.to_url()

        assert url.drivername == "postgresql+psycopg"
        assert url.host == "localhost"
        assert url.port == 5432
        assert url.database == "testdb"
        assert url.username == "testuser"

    def test_to_url_uses_secret_password(self):
        config = PostgresConfig(
            host="localhost",
            port=5432,
            db="testdb",
            user="testuser",
            password=SecretStr("secret123"),
        )

        url = config.to_url()

        assert url.password == "secret123"

    def test_to_sync_url_matches_postgres_driver(self):
        config = PostgresConfig(
            host="localhost",
            port=5432,
            db="testdb",
            user="testuser",
            password=SecretStr("testpass"),
        )

        url = config.to_sync_url()

        assert url.drivername == "postgresql+psycopg"

    def test_defaults(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_DB", "postgres")
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_PORT", "5432")
        monkeypatch.setenv("POSTGRES_USER", "postgres")
        config = PostgresConfig()

        assert config.host == "localhost"
        assert config.port == 5432
        assert config.db == "postgres"
        assert config.user == "postgres"


class TestSqliteConfig:
    def test_to_url_memory(self):
        config = SqliteConfig(db_path=None)

        url = config.to_url()

        assert url.drivername == "sqlite+aiosqlite"
        assert url.database == ":memory:"

    def test_to_url_file(self, tmp_path: Path):
        db_file = tmp_path / "test.db"
        config = SqliteConfig(db_path=db_file)

        url = config.to_url()

        assert url.drivername == "sqlite+aiosqlite"
        assert url.database == str(db_file)

    def test_to_sync_url_uses_pysqlite(self, tmp_path: Path):
        db_file = tmp_path / "test.db"
        config = SqliteConfig(db_path=db_file)

        url = config.to_sync_url()

        assert url.drivername == "sqlite+pysqlite"
        assert url.database == str(db_file)


class TestOriginUrlValidation:
    def test_valid_origin_url(self):
        adapter = TypeAdapter(OriginUrl)

        result = adapter.validate_python("http://localhost:3000")

        assert str(result) == "http://localhost:3000/"

    def test_valid_origin_url_with_trailing_slash(self):
        adapter = TypeAdapter(OriginUrl)

        result = adapter.validate_python("http://localhost:3000/")

        assert str(result) == "http://localhost:3000/"

    def test_rejects_url_with_path(self):
        adapter = TypeAdapter(OriginUrl)

        with pytest.raises(ValidationError, match="URL must be an origin with no path"):
            adapter.validate_python("http://localhost:3000/api/v1")

    def test_rejects_url_with_query_string(self):
        adapter = TypeAdapter(OriginUrl)

        with pytest.raises(
            ValidationError, match="URL must be an origin with no query string"
        ):
            adapter.validate_python("http://localhost:3000?foo=bar")

    def test_rejects_url_with_fragment(self):
        adapter = TypeAdapter(OriginUrl)

        with pytest.raises(
            ValidationError, match="URL must be an origin with no fragment"
        ):
            adapter.validate_python("http://localhost:3000#section")


class TestSettings:
    def test_get_database_url_postgres_dialect(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_HOST", "pghost")
        monkeypatch.setenv("POSTGRES_DB", "pgdb")

        settings = Settings(dialect="postgresql")
        url = settings.get_database_url()

        assert url.drivername == "postgresql+psycopg"
        assert url.host == "pghost"
        assert url.database == "pgdb"

    def test_get_database_url_sqlite_dialect(self):
        settings = Settings(dialect="sqlite")

        url = settings.get_database_url()

        assert url.drivername == "sqlite+aiosqlite"
        assert url.database == ":memory:"

    def test_get_sync_database_url_sqlite_dialect(self):
        settings = Settings(dialect="sqlite")

        url = settings.get_sync_database_url()

        assert url.drivername == "sqlite+pysqlite"
        assert url.database == ":memory:"

    def test_get_sync_database_url_postgres_dialect(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_HOST", "pghost")
        monkeypatch.setenv("POSTGRES_DB", "pgdb")

        settings = Settings(dialect="postgresql")
        url = settings.get_sync_database_url()

        assert url.drivername == "postgresql+psycopg"
        assert url.host == "pghost"
        assert url.database == "pgdb"

    def test_default_dialect_is_postgresql(self):
        settings = Settings()

        assert settings.dialect == "postgresql"

    def test_default_environment_is_dev(self):
        settings = Settings()

        assert settings.environment == "dev"

    def test_environment_name_normalizes_case_and_whitespace(self):
        settings = Settings(environment=" PR-8 ")

        assert settings.environment == " PR-8 "
        assert settings.environment_name == "pr-8"

    def test_is_prod_for_prod(self):
        settings = Settings(environment="prod")

        assert settings.is_prod is True

    def test_is_prod_for_production(self):
        settings = Settings(environment="production")

        assert settings.is_prod is True

    def test_allows_disabled_auth_for_pr(self):
        settings = Settings(environment="PR-8", auth_disabled=True)

        assert settings.allows_disabled_auth is True

    def test_allows_disabled_auth_for_next_is_false(self):
        settings = Settings(environment="next", auth_disabled=True)

        assert settings.allows_disabled_auth is False

    def test_default_frontend_origin_url(self, monkeypatch):
        monkeypatch.delenv("FRONTEND_ORIGIN_URL", raising=False)
        settings = Settings(_env_file=None)

        assert str(settings.frontend_origin_url) == "http://localhost:3000/"

    @pytest.mark.parametrize("ratio", [-0.1, 1.5])
    def test_otel_sample_ratio_out_of_range_is_rejected(self, ratio):
        with pytest.raises(ValidationError):
            Settings(otel_sample_ratio=ratio)
