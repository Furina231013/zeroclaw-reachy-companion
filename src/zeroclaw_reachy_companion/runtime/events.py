from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CompanionEvent:
    """Mockable external event for Phase 1/2 companion behavior tests."""

    type: str
    confidence: float = 1.0
    source: str = "mock"
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: "CompanionEvent | dict[str, Any]") -> "CompanionEvent":
        if isinstance(value, CompanionEvent):
            return value
        if not isinstance(value, dict):
            raise TypeError("event must be a CompanionEvent or dict")

        event_type = value.get("type")
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event.type is required")

        payload = value.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}

        return cls(
            type=event_type.strip(),
            confidence=float(value.get("confidence", 1.0)),
            source=str(value.get("source") or "mock"),
            payload=payload,
        )
