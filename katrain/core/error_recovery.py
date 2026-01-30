"""Error recovery module for Phase 90.

Uses existing diagnostics infrastructure - does NOT duplicate.
Thread-safe deduplication with deterministic event IDs.

Python 3.9 compatible - uses Optional/Union instead of PEP604.
"""
import hashlib
import threading
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from katrain.core.diagnostics import DiagnosticsBundle


class DiagnosticsTrigger(Enum):
    """Triggers for diagnostics dump (NOT engine error categories)."""

    ENGINE_START_FAILED = "engine_start_failed"
    TEST_ANALYSIS_FAILED = "test_analysis_failed"
    CONSECUTIVE_FAILURE = "consecutive_failure"
    MANUAL = "manual"


@dataclass(frozen=True)
class RecoveryEvent:
    """Event that triggered recovery/diagnostics."""

    trigger: DiagnosticsTrigger
    error_message: str
    event_id: str  # Deterministic, for deduplication

    @staticmethod
    def create(
        trigger: DiagnosticsTrigger, code: str, error_message: str
    ) -> "RecoveryEvent":
        """Create event with deterministic SHA256-based ID."""
        raw = f"{trigger.value}:{code}:{error_message}"
        event_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return RecoveryEvent(
            trigger=trigger, error_message=error_message, event_id=event_id
        )


# Thread-safe deduplication (single gate)
_dedupe_lock = threading.Lock()
_last_dump_event_id: Optional[str] = None


def should_auto_dump(event: RecoveryEvent) -> bool:
    """Check if auto-dump should run (thread-safe, prevents double dump).

    This is the SINGLE gate for auto-dump. Do not add other gates.
    """
    global _last_dump_event_id
    with _dedupe_lock:
        if event.event_id == _last_dump_event_id:
            return False
        _last_dump_event_id = event.event_id
        return True


def reset_dedupe_state() -> None:
    """Reset dedupe state (for testing only)."""
    global _last_dump_event_id
    with _dedupe_lock:
        _last_dump_event_id = None


# UTF-8 byte-bounded truncation
LLM_TEXT_MAX_BYTES = 4096


def truncate_to_bytes(text: str, max_bytes: int = LLM_TEXT_MAX_BYTES) -> str:
    """Truncate text to fit within max_bytes (UTF-8).

    Ensures the result is valid UTF-8 and <= max_bytes.
    Adds "... [truncated]" suffix if truncated.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    # Reserve space for suffix
    suffix = "... [truncated]"
    suffix_bytes = len(suffix.encode("utf-8"))
    target_bytes = max_bytes - suffix_bytes

    # Truncate at valid UTF-8 boundary
    truncated = encoded[:target_bytes].decode("utf-8", errors="ignore")
    return truncated + suffix
