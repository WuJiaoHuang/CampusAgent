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
    llm_disable_thinking: bool = True
    gateway_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8080")
    jwt_token: SecretStr = Field(default=SecretStr(""), repr=False)
    sqlite_path: Path = Path("data/campus_agent.sqlite3")
    chroma_path: Path = Path("data/chroma")
    http_timeout_seconds: float = 10.0
    knowledge_dir: Path = Path("knowledge")
    vector_db_path: Path = Path("data/chroma")
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    model_cache_dir: Path = Path("data/models")
    embedding_batch_size: int = 16
    jwt_secret: SecretStr = Field(default=SecretStr(""), repr=False)
    jwt_algorithm: str = "HS512"
    max_tool_calls_per_request: int = 4
