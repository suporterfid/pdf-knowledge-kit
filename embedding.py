"""Custom fastembed model registration.

This module attempts to register a CLS-pooled variant of
"sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" as
"paraphrase-multilingual-MiniLM-L12-v2-cls". If the running fastembed
version doesn't support custom registration, this becomes a no-op so the
application can still boot using the base model.
"""

try:  # Prefer native helper if available
    from fastembed import add_custom_model  # type: ignore
except Exception:  # pragma: no cover - fallback / no-op for older versions
    def add_custom_model(*, name: str, base: str, pooling: str) -> None:  # type: ignore
        # Older fastembed versions may not support registration APIs.
        # Silently no-op to avoid breaking app startup.
        return

try:
    add_custom_model(
        name="paraphrase-multilingual-MiniLM-L12-v2-cls",
        base="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        pooling="cls",
    )
except Exception:
    # If registration fails, continue without custom model.
    pass
