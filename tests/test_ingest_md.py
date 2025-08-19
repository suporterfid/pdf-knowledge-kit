import pathlib
import ingest


class DummyEmbedder:
    def embed(self, texts):
        return [[0.0] * 384 for _ in texts]


import pytest


@pytest.mark.parametrize("fname", ["sample_en.md", "sample_pt.md", "sample_es.md"])
def test_read_chunk_embed_markdown(fname, monkeypatch):
    path = pathlib.Path(__file__).parent / "md_samples" / fname

    text = ingest.read_md_text(path)
    assert text.strip() != ""

    chunks = ingest.chunk_text(text)
    assert chunks

    monkeypatch.setattr(ingest, "TextEmbedding", lambda model_name: DummyEmbedder())
    embedder = ingest.TextEmbedding(model_name=ingest.EMBEDDING_MODEL)

    vectors = list(embedder.embed(chunks))
    assert len(vectors) == len(chunks)
