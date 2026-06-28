"""Variable visit selection with deterministic jitter for batch analysis."""

from __future__ import annotations

import hashlib
import os


def choose_visits_for_sgf(
    sgf_path: str,
    base_visits: int,
    jitter_pct: float = 0.0,
    deterministic: bool = True,
) -> int:
    """Choose visits for an SGF file with optional jitter.

    Args:
        sgf_path: Path to the SGF file (used for deterministic hashing)
        base_visits: Base visits count
        jitter_pct: Jitter percentage (0-25%), clamped for safety
        deterministic: If True, use path-based hash for reproducibility

    Returns:
        Visits count with jitter applied

    Examples:
        >>> choose_visits_for_sgf("game1.sgf", 500, jitter_pct=10, deterministic=True)
        475  # or similar, deterministic based on path
        >>> choose_visits_for_sgf("game1.sgf", 500, jitter_pct=0)
        500  # No jitter
    """
    if jitter_pct <= 0 or base_visits <= 0:
        return base_visits

    # Clamp jitter to max 25% for safety
    jitter_pct = min(jitter_pct, 25.0)

    # Calculate jitter range
    max_jitter = base_visits * (jitter_pct / 100.0)

    if deterministic:
        # Use md5 hash of normalized path for reproducibility
        # Normalize path: resolve, convert to forward slashes, lowercase
        normalized = os.path.normpath(os.path.abspath(sgf_path))
        normalized = normalized.replace("\\", "/").lower()
        hash_bytes = hashlib.md5(normalized.encode("utf-8")).digest()
        # Use first 4 bytes as unsigned int
        hash_val = int.from_bytes(hash_bytes[:4], byteorder="big")
        # Map to [-max_jitter, +max_jitter]
        jitter = (hash_val / 0xFFFFFFFF) * 2 * max_jitter - max_jitter
    else:
        import random

        jitter = random.uniform(-max_jitter, max_jitter)

    result = int(base_visits + jitter)
    # Ensure at least 1 visit
    return max(1, result)
