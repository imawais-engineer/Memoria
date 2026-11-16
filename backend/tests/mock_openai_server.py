"""Minimal OpenAI-compatible mock server used by the provider tests.

Model names select behaviours:

* ``reasoner``     returns ``reasoning_content`` next to ``content``.
* ``think-inline`` puts ``<think>..</think>`` inside ``content``.
* ``no-schema``    rejects ``response_format.type == json_schema`` with 400.
* ``no-format``    rejects any ``response_format`` with 400 (prompt+parse only).
* ``fenced``       wraps JSON answers in a markdown fence.
* ``embed-N``      (embeddings) returns N-dimensional vectors; default 1024.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

ANSWER = "Hello from the mock"
REASONING = "Let me think about this."
STRUCTURED = {"summary": "mock summary", "score": 3}


def deterministic_vector(text: str, dim: int) -> list[float]:
    seed = hashlib.sha256(text.encode()).digest()
    raw = [(seed[i % len(seed)] + i) % 97 - 48 for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]


def _completion(model: str, message: dict[str, Any], finish: str = "stop") -> dict:
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
    }


def create_mock_app() -> FastAPI:
    app = FastAPI()
    app.state.requests = []  # recorded request bodies for assertions

    @app.get("/v1/models")
    async def models() -> dict:
        return {
            "object": "list",
            "data": [{"id": m, "object": "model"} for m in ("reasoner", "plain")],
        }

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        body = await request.json()
        app.state.requests.append(body)
        model = body.get("model", "plain")
        fmt = (body.get("response_format") or {}).get("type")

        if model == "no-format" and fmt:
            return JSONResponse({"error": {"message": "response_format unsupported"}}, 400)
        if model == "no-schema" and fmt == "json_schema":
            return JSONResponse({"error": {"message": "json_schema unsupported"}}, 400)
        if model == "boom":
            return JSONResponse({"error": {"message": "server exploded"}}, 500)

        if body.get("stream"):
            return StreamingResponse(_stream(model), media_type="text/event-stream")

        if body.get("tools"):
            fn = body["tools"][0]["function"]["name"]
            args = {"memories": [{"content": "User likes tea", "memory_type": "preference"}]}
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": fn, "arguments": json.dumps(args)},
                    }
                ],
            }
            if model == "reasoner":
                message["reasoning_content"] = REASONING
            return _completion(model, message, "tool_calls")

        if fmt:
            text = json.dumps(STRUCTURED)
        elif not fmt and "JSON object only" in json.dumps(body["messages"]):
            text = json.dumps(STRUCTURED)
        else:
            text = ANSWER
        if model == "fenced":
            text = f"Sure!\n```json\n{text}\n```"
        message: dict[str, Any] = {"role": "assistant", "content": text}
        if model == "reasoner":
            message["reasoning_content"] = REASONING
        if model == "think-inline":
            message["content"] = f"<think>{REASONING}</think>{text}"
        return _completion(model, message)

    def _stream(model: str):
        def sse(delta: dict) -> str:
            return "data: " + json.dumps({"choices": [{"index": 0, "delta": delta}]}) + "\n\n"

        async def gen():
            yield ": keep-alive\n\n"
            if model == "reasoner":
                for part in ("Let me ", "think."):
                    yield sse({"reasoning_content": part})
            if model == "think-inline":
                for part in ("<thi", "nk>hmm</th", "ink>Hel", "lo"):
                    yield sse({"content": part})
            else:
                for part in ("Hello", " ", "world"):
                    yield sse({"content": part})
            yield "data: [DONE]\n\n"

        return gen()

    @app.post("/v1/embeddings")
    async def embeddings(request: Request):
        body = await request.json()
        app.state.requests.append(body)
        model = body.get("model", "")
        dim = 1024
        if model.startswith("embed-"):
            dim = int(model.split("-", 1)[1])
        if "dimensions" in body:
            dim = int(body["dimensions"])
        inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
        return {
            "object": "list",
            "model": model,
            "data": [
                {"object": "embedding", "index": i, "embedding": deterministic_vector(t, dim)}
                for i, t in enumerate(inputs)
            ],
        }

    return app
