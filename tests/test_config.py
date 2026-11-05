"""Configuration acceptance tests without external services."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from campus_agent.config import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    """Never read developer secrets or the real project .env."""
    import os

    for name in os.environ:
        if name.startswith("CAMPUS_AGENT_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


def test_defaults_allow_offline_initialization():
    settings = Settings()

    assert str(settings.gateway_url) == "http://localhost:8080/"
    assert settings.llm_api_key.get_secret_value() == ""
    assert settings.jwt_token.get_secret_value() == ""
    assert settings.sqlite_path == Path("data/campus_agent.sqlite3")
    assert not settings.sqlite_path.exists()
    assert not settings.chroma_path.exists()


def test_environment_overrides_dotenv(monkeypatch):
    Path(".env").write_text(
        "CAMPUS_AGENT_GATEWAY_URL=http://localhost:9000\n"
        "CAMPUS_AGENT_LLM_MODEL=example-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CAMPUS_AGENT_GATEWAY_URL", "http://127.0.0.1:8080")

    settings = Settings()

    assert str(settings.gateway_url) == "http://127.0.0.1:8080/"
    assert settings.llm_model == "example-model"


def test_secrets_are_not_exposed_in_repr_or_json(monkeypatch):
    monkeypatch.setenv("CAMPUS_AGENT_LLM_API_KEY", "unit-test-api-key")
    monkeypatch.setenv("CAMPUS_AGENT_JWT_TOKEN", "unit-test-jwt")

    settings = Settings()

    for secret in ("unit-test-api-key", "unit-test-jwt"):
        assert secret not in repr(settings)
        assert secret not in settings.model_dump_json()
    assert settings.llm_api_key.get_secret_value() == "unit-test-api-key"
    assert settings.jwt_token.get_secret_value() == "unit-test-jwt"


@pytest.mark.parametrize("field", ["gateway_url", "llm_base_url"])
def test_rejects_non_http_urls(field):
    with pytest.raises(ValidationError):
        Settings(**{field: "file:///invalid"})
