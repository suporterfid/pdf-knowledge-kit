import contextlib
import http.server
import socketserver
import threading

import ingest


HTML = """
<html><head><title>Test</title><style>.hide{}</style><script>var a=1;</script></head>
<body><h1>Hello</h1><p>World!</p></body></html>
"""


@contextlib.contextmanager
def run_server(content=HTML):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))

        def log_message(self, *args, **kwargs):
            return

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as httpd:
        url = f"http://127.0.0.1:{httpd.server_address[1]}"
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        try:
            yield url
        finally:
            httpd.shutdown()
            thread.join()


class DummyEmbedder:
    def embed(self, texts):
        return [[0.0] * 384 for _ in texts]


def test_read_chunk_embed_url(monkeypatch):
    with run_server() as url:
        text = ingest.read_url_text(url)
    assert "Hello" in text
    assert "World!" in text
    assert "var a" not in text

    chunks = ingest.chunk_text(text)
    assert chunks

    monkeypatch.setattr(ingest, "TextEmbedding", lambda model_name: DummyEmbedder())
    embedder = ingest.TextEmbedding(model_name=ingest.EMBEDDING_MODEL)

    vectors = list(embedder.embed(chunks))
    assert len(vectors) == len(chunks)
