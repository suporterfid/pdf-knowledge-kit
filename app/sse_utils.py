"""SSE helpers for token streaming.

This module groups tiny utilities that turn a stream of micro‑tokens into
human‑friendly chunks and emit them as Server‑Sent Events (SSE). The goal is
to reduce flicker and awkward spacing while keeping latency low.

Event format produced:
- "event: token" with "data: <partial_text>" for incremental chunks
- "event: text" with "data: <full_normalized_text>" at the end
"""

import asyncio
import re
from typing import AsyncIterator

# Punctuation sets for flushing and spacing rules
PUNCT_CUTOFF = set(list(".,;:!?…"))
CLOSE_PUNCT = set(list(")]}"))
OPEN_PUNCT = set(list("([{"))


def _should_flush(buf: str, tok: str) -> bool:
    """Heuristic to decide when to emit an intermediate SSE token.

    We flush on whitespace boundaries and after closing/terminal punctuation so
    the UI displays smooth phrases, with a safety cutoff for very long buffers.
    """
    if tok in (" ", "\n"):
        return True
    if buf and (buf[-1] in PUNCT_CUTOFF or buf[-1] in CLOSE_PUNCT or tok == "\n"):
        return True
    return len(buf) >= 80


def _join_token(prev: str, tok: str) -> str:
    """Join a token to the existing buffer using simple spacing heuristics.

    Rules are intentionally small and fast:
    - stick short alphabetical fragments to preceding words ("read" + "ing")
    - trim spaces before punctuation/closing brackets
    - trim spaces after opening brackets
    """
    if not prev:
        return tok

    # If the token is a small alphabetical fragment, join without space
    if 1 <= len(tok) <= 3 and all(ch.isalpha() for ch in tok):
        letters = re.search(r"[\w]+$", prev, flags=re.UNICODE)
        if letters and len(letters.group(0)) >= 4:
            return prev + tok

    # Remove space before closing punctuation
    if tok in CLOSE_PUNCT and prev.endswith(" "):
        return prev[:-1] + tok

    # Remove space before punctuation
    if tok in PUNCT_CUTOFF and prev.endswith(" "):
        return prev[:-1] + tok

    # Remove space after opening punctuation
    if prev and prev[-1] in OPEN_PUNCT and tok.startswith(" "):
        return prev + tok.lstrip()

    return prev + tok


def _normalize_text(s: str) -> str:
    """Normalize whitespace and punctuation spacing for the final text."""
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s+([,.;:!?…])", r"\1", s)
    s = re.sub(r"([(\[{])\s+", r"\1", s)
    s = re.sub(r"\s+([)\]}])", r"\1", s)
    return s.strip()


async def sse_word_buffer(token_iter: AsyncIterator[str]) -> AsyncIterator[str]:
    """Aggregate micro‑tokens and emit SSE events with partial/final text.

    Parameters
    ----------
    token_iter:
        Asynchronous iterator that yields small string tokens.

    Yields
    ------
    str:
        SSE‑formatted lines ("event: ...\ndata: ...\n\n") suitable for
        streaming directly in a FastAPI StreamingResponse.
    """
    buf = ""
    full_text: list[str] = []
    async for tok in token_iter:
        tok = "" if tok is None else str(tok)
        new_buf = _join_token(buf, tok)
        flush = _should_flush(new_buf, tok)
        buf = new_buf
        if flush and buf:
            full_text.append(buf)
            yield f"event: token\ndata: {buf}\n\n"
            buf = ""
        await asyncio.sleep(0)
    if buf:
        full_text.append(buf)
        yield f"event: token\ndata: {buf}\n\n"
    final = _normalize_text("".join(full_text))
    yield f"event: text\ndata: {final}\n\n"
