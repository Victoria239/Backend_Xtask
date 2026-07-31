"""Embedding provider with OpenAI primary + deterministic local fallback.

The fallback uses a hash-based projection that produces stable, reasonable-quality
vectors without external services — good enough for dev / offline / CI. It is NOT
a real semantic encoder; production deployments MUST set OPENAI_API_KEY (or wire
sentence-transformers via the same interface).
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import Iterable, Protocol

import httpx

from services.rag import EMBEDDING_DIM


class EmbeddingProvider(Protocol):
    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


# ─── OpenAI provider ────────────────────────────────────────────
class OpenAIEmbeddingProvider:
    name = "openai:text-embedding-3-small"

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = await self._client.post(
            "/embeddings",
            json={"model": self.model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return [item["embedding"] for item in data]


# ─── Ollama provider (local, sin API externa) ──────────────────
class OllamaEmbeddingProvider:
    """Embeddings vía Ollama local. Default model: nomic-embed-text (768-dim)."""

    def __init__(self, base_url: str = "http://ollama:11434", model: str = "nomic-embed-text"):
        self.model = model
        self.name = f"ollama:{model}"
        self._client = httpx.AsyncClient(base_url=base_url, timeout=120.0)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Ollama soporta /api/embed (multi) o /api/embeddings (single).
        # Usamos multi para una sola llamada.
        resp = await self._client.post(
            "/api/embed",
            json={"model": self.model, "input": texts},
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]


# ─── Deterministic local fallback ───────────────────────────────
class HashEmbeddingProvider:
    """Hash-based pseudo-embeddings. Deterministic, no dependencies.

    Produces L2-normalised vectors of dimension ``EMBEDDING_DIM`` by hashing
    word n-grams into buckets. Quality is far below a real encoder but it is
    sufficient to validate the end-to-end pipeline in development.
    """

    name = "local:hash-fallback"

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = self._tokenise(text)
        # unigrams + bigrams
        grams: list[str] = list(tokens)
        grams.extend(f"{a}_{b}" for a, b in zip(tokens, tokens[1:]))
        for gram in grams:
            h = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if (h[4] & 1) else -1.0
            vec[bucket] += sign
        # L2 normalise
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        return [t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if t]


# ─── Factory ────────────────────────────────────────────────────
def get_embedding_provider() -> EmbeddingProvider:
    """Prioridad: Ollama (local) > OpenAI > Hash fallback."""
    if os.environ.get("OLLAMA_BASE_URL"):
        return OllamaEmbeddingProvider(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434"),
            model=os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        )
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        return OpenAIEmbeddingProvider(api_key=api_key)
    return HashEmbeddingProvider()


async def embed_batch(provider: EmbeddingProvider, texts: Iterable[str], batch_size: int = 32) -> list[list[float]]:
    """Embed many texts in batches to respect API rate limits."""
    items = list(texts)
    out: list[list[float]] = []
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        out.extend(await provider.embed(batch))
    return out
