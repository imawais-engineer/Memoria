"""Memoria MCP server exposing ``remember``, ``recall`` and ``forget``.

Transports:

* stdio: ``python -m app.mcp.server``. The user is taken from
  ``MEMORIA_MCP_TOKEN`` (a Memoria JWT) or ``MEMORIA_MCP_USER_ID`` (a user UUID,
  for local single-user use only).
* streamable HTTP: mounted at ``/mcp/`` by the FastAPI app via
  :func:`mount_mcp`. Every request needs ``Authorization: Bearer <JWT>``, the
  same token the REST API uses. The token's subject scopes all memory access.

Tool handlers (``remember_handler`` etc.) take the user id and a database
session explicitly so they can be tested without a transport.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import HTTPException
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token
from app.services.limits import enforce_mcp_limits, charge_mcp_tokens, estimate_tokens
from app.memory.ingestion import extract_and_store_memories
from app.memory.models import Memory
from app.memory.retrieval import retrieve_with_why

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 8000
MAX_QUERY_CHARS = 1000

_current_user: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "memoria_mcp_user", default=None
)


class MCPAuthError(Exception):
    """Raised when no authenticated user is available for a tool call."""


def resolve_user_id() -> str:
    """User for the current call: HTTP bearer context, else stdio env vars."""

    user = _current_user.get()
    if user:
        return user
    token = os.environ.get("MEMORIA_MCP_TOKEN", "").strip()
    if token:
        try:
            return decode_access_token(token)
        except HTTPException as exc:
            raise MCPAuthError(f"MEMORIA_MCP_TOKEN rejected: {exc.detail}") from exc
    raw = os.environ.get("MEMORIA_MCP_USER_ID", "").strip()
    if raw:
        try:
            return str(uuid.UUID(raw))
        except ValueError as exc:
            raise MCPAuthError("MEMORIA_MCP_USER_ID is not a valid UUID") from exc
    raise MCPAuthError(
        "Not authenticated: send a bearer token or set MEMORIA_MCP_TOKEN"
    )


@asynccontextmanager
async def open_session() -> AsyncIterator[AsyncSession]:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


async def remember_handler(
    user_id: str, text: str, db: AsyncSession, session_id: str | None = None
) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("text must not be empty")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"text exceeds {MAX_TEXT_CHARS} characters")
    created = await extract_and_store_memories(
        text, user_id, f"mcp-{uuid.uuid4()}", db, session_id=session_id
    )
    return {
        "stored": len(created),
        "memories": [
            {
                "id": str(m.id),
                "type": m.type,
                "kind": getattr(m, "kind", None),
                "content": m.content,
            }
            for m in created
        ],
    }


async def recall_handler(
    user_id: str,
    query: str,
    db: AsyncSession,
    include_superseded: bool = False,
) -> dict[str, Any]:
    query = (query or "").strip()
    if not query:
        raise ValueError("query must not be empty")
    if len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"query exceeds {MAX_QUERY_CHARS} characters")
    items = await retrieve_with_why(
        user_id, query, db_session=db, include_superseded=include_superseded
    )
    return {"count": len(items), "memories": items}


async def forget_handler(user_id: str, memory_id: str, db: AsyncSession) -> dict[str, Any]:
    try:
        mem_uuid = uuid.UUID(memory_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("memory_id must be a UUID") from exc
    result = await db.execute(
        delete(Memory).where(Memory.id == mem_uuid, Memory.user_id == user_id)
    )
    await db.commit()
    return {"forgotten": result.rowcount > 0, "memory_id": str(mem_uuid)}


def build_server() -> FastMCP:
    mcp = FastMCP(
        "memoria",
        instructions=(
            "Long-term memory. Use remember to store facts or preferences, "
            "recall to search them (results include why they matched), and "
            "forget to delete one by id."
        ),
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        # Mounted behind arbitrary hostnames; access is gated by bearer JWT.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )

    @mcp.tool()
    async def remember(text: str, session_id: str | None = None) -> str:
        """Extract and store durable memories from ``text``."""
        user_id = resolve_user_id()
        await enforce_mcp_limits(user_id)
        result: dict[str, Any] | None = None
        try:
            async with open_session() as db:
                result = await remember_handler(user_id, text, db, session_id)
            return json.dumps(result)
        finally:
            # Charge even when the handler fails after the provider call.
            # Stored memory text approximates the LLM extraction output.
            stored = [m["content"] for m in (result or {}).get("memories", [])]
            await charge_mcp_tokens(user_id, estimate_tokens(text or "", *stored))

    @mcp.tool()
    async def recall(query: str, include_superseded: bool = False) -> str:
        """Search memories. Each result has a ``why`` explanation."""
        user_id = resolve_user_id()
        await enforce_mcp_limits(user_id)
        async with open_session() as db:
            result = await recall_handler(user_id, query, db, include_superseded)
        await charge_mcp_tokens(user_id, estimate_tokens(query))
        return json.dumps(result)

    @mcp.tool()
    async def forget(memory_id: str) -> str:
        """Delete one of your memories by id."""
        user_id = resolve_user_id()
        async with open_session() as db:
            return json.dumps(await forget_handler(user_id, memory_id, db))

    return mcp


mcp_server = build_server()


class BearerAuthMiddleware:
    """ASGI wrapper: validates the bearer JWT and sets the call's user."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth = headers.get(b"authorization", b"").decode("latin-1")
        scheme, _, token = auth.partition(" ")
        user = None
        if scheme.lower() == "bearer" and token.strip():
            try:
                user = decode_access_token(token.strip())
            except HTTPException:
                user = None
        if user is None:
            body = b'{"error":"unauthorized"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"www-authenticate", b"Bearer"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        reset = _current_user.set(user)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_user.reset(reset)


def mount_mcp(application: Any) -> None:
    """Mount the authenticated streamable HTTP server at ``/mcp/``."""

    server = build_server()  # fresh instance: a session manager runs once
    application.state.mcp_server = server
    application.mount("/mcp", BearerAuthMiddleware(server.streamable_http_app()))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()
