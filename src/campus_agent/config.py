"""Environment-based configuration; importing this module performs no I/O."""

from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load process environment before .env; secrets are hidden in repr."""

    model_config = SettingsConfigDict(
        env_prefix="CAMPUS_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    llm_base_url: AnyHttpUrl = AnyHttpUrl("https://api.openai.com/v1")
    llm_model: str = ""
    gateway_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8080")
    jwt_token: SecretStr = Field(default=SecretStr(""), repr=False)
    sqlite_path: Path = Path("data/campus_agent.sqlite3")
    chroma_path: Path = Path("data/chroma")
