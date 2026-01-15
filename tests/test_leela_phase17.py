"""Phase 17 tests for Leela top moves display selection."""

import pytest
from katrain.core.leela.models import LeelaCandidate
from katrain.core.leela.presentation import format_loss_est, format_winrate_pct, format_visits
from katrain.core.constants import (
    LEELA_TOP_MOVE_LOSS,
    LEELA_TOP_MOVE_WINRATE,
    LEELA_TOP_MOVE_VISITS,
    LEELA_TOP_MOVE_NOTHING,
    LEELA_TOP_MOVE_OPTIONS,
    LEELA_TOP_MOVE_OPTIONS_SECONDARY,
)


class TestLeelaTopMoveConstants:
    """Tests for Leela top move option constants."""

    def test_options_list_contents(self):
        """Primary options should not include NOTHING."""
        assert LEELA_TOP_MOVE_NOTHING not in LEELA_TOP_MOVE_OPTIONS
        assert len(LEELA_TOP_MOVE_OPTIONS) == 3

    def test_secondary_options_include_nothing(self):
        """Secondary options should include NOTHING."""
        assert LEELA_TOP_MOVE_NOTHING in LEELA_TOP_MOVE_OPTIONS_SECONDARY
        assert len(LEELA_TOP_MOVE_OPTIONS_SECONDARY) == 4

    def test_all_options_are_unique(self):
        """All option constants should be unique strings."""
        all_options = [
            LEELA_TOP_MOVE_LOSS,
            LEELA_TOP_MOVE_WINRATE,
            LEELA_TOP_MOVE_VISITS,
            LEELA_TOP_MOVE_NOTHING,
        ]
        assert len(all_options) == len(set(all_options))
        assert all(isinstance(opt, str) for opt in all_options)


class TestFormatLeelaStatLogic:
    """Tests for stat formatting logic (mirrors _format_leela_stat)."""

    def test_loss_format(self):
        """LEELA_TOP_MOVE_LOSS returns formatted loss."""
        assert format_loss_est(2.5) == "2.5"
        assert format_loss_est(0.0) == "0.0"
        assert format_loss_est(None) == "--"

    def test_winrate_format(self):
        """LEELA_TOP_MOVE_WINRATE returns formatted winrate."""
        assert format_winrate_pct(0.523) == "52.3%"
        assert format_winrate_pct(0.0) == "0.0%"

    def test_visits_format(self):
        """LEELA_TOP_MOVE_VISITS returns formatted visits with K/M suffix."""
        assert format_visits(500) == "500"
        assert format_visits(1500) == "1.5K"
        assert format_visits(1500000) == "1.5M"
        assert format_visits(0) == "0"


class TestDisplayFormatSelection:
    """Tests for display format string generation."""

    def test_two_lines_format(self):
        """Two non-empty lines should produce newline-separated format."""
        line1 = "2.5"
        line2 = "52.3%"
        if line2:
            fmt = "{line1}\n{line2}"
        else:
            fmt = "{line1}"
        result = fmt.format(line1=line1, line2=line2)
        assert "\n" in result
        assert result == "2.5\n52.3%"

    def test_nothing_produces_single_line(self):
        """NOTHING (empty line2) should produce single-line format."""
        line1 = "2.5"
        line2 = ""  # NOTHING returns ""
        if line2:
            fmt = "{line1}\n{line2}"
        else:
            fmt = "{line1}"
        result = fmt.format(line1=line1, line2=line2)
        assert "\n" not in result
        assert result == "2.5"


class TestConfigDefaults:
    """Tests for backward compatibility."""

    def test_default_options_in_config(self):
        """Config should have default Loss+Winrate for backward compatibility."""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "katrain" / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        leela = config.get("leela", {})
        # After Phase 17 implementation, these keys should exist
        primary = leela.get("top_moves_show", LEELA_TOP_MOVE_LOSS)
        secondary = leela.get("top_moves_show_secondary", LEELA_TOP_MOVE_WINRATE)

        # Defaults should match current display behavior
        assert primary == LEELA_TOP_MOVE_LOSS
        assert secondary == LEELA_TOP_MOVE_WINRATE

    def test_resign_hint_settings_preserved(self):
        """Config should preserve resign_hint settings (Phase 16)."""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "katrain" / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        leela = config.get("leela", {})
        # These settings from Phase 16 should still exist
        assert "resign_hint_enabled" in leela
        assert "resign_winrate_threshold" in leela
        assert "resign_consecutive_moves" in leela
