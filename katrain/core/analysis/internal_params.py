"""Phase 248-B3: Resolver for the "advanced" internal-parameter overrides.

Before Phase 248-B3 the important-move scoring constants
(``THRESHOLD_SCORE_STDEV_CHAOS``, ``COMPLEXITY_DISCOUNT_FACTOR``,
``DIVERSITY_PENALTY_FACTOR``, ``MEANING_TAG_WEIGHTS``, ``MIN_LOSS_DISPLAY``,
and the Beginner Hint visits gates) were hard-coded module globals
inside :mod:`katrain.core.analysis.critical_moves`,
:mod:`katrain.core.analysis.models.important_moves`, and
:mod:`katrain.core.beginner`. Power users had no way to dial the
sensitivity of these constants without editing source.

This module introduces a *single* resolver,
:func:`resolve_internal_params`, that maps a ``mykatrain_settings``
config dict onto a typed :class:`InternalParams` dataclass. The
resolver is permissive: unknown keys, out-of-range values, and
type-mismatches silently fall back to the original Phase 50-179
defaults so a user typo can never crash the GUI.

The resolver is the *only* public API. Downstream code (currently
just the docstring-level hand-off in :func:`select_critical_moves`
— see :data:`critical_moves` consumers) reads via
:func:`resolve_internal_params(ctx_config)` and applies the
overrides. Hooking the live values into the scoring path is a
follow-up phase (Phase γ-D1 will use the dataclass as the source
of truth at runtime).

Public surface:
- :class:`InternalParams` — frozen dataclass with the 5 + 1
  overridable fields.
- :func:`resolve_internal_params(mykatrain_settings) -> InternalParams`
- :func:`get_default_internal_params() -> InternalParams` (the
  Phase 50-179 baseline; re-exposed for tests + LLM coach paths
  that want the canonical defaults without going through config).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InternalParams:
    """User-tunable advanced parameters (Phase 248-B3).

    All fields have the *original Phase 50-179 hard-coded value* as
    the default. The resolver (:func:`resolve_internal_params`) only
    overrides a field when the user explicitly sets it in
    ``mykatrain_settings.advanced_params.<key>``.

    Attributes:
        threshold_score_stdev_chaos: KataGo ``scoreStdev`` threshold
            above which a candidate is considered "chaotic" and
            discounted in the critical_3 selection. Default 20.0.
        complexity_discount_factor: Multiplier applied to the
            importance score of a chaotic candidate (1.0 = no
            discount, 0.3 = keep 30% of the original score).
            Default 0.3.
        diversity_penalty_factor: Multiplier applied to repeated
            meaning tags in the critical_3 greedy selection. 0.85
            means the second occurrence of a tag is reduced to
            72.25% (0.85^2), the third to 61.4% (0.85^3), etc.
            Default 0.85.
        min_loss_display: Fallback threshold (in score points) used
            by :func:`pick_important_moves` when the importance
            threshold path is empty. A move must have at least this
            much ``raw_score`` to surface. Default 0.3.
        beginner_hint_min_visits: Phase 179-200 visits gate for
            :data:`Beginner Hint` reliability. The
            :func:`_is_reliable` helper in
            :mod:`katrain.core.beginner.hints._gate` checks
            ``root_visits >= beginner_hint_min_visits``. Default 100.
        katago_uncertain_min_visits: Visits gate for the
            ``KATAGO_UNCERTAIN`` summary hint. Higher than
            :attr:`beginner_hint_min_visits` because ``scoreStdev``
            is noisy at low visit counts. Default 300.
    """

    threshold_score_stdev_chaos: float = 20.0
    complexity_discount_factor: float = 0.3
    diversity_penalty_factor: float = 0.85
    min_loss_display: float = 0.3
    beginner_hint_min_visits: int = 100
    katago_uncertain_min_visits: int = 300


# The Phase 50-179 baseline (re-exposed for callers that want a
# canonical defaults object).
DEFAULT_INTERNAL_PARAMS = InternalParams()


# Per-field bounds. Out-of-range values in user config silently snap
# back to the defaults so a typo cannot crash the GUI.
_INTERNAL_PARAM_BOUNDS: dict[str, tuple[float | int, float | int]] = {
    "threshold_score_stdev_chaos": (1.0, 100.0),
    "complexity_discount_factor": (0.05, 1.0),
    "diversity_penalty_factor": (0.50, 1.00),
    "min_loss_display": (0.0, 5.0),
    "beginner_hint_min_visits": (1, 1000),
    "katago_uncertain_min_visits": (1, 2000),
}


# Field name in the dataclass ↔ key under
# ``mykatrain_settings.advanced_params``. Same names so the user
# can write ``advanced_params.threshold_score_stdev_chaos = 25``.
_FIELDS: tuple[str, ...] = (
    "threshold_score_stdev_chaos",
    "complexity_discount_factor",
    "diversity_penalty_factor",
    "min_loss_display",
    "beginner_hint_min_visits",
    "katago_uncertain_min_visits",
)


def get_default_internal_params() -> InternalParams:
    """Return the Phase 50-179 baseline (always a fresh frozen copy)."""
    return InternalParams()


def resolve_internal_params(mykatrain_settings: dict | None) -> InternalParams:
    """Resolve :class:`InternalParams` from a ``mykatrain_settings`` config dict.

    Resolution rules (all permissive, all silent on failure):
    1. ``None`` / empty / non-dict input → defaults.
    2. ``advanced_params`` missing / not a dict → defaults.
    3. For each known field: if the key is absent → default. If the
       value is not parseable as ``float`` / ``int`` → default. If
       the parsed value is out of bounds → default. Otherwise use
       the user's value.

    Args:
        mykatrain_settings: The ``mykatrain_settings`` sub-dict from
            the user's config (typically ``ctx.config("mykatrain_settings")``).

    Returns:
        A frozen :class:`InternalParams` with at least the defaults;
        some fields may be overridden by the user.
    """
    if not isinstance(mykatrain_settings, dict):
        return get_default_internal_params()

    raw = mykatrain_settings.get("advanced_params")
    if not isinstance(raw, dict):
        return get_default_internal_params()

    overrides: dict[str, float | int] = {}
    for field in _FIELDS:
        if field not in raw:
            continue
        value = raw[field]
        # Type check
        is_int_field = field.endswith("_visits")
        try:
            parsed: float | int = int(value) if is_int_field else float(value)
        except (TypeError, ValueError):
            continue
        # Range check
        lo, hi = _INTERNAL_PARAM_BOUNDS[field]
        if parsed < lo or parsed > hi:
            continue
        overrides[field] = parsed

    if not overrides:
        return get_default_internal_params()

    return InternalParams(**overrides)


__all__ = [
    "InternalParams",
    "DEFAULT_INTERNAL_PARAMS",
    "get_default_internal_params",
    "resolve_internal_params",
]
