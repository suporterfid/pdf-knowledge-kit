"""Lightweight NLP utilities for intent, entity and sentiment extraction."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from langdetect import detect, LangDetectException

_POSITIVE = {"great", "good", "awesome", "love", "thanks", "helpful"}
_NEGATIVE = {"bad", "terrible", "angry", "hate", "upset", "cancel", "complain"}

_INTENT_PATTERNS = {
    "complaint": re.compile(r"\bcomplain|not\s+working|angry\b", re.I),
    "cancellation": re.compile(r"\bcancel|terminate|stop\b", re.I),
    "support_followup": re.compile(r"follow\s*up|check\s+back", re.I),
    "callback_request": re.compile(r"call\s+me|phone\s+me", re.I),
}

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_AMOUNT_PATTERN = re.compile(r"\b\$?(\d+[.,]?\d*)\b")
_DATETIME_PATTERN = re.compile(r"\b(?:tomorrow|next week|next monday|later today)\b", re.I)


@dataclass
class NlpPipeline:
    """Deterministic NLP pipeline used across adapters and services."""

    def analyse(self, text: str) -> Dict[str, Any]:
        text = text or ""
        lowered = text.lower()
        intent_label = "unknown"
        intent_score = 0.0
        for label, pattern in _INTENT_PATTERNS.items():
            if pattern.search(text):
                intent_label = label
                intent_score = 0.9
                break
        if intent_label == "unknown" and "help" in lowered:
            intent_label = "support"
            intent_score = 0.6
        sentiment = self._sentiment(lowered)
        entities = self._entities(text)
        language = self._language(text)
        return {
            "intent": {"label": intent_label, "confidence": intent_score},
            "entities": entities,
            "sentiment": sentiment,
            "language": language,
        }

    def _sentiment(self, lowered: str) -> Dict[str, Any]:
        positives = sum(1 for token in _POSITIVE if token in lowered)
        negatives = sum(1 for token in _NEGATIVE if token in lowered)
        score = 0.0
        label = "neutral"
        if positives or negatives:
            score = (positives - negatives) / max(positives + negatives, 1)
            if score > 0:
                label = "positive"
            elif score < 0:
                label = "negative"
        if label == "negative":
            score = min(abs(score), 1.0)
        else:
            score = min(score, 1.0)
        return {"label": label, "score": abs(score)}

    def _entities(self, text: str) -> List[Dict[str, Any]]:
        entities: List[Dict[str, Any]] = []
        for match in _EMAIL_PATTERN.finditer(text):
            entities.append(
                {
                    "type": "email",
                    "value": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        for match in _AMOUNT_PATTERN.finditer(text):
            entities.append(
                {
                    "type": "amount",
                    "value": match.group(1),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        for match in _DATETIME_PATTERN.finditer(text):
            value = datetime.now(timezone.utc)
            if "tomorrow" in match.group(0).lower():
                value += timedelta(days=1)
            elif "next week" in match.group(0).lower():
                value += timedelta(days=7)
            elif "next monday" in match.group(0).lower():
                days_ahead = (0 - value.weekday() + 7) % 7 or 7
                value += timedelta(days=days_ahead)
            else:  # later today
                value += timedelta(hours=4)
            entities.append(
                {
                    "type": "datetime",
                    "value": value.isoformat(),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        return entities

    def _language(self, text: str) -> Optional[str]:
        try:
            return detect(text) if text else None
        except LangDetectException:
            return None
