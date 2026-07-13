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
    dashscope_base_url: str = ""
    database_url: str = "postgresql+asyncpg://user:pass@localhost/memoria"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "supersecret"
    # Fixed token guarding destructive demo endpoints (e.g. DELETE /api/memories).
    demo_api_token: str = "memoria-demo-token"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    Caching avoids re-reading the ``.env`` file on every access and gives the
    rest of the app a single, consistent configuration object.
    """

    return Settings()
