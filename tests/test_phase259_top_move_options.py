"""Phase 259 (I-11): TOP_MOVE_OPTIONS extension.

Adds three new candidate-marker columns:
- ``TOP_MOVE_SCORE_STDEV`` — KataGo's per-move scoreStdev
- ``TOP_MOVE_POLICY`` — KataGo's per-move prior (policy network)
- ``TOP_MOVE_OWNERSHIP`` — position-level predicted territory skew

Tests are Kivy-free: they exercise the key-population logic
(the dict that ``draw_kata_hint_marker`` formats) and the
i18n presence.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from katrain.core.constants import (
    TOP_MOVE_OPTIONS,
    TOP_MOVE_OWNERSHIP,
    TOP_MOVE_POLICY,
    TOP_MOVE_SCORE_STDEV,
)


# ---------------------------------------------------------------------------
# Replica of the key-population logic in badukpan_hints.py:467-477
# ---------------------------------------------------------------------------


def _populate_keys(move_dict, player_sign=1):
    """Replicate the ``keys[...] = ...`` block in draw_kata_hint_marker."""
    keys: dict[str, str] = {}
    keys["top_move_delta_score"] = f"{-move_dict.get('pointsLost', 0.0):.1f}"
    keys["top_move_score"] = f"{player_sign * move_dict.get('scoreLead', 0):.1f}"
    winrate = move_dict.get("winrate", 0.5) if player_sign == 1 else 1 - move_dict.get("winrate", 0.5)
    keys["top_move_winrate"] = f"{winrate * 100:.1f}"
    keys["top_move_delta_winrate"] = f"{-move_dict.get('winrateLost', 0.0):+.1%}"
    keys["top_move_visits"] = f"{move_dict.get('visits', 0)}"
    # Phase 259: three new columns.
    score_stdev = move_dict.get("scoreStdev", 0.0) or 0.0
    keys[TOP_MOVE_SCORE_STDEV] = f"{score_stdev:.1f}"
    prior = move_dict.get("prior", 0.0) or 0.0
    keys[TOP_MOVE_POLICY] = f"{prior * 100:.1f}%"
    ownership = move_dict.get("ownership", 0.0) or 0.0
    if ownership >= 0:
        keys[TOP_MOVE_OWNERSHIP] = f"B{ownership * 100:.0f}"
    else:
        keys[TOP_MOVE_OWNERSHIP] = f"W{-ownership * 100:.0f}"
    return keys


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTopMoveOptionsExtended:
    """Phase 259: TOP_MOVE_OPTIONS now includes 3 new entries."""

    def test_includes_score_stdev(self):
        assert TOP_MOVE_SCORE_STDEV in TOP_MOVE_OPTIONS

    def test_includes_policy(self):
        assert TOP_MOVE_POLICY in TOP_MOVE_OPTIONS

    def test_includes_ownership(self):
        assert TOP_MOVE_OWNERSHIP in TOP_MOVE_OPTIONS

    def test_total_options_count(self):
        """5 original (excluding TOP_MOVE_NOTHING) + 3 new = 8 functional + 1 NOTHING."""
        functional = [o for o in TOP_MOVE_OPTIONS if o != "top_move_nothing"]
        assert len(functional) == 8

    def test_nothing_still_present(self):
        """Backward compat: TOP_MOVE_NOTHING must remain in the list."""
        assert "top_move_nothing" in TOP_MOVE_OPTIONS


class TestNewKeysPopulated:
    """Phase 259: score_stdev / policy / ownership keys are populated."""

    def test_score_stdev_formatted(self):
        keys = _populate_keys({"scoreStdev": 3.5, "visits": 100})
        assert keys[TOP_MOVE_SCORE_STDEV] == "3.5"

    def test_score_stdev_missing_defaults_to_zero(self):
        keys = _populate_keys({})
        assert keys[TOP_MOVE_SCORE_STDEV] == "0.0"

    def test_score_stdev_none_defaults_to_zero(self):
        """KataGo can send scoreStdev=None when visits are too low."""
        keys = _populate_keys({"scoreStdev": None})
        assert keys[TOP_MOVE_SCORE_STDEV] == "0.0"

    def test_policy_formatted_as_percent(self):
        keys = _populate_keys({"prior": 0.5})
        assert keys[TOP_MOVE_POLICY] == "50.0%"

    def test_policy_zero(self):
        keys = _populate_keys({"prior": 0.0})
        assert keys[TOP_MOVE_POLICY] == "0.0%"

    def test_policy_one_hundred_percent(self):
        keys = _populate_keys({"prior": 1.0})
        assert keys[TOP_MOVE_POLICY] == "100.0%"

    def test_policy_missing_defaults_to_zero(self):
        keys = _populate_keys({})
        assert keys[TOP_MOVE_POLICY] == "0.0%"

    def test_ownership_black_dominant(self):
        keys = _populate_keys({"ownership": 0.78})
        assert keys[TOP_MOVE_OWNERSHIP] == "B78"

    def test_ownership_white_dominant(self):
        keys = _populate_keys({"ownership": -0.82})
        assert keys[TOP_MOVE_OWNERSHIP] == "W82"

    def test_ownership_zero_shows_B0(self):
        keys = _populate_keys({"ownership": 0.0})
        # 0.0 is non-negative, so shows B0 (not W0).
        assert keys[TOP_MOVE_OWNERSHIP] == "B0"

    def test_ownership_missing_defaults_to_zero(self):
        keys = _populate_keys({})
        assert keys[TOP_MOVE_OWNERSHIP] == "B0"

    def test_all_previous_keys_still_present(self):
        """Phase 259 must NOT regress the pre-existing 5 columns."""
        keys = _populate_keys({
            "pointsLost": 1.5, "scoreLead": -0.3, "winrate": 0.55,
            "winrateLost": 0.02, "visits": 200, "scoreStdev": 2.0,
            "prior": 0.4, "ownership": 0.3,
        })
        assert "top_move_delta_score" in keys
        assert "top_move_score" in keys
        assert "top_move_winrate" in keys
        assert "top_move_delta_winrate" in keys
        assert "top_move_visits" in keys


class TestI18nPresence:
    """Phase 259: 3 new i18n keys are translated in jp + en."""

    @pytest.fixture
    def locale_dir(self):
        from katrain import __file__ as katrain_init
        return Path(katrain_init).parent / "i18n" / "locales"

    def test_jp_translations_present(self, locale_dir):
        import gettext

        locales = gettext.translation("katrain", str(locale_dir), languages=["jp"])
        for key in ("top_move_score_stdev", "top_move_policy", "top_move_ownership"):
            translated = locales.gettext(key)
            assert translated and translated != key, f"jp missing '{key}'"

    def test_en_translations_present(self, locale_dir):
        import gettext

        locales = gettext.translation("katrain", str(locale_dir), languages=["en"])
        for key in ("top_move_score_stdev", "top_move_policy", "top_move_ownership"):
            translated = locales.gettext(key)
            assert translated and translated != key, f"en missing '{key}'"


class TestProductionCodeUsesNewKeys:
    """AST guard: production code populates the new keys."""

    @pytest.fixture
    def badukpan_hints_source(self) -> str:
        return Path(__file__).parent.parent / "katrain" / "gui" / "badukpan_hints.py"

    def test_populates_score_stdev(self, badukpan_hints_source):
        text = badukpan_hints_source.read_text(encoding="utf-8")
        assert "TOP_MOVE_SCORE_STDEV" in text
        assert "scoreStdev" in text

    def test_populates_policy(self, badukpan_hints_source):
        text = badukpan_hints_source.read_text(encoding="utf-8")
        assert "TOP_MOVE_POLICY" in text
        assert '"prior"' in text

    def test_populates_ownership(self, badukpan_hints_source):
        text = badukpan_hints_source.read_text(encoding="utf-8")
        assert "TOP_MOVE_OWNERSHIP" in text
        assert "ownership" in text
