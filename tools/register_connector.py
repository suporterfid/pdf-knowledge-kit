"""Utility CLI for registering connectors and monitoring ingestion jobs."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, Iterable, Optional

import requests

DEFAULT_POLL_SECONDS = 5.0


def _build_headers(api_key: str) -> Dict[str, str]:
    return {"X-API-Key": api_key}


def _request(
    session: requests.Session,
    method: str,
    host: str,
    path: str,
    *,
    api_key: str,
    **kwargs: Any,
) -> requests.Response:
    url = host.rstrip("/") + path
    headers = kwargs.pop("headers", {})
    headers.update(_build_headers(api_key))
    resp = session.request(method, url, headers=headers, timeout=30, **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed: {resp.status_code} {resp.text}")
    return resp


def _normalise_json(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


def _find_definition_id(
    session: requests.Session,
    host: str,
    *,
    api_key: str,
    name: str,
) -> Optional[str]:
    resp = _request(
        session,
        "GET",
        host,
        "/api/admin/ingest/connector_definitions",
        api_key=api_key,
    )
    payload = resp.json()
    for item in payload.get("items", []):
        if item.get("name") == name:
            return item.get("id")
    return None


def register_definition(
    session: requests.Session,
    host: str,
    *,
    api_key: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    existing_id = _find_definition_id(session, host, api_key=api_key, name=payload["name"])
    method = "POST" if existing_id is None else "PUT"
    path = "/api/admin/ingest/connector_definitions"
    if existing_id:
        path += f"/{existing_id}"
    resp = _request(
        session,
        method,
        host,
        path,
        api_key=api_key,
        json=payload,
    )
    return resp.json()


def trigger_job(
    session: requests.Session,
    host: str,
    *,
    api_key: str,
    connector_type: str,
    job_payload: Dict[str, Any],
) -> str:
    path_map = {
        "database": "/api/admin/ingest/database",
        "api": "/api/admin/ingest/api",
        "transcription": "/api/admin/ingest/transcription",
    }
    path = path_map[connector_type]
    resp = _request(
        session,
        "POST",
        host,
        path,
        api_key=api_key,
        json=job_payload,
    )
    return resp.json()["job_id"]


def poll_job(
    session: requests.Session,
    host: str,
    *,
    api_key: str,
    job_id: str,
    poll_seconds: float,
) -> Dict[str, Any]:
    while True:
        resp = _request(
            session,
            "GET",
            host,
            f"/api/admin/ingest/jobs/{job_id}",
            api_key=api_key,
        )
        job = resp.json()
        status = job.get("status")
        print(f"job={job_id} status={status} updated_at={job.get('updated_at')}")
        if status in {"succeeded", "failed", "canceled"}:
            return job
        time.sleep(poll_seconds)


def follow_logs(
    session: requests.Session,
    host: str,
    *,
    api_key: str,
    job_id: str,
    poll_seconds: float,
) -> None:
    offset = 0
    while True:
        resp = _request(
            session,
            "GET",
            host,
            f"/api/admin/ingest/jobs/{job_id}/logs",
            api_key=api_key,
            params={"offset": offset},
        )
        payload = resp.json()
        content = payload.get("content") or ""
        if content:
            sys.stdout.write(content)
            sys.stdout.flush()
        offset = payload.get("next_offset", offset)
        status = payload.get("status")
        if status in {"succeeded", "failed", "canceled"}:
            break
        time.sleep(poll_seconds)


def load_source(
    session: requests.Session,
    host: str,
    *,
    api_key: str,
    source_id: str,
) -> Dict[str, Any]:
    resp = _request(
        session,
        "GET",
        host,
        "/api/admin/ingest/sources",
        api_key=api_key,
        params={"active": "true"},
    )
    for item in resp.json().get("items", []):
        if item.get("id") == source_id:
            return item
    raise RuntimeError(f"Source {source_id} not found")


def build_database_payload(args: argparse.Namespace) -> Dict[str, Any]:
    queries: Iterable[Dict[str, Any]]
    if args.database_query_sql:
        queries = [
            _normalise_json(
                {
                    "name": args.database_query_name,
                    "sql": args.database_query_sql,
                    "text_column": args.database_text_column,
                    "id_column": args.database_id_column,
                }
            )
        ]
    else:
        queries = []
    params = _normalise_json(
        {
            "dsn": args.database_dsn,
            "host": args.database_host,
            "database": args.database_name,
            "queries": list(queries),
        }
    )
    credentials = None
    if args.database_username or args.database_password:
        credentials = {
            "values": _normalise_json(
                {
                    "username": args.database_username,
                    "password": args.database_password,
                }
            )
        }
    return {
        "type": "database",
        "params": params,
        "credentials": credentials,
    }


def build_api_payload(args: argparse.Namespace) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    for entry in args.api_header:
        if "=" not in entry:
            raise ValueError(f"Invalid header format: {entry!r}")
        key, value = entry.split("=", 1)
        headers[key.strip()] = value.strip()
    params = _normalise_json(
        {
            "base_url": args.api_base,
            "endpoint": args.api_endpoint,
            "id_field": args.api_id_field,
            "text_fields": args.text_field,
            "pagination": None,
        }
    )
    credentials = None
    if args.api_token or headers:
        credentials = {
            "values": _normalise_json(
                {
                    "token": args.api_token,
                    "headers": headers if headers else None,
                }
            )
        }
    return {
        "type": "api",
        "params": params,
        "credentials": credentials,
    }


def build_transcription_payload(args: argparse.Namespace) -> Dict[str, Any]:
    params = _normalise_json(
        {
            "provider": args.provider,
            "media_uri": args.media_uri,
            "language": args.language,
            "cache_dir": args.cache_dir,
        }
    )
    credentials = None
    if args.aws_access_key and args.aws_secret_key:
        credentials = {
            "values": {
                "aws_access_key_id": args.aws_access_key,
                "aws_secret_access_key": args.aws_secret_key,
            }
        }
    return {
        "type": "audio_transcript",
        "params": params,
        "credentials": credentials,
        "connector_metadata": _normalise_json({"media_type": args.media_type}),
    }


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="http://localhost:8000", help="FastAPI base URL")
    parser.add_argument("--operator-key", required=True, help="API key with operator role")
    parser.add_argument("--viewer-key", help="Viewer API key used for log polling")
    parser.add_argument("--name", required=True, help="Connector definition name")
    parser.add_argument("--description", help="Optional description for the connector")
    parser.add_argument("--label", help="Label applied to the source during job run")
    parser.add_argument("--run-now", action="store_true", help="Trigger an ingestion job after registering")
    parser.add_argument("--job-id", help="Monitor an existing job instead of triggering a new one")
    parser.add_argument("--follow-logs", action="store_true", help="Stream job logs while polling status")
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)

    subparsers = parser.add_subparsers(dest="connector_type", required=True)

    db_parser = subparsers.add_parser("database", help="Register a database connector")
    db_parser.add_argument("--database-dsn")
    db_parser.add_argument("--database-host")
    db_parser.add_argument("--database-name")
    db_parser.add_argument("--database-username")
    db_parser.add_argument("--database-password")
    db_parser.add_argument("--database-query-sql")
    db_parser.add_argument("--database-query-name")
    db_parser.add_argument("--database-text-column")
    db_parser.add_argument("--database-id-column")

    api_parser = subparsers.add_parser("api", help="Register a REST connector")
    api_parser.add_argument("--api-base")
    api_parser.add_argument("--api-endpoint", required=True)
    api_parser.add_argument("--api-id-field", required=True)
    api_parser.add_argument("--text-field", action="append", required=True)
    api_parser.add_argument("--api-token")
    api_parser.add_argument("--api-header", action="append", default=[])

    tr_parser = subparsers.add_parser("transcription", help="Register a transcription connector")
    tr_parser.add_argument("--provider", default="mock")
    tr_parser.add_argument("--media-uri", required=True)
    tr_parser.add_argument("--language")
    tr_parser.add_argument("--cache-dir")
    tr_parser.add_argument("--media-type", choices=["audio", "video"], default="audio")
    tr_parser.add_argument("--aws-access-key")
    tr_parser.add_argument("--aws-secret-key")

    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    session = requests.Session()

    base_payload: Dict[str, Any]
    if args.connector_type == "database":
        base_payload = build_database_payload(args)
    elif args.connector_type == "api":
        base_payload = build_api_payload(args)
    else:
        base_payload = build_transcription_payload(args)

    definition_payload = dict(base_payload)
    definition_payload.update({"name": args.name, "description": args.description})
    definition_payload = _normalise_json(definition_payload)

    definition = register_definition(
        session,
        args.host,
        api_key=args.operator_key,
        payload=definition_payload,
    )
    print(f"definition_id={definition.get('id')} type={definition.get('type')}")

    job_id: Optional[str] = args.job_id
    if args.run_now and not job_id:
        job_payload = {
            "connector_definition_id": definition["id"],
            "label": args.label,
        }
        for key in ("params", "credentials", "connector_metadata"):
            value = base_payload.get(key)
            if value:
                job_payload[key] = value
        job_payload = _normalise_json(job_payload)
        job_id = trigger_job(
            session,
            args.host,
            api_key=args.operator_key,
            connector_type=args.connector_type,
            job_payload=job_payload,
        )
        print(f"triggered job_id={job_id}")

    if not job_id:
        return

    viewer_key = args.viewer_key or args.operator_key
    job = poll_job(
        session,
        args.host,
        api_key=viewer_key,
        job_id=job_id,
        poll_seconds=args.poll_seconds,
    )

    if args.follow_logs:
        follow_logs(
            session,
            args.host,
            api_key=viewer_key,
            job_id=job_id,
            poll_seconds=args.poll_seconds,
        )

    source_id = job.get("source_id")
    if source_id:
        source = load_source(session, args.host, api_key=viewer_key, source_id=source_id)
        print("\nSource summary:")
        print(json.dumps(
            {
                "id": source.get("id"),
                "type": source.get("type"),
                "label": source.get("label"),
                "version": source.get("version"),
                "sync_state": source.get("sync_state"),
            },
            indent=2,
            default=str,
        ))


if __name__ == "__main__":
    main()
