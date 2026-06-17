"""Dataclasses describing the result of a single provider/model test.

These are kept deliberately tiny and serialisable so they can be dumped
to JSON, embedded in reports, or surfaced over HTTP without extra
adapter code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TestResult:
    """Basic test result (kept for backwards compatibility).

    Prefer :class:`TestResultWithTypes` for new code — it additionally
    records the response types the model was probed for.
    """

    provider: str
    model: str
    working: bool
    response_time: float
    error: Optional[str] = None
    response_content: Optional[str] = None
    media_type: Optional[str] = None


@dataclass
class TestResultWithTypes:
    """Rich test result including the response types that were probed."""

    provider: str
    model: str
    working: bool
    response_time: float
    error: Optional[str] = None
    response_content: Optional[str] = None
    media_type: Optional[str] = None
    response_types: List[str] = field(default_factory=lambda: ["text"])

    def __post_init__(self) -> None:
        # Defensive: callers occasionally pass ``None`` explicitly when
        # building results from serialised data.
        if self.response_types is None:
            self.response_types = ["text"]
        # Ensure 'text' is always present so downstream stats are stable.
        if "text" not in self.response_types:
            self.response_types = ["text", *self.response_types]

    def to_dict(self) -> dict:
        """Serialise to a plain dict (JSON-friendly)."""
        return {
            "provider": self.provider,
            "model": self.model,
            "working": self.working,
            "response_time": self.response_time,
            "error": self.error,
            "response_content": self.response_content,
            "media_type": self.media_type,
            "response_types": list(self.response_types),
        }
