"""Top-move hint marker key assembly (Kivy-independent core).

Phase 259 (I-11) added three optional KataGo columns to the top-move
hint marker: scoreStdev, policy, ownership. The keys dict used to
populate the Kivy markup was assembled inline inside
``katrain.gui.badukpan_hints.draw_kata_hint_marker``, which forced
headless tests to copy the block verbatim. The copy had already
drifted from the production code once (it was missing the
``format_loss_str`` call that the production code uses for the
delta-score column).

This module hosts the **key-population** logic as a pure function
that returns the assembled dict. The GUI wrapper calls it and then
hands the dict to Kivy markup. Headless tests verify the assembled
dict directly without importing Kivy.
"""

from __future__ import annotations

from typing import Any

# Re-export the TOP_MOVE_* constants so callers can index the result
# dict with the same names used by the production code, without
# reaching across to ``katrain.core.constants`` separately.
from katrain.core.constants.metadata import (
    TOP_MOVE_DELTA_SCORE,
    TOP_MOVE_DELTA_WINRATE,
    TOP_MOVE_OWNERSHIP,
    TOP_MOVE_POLICY,
    TOP_MOVE_SCORE,
    TOP_MOVE_SCORE_STDEV,
    TOP_MOVE_VISITS,
    TOP_MOVE_WINRATE,
)


def _resolve_ownership_scalar(move_dict: dict[str, Any]) -> float:
    """Reduce a per-move ownership dict to a single ``[-1.0, +1.0]`` scalar.

    The production GUI resolver additionally consults
    ``current_node.analysis["ownership"]`` (a list of per-cell values);
    that half stays in the GUI layer. Here we only normalise whatever
    the ``move_dict["ownership"]`` slot holds, which is the slice of
    the logic that depends purely on the move analysis.
    """
    ownership = move_dict.get("ownership", 0.0)
    if isinstance(ownership, list):
        ownership = sum(ownership) / len(ownership) if ownership else 0.0
    return float(ownership) if ownership else 0.0


def assemble_top_move_keys(
    move_dict: dict[str, Any],
    player_sign: int = 1,
    delta_score_formatted: str | None = None,
    visits_formatted: str | None = None,
) -> dict[str, str]:
    """Return the ``keys[...] = ...`` dict that ``draw_kata_hint_marker``
    populates before applying Kivy markup.

    Args:
        move_dict: KataGo's per-move analysis dict (pointsLost, winrate,
            visits, scoreStdev, prior, ownership, ...).
        player_sign: ``+1`` for the next-player view, ``-1`` for the
            opponent view. Affects only the ``winrate`` column.
        delta_score_formatted: Pre-formatted delta-score string. The
            production GUI calls :func:`format_loss_str` to add the
            theme-specific "−1.5" markup; headless tests pass the raw
            ``-pointsLost`` formatting and the GUI passes the themed
            value. ``None`` falls back to ``{-pointsLost:.1f}``.
        visits_formatted: Pre-formatted visits string. The production
            GUI calls :func:`format_visits` which can pluralise; tests
            can pass the raw integer. ``None`` falls back to the raw
            int.

    Returns:
        The dict of pre-formatted string values indexed by the
        ``TOP_MOVE_*`` constants. Empty dict on missing input; the
        caller is responsible for guarding.
    """
    if move_dict is None:
        return {}

    keys: dict[str, str] = {}
    if delta_score_formatted is None:
        delta_score_formatted = f"{-move_dict.get('pointsLost', 0.0):.1f}"
    keys[TOP_MOVE_DELTA_SCORE] = delta_score_formatted
    keys[TOP_MOVE_SCORE] = f"{player_sign * move_dict.get('scoreLead', 0):.1f}"
    winrate_raw = move_dict.get("winrate", 0.5)
    winrate = winrate_raw if player_sign == 1 else 1 - winrate_raw
    keys[TOP_MOVE_WINRATE] = f"{winrate * 100:.1f}"
    keys[TOP_MOVE_DELTA_WINRATE] = f"{-move_dict.get('winrateLost', 0.0):+.1%}"
    if visits_formatted is None:
        visits_formatted = f"{move_dict.get('visits', 0)}"
    keys[TOP_MOVE_VISITS] = visits_formatted

    # Phase 259: three new optional columns. ``scoreStdev`` is the
    # per-move KataGo uncertainty; 0 (or missing) means the position
    # is quiet. ``prior`` is the policy-network probability for this
    # specific move (0.0 - 1.0), displayed as percent. ``ownership``
    # is the position-level predicted territory skew.
    score_stdev = move_dict.get("scoreStdev", 0.0) or 0.0
    keys[TOP_MOVE_SCORE_STDEV] = f"{score_stdev:.1f}"
    prior = move_dict.get("prior", 0.0) or 0.0
    keys[TOP_MOVE_POLICY] = f"{prior * 100:.1f}%"
    ownership = _resolve_ownership_scalar(move_dict)
    if ownership >= 0:
        keys[TOP_MOVE_OWNERSHIP] = f"B{ownership * 100:.0f}"
    else:
        keys[TOP_MOVE_OWNERSHIP] = f"W{-ownership * 100:.0f}"
    return keys
