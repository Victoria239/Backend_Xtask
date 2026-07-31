"""Semantic chunker for RAG ingestion.

Strategy:
  1. Normalise whitespace.
  2. Split by sentence-like boundaries (.?!\n) keeping the delimiter.
  3. Greedy-pack sentences into chunks of `target_tokens` (~4 chars/token heuristic),
     adding `overlap_tokens` of trailing context from the previous chunk so
     embeddings on chunk boundaries don't lose semantics.

This is intentionally dependency-free so it works without spaCy/NLTK in dev.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SENT_SPLIT = re.compile(r"(?<=[\.\?\!])\s+|\n{2,}")
_CHARS_PER_TOKEN = 4  # rough heuristic that matches GPT-style tokenisation


@dataclass(frozen=True)
class Chunk:
    position: int
    content: str
    token_count: int


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def chunk_text(
    text: str,
    target_tokens: int = 350,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Split ``text`` into overlapping semantic chunks.

    Returns an empty list when ``text`` is empty or whitespace only.
    """

    if not text or not text.strip():
        return []

    normalised = re.sub(r"[ \t]+", " ", text).strip()
    sentences = [s.strip() for s in _SENT_SPLIT.split(normalised) if s.strip()]

    target_chars = target_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN

    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_len = 0
    position = 0

    def flush() -> None:
        nonlocal buffer, buffer_len, position
        if not buffer:
            return
        content = " ".join(buffer).strip()
        chunks.append(Chunk(position=position, content=content, token_count=_estimate_tokens(content)))
        position += 1
        # carry overlap into the next buffer
        if overlap_chars > 0 and len(content) > overlap_chars:
            tail = content[-overlap_chars:]
            buffer = [tail]
            buffer_len = len(tail)
        else:
            buffer = []
            buffer_len = 0

    for sentence in sentences:
        s_len = len(sentence) + 1  # +1 for the space separator
        if buffer_len + s_len > target_chars and buffer:
            flush()
        buffer.append(sentence)
        buffer_len += s_len

    flush()
    return chunks
