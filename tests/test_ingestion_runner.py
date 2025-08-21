import app.ingestion.service as service
from app.ingestion.runner import IngestionRunner
from uuid import uuid4
from threading import Event
import time
import pathlib


def test_runner_cancel_stops_work():
    runner = IngestionRunner(max_workers=1)
    job_id = uuid4()
    events = {}

    def work(ev: Event):
        events['evt'] = ev
        while not ev.is_set():
            time.sleep(0.01)

    fut = runner.submit(job_id, work)
    runner.cancel(job_id)
    # give thread time to process cancellation
    time.sleep(0.05)
    assert events['evt'].is_set()
    assert fut.cancelled() or fut.done()


def test_setup_job_logging_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job_id = uuid4()
    logger, _ = service._setup_job_logging(job_id)
    logger.info("hello")
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)
    log_path = pathlib.Path("logs") / "jobs" / f"{job_id}.log"
    assert log_path.exists()
    assert "hello" in log_path.read_text(encoding="utf-8")


def test_runner_submit_and_cleanup():
    runner = IngestionRunner(max_workers=1)
    job_id = uuid4()
    called = {}

    def work(ev: Event):
        called["ran"] = True

    fut = runner.submit(job_id, work)
    fut.result(timeout=1)
    assert called["ran"]
    # manual cleanup to remove bookkeeping
    runner._events.pop(job_id, None)
    runner._futures.pop(job_id, None)
    assert list(runner.list()) == []
