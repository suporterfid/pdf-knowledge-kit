import pathlib
from uuid import uuid4

import runpy


def test_cli_invokes_service(tmp_path, monkeypatch):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    doc = docs_dir / "a.md"
    doc.write_text("hi", encoding="utf-8")
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("http://b\n", encoding="utf-8")
    sid = uuid4()
    called = {}

    mod = runpy.run_path("ingest.py", run_name="ingest_cli")
    svc = mod["_service"]

    monkeypatch.setattr(svc, "ingest_local", lambda path, **kw: called.setdefault("local", []).append(path))
    monkeypatch.setattr(svc, "ingest_urls", lambda urls: called.setdefault("urls", urls))
    monkeypatch.setattr(svc, "reindex_source", lambda source_id: called.setdefault("reindex", source_id))

    mod["main"]([
        "--docs", str(docs_dir),
        "--url", "http://a",
        "--urls-file", str(urls_file),
        "--reindex", str(sid),
    ])

    assert called["local"] == [doc]
    assert called["urls"] == ["http://a", "http://b"]
    assert called["reindex"] == sid
