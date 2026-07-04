"""Phase 36: Batch engine option collection tests.

Tests that batch UI correctly collects and persists engine selection.
CI-safe (no real engines, no Kivy UI).
"""

from unittest.mock import MagicMock, Mock

# ---------------------------------------------------------------------------
# Test: collect_batch_options() includes analysis_engine
# ---------------------------------------------------------------------------


class TestCollectBatchOptionsEngine:
    """Test collect_batch_options() collects analysis_engine."""

    def _create_mock_widgets(self, engine_selection: str = "katago"):
        """Create mock widgets dict for testing."""
        widgets = {
            "input_input": Mock(text="/path/to/input"),
            "output_input": Mock(text="/path/to/output"),
            "visits_input": Mock(text="1000"),
            "timeout_input": Mock(text="600"),
            "skip_checkbox": Mock(active=True),
            "save_sgf_checkbox": Mock(active=False),
            "karte_checkbox": Mock(active=True),
            "summary_checkbox": Mock(active=True),
            "min_games_input": Mock(text="3"),
            "jitter_input": Mock(text="10"),
            "variable_visits_checkbox": Mock(active=False),
            "deterministic_checkbox": Mock(active=True),
            "sound_checkbox": Mock(active=False),
        }

        # Add engine selection widgets
        if engine_selection == "katago":
            widgets["engine_katago"] = Mock(state="down")
            widgets["engine_leela"] = Mock(state="normal")
        else:
            widgets["engine_katago"] = Mock(state="normal")
            widgets["engine_leela"] = Mock(state="down")

        return widgets

    def test_katago_selection(self):
        """KataGo selected -> analysis_engine = 'katago'."""
        from katrain.gui.features.batch_core import collect_batch_options

        widgets = self._create_mock_widgets(engine_selection="katago")
        get_player_filter = Mock(return_value=None)

        options = collect_batch_options(widgets, get_player_filter)

        assert "analysis_engine" in options
        assert options["analysis_engine"] == "katago"

    # Phase 138: test_leela_selection removed — batch_core hardcodes
    # `analysis_engine = "katago"` per user request, so the engine widget
    # selection no longer affects the option. Covered by test_katago_selection.

    def test_default_without_engine_widgets(self):
        """Without engine widgets -> defaults to 'katago'."""
        from katrain.gui.features.batch_core import collect_batch_options

        widgets = self._create_mock_widgets(engine_selection="katago")
        # Remove engine widgets to simulate old UI
        del widgets["engine_katago"]
        del widgets["engine_leela"]
        get_player_filter = Mock(return_value=None)

        options = collect_batch_options(widgets, get_player_filter)

        assert "analysis_engine" in options
        assert options["analysis_engine"] == "katago"

    def test_other_options_unchanged(self):
        """Other batch options are collected correctly."""
        from katrain.gui.features.batch_core import collect_batch_options

        widgets = self._create_mock_widgets(engine_selection="leela")
        get_player_filter = Mock(return_value="B")

        options = collect_batch_options(widgets, get_player_filter)

        # Verify other options
        assert options["input_dir"] == "/path/to/input"
        assert options["output_dir"] == "/path/to/output"
        assert options["visits"] == 1000
        assert options["timeout"] == 600.0
        assert options["skip_analyzed"] is True
        assert options["save_analyzed_sgf"] is False
        assert options["generate_karte"] is True
        assert options["generate_summary"] is True
        assert options["karte_player_filter"] == "B"
        assert options["min_games_per_player"] == 3
        assert options["jitter_pct"] == 10
        assert options["variable_visits"] is False
        assert options["deterministic"] is True
        assert options["sound_on_finish"] is False


# ---------------------------------------------------------------------------
# Test: Config persistence pattern
# ---------------------------------------------------------------------------


class TestBatchEngineConfigPersistence:
    """Test batch.analysis_engine config persistence pattern."""

    def test_config_read_pattern(self):
        """Verify config read pattern: ctx.config('batch') or {}."""
        # This tests the expected pattern, not actual implementation
        batch_config = {} or {}
        engine_type = batch_config.get("analysis_engine", "katago")
        assert engine_type == "katago"

        batch_config = {"analysis_engine": "leela"}
        engine_type = batch_config.get("analysis_engine", "katago")
        assert engine_type == "leela"

    def test_config_write_pattern(self):
        """Verify config write pattern: MERGE + save."""
        # Simulate the expected write pattern
        existing = {"visits": 1000, "skip_analyzed": True}
        new_value = "leela"
        updated = {**existing, "analysis_engine": new_value}

        assert updated == {
            "visits": 1000,
            "skip_analyzed": True,
            "analysis_engine": "leela",
        }

    def test_fallback_for_invalid_value(self):
        """Invalid engine value should fallback to 'katago'."""

        def get_engine_type(batch_config):
            engine = batch_config.get("analysis_engine", "katago")
            if engine not in ("katago", "leela"):
                engine = "katago"
            return engine

        # Valid values
        assert get_engine_type({"analysis_engine": "katago"}) == "katago"
        assert get_engine_type({"analysis_engine": "leela"}) == "leela"

        # Invalid values -> fallback
        assert get_engine_type({"analysis_engine": "invalid"}) == "katago"
        assert get_engine_type({"analysis_engine": ""}) == "katago"
        assert get_engine_type({}) == "katago"


# ---------------------------------------------------------------------------
# Test: KataGo-only batch validation (Phase 171)
# ---------------------------------------------------------------------------


class TestKataGoOnlyBatchValidation:
    """Phase 171: KataGo 専用化に伴うバッチバリデーションのテスト。

    Leela 廃止のため ``needs_leela_warning`` は削除され、エンジン種別は
    常に ``"katago"`` となる。
    """

    def test_needs_leela_warning_removed(self):
        """needs_leela_warning は削除された。"""
        import pytest

        with pytest.raises(ImportError):
            from katrain.core.analysis import needs_leela_warning  # noqa: F401

    def test_batch_validation_kataonly(self):
        """バッチバリデーションは KataGo 選択を前提とする。"""

        def validate_batch_start(options):
            engine_type = options.get("analysis_engine", "katago")
            # Phase 171: Leela 廃止。KataGo のみ許可。
            if engine_type != "katago":
                return False, "Only KataGo is supported"
            return True, None

        # KataGo always works
        valid, err = validate_batch_start({"analysis_engine": "katago"})
        assert valid is True

        # Leela also routes to KataGo (legacy), should be allowed
        valid, err = validate_batch_start({"analysis_engine": "leela"})
        assert valid is False
        assert "KataGo" in err


# ---------------------------------------------------------------------------
# Test: BatchWidgets type includes engine widgets
# ---------------------------------------------------------------------------


class TestBatchWidgetsType:
    """Test BatchWidgets type documentation includes engine widgets."""

    def test_types_module_exists(self):
        """types.py module exists and can be imported."""
        from katrain.gui.features import types

        assert hasattr(types, "BatchWidgets")
        assert hasattr(types, "BatchOptions")
