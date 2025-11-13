"""Provider credential helpers supporting multiple LLM vendors."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCredentials:
    """Container for credentials resolved for a provider."""

    provider: str
    api_key: str | None
    extras: dict[str, str]

    def as_headers(self) -> dict[str, str]:
        """Return HTTP headers suitable for calling the provider API."""

        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        for key, value in self.extras.items():
            headers[key] = value
        return headers


class ProviderRegistry:
    """Resolve provider credentials from environment or explicit overrides."""

    _DEFAULT_ENV_MAP: Mapping[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "meta": "META_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
    }

    def __init__(self, overrides: Mapping[str, Mapping[str, str]] | None = None):
        self._overrides = {
            (k.lower() if isinstance(k, str) else k): dict(v)
            for k, v in (overrides or {}).items()
        }

    def get_credentials(self, provider: str) -> ProviderCredentials:
        """Return credentials for ``provider``.

        The lookup order prefers explicit overrides (e.g. injected during
        testing) and falls back to environment variables using
        ``_DEFAULT_ENV_MAP``.
        """

        key = provider.lower()
        if key in self._overrides:
            override = self._overrides[key]
            return ProviderCredentials(
                provider=provider,
                api_key=override.get("api_key"),
                extras={k: v for k, v in override.items() if k != "api_key"},
            )
        env_var = self._DEFAULT_ENV_MAP.get(key)
        api_key = os.getenv(env_var) if env_var else None
        extras: dict[str, str] = {}
        if key == "azure":
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            if endpoint:
                extras["X-API-Endpoint"] = endpoint
        return ProviderCredentials(provider=provider, api_key=api_key, extras=extras)

    def list_supported_providers(self) -> dict[str, str | None]:
        """Return a mapping of supported providers to resolved API keys."""

        providers = set(self._DEFAULT_ENV_MAP.keys()) | set(self._overrides.keys())
        return {name: self.get_credentials(name).api_key for name in sorted(providers)}
