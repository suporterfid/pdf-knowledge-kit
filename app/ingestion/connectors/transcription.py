"""Transcription connector capable of downloading media and invoking providers."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any, Dict, Iterable, List, Optional, Protocol
from uuid import uuid4

import requests

try:  # pragma: no cover - optional dependency
    import boto3  # type: ignore
except Exception:  # pragma: no cover - fallback when boto3 is unavailable
    boto3 = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from faster_whisper import WhisperModel  # type: ignore

    _WHISPER_BACKEND = "faster_whisper"
except Exception:  # pragma: no cover - fallback to openai-whisper
    WhisperModel = None  # type: ignore
    try:  # pragma: no cover - optional dependency
        import whisper as _openai_whisper  # type: ignore

        _WHISPER_BACKEND = "openai_whisper"
    except Exception:  # pragma: no cover - no whisper backend installed
        _openai_whisper = None  # type: ignore
        _WHISPER_BACKEND = "unavailable"

from ..models import Source, TranscriptionSourceParams
from ..parsers import Chunk
from . import ConnectorRecord


# ---------------------------------------------------------------------------
# Dataclasses and result containers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TranscriptionSegment:
    """Represents a single segment emitted by a transcription provider."""

    text: str
    start: float | None = None
    end: float | None = None
    speaker: str | None = None
    confidence: float | None = None

    def to_metadata(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "transcript_start": self.start,
            "transcript_end": self.end,
            "transcript_speaker": self.speaker,
            "transcript_confidence": self.confidence,
        }
        return {k: v for k, v in payload.items() if v is not None}


@dataclass(slots=True)
class TranscriptionResult:
    """Container returned by providers with structured data."""

    segments: List[TranscriptionSegment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTranscriptionProvider(Protocol):
    """Protocol describing a transcription provider implementation."""

    name: str

    def transcribe(
        self,
        media_path: Path,
        *,
        media_uri: str,
        config: TranscriptionSourceParams,
        cancel_event: Event | None = None,
    ) -> TranscriptionResult:
        ...


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------


class MockTranscriptionProvider:
    """Provider primarily intended for tests and offline development."""

    name = "mock"

    def __init__(self, config: TranscriptionSourceParams) -> None:
        self._config = config

    def transcribe(
        self,
        media_path: Path,
        *,
        media_uri: str,
        config: TranscriptionSourceParams,
        cancel_event: Event | None = None,
    ) -> TranscriptionResult:
        segments_config = config.get("segments") or self._config.get("segments") or []
        segments: List[TranscriptionSegment] = []
        for entry in segments_config:
            segments.append(
                TranscriptionSegment(
                    text=str(entry.get("text", "")),
                    start=entry.get("start"),
                    end=entry.get("end"),
                    speaker=entry.get("speaker"),
                    confidence=entry.get("confidence"),
                )
            )

        if not segments:
            transcript_text = (
                config.get("transcript_text")
                or self._config.get("transcript_text")
                or ""
            )
            if transcript_text:
                segments = [TranscriptionSegment(text=transcript_text, start=0.0, end=None)]

        metadata: Dict[str, Any] = {
            "provider": self.name,
            "language": config.get("language") or self._config.get("language"),
        }
        metadata.update(config.get("extra_metadata") or {})
        metadata.update(self._config.get("extra_metadata") or {})
        metadata.setdefault("media_uri", media_uri)
        metadata.setdefault("generated_at", datetime.utcnow().isoformat())
        return TranscriptionResult(segments=segments, metadata=metadata)


class WhisperLocalProvider:
    """Provider that runs a local Whisper model (faster-whisper or openai)."""

    name = "whisper_local"

    def __init__(self, config: TranscriptionSourceParams, logger: logging.Logger) -> None:
        self._config = config
        self.logger = logger
        if _WHISPER_BACKEND == "unavailable":
            raise RuntimeError(
                "Whisper local provider requires either 'faster-whisper' or 'openai-whisper'"
            )

    def transcribe(
        self,
        media_path: Path,
        *,
        media_uri: str,
        config: TranscriptionSourceParams,
        cancel_event: Event | None = None,
    ) -> TranscriptionResult:
        language = config.get("language") or self._config.get("language")
        diarization = config.get("diarization") or self._config.get("diarization")

        if _WHISPER_BACKEND == "faster_whisper":  # pragma: no cover - optional path
            model_name = config.get("whisper_model") or self._config.get("whisper_model") or "base"
            compute_type = (
                config.get("whisper_compute_type")
                or self._config.get("whisper_compute_type")
                or "int8"
            )
            model = WhisperModel(model_name, compute_type=compute_type)
            segments: List[TranscriptionSegment] = []
            total_conf = 0.0
            count_conf = 0
            for segment in model.transcribe(str(media_path), language=language)[0]:
                if cancel_event and cancel_event.is_set():
                    break
                confidence = segment.avg_logprob
                if confidence is not None:
                    total_conf += confidence
                    count_conf += 1
                segments.append(
                    TranscriptionSegment(
                        text=segment.text.strip(),
                        start=float(segment.start) if segment.start is not None else None,
                        end=float(segment.end) if segment.end is not None else None,
                        speaker=None,
                        confidence=float(confidence) if confidence is not None else None,
                    )
                )
            avg_conf = total_conf / count_conf if count_conf else None
            metadata: Dict[str, Any] = {
                "provider": self.name,
                "backend": _WHISPER_BACKEND,
                "language": language,
                "diarization": diarization,
                "average_confidence": avg_conf,
                "media_uri": media_uri,
            }
            return TranscriptionResult(segments=segments, metadata=metadata)

        # pragma: no cover - optional openai whisper branch
        model_name = config.get("whisper_model") or self._config.get("whisper_model") or "base"
        model = _openai_whisper.load_model(model_name)
        result = model.transcribe(str(media_path), language=language)
        segments = [
            TranscriptionSegment(
                text=segment.get("text", "").strip(),
                start=float(segment.get("start")) if segment.get("start") is not None else None,
                end=float(segment.get("end")) if segment.get("end") is not None else None,
                speaker=None,
                confidence=None,
            )
            for segment in result.get("segments", [])
        ]
        metadata = {
            "provider": self.name,
            "backend": _WHISPER_BACKEND,
            "language": language,
            "diarization": diarization,
            "media_uri": media_uri,
        }
        return TranscriptionResult(segments=segments, metadata=metadata)


class AwsTranscribeProvider:
    """Provider that schedules an asynchronous AWS Transcribe job and polls."""

    name = "aws_transcribe"

    def __init__(self, config: TranscriptionSourceParams, logger: logging.Logger) -> None:
        if boto3 is None:
            raise RuntimeError("AWS transcription requires 'boto3' to be installed")
        self._config = config
        self.logger = logger
        region = config.get("aws_region") or os.getenv("AWS_REGION") or "us-east-1"
        self.client = boto3.client("transcribe", region_name=region)

    def transcribe(
        self,
        media_path: Path,
        *,
        media_uri: str,
        config: TranscriptionSourceParams,
        cancel_event: Event | None = None,
    ) -> TranscriptionResult:
        params = dict(self._config.get("aws_transcribe_params") or {})
        params.update(config.get("aws_transcribe_params") or {})

        if not media_uri.startswith("s3://"):
            raise ValueError("AWS Transcribe provider requires media_uri to be an s3:// URL")

        job_name = params.get("TranscriptionJobName") or (
            (config.get("job_name_prefix") or self._config.get("job_name_prefix") or "transcription")
            + f"-{uuid4()}"
        )
        media_format = params.get("MediaFormat")
        if not media_format:
            suffix = Path(media_uri).suffix.lstrip(".")
            media_format = suffix or "mp3"
        job_args: Dict[str, Any] = {
            "TranscriptionJobName": job_name,
            "LanguageCode": params.get("LanguageCode")
            or config.get("language")
            or self._config.get("language")
            or "en-US",
            "Media": {"MediaFileUri": media_uri},
            "MediaFormat": media_format,
        }
        for key, value in params.items():
            if key not in job_args:
                job_args[key] = value

        self.client.start_transcription_job(**job_args)
        poll_seconds = config.get("poll_interval") or self._config.get("poll_interval") or 15.0

        while True:
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("Transcription cancelled")
            response = self.client.get_transcription_job(TranscriptionJobName=job_name)
            status = response["TranscriptionJob"]["TranscriptionJobStatus"]
            if status == "FAILED":  # pragma: no cover - depends on AWS
                reason = response["TranscriptionJob"].get("FailureReason", "unknown")
                raise RuntimeError(f"AWS Transcribe job failed: {reason}")
            if status == "COMPLETED":
                break
            time.sleep(float(poll_seconds))

        transcript_uri = response["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        resp = requests.get(transcript_uri, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("results", {}).get("items", [])
        segments: List[TranscriptionSegment] = []
        current_text_parts: List[str] = []
        start_time: Optional[float] = None
        end_time: Optional[float] = None
        for item in items:
            item_type = item.get("type")
            if item_type == "pronunciation":
                start_time = float(item.get("start_time")) if item.get("start_time") else start_time
                end_time = float(item.get("end_time")) if item.get("end_time") else end_time
                alternatives = item.get("alternatives", [])
                if alternatives:
                    current_text_parts.append(alternatives[0].get("content", ""))
            elif item_type == "punctuation":
                alternatives = item.get("alternatives", [])
                if alternatives:
                    current_text_parts.append(alternatives[0].get("content", ""))
            elif item_type == "speaker_label":
                # Ignore speaker labels in this simplified parser.
                pass
            if item.get("end_of_segment"):
                if current_text_parts:
                    text = " ".join(part for part in current_text_parts if part)
                    segments.append(
                        TranscriptionSegment(text=text.strip(), start=start_time, end=end_time)
                    )
                current_text_parts = []
                start_time = None
                end_time = None
        if current_text_parts:
            text = " ".join(part for part in current_text_parts if part)
            segments.append(
                TranscriptionSegment(text=text.strip(), start=start_time, end=end_time)
            )

        metadata = {
            "provider": self.name,
            "language": job_args.get("LanguageCode"),
            "job_name": job_name,
            "media_uri": media_uri,
            "media_format": media_format,
        }
        return TranscriptionResult(segments=segments, metadata=metadata)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _download_http(url: str, dest: Path, *, timeout: int = 30) -> Path:
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()
    with dest.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                fh.write(chunk)
    return dest


def _download_s3(uri: str, dest: Path) -> Path:
    if boto3 is None:
        raise RuntimeError("Downloading from s3:// requires boto3 to be installed")
    bucket, _, key = uri[5:].partition("/")
    if not bucket or not key:
        raise ValueError("Invalid S3 URI; expected s3://bucket/key")
    client = boto3.client("s3")
    client.download_file(bucket, key, str(dest))
    return dest


def _resolve_media(
    source: Source,
    params: TranscriptionSourceParams,
    *,
    logger: logging.Logger,
) -> tuple[Path, str, bool]:
    """Return a tuple (path, uri, should_cleanup)."""

    media_uri = (
        params.get("media_uri")
        or source.location
        or source.path
        or (str(source.url) if source.url else None)
    )
    if not media_uri:
        raise ValueError("Transcription sources require params.media_uri or source location")

    if media_uri.startswith("s3://"):
        tmp_dir = Path(tempfile.mkdtemp(prefix="transcription-"))
        tmp_path = tmp_dir / Path(media_uri).name
        logger.info("downloading media from %s", media_uri)
        _download_s3(media_uri, tmp_path)
        return tmp_path, media_uri, True

    if media_uri.startswith("http://") or media_uri.startswith("https://"):
        tmp_dir = Path(tempfile.mkdtemp(prefix="transcription-"))
        filename = Path(media_uri).name or f"download-{uuid4()}"
        tmp_path = tmp_dir / filename
        logger.info("downloading media from %s", media_uri)
        _download_http(media_uri, tmp_path)
        return tmp_path, media_uri, True

    path = Path(media_uri)
    if not path.exists():
        raise FileNotFoundError(f"Media path {media_uri} does not exist")
    return path, str(path), False


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            if chunk:
                h.update(chunk)
    return h.hexdigest()


def _load_cached_segments(cache_path: Path, checksum: str) -> Optional[TranscriptionResult]:
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if payload.get("media_checksum") != checksum:
        return None
    segments = [
        TranscriptionSegment(
            text=entry.get("text", ""),
            start=entry.get("start"),
            end=entry.get("end"),
            speaker=entry.get("speaker"),
            confidence=entry.get("confidence"),
        )
        for entry in payload.get("segments", [])
    ]
    metadata = payload.get("metadata", {})
    return TranscriptionResult(segments=segments, metadata=metadata)


def _persist_cache(cache_path: Path, checksum: str, result: TranscriptionResult) -> None:
    payload = {
        "media_checksum": checksum,
        "segments": [
            {
                "text": segment.text,
                "start": segment.start,
                "end": segment.end,
                "speaker": segment.speaker,
                "confidence": segment.confidence,
            }
            for segment in result.segments
        ],
        "metadata": result.metadata,
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Connector implementation
# ---------------------------------------------------------------------------


class TranscriptionConnector:
    """Connector responsible for orchestrating transcription jobs."""

    def __init__(self, source: Source, *, logger: logging.Logger | None = None) -> None:
        self.source = source
        self.logger = logger or logging.getLogger(__name__)
        params: TranscriptionSourceParams | Dict[str, Any] = source.params or {}
        self.params = params
        self.poll_interval = float(params.get("poll_interval") or 15.0)
        cache_dir = Path(params.get("cache_dir") or "tmp/transcriptions")
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir
        cache_key = (
            params.get("cache_key")
            or source.location
            or source.path
            or (str(source.url) if source.url else None)
            or str(source.id)
        )
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in cache_key)
        self.cache_path = cache_dir / f"{safe_name}.json"

        provider_name = (params.get("provider") or "whisper_local").lower()
        self.provider = self._create_provider(provider_name)

        self.job_metadata: Dict[str, Any] = {
            "provider": provider_name,
            "segments": 0,
        }
        self.next_sync_state: Dict[str, Any] = dict(source.sync_state or {})

    # ------------------------------------------------------------------
    # Provider factory
    # ------------------------------------------------------------------

    def _create_provider(self, name: str) -> BaseTranscriptionProvider:
        if name in {"mock", "test"}:
            return MockTranscriptionProvider(self.params)
        if name in {"whisper", "whisper_local"}:
            return WhisperLocalProvider(self.params, self.logger)
        if name in {"aws", "aws_transcribe"}:
            return AwsTranscribeProvider(self.params, self.logger)
        raise ValueError(f"Unsupported transcription provider '{name}'")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stream(self, cancel_event: Event | None = None) -> Iterable[ConnectorRecord]:
        media_path, media_uri, should_cleanup = _resolve_media(
            self.source, self.params, logger=self.logger
        )
        try:
            checksum = _sha256(media_path)
            cache_ttl = self.params.get("cache_ttl_seconds")
            result: TranscriptionResult | None = None
            use_cache = False
            if self.cache_path.exists() and cache_ttl is not None:
                mtime = datetime.fromtimestamp(self.cache_path.stat().st_mtime)
                if datetime.utcnow() - mtime <= timedelta(seconds=int(cache_ttl)):
                    use_cache = True

            if not use_cache and self.source.sync_state:
                prev_checksum = self.source.sync_state.get("media_checksum")
                if prev_checksum == checksum:
                    use_cache = True

            if use_cache:
                result = _load_cached_segments(self.cache_path, checksum)

            if result is None:
                self.logger.info("running transcription provider=%s", self.provider.name)
                result = self.provider.transcribe(
                    media_path,
                    media_uri=media_uri,
                    config=self.params,
                    cancel_event=cancel_event,
                )
                _persist_cache(self.cache_path, checksum, result)

            self.job_metadata["cache_hit"] = bool(result is not None and use_cache)

            if cancel_event and cancel_event.is_set():
                return

            if not result.segments:
                self.logger.warning("no segments produced for %s", media_uri)
                return

            total_text = "\n".join(segment.text for segment in result.segments if segment.text)
            mime_type = (
                self.params.get("output_mime_type")
                or result.metadata.get("mime_type")
                or "text/plain+transcript"
            )

            chunks: List[Chunk] = []
            for idx, segment in enumerate(result.segments, start=1):
                extra = {
                    **(result.metadata.get("chunk_extra", {}) or {}),
                    **segment.to_metadata(),
                }
                if result.metadata.get("language"):
                    extra.setdefault("transcript_language", result.metadata["language"])
                extra.setdefault("transcript_index", idx)
                extra.setdefault("transcript_provider", result.metadata.get("provider"))
                chunk_text = segment.text.strip()
                if not chunk_text:
                    continue
                chunks.append(
                    Chunk(
                        content=chunk_text,
                        source_path=media_uri,
                        mime_type=mime_type,
                        page_number=idx,
                        extra=extra,
                    )
                )

            if not chunks:
                return

            self.job_metadata.update(
                {
                    "segments": len(chunks),
                    "language": result.metadata.get("language"),
                    "provider": result.metadata.get("provider", self.provider.name),
                }
            )

            document_state = {
                "media_checksum": checksum,
                "provider": result.metadata.get("provider", self.provider.name),
                "language": result.metadata.get("language"),
                "cache_path": str(self.cache_path),
                "segments": len(chunks),
                "generated_at": result.metadata.get("generated_at")
                or datetime.utcnow().isoformat(),
            }
            document_state.update(result.metadata)

            self.next_sync_state.update(
                {
                    "media_checksum": checksum,
                    "cache_path": str(self.cache_path),
                    "language": result.metadata.get("language"),
                }
            )

            yield ConnectorRecord(
                document_path=media_uri,
                chunks=chunks,
                bytes_len=len(total_text.encode("utf-8")),
                page_count=len(chunks),
                document_sync_state=document_state,
                extra_info={
                    "provider": result.metadata.get("provider", self.provider.name),
                    "language": result.metadata.get("language"),
                },
            )
        finally:
            if should_cleanup:
                try:
                    shutil.rmtree(media_path.parent)
                except Exception:  # pragma: no cover - best effort cleanup
                    pass


__all__ = ["TranscriptionConnector", "TranscriptionSegment", "TranscriptionResult"]

