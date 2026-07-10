"""Non-cryptographic short-hash helper (Phase H-3).

Several call sites in :mod:`katrain.core.batch` and
:mod:`katrain.core.game` previously used ``hashlib.md5`` to derive a
short identifier from a string (filename, SGF path, batch timestamp,
...). MD5 is fine for non-cryptographic uniqueness but it is no
longer the recommended modern choice. This helper centralises the
behaviour on top of :mod:`hashlib.blake2b`, which is faster on
modern CPUs and ships in the stdlib (Python 3.6+).

The output is a lowercase hex string of length ``n_chars`` (1-64). The
hash is **not** a cryptographic identifier; do not use it for
security-sensitive purposes.
"""

from __future__ import annotations

import hashlib


def short_hash(text: str, n_chars: int = 6) -> str:
    """Return a short, deterministic identifier for ``text``.

    Args:
        text: The input string. Will be encoded as UTF-8.
        n_chars: Number of hex characters to return. Must be in
            ``1..64``. Default 6 (24 bits of entropy, matches the
            pre-Phase-H-3 call sites).

    Returns:
        Lowercase hex string of length ``n_chars``.

    Raises:
        ValueError: if ``n_chars`` is out of range.
    """
    if not 1 <= n_chars <= 64:
        raise ValueError(f"n_chars must be in 1..64, got {n_chars}")
    # digest_size in bytes; we keep 1 byte for 1-2 hex chars, and bump
    # up to 8 bytes (64 bits, 16 hex chars) for the larger outputs.
    digest_size = max(1, (n_chars + 1) // 2)
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=digest_size).hexdigest()
    return digest[:n_chars]
