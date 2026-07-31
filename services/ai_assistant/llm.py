"""LLM providers: OpenRouter > OpenAI > extractive fallback.

OpenRouter is a router for chat completions (OpenAI, Anthropic, Llama, Mistral,
Gemini...) via a single key. The protocol is OpenAI-compatible.

The extractive fallback stitches RAG snippets into a structured answer when no
API key is configured — useful for offline dev, but flagged as such so we don't
lie about "generating" content.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class LlmAnswer:
    answer: str
    provider: str


@dataclass
class ToolCall:
    """A tool invocation requested by the LLM."""
    id: str
    name: str
    arguments: dict


@dataclass
class LlmTurn:
    """One round-trip with the LLM in a tool-using conversation.

    Either `content` is set (final answer) or `tool_calls` is non-empty
    (LLM wants to call functions before answering).
    """
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class SupportsTools:
    """Marker / capability check for providers that support function calling."""
    supports_tools: bool = False


class _OpenAICompatibleChatMixin:
    """Shared chat-completion logic for OpenAI-style endpoints (OpenAI, OpenRouter)."""

    supports_tools = True
    model: str
    name: str
    _client: httpx.AsyncClient

    async def complete(self, system: str, user: str) -> LlmAnswer:
        resp = await self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return LlmAnswer(answer=content, provider=self.name)

    async def turn(self, messages: list[dict], tools: list[dict] | None = None) -> LlmTurn:
        """Execute a single conversation turn. May return content or tool_calls."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        choice = resp.json()["choices"][0]["message"]
        raw_calls = choice.get("tool_calls") or []
        calls: list[ToolCall] = []
        for rc in raw_calls:
            fn = rc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=rc.get("id", ""), name=fn.get("name", ""), arguments=args))
        return LlmTurn(content=choice.get("content"), tool_calls=calls)


class OpenAIChatProvider(_OpenAICompatibleChatMixin):
    name = "openai:gpt-4o-mini"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )


class OllamaChatProvider(_OpenAICompatibleChatMixin):
    """Ollama local LLM — OpenAI-compatible API en `/v1`.

    Modelos recomendados (que soportan function calling):
    - `llama3.2:3b` — Meta, 2GB en disco, ~4GB RAM
    - `qwen2.5:3b` — Alibaba, mejor en español
    - `llama3.1:8b` — más calidad pero ~8GB RAM
    """

    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        model: str = "llama3.2:3b",
    ):
        self.model = model
        self.name = f"ollama:{model}"
        # Ollama expone OpenAI-compat en /v1/. No requiere auth.
        self._client = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/v1",
            timeout=120.0,  # más generoso — local LLM puede ser lento en frío
        )


class OpenRouterChatProvider(_OpenAICompatibleChatMixin):
    """OpenRouter chat completions — OpenAI-compatible API with model routing.

    See https://openrouter.ai/docs. Model names use the provider-prefixed form,
    e.g. `anthropic/claude-3.5-haiku`, `openai/gpt-4o-mini`,
    `meta-llama/llama-3.1-70b-instruct`, `google/gemini-flash-1.5`.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-3.5-haiku",
        app_name: str = "XTask",
        app_url: str = "http://localhost:3001",
    ):
        self.api_key = api_key
        self.model = model
        self.name = f"openrouter:{model}"
        self._client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {api_key}",
                # OpenRouter ranking headers (optional but recommended)
                "HTTP-Referer": app_url,
                "X-Title": app_name,
            },
            timeout=60.0,
        )


class ExtractiveProvider:
    """Deterministic extractive answerer used when no API key is set."""

    name = "local:extractive-fallback"
    supports_tools = False

    async def complete(self, system: str, user: str) -> LlmAnswer:
        # The `user` payload already contains the assembled context + question.
        # We just echo back a structured extractive response.
        marker = "CONTEXT:"
        if marker in user:
            ctx, _, _ = user.partition("QUESTION:")
            ctx = ctx.replace(marker, "").strip()
        else:
            ctx = user
        answer = (
            "(Modo extractivo — sin OPENAI_API_KEY)\n\n"
            "Lo más relevante encontrado en tu corpus es lo siguiente. Revísalo y "
            "ajusta según el caso:\n\n" + ctx[:2000]
        )
        return LlmAnswer(answer=answer, provider=self.name)


def get_llm_provider():
    """Selects the LLM provider: Ollama (local) > OpenRouter > OpenAI > extractive."""
    if os.environ.get("OLLAMA_BASE_URL"):
        base = os.environ["OLLAMA_BASE_URL"]
        model = os.environ.get("OLLAMA_MODEL", "llama3.2:3b").strip()
        return OllamaChatProvider(base_url=base, model=model)

    or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if or_key:
        model = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3.5-haiku").strip()
        app_url = os.environ.get("OPENROUTER_APP_URL", "http://localhost:3001").strip()
        return OpenRouterChatProvider(api_key=or_key, model=model, app_url=app_url)

    oa_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if oa_key:
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
        return OpenAIChatProvider(api_key=oa_key, model=model)

    return ExtractiveProvider()
