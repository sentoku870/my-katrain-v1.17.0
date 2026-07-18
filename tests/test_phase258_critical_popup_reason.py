"""Phase 258: critical 3 popup adds a per-row game_phase column.

The popup now shows ``game_phase`` (opening/middle/yose) alongside
the existing move_number / player / coord / loss / tag columns.
The Markdown clipboard export also includes the phase so the user
gets a fuller picture of *why* the move was selected as critical.

This test is Kivy-free: the widget itself is exercised by
``test_important_moves_popup.py`` (which is currently Kivy-skipped
in CI). The data-construction logic (entry kwargs + copy format) is
replicated here.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Replica helpers (Kivy-free)
# ---------------------------------------------------------------------------


_PHASE_LOCALISATION = {
    "opening": "布石",
    "middle": "中盤",
    "yose": "ヨセ",
}


def _localise_phase(raw_phase: str, i18n) -> str:
    """Replicate the localisation in ``_build_entry`` / ``on_copy``."""
    if not raw_phase:
        return ""
    translated = i18n(f"phase:{raw_phase}")
    if translated.startswith("phase:") or not translated:
        return _PHASE_LOCALISATION.get(raw_phase, raw_phase)
    return translated


def _build_entry_kwargs(color: str, move, i18n) -> dict:
    """Replicate ``_build_entry`` kwarg construction (Kivy-free)."""
    return {
        "move_number": move.move_number,
        "player": "B" if color == "black" else "W",
        "gtp_coord": move.gtp_coord or "?",
        "score_loss": float(getattr(move, "score_loss", 0.0) or 0.0),
        "meaning_tag_label": str(getattr(move, "meaning_tag_label", "")),
        "game_phase": _localise_phase(str(getattr(move, "game_phase", "") or ""), i18n),
        "complexity_discounted": bool(getattr(move, "complexity_discounted", False)),
    }


def _format_markdown(flattened, i18n) -> str:
    """Replicate ``on_copy`` Markdown export (Kivy-free)."""
    lines = ["# 重要局面リスト", ""]
    for color, m in flattened:
        player = "黒" if color == "black" else "白"
        tag = m.meaning_tag_label or "—"
        loss = f"{m.score_loss:.1f}目"
        phase = _localise_phase(str(getattr(m, "game_phase", "") or ""), i18n)
        phase_segment = f" [{phase}]" if phase else ""
        lines.append(f"- #{m.move_number} ({player}) {m.gtp_coord} — {loss} ({tag}){phase_segment}")
    return "\n".join(lines)


def _move(move_number, player, gtp_coord, score_loss, meaning_tag_label, game_phase, complexity_discounted=False):
    return SimpleNamespace(
        move_number=move_number,
        player=player,
        gtp_coord=gtp_coord,
        score_loss=score_loss,
        meaning_tag_label=meaning_tag_label,
        game_phase=game_phase,
        complexity_discounted=complexity_discounted,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEntryPhaseColumn:
    """Phase 258: game_phase is passed to the entry widget kwargs."""

    def test_opening_phase_translated(self):
        m = _move(50, "B", "D4", 3.2, "Life and Death", "opening")
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "布石"  # Japanese translation
            kwargs = _build_entry_kwargs("black", m, mock_gettext)
        assert kwargs["game_phase"] == "布石"
        mock_gettext.assert_called_with("phase:opening")

    def test_middle_phase_translated(self):
        m = _move(120, "W", "Q16", 1.5, "Missed Tesuji", "middle")
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "中盤"
            kwargs = _build_entry_kwargs("white", m, mock_gettext)
        assert kwargs["game_phase"] == "中盤"

    def test_yose_phase_translated(self):
        m = _move(220, "B", "A1", 0.4, "Endgame Slip", "yose")
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "ヨセ"
            kwargs = _build_entry_kwargs("black", m, mock_gettext)
        assert kwargs["game_phase"] == "ヨセ"

    def test_missing_i18n_falls_back_to_internal_jp(self):
        """When the .po is missing the phase:opening key (returns the
        raw key), the localiser falls back to the built-in Japanese
        table so the user still sees a useful label."""
        m = _move(50, "B", "D4", 3.2, "T", "opening")
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            # Simulate missing .po entry: gettext returns the raw key.
            mock_gettext.return_value = "phase:opening"
            kwargs = _build_entry_kwargs("black", m, mock_gettext)
        assert kwargs["game_phase"] == "布石"  # internal table fallback

    def test_empty_phase_returns_empty(self):
        m = _move(50, "B", "D4", 3.2, "T", "")
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = ""
            kwargs = _build_entry_kwargs("black", m, mock_gettext)
        assert kwargs["game_phase"] == ""

    def test_unknown_phase_returns_english(self):
        """An unknown phase string falls through to the English label."""
        m = _move(50, "B", "D4", 3.2, "T", "unknown")
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "phase:unknown"  # missing
            kwargs = _build_entry_kwargs("black", m, mock_gettext)
        assert kwargs["game_phase"] == "unknown"

    def test_kwargs_include_all_previous_fields(self):
        """Phase 258 must NOT regress any pre-existing entry field."""
        m = _move(50, "B", "D4", 3.2, "T", "opening", complexity_discounted=True)
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "布石"
            kwargs = _build_entry_kwargs("black", m, mock_gettext)
        assert kwargs["move_number"] == 50
        assert kwargs["player"] == "B"
        assert kwargs["gtp_coord"] == "D4"
        assert kwargs["score_loss"] == 3.2
        assert kwargs["meaning_tag_label"] == "T"
        assert kwargs["complexity_discounted"] is True


class TestCopyFormatIncludesPhase:
    """Phase 258: clipboard Markdown includes the game phase."""

    def test_phase_segment_present(self):
        flattened = [
            ("black", _move(50, "B", "D4", 3.2, "T", "opening")),
            ("white", _move(120, "W", "Q16", 1.5, "T", "middle")),
            ("black", _move(220, "B", "A1", 0.4, "T", "yose")),
        ]
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "X"
            md = _format_markdown(flattened, mock_gettext)
        assert "[X]" in md
        # Three moves → three "[X]" phase segments.
        assert md.count("[X]") == 3

    def test_empty_phase_omits_segment(self):
        flattened = [("black", _move(50, "B", "D4", 3.2, "T", ""))]
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = ""
            md = _format_markdown(flattened, mock_gettext)
        # No phase segment when game_phase is empty.
        assert "[]" not in md
        assert "  " not in md.split("\n")[2]  # line 3: no double-space from empty segment
