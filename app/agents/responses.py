"""Response parameter defaults for agent executions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ResponseParameterStore:
    """Maintain provider specific response parameter defaults."""

    _DEFAULTS: Mapping[str, dict[str, Any]] = {
        "openai": {"temperature": 0.7, "max_tokens": 1024},
        "anthropic": {"temperature": 0.2, "max_tokens": 2048},
        "google": {"temperature": 0.3, "candidate_count": 1},
        "meta": {"temperature": 0.6},
        "azure": {"temperature": 0.65, "max_tokens": 1024},
    }

    def __init__(self, overrides: Mapping[str, Mapping[str, Any]] | None = None):
        self._defaults: dict[str, dict[str, Any]] = {
            provider: dict(params) for provider, params in self._DEFAULTS.items()
        }
        if overrides:
            for provider, params in overrides.items():
                merged = self._defaults.setdefault(provider.lower(), {})
                merged.update(params)

    def defaults_for_provider(self, provider: str) -> dict[str, Any]:
        """Return defaults for ``provider``."""

        return dict(self._defaults.get(provider.lower(), {"temperature": 0.5}))

    def merge(self, provider: str, *overrides: dict[str, Any] | None) -> dict[str, Any]:
        """Merge multiple overrides on top of provider defaults."""

        params = self.defaults_for_provider(provider)
        for override in overrides:
            if override:
                params.update(override)
        return params
