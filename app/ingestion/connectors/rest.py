"""REST connector that fetches JSON resources and emits text chunks."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from threading import Event
from typing import Any
from urllib.parse import urljoin

import requests

from ..chunking import chunk_text
from ..models import ApiSourceParams, Source
from . import ConnectorRecord


class RestConnector:
    """Fetch paginated REST endpoints and emit chunks for each record."""

    def __init__(
        self,
        source: Source,
        *,
        session: requests.Session | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.source = source
        self.logger = logger or logging.getLogger(__name__)
        self.session = session or requests.Session()
        params: ApiSourceParams | dict[str, Any] = source.params or {}
        endpoint = params.get("endpoint")
        if not endpoint and not source.url:
            raise ValueError("REST connector requires params.endpoint or source.url")
        base_url = params.get("base_url") or (str(source.url) if source.url else "")
        if endpoint and endpoint.startswith("http"):
            self._endpoint_url = endpoint
        elif endpoint:
            if not base_url:
                raise ValueError(
                    "REST connector requires params.base_url when endpoint is relative"
                )
            self._endpoint_url = urljoin(
                base_url.rstrip("/") + "/", endpoint.lstrip("/")
            )
        else:
            self._endpoint_url = base_url

        self._method = (params.get("method") or "GET").upper()
        self._headers = self._prepare_headers(params.get("headers") or {})
        self._query_params = dict(params.get("query_params") or {})
        self._body = dict(params.get("body") or {})
        self._pagination = dict(params.get("pagination") or {})
        self._records_path = params.get("records_path") or "data"
        self._id_field = params.get("id_field") or "id"
        self._text_fields = params.get("text_fields") or ["content"]
        self._timestamp_field = params.get("timestamp_field")
        self._mime_type = params.get("mime_type") or "application/json"
        self._document_template = (
            params.get("document_path_template") or "{endpoint}/{id}"
        )

        base_state = dict(source.sync_state or {})
        self.next_sync_state: dict[str, Any] = dict(base_state)
        self.job_metadata: dict[str, Any] = {
            "pages": 0,
            "records": 0,
            "chunks": 0,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _prepare_headers(self, headers: dict[str, str]) -> dict[str, str]:
        prepared = dict(headers)
        credentials = self.source.credentials or {}
        if isinstance(credentials, dict):
            for key, value in list(prepared.items()):
                if isinstance(value, str):
                    try:
                        prepared[key] = value.format(**credentials)
                    except Exception:
                        prepared[key] = value
        elif isinstance(credentials, str):
            for key, value in list(prepared.items()):
                if isinstance(value, str):
                    prepared[key] = value.format(token=credentials)
        return prepared

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return str(value)

    @staticmethod
    def _lookup(payload: Any, path: str | None) -> Any:
        if not path:
            return payload
        current = payload
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list):
                try:
                    index = int(part)
                except ValueError:
                    return None
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                return None
        return current

    def _prepare_request(self, cursor: Any, page: int | None) -> dict[str, Any]:
        params = dict(self._query_params)
        pagination_type = self._pagination.get("type", "cursor")
        if pagination_type == "cursor" and cursor is not None:
            params[self._pagination.get("cursor_param", "cursor")] = cursor
        elif pagination_type == "page" and page is not None:
            params[self._pagination.get("page_param", "page")] = page
            if self._pagination.get("page_size_param") and self._pagination.get(
                "page_size"
            ):
                params.setdefault(
                    self._pagination["page_size_param"],
                    self._pagination["page_size"],
                )

        request_kwargs: dict[str, Any] = {"headers": self._headers, "timeout": 30}
        if self._method in {"GET", "DELETE"}:
            request_kwargs["params"] = params
        else:
            request_kwargs["params"] = params
            request_kwargs["json"] = self._body
        return request_kwargs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stream(self, cancel_event: Event | None = None) -> Iterable[ConnectorRecord]:
        """Yield :class:`ConnectorRecord` entries for each REST resource."""

        pagination_type = self._pagination.get("type", "cursor")
        cursor = self.next_sync_state.get("cursor")
        page = self.next_sync_state.get("page", self._pagination.get("start_page", 1))

        while True:
            if cancel_event and cancel_event.is_set():
                break

            request_kwargs = self._prepare_request(
                cursor, page if pagination_type == "page" else None
            )
            response = self.session.request(
                self._method, self._endpoint_url, **request_kwargs
            )
            response.raise_for_status()
            payload = response.json()
            self.job_metadata["pages"] += 1

            records = self._lookup(payload, self._records_path)
            if records is None:
                records = []
            if not isinstance(records, list):
                raise ValueError(
                    "REST connector expects the records_path to resolve to a list"
                )

            for record in records:
                if cancel_event and cancel_event.is_set():
                    break

                text_parts: list[str] = []
                for field in self._text_fields:
                    value = self._lookup(record, field)
                    if value is not None:
                        text_parts.append(str(value))

                text_body = "\n\n".join(part for part in text_parts if part).strip()
                if not text_body:
                    continue

                record_id = self._lookup(record, self._id_field)
                if record_id is None:
                    raise ValueError(
                        "REST connector requires id_field to be present in records"
                    )

                timestamp_value = None
                if self._timestamp_field:
                    timestamp_value = self._lookup(record, self._timestamp_field)

                document_path = self._document_template.format(
                    endpoint=self._endpoint_url.rstrip("/").split("//")[-1],
                    id=record_id,
                )

                extra_metadata: dict[str, Any] = {
                    "connector": "rest",
                    "endpoint": self._endpoint_url,
                    "record_id": self._json_safe(record_id),
                }
                if timestamp_value is not None:
                    extra_metadata["timestamp"] = self._json_safe(timestamp_value)

                chunks = chunk_text(
                    text_body,
                    source_path=document_path,
                    mime_type=self._mime_type,
                    page_number=1,
                    extra_metadata=extra_metadata,
                )

                if not chunks:
                    continue

                self.job_metadata["records"] += 1
                self.job_metadata["chunks"] += len(chunks)

                document_state = {
                    "record_id": self._json_safe(record_id),
                }
                if timestamp_value is not None:
                    document_state["timestamp"] = self._json_safe(timestamp_value)

                yield ConnectorRecord(
                    document_path=document_path,
                    chunks=chunks,
                    bytes_len=len(text_body.encode("utf-8")),
                    page_count=1,
                    document_sync_state=document_state,
                    extra_info={
                        "endpoint": self._endpoint_url,
                        "record_id": self._json_safe(record_id),
                    },
                )

            # Pagination cursor update
            if pagination_type == "cursor":
                next_cursor = self._lookup(
                    payload, self._pagination.get("next_cursor_path", "next")
                )
                if not next_cursor or next_cursor == cursor:
                    self.next_sync_state["cursor"] = self._json_safe(next_cursor)
                    break
                cursor = next_cursor
                self.next_sync_state["cursor"] = self._json_safe(cursor)
            else:
                page = (page or 0) + 1
                self.next_sync_state["page"] = page
                expected_page_size = self._pagination.get("page_size")
                if expected_page_size and len(records) < int(expected_page_size):
                    break
                if not records:
                    break


__all__ = ["RestConnector"]
