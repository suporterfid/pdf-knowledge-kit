"""Compatibility module for legacy imports.

This file simply aliases :mod:`app.ingestion.service` so existing imports of
``ingest`` continue to work. Any attribute set on this module actually modifies
``app.ingestion.service``.
"""
import sys
from app.ingestion import service as _service

sys.modules[__name__] = _service
