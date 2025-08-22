import asyncio
import re
from typing import AsyncIterator

# Punctuation sets for flushing and spacing rules
PUNCT_CUTOFF = set(list(".,;:!?…"))
CLOSE_PUNCT = set(list(")]}"))
OPEN_PUNCT = set(list("([{"))


def _should_flush(buf: str, tok: str) -> bool:
    """Decide when the current buffer should be flushed.

    Flush on spaces/newlines, when the buffer ends with terminal punctuation,
    or when it grows too large (fallback >80 chars).
    """
    if tok in (" ", "\n"):
        return True
    if buf and (buf[-1] in PUNCT_CUTOFF or buf[-1] in CLOSE_PUNCT or tok == "\n"):
        return True
    return len(buf) >= 80


def _join_token(prev: str, tok: str) -> str:
    """Join a new token to the existing buffer using simple heuristics."""
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
    """Light text normalization for the final aggregated text."""
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s+([,.;:!?…])", r"\1", s)
    s = re.sub(r"([(\[{])\s+", r"\1", s)
    s = re.sub(r"\s+([)\]}])", r"\1", s)
    return s.strip()


async def sse_word_buffer(token_iter: AsyncIterator[str]) -> AsyncIterator[str]:
    """Aggregate micro-tokens into human readable chunks and emit SSE events."""
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
