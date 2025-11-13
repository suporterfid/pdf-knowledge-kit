from __future__ import annotations

import wave
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from app.ingestion.connectors.transcription import (
    TranscriptionConnector,
    TranscriptionResult,
    TranscriptionSegment,
)
from app.ingestion.models import Source, SourceType


@pytest.fixture()
def audio_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "sample.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)
    return path


def _make_source(audio_path: Path, **overrides: Any) -> Source:
    payload = {
        "id": uuid4(),
        "type": SourceType.AUDIO_TRANSCRIPT,
        "created_at": datetime.utcnow(),
        "path": str(audio_path),
        "params": {
            "provider": "mock",
            "cache_dir": str(audio_path.parent / "cache"),
            "language": "en",
        },
    }
    payload.update(overrides)
    return Source(**payload)


def test_transcription_connector_mock_segments(
    tmp_path: Path, audio_fixture: Path
) -> None:
    params = {
        "provider": "mock",
        "cache_dir": str(tmp_path / "cache"),
        "segments": [
            {
                "text": "Hello",
                "start": 0.0,
                "end": 1.0,
                "speaker": "A",
                "confidence": 0.9,
            },
            {"text": "World", "start": 1.0, "end": 2.0},
        ],
        "extra_metadata": {"topic": "greeting"},
        "language": "en",
    }
    source = _make_source(audio_fixture, params=params)

    connector = TranscriptionConnector(source)
    records = list(connector.stream())

    assert len(records) == 1
    record = records[0]
    assert len(record.chunks) == 2
    first_chunk, second_chunk = record.chunks

    assert first_chunk.extra["transcript_start"] == 0.0
    assert first_chunk.extra["transcript_speaker"] == "A"
    assert second_chunk.extra["transcript_index"] == 2
    assert record.document_sync_state["media_checksum"]
    assert connector.job_metadata["segments"] == 2
    assert (
        connector.next_sync_state["media_checksum"]
        == record.document_sync_state["media_checksum"]
    )


def test_transcription_connector_with_custom_provider(
    monkeypatch, tmp_path: Path, audio_fixture: Path
) -> None:
    class FakeProvider:
        name = "whisper"

        def __init__(self) -> None:
            self.called_with: tuple[Path, str] | None = None

        def transcribe(
            self, media_path: Path, *, media_uri: str, config, cancel_event=None
        ):
            self.called_with = (media_path, media_uri)
            return TranscriptionResult(
                segments=[
                    TranscriptionSegment(text="Segment one", start=0.0, end=1.2),
                    TranscriptionSegment(
                        text="Segment two", start=1.2, end=2.5, confidence=0.8
                    ),
                ],
                metadata={
                    "provider": "whisper",
                    "language": "en",
                    "chunk_extra": {"speaker_label": "auto"},
                },
            )

    fake_provider = FakeProvider()
    monkeypatch.setattr(
        TranscriptionConnector,
        "_create_provider",
        lambda self, name: fake_provider,
    )

    params = {
        "provider": "whisper",
        "cache_dir": str(tmp_path / "cache"),
        "language": "en",
    }
    source = _make_source(audio_fixture, params=params)

    connector = TranscriptionConnector(source)
    records = list(connector.stream())

    assert fake_provider.called_with is not None
    media_path, media_uri = fake_provider.called_with
    assert media_path.exists()
    assert media_uri == str(audio_fixture)

    record = records[0]
    assert len(record.chunks) == 2
    assert record.chunks[0].extra["speaker_label"] == "auto"
    assert connector.job_metadata["provider"] == "whisper"
    assert record.document_sync_state["provider"] == "whisper"
