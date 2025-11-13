"""Database connector that streams rows as text chunks."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from threading import Event
from typing import Any

import psycopg
from psycopg import conninfo as psycopg_conninfo
from psycopg.rows import dict_row

from ..chunking import chunk_text
from ..models import DatabaseQueryConfig, DatabaseSourceParams, Source
from . import ConnectorRecord


class SqlConnector:
    """Execute configured SQL queries and emit chunked rows."""

    def __init__(self, source: Source, *, logger: logging.Logger | None = None):
        self.source = source
        self.logger = logger or logging.getLogger(__name__)
        params: DatabaseSourceParams | dict[str, Any] = source.params or {}
        queries = list(params.get("queries") or [])
        if not queries:
            raise ValueError("database connector requires params.queries")
        self._queries: list[DatabaseQueryConfig] = queries
        self._conninfo = self._resolve_conninfo(params, source.credentials)
        base_state = dict(source.sync_state or {})
        queries_state = dict(base_state.get("queries") or {})
        self.next_sync_state: dict[str, Any] = {
            **base_state,
            "queries": dict(queries_state),
        }
        self.job_metadata: dict[str, Any] = {
            "queries": len(self._queries),
            "rows": 0,
            "chunks": 0,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_conninfo(
        params: DatabaseSourceParams | dict[str, Any], credentials: Any
    ) -> str:
        if isinstance(params, dict) and params.get("dsn"):
            return str(params["dsn"])

        options: dict[str, Any] = {}
        if isinstance(params, dict):
            if params.get("host"):
                options["host"] = params["host"]
            if params.get("port"):
                options["port"] = params["port"]
            if params.get("database"):
                options["dbname"] = params["database"]
            if params.get("user"):
                options["user"] = params["user"]

        if isinstance(credentials, dict):
            if credentials.get("username") and not options.get("user"):
                options["user"] = credentials.get("username")
            if credentials.get("user") and not options.get("user"):
                options["user"] = credentials.get("user")
            if credentials.get("password"):
                options["password"] = credentials.get("password")
        elif isinstance(credentials, str) and credentials:
            options.setdefault("password", credentials)

        clean_opts = {k: v for k, v in options.items() if v is not None}
        if not clean_opts:
            raise ValueError(
                "database connector requires connection parameters or credentials"
            )
        return psycopg_conninfo.make_conninfo(**clean_opts)

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return str(value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stream(self, cancel_event: Event | None = None) -> Iterable[ConnectorRecord]:
        """Yield :class:`ConnectorRecord` entries for each database row."""

        base_state = dict(self.source.sync_state or {})
        existing_queries = dict(base_state.get("queries") or {})
        next_queries: dict[str, Any] = dict(existing_queries)

        with psycopg.connect(self._conninfo, row_factory=dict_row) as conn:
            for index, query_cfg in enumerate(self._queries):
                if cancel_event and cancel_event.is_set():
                    break

                query_name = (
                    query_cfg.get("name") or query_cfg.get("table") or f"query_{index}"
                )
                sql = query_cfg.get("sql")
                if not sql:
                    raise ValueError(f"query '{query_name}' is missing required sql")

                text_column = query_cfg.get("text_column")
                id_column = query_cfg.get("id_column")
                if not text_column or not id_column:
                    raise ValueError(
                        f"query '{query_name}' requires text_column and id_column"
                    )

                cursor_column = query_cfg.get("cursor_column")
                cursor_param = query_cfg.get("cursor_param", "cursor")
                query_params = dict(query_cfg.get("params") or {})
                existing_cursor_state = existing_queries.get(query_name) or {}
                cursor_value = existing_cursor_state.get(
                    "cursor", query_cfg.get("initial_cursor")
                )
                if cursor_column and cursor_value is not None:
                    query_params.setdefault(cursor_param, cursor_value)

                latest_cursor = None

                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(sql, query_params or None)
                    for row in cur:
                        if cancel_event and cancel_event.is_set():
                            break

                        text_value = row.get(text_column)
                        if text_value is None:
                            continue

                        record_id = row.get(id_column)
                        document_template = (
                            query_cfg.get("document_path_template") or "{table}/{id}"
                        )
                        document_path = document_template.format(
                            table=query_cfg.get("table") or query_name,
                            id=record_id,
                            query=query_name,
                        )

                        extra_metadata: dict[str, Any] = {
                            "connector": "sql",
                            "query": query_name,
                            "table": query_cfg.get("table") or query_name,
                            "row_id": self._json_safe(record_id),
                        }

                        for column in query_cfg.get("extra_metadata_fields") or []:
                            if column in row:
                                extra_metadata[column] = self._json_safe(row[column])

                        if cursor_column and cursor_column in row:
                            latest_cursor = row[cursor_column]
                            extra_metadata[cursor_column] = self._json_safe(
                                latest_cursor
                            )

                        text_str = str(text_value)
                        chunks = chunk_text(
                            text_str,
                            source_path=document_path,
                            mime_type=query_cfg.get("mime_type", "text/plain"),
                            page_number=1,
                            extra_metadata=extra_metadata,
                        )

                        if not chunks:
                            continue

                        self.job_metadata["rows"] += 1
                        self.job_metadata["chunks"] += len(chunks)

                        document_state: dict[str, Any] | None = None
                        if cursor_column and latest_cursor is not None:
                            document_state = {
                                "query": query_name,
                                "cursor_column": cursor_column,
                                "cursor": self._json_safe(latest_cursor),
                                "row_id": self._json_safe(record_id),
                            }

                        yield ConnectorRecord(
                            document_path=document_path,
                            chunks=chunks,
                            bytes_len=len(text_str.encode("utf-8")),
                            page_count=1,
                            document_sync_state=document_state,
                            extra_info={
                                "query": query_name,
                                "row_id": self._json_safe(record_id),
                            },
                        )

                if latest_cursor is not None:
                    next_queries[query_name] = {
                        "cursor": self._json_safe(latest_cursor),
                        "cursor_column": cursor_column,
                    }

        self.next_sync_state = {**base_state, "queries": next_queries}


__all__ = ["SqlConnector"]
