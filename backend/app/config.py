"""Application configuration loaded from environment variables / a .env file.

Settings are read with ``pydantic-settings``. Environment variable names are
matched case-insensitively, so ``DASHSCOPE_API_KEY`` populates
``dashscope_api_key`` and so on.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# ``config.py`` lives at ``backend/app/config.py`` so the project root
# (``memoria/``) is three levels up. Resolving the ``.env`` path from the file
# location keeps configuration loading independent of the current working
# directory (e.g. whether uvicorn is started from ``backend/`` or the repo root).
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
ENV_FILE: Path = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Defaults are provided so the application (and its ``/health`` endpoint) can
    start even when no ``.env`` file is present, which is convenient for local
    smoke tests and CI. Real deployments should supply proper values.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    dashscope_api_key: str = ""
    # Alternate secret name used by some Cursor environments.
    qwen_dashscope_api: str = ""
    # Optional DashScope endpoint override. Leave empty for the SDK default
    # (Beijing); set to the international endpoint for intl-region keys, e.g.
    # https://dashscope-intl.aliyuncs.com/api/v1
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/api/v1"

    # --- Provider-agnostic LLM settings (any OpenAI-compatible API) ---------
    # ``openai`` (any OpenAI-compatible endpoint) or ``dashscope`` (native SDK).
    # Empty means: ``openai`` when LLM_BASE_URL is set, otherwise ``dashscope``.
    llm_provider: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_chat_model: str = ""
    llm_fast_model: str = ""
    llm_embedding_model: str = ""
    # Comma separated chat models shown in the model switcher.
    llm_chat_models: str = ""
    # Send ``dimensions`` with embedding requests (OpenAI text-embedding-3-*).
    llm_embedding_send_dimensions: bool = False
    llm_timeout_seconds: float = 120.0
    # Expected embedding vector length. Must match the pgvector column.
    embedding_dim: int = 1024
    database_url: str = "postgresql+asyncpg://user:pass@localhost/memoria"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "supersecret"
    # Fixed token guarding destructive demo endpoints (e.g. DELETE /api/memories).
    demo_api_token: str = "memoria-demo-token"
    # ``dev`` or ``production``. Outside dev the default SECRET_KEY is refused.
    environment: str = "dev"
    # Access token lifetime for JWTs issued by /auth/login and /auth/signup.
    access_token_ttl_minutes: int = 60 * 24
    # Enforce the legacy X-API-Token guard on destructive routes. Empty means
    # enabled in dev and disabled elsewhere (JWT is always required).
    allow_demo_token: bool | None = None
    # Per-user requests per minute on LLM-backed routes (0 disables).
    rate_limit_per_min: int = 30
    # Per-user estimated LLM tokens per UTC day (0 disables).
    daily_token_cap: int = 200_000


DEFAULT_SECRET_KEY = "supersecret"


def is_dev(settings: Settings) -> bool:
    return settings.environment.strip().lower() in {"dev", "development", "local", "test"}


def demo_token_enabled(settings: Settings) -> bool:
    """Whether the X-API-Token demo guard applies (default: only in dev)."""

    if settings.allow_demo_token is not None:
        return settings.allow_demo_token
    return is_dev(settings)


def validate_runtime_settings(settings: Settings) -> None:
    """Refuse to start outside dev with the default or a weak SECRET_KEY."""

    if not is_dev(settings) and (
        settings.secret_key == DEFAULT_SECRET_KEY or len(settings.secret_key) < 32
    ):
        raise RuntimeError(
            "SECRET_KEY must be set to a random value of at least 32 characters "
            "when ENVIRONMENT is not dev"
        )


def resolve_llm_provider(settings: Settings) -> str:
    """Return ``openai`` or ``dashscope`` for the given settings."""

    name = (settings.llm_provider or "").strip().lower()
    if name in {"openai", "dashscope"}:
        return name
    if name:
        raise ValueError(f"Unsupported LLM_PROVIDER {name!r}; use 'openai' or 'dashscope'")
    return "openai" if settings.llm_base_url.strip() else "dashscope"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    Caching avoids re-reading the ``.env`` file on every access and gives the
    rest of the app a single, consistent configuration object.
    """

    return Settings()
