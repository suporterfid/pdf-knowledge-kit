"""Prompt template helpers for the agent service."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


class PromptTemplateStore:
    """Resolve prompt templates based on agent persona and provider."""

    _DEFAULT_TEMPLATES: Mapping[str, Mapping[str, str]] = {
        "general": {
            "default": "You are a helpful general-purpose assistant. Be concise and friendly.",
            "anthropic": "You are an insightful assistant. Provide balanced and thoughtful answers.",
        },
        "support": {
            "default": "You are a customer support agent. Empathise, clarify the issue and provide steps to resolve it.",
        },
        "sales": {
            "default": "You are a persuasive sales assistant. Qualify the lead and highlight product value with warmth.",
        },
        "hr": {
            "default": "You are an HR assistant. Provide policy guidance with empathy and clarity.",
        },
    }

    def __init__(self, extra_templates: Optional[Mapping[str, Mapping[str, str]]] = None):
        self._templates: Dict[str, Dict[str, str]] = {
            key: dict(value) for key, value in self._DEFAULT_TEMPLATES.items()
        }
        if extra_templates:
            for persona, mapping in extra_templates.items():
                merged = self._templates.setdefault(persona, {})
                merged.update(mapping)

    def resolve(self, persona: Optional[Dict[str, Any]], provider: str, custom_template: Optional[str]) -> str:
        """Return the prompt template for the persona/provider combination."""

        if custom_template:
            return custom_template
        persona_type = (persona or {}).get("type") or (persona or {}).get("persona") or "general"
        persona_type = str(persona_type).lower()
        provider_key = provider.lower()
        persona_templates = self._templates.get(persona_type)
        if persona_templates:
            if provider_key in persona_templates:
                return persona_templates[provider_key]
            if "default" in persona_templates:
                return persona_templates["default"]
        fallback = self._templates["general"]
        return fallback.get(provider_key) or fallback["default"]

    def render(self, base_template: str, persona: Optional[Dict[str, Any]], user_input: str) -> str:
        """Render the final prompt for preview/testing."""

        persona_instructions = ""
        if persona:
            traits = ", ".join(f"{k}: {v}" for k, v in persona.items() if k != "type")
            if traits:
                persona_instructions = f"\nPersona traits: {traits}"
        return f"{base_template}\nUser input: {user_input}{persona_instructions}".strip()
