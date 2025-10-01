import app.ingestion.service as ingest
import pytest


class DummyEmbedder:
    def embed(self, texts):
        return [[0.0] * 384 for _ in texts]


class DummyResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


HTML_SNIPPETS = [
    "<html><body><h1>Hello</h1><p>World!</p></body></html>",
    "<html><body><h1>Ol\u00e1</h1><p>Mundo!</p></body></html>",
    "<html><body><h1>Hola</h1><p>Mundo!</p></body></html>",
]


@pytest.mark.parametrize("html", HTML_SNIPPETS)
def test_read_chunk_embed_url(html, monkeypatch):
    def fake_get(url, timeout=10):
        return DummyResponse(html)

    monkeypatch.setattr(ingest.requests, "get", fake_get)

    text = ingest.read_url_text("http://example.com")
    assert text.strip() != ""

    chunks = ingest.chunk_text(
        text,
        source_path="http://example.com",
        mime_type="text/html",
        page_number=1,
    )
    assert chunks

    monkeypatch.setattr(ingest, "TextEmbedding", lambda model_name: DummyEmbedder())
    embedder = ingest.TextEmbedding(model_name=ingest.EMBEDDING_MODEL)

    vectors = list(embedder.embed([chunk.content for chunk in chunks]))
    assert len(vectors) == len(chunks)
