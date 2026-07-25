"""Phase 272: Player rank → CoachMode key conversion.

Phase 272 unifies the user-facing rank setting (previously a free-text
field like ``"4d"`` / ``"4段"``) with the 5-level :class:`CoachMode`
enum (``BEGINNER`` / ``INTERMEDIATE`` / ``DAN`` / ``ADVANCED`` /
``EXPERT``).

This module is the **single source of truth** for:

- Parsing legacy rank strings into a mode key (backward compatibility)
- Validating mode keys
- Migrating config dicts that still hold legacy rank values

Downstream code (LLM Coach, Beginner Hints, PV Filter, AI opponent)
should use :func:`parse_mode_key` rather than calling
:func:`estimate_mode_from_rank` directly, because the input may be
either a mode key or a legacy rank string.

Note:
    This module is Kivy-free (lives under ``katrain/common/``) so it
    can be unit-tested on CI without a display.
"""

from __future__ import annotations

from typing import Any

from katrain.core.coach.master_db import CoachMode, estimate_mode_from_rank


def parse_mode_key(raw: str | None) -> str | None:
    """Normalise a raw rank string to a :class:`CoachMode.value` key.

    Accepts:

    - A mode key (e.g. ``"advanced"``): returned as-is after lowercasing
      and stripping whitespace, provided it matches a known mode.
    - Legacy rank notation (``"4d"`` / ``"4段"`` / ``"10k"``): mapped
      to the nearest mode via :func:`estimate_mode_from_rank`.
    - Empty / ``None``: returns ``None``.
    - Unrecognised input: returns ``None``.

    Returns:
        The mode key (e.g. ``"advanced"``), or ``None`` when no mapping.

    Example:
        >>> parse_mode_key("4d")
        'advanced'
        >>> parse_mode_key("ADVANCED")
        'advanced'
        >>> parse_mode_key("4段")
        'advanced'
        >>> parse_mode_key(None) is None
        True
    """
    if not raw:
        return None
    if isinstance(raw, str):
        cleaned = raw.strip().lower()
        if not cleaned:
            return None
        try:
            CoachMode(cleaned)
            return cleaned
        except ValueError:
            pass
    mode = estimate_mode_from_rank(raw)
    if mode is None:
        return None
    return mode.value


def is_valid_mode_key(raw: str | None) -> bool:
    """Return True when ``raw`` is a valid :class:`CoachMode` key.

    Accepts the value with or without case normalisation; whitespace
    is stripped before validation.
    """
    if not raw:
        return False
    try:
        CoachMode(raw.strip().lower())
        return True
    except ValueError:
        return False


def coerce_to_mode_key(raw: str | None, *, default: CoachMode = CoachMode.INTERMEDIATE) -> str:
    """Return a mode key for ``raw``, falling back to ``default``.

    Use this when the caller cannot tolerate ``None`` (e.g. when
    constructing a prompt builder argument). The default is
    :data:`CoachMode.INTERMEDIATE` so that an empty / unrecognised
    input never silently picks :data:`CoachMode.BEGINNER` (which was
    the historical footgun in :mod:`katrain.core.coach.cli`).
    """
    parsed = parse_mode_key(raw)
    if parsed is None:
        return default.value
    return parsed


def migrate_general_player_rank(config: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy ``general/player_rank`` text to a mode key (in place).

    Phase 272: legacy configs may have ``"4d"`` / ``"4段"`` stored in
    ``general/player_rank``. After this migration the value is always
    one of: ``"beginner"``, ``"intermediate"``, ``"dan"``, ``"advanced"``,
    ``"expert"``.

    Rules:

    - Already a mode key → no-op (idempotent).
    - Legacy rank text → mapped via :func:`parse_mode_key`.
    - Empty / unrecognised → ``"intermediate"`` (safe default).
    - Returns the (mutated) config dict for chaining.

    Note:
        The function mutates the dict in place AND returns it. This is
        intentional so the popup / CLI call sites can chain.

    Example:
        >>> cfg = {"general": {"player_rank": "4段"}}
        >>> migrate_general_player_rank(cfg)
        {'general': {'player_rank': 'advanced'}}
    """
    if not isinstance(config, dict):
        return config
    general = config.get("general")
    if not isinstance(general, dict):
        return config
    raw = general.get("player_rank", "")
    if is_valid_mode_key(raw):
        return config
    parsed = parse_mode_key(raw)
    if parsed is None:
        parsed = CoachMode.INTERMEDIATE.value
    general["player_rank"] = parsed
    return config


__all__ = [
    "parse_mode_key",
    "is_valid_mode_key",
    "coerce_to_mode_key",
    "migrate_general_player_rank",
]
