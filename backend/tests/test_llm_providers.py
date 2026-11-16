"""Provider-layer tests against the mock OpenAI-compatible server."""

from __future__ import annotations

import pytest

from app.config import Settings, resolve_llm_provider
from app.core.llm import dimcheck
from app.core.llm.base import (
    EmbeddingDimensionError,
    LLMError,
    UnsupportedCapabilityError,
    check_embedding_dim,
    parse_json_object,
    strip_reasoning,
)
from tests.mock_openai_server import ANSWER, REASONING, STRUCTURED


def test_provider_selection():
    assert resolve_llm_provider(Settings(_env_file=None)) == "dashscope"
    assert resolve_llm_provider(Settings(_env_file=None, llm_base_url="http://x/v1")) == "openai"
    assert (
        resolve_llm_provider(Settings(_env_file=None, llm_base_url="http://x", llm_provider="dashscope"))
        == "dashscope"
    )
    with pytest.raises(ValueError):
        resolve_llm_provider(Settings(_env_file=None, llm_provider="nope"))


async def test_chat(openai_provider):
    assert await openai_provider().chat([{"role": "user", "content": "hi"}], "plain") == ANSWER


async def test_chat_sends_bearer_and_maps_legacy_model(openai_provider, mock_llm_server):
    p = openai_provider(llm_chat_model="plain")
    await p.chat([{"role": "user", "content": "hi"}], "qwen-plus")
    assert mock_llm_server.app.state.requests[-1]["model"] == "plain"


async def test_reasoning_content_not_in_chat(openai_provider):
    text = await openai_provider().chat([{"role": "user", "content": "hi"}], "reasoner")
    assert text == ANSWER
    assert REASONING not in text


async def test_inline_think_stripped(openai_provider):
    text = await openai_provider().chat([{"role": "user", "content": "hi"}], "think-inline")
    assert text == ANSWER


async def test_stream_separates_reasoning(openai_provider):
    events = [e async for e in openai_provider().stream_events([{"role": "user", "content": "hi"}], "reasoner")]
    assert "".join(e.text for e in events if e.kind == "reasoning") == "Let me think."
    assert "".join(e.text for e in events if e.kind == "content") == "Hello world"


async def test_stream_inline_think_split_across_chunks(openai_provider):
    events = [e async for e in openai_provider().stream_events([{"role": "user", "content": "hi"}], "think-inline")]
    assert "".join(e.text for e in events if e.kind == "content") == "Hello"
    assert "".join(e.text for e in events if e.kind == "reasoning") == "hmm"


async def test_stream_error_status(openai_provider):
    with pytest.raises(LLMError, match="500"):
        async for _ in openai_provider().stream_events([{"role": "user", "content": "x"}], "boom"):
            pass


async def test_tool_calling_shape(openai_provider):
    from app.memory.ingestion import EXTRACT_MEMORIES_TOOL, _extract_tool_arguments

    response = await openai_provider().chat_with_tools(
        [{"role": "user", "content": "I like tea"}], EXTRACT_MEMORIES_TOOL, "reasoner"
    )
    args = _extract_tool_arguments(response)
    assert args["memories"][0]["content"] == "User likes tea"
    assert "reasoning_content" not in response.output["choices"][0]["message"]


@pytest.mark.parametrize("model", ["plain", "no-schema", "no-format", "fenced"])
async def test_structured_with_fallbacks(openai_provider, model):
    result = await openai_provider().structured(
        [{"role": "user", "content": "go"}], {"type": "object"}, model
    )
    assert result == STRUCTURED


async def test_structured_remembers_downgrade(openai_provider, mock_llm_server):
    p = openai_provider()
    msgs = [{"role": "user", "content": "go"}]
    await p.structured(msgs, {"type": "object"}, "no-schema")
    mock_llm_server.app.state.requests.clear()
    await p.structured(msgs, {"type": "object"}, "no-schema")
    assert len(mock_llm_server.app.state.requests) == 1
    assert mock_llm_server.app.state.requests[0]["response_format"]["type"] == "json_object"


async def test_server_error_raises(openai_provider):
    with pytest.raises(LLMError, match="500"):
        await openai_provider().chat([{"role": "user", "content": "x"}], "boom")


async def test_embeddings_deterministic_and_default_dim(openai_provider):
    p = openai_provider()
    a = await p.embed("hello", "text-embedding-v3")
    b = await p.embed("hello", "text-embedding-v3")
    assert a == b and len(a) == 1024
    assert a != await p.embed("other", "text-embedding-v3")


async def test_embedding_model_mapping_and_dimensions(openai_provider, mock_llm_server):
    p = openai_provider(
        llm_embedding_model="embed-8", llm_embedding_send_dimensions=True, embedding_dim=16
    )
    vec = await p.embed("x", "text-embedding-v3")
    assert len(vec) == 16
    assert mock_llm_server.app.state.requests[-1]["model"] == "embed-8"


async def test_get_embedding_facade_validates_dimension(monkeypatch, openai_provider):
    from app.core import dashscope_client

    monkeypatch.setattr(dashscope_client, "get_provider", lambda: openai_provider())
    assert len(await dashscope_client.get_embedding("hi")) == 1024
    monkeypatch.setattr(
        dashscope_client, "get_provider", lambda: openai_provider(llm_embedding_model="embed-8")
    )
    with pytest.raises(EmbeddingDimensionError, match="EMBEDDING_DIM"):
        await dashscope_client.get_embedding("hi")


async def test_media_unsupported_on_openai(openai_provider):
    p = openai_provider()
    with pytest.raises(UnsupportedCapabilityError, match="dashscope"):
        await p.generate_image("cat", "m", "1*1")
    with pytest.raises(UnsupportedCapabilityError):
        await p.generate_video("cat", "m", 5)
    with pytest.raises(UnsupportedCapabilityError):
        await p.synthesize_speech("hi", "m", "v")


async def test_models_endpoint(mock_llm_server):
    import httpx

    r = httpx.get(f"{mock_llm_server.base_url}/models")
    assert {m["id"] for m in r.json()["data"]} == {"reasoner", "plain"}


def test_helpers():
    assert strip_reasoning("<think>x</think>ok") == "ok"
    assert strip_reasoning("a<think>unterminated") == "a"
    assert parse_json_object('text {"a": 1} tail') == {"a": 1}
    with pytest.raises(LLMError):
        parse_json_object("no json")
    with pytest.raises(EmbeddingDimensionError):
        check_embedding_dim([0.0] * 3, 4)


def test_dimcheck_compare():
    dimcheck.compare_dims(1024, 1024)
    dimcheck.compare_dims(1024, None)
    with pytest.raises(EmbeddingDimensionError, match="vector\\(1536\\)"):
        dimcheck.compare_dims(1024, 1536)


def test_openai_provider_requires_base_url():
    from app.core.llm.openai_compat import OpenAICompatProvider

    with pytest.raises(LLMError):
        OpenAICompatProvider(Settings(_env_file=None))
