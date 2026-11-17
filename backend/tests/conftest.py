"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from collections.abc import AsyncGenerator
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("ENVIRONMENT", "dev")

from app.core.auth import create_access_token
from app.core.database import get_db
from app.main import app
from app.memory.models import Base
import app.models as _orm_models  # noqa: F401 — register ORM tables for create_all


class UserIdAuth(httpx.Auth):
    """Mint a real JWT for the ``user_id`` found in the query or JSON body.

    The routes still verify the token. Tests that need another identity (or no
    identity) pass an explicit ``Authorization`` header, which takes precedence.
    """

    def auth_flow(self, request: httpx.Request):
        if "authorization" not in request.headers:
            user_id = request.url.params.get("user_id")
            if not user_id and request.content:
                try:
                    user_id = json.loads(request.content).get("user_id")
                except (ValueError, AttributeError):
                    user_id = None
            if user_id:
                request.headers["Authorization"] = (
                    f"Bearer {create_access_token(str(user_id))}"
                )
        yield request


@pytest.fixture
def user_auth() -> UserIdAuth:
    """httpx auth that mints a JWT for the request's ``user_id``."""
    return UserIdAuth()


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://user:pass@localhost/memoria",
)


@pytest_asyncio.fixture
async def db_session_factory():
    """Session factory bound to TEST_DATABASE_URL; skips if the DB is unreachable."""

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"Test database unreachable ({type(exc).__name__})")

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield SessionLocal

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", auth=UserIdAuth()
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def mock_llm_server():
    """Run the mock OpenAI-compatible server on a free local port."""

    import uvicorn

    from tests.mock_openai_server import create_mock_app

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    mock_app = create_mock_app()
    server = uvicorn.Server(
        uvicorn.Config(mock_app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    else:  # pragma: no cover
        pytest.fail("mock LLM server did not start")
    yield SimpleNamespace(base_url=f"http://127.0.0.1:{port}/v1", app=mock_app)
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def openai_provider(mock_llm_server):
    """Factory building an OpenAICompatProvider pointed at the mock server."""

    from app.config import Settings
    from app.core.llm.openai_compat import OpenAICompatProvider

    def make(**overrides):
        settings = Settings(
            _env_file=None,
            llm_base_url=mock_llm_server.base_url,
            llm_api_key="test-key",
            **overrides,
        )
        return OpenAICompatProvider(settings)

    return make
