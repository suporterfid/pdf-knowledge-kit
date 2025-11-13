import runpy
from uuid import uuid4

TEST_TENANT_ID = uuid4()


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

    def fake_ingest_local(path, *, tenant_id, **kw):
        called.setdefault("local", []).append(path)
        return uuid4()

    def fake_ingest_urls(urls, *, tenant_id):
        called.setdefault("urls", urls)
        called.setdefault("urls_tenant", tenant_id)
        return uuid4()

    def fake_reindex(source_id, *, tenant_id):
        called.setdefault("reindex", source_id)
        called.setdefault("reindex_tenant", tenant_id)
        return uuid4()

    monkeypatch.setattr(svc, "ingest_local", fake_ingest_local)
    monkeypatch.setattr(svc, "ingest_urls", fake_ingest_urls)
    monkeypatch.setattr(svc, "reindex_source", fake_reindex)
    monkeypatch.setattr(svc, "wait_for_job", lambda job_id: None)

    mod["main"](
        [
            "--docs",
            str(docs_dir),
            "--url",
            "http://a",
            "--urls-file",
            str(urls_file),
            "--tenant-id",
            str(TEST_TENANT_ID),
            "--reindex",
            str(sid),
        ]
    )

    assert called["local"] == [doc]
    assert called["urls"] == ["http://a", "http://b"]
    assert called["reindex"] == sid
    assert called["urls_tenant"] == str(TEST_TENANT_ID)
    assert called["reindex_tenant"] == str(TEST_TENANT_ID)
