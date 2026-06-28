"""Engine polling helpers for batch analysis synchronization."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine


def wait_for_analysis(engine: KataGoEngine, timeout: float = 300.0, poll_interval: float = 0.5) -> bool:
    """Wait for the engine to finish all pending analysis queries.

    Args:
        engine: KataGo engine instance (or any engine with is_idle() method)
        timeout: Maximum time to wait in seconds
        poll_interval: Time between checks in seconds

    Returns:
        True if analysis completed, False if timeout
    """
    start_time = time.time()
    while not engine.is_idle():
        if time.time() - start_time > timeout:
            return False
        time.sleep(poll_interval)
    return True
