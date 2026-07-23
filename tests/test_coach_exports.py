"""Consolidated TestExports for ``katrain.core.coach`` public surface.

Phase 2 of the test-suite cleanup: the per-module ``TestExports`` classes
that each only loop over a few ``hasattr(pkg, name)`` assertions are
merged here. A single import of ``katrain.core.coach`` is reused across
every group, and failures point at the missing export directly.

Adding a new public symbol to ``katrain.core.coach`` is now a one-line
edit here, rather than N touch-points across per-feature test files.
"""

from __future__ import annotations

import katrain.core.coach as coach_pkg
import katrain.core.coach.master_db as master_db_mod

_LEXICON_NAMES = [
    "LexiconEntry",
    "LexiconConcept",
    "LexiconBundle",
    "DEFAULT_LEXICON_PATH",
    "load_lexicon",
    "get_entry",
    "get_concept",
    "entries_by_level",
    "entries_by_category",
    "validate_references",
    "inject_lexicon_for_prompt",
    "all_ids",
]

_MASTER_DB_NAMES = [
    "CoachMode",
    "ToneVoice",
    "RankRange",
    "ModeConfig",
    "ToneConfig",
    "get_mode_config",
    "get_tone_config",
    "all_modes",
    "all_tones",
    "estimate_mode_from_rank",
    "estimate_mode_from_loss",
]

_PROMPT_BUILDER_NAMES = [
    "PromptConfig",
    "LlmPrompt",
    "build_translation_prompt",
    "append_llm_prompt_block",
    "render_markdown",
]

_POPUP_LOGIC_NAMES = [
    "PERSPECTIVE_AUTO",
    "PERSPECTIVE_BLACK",
    "PERSPECTIVE_WHITE",
    "SUMMARY_BIRDSEYE_SENTINEL",
    "MAX_RESPONSE_INPUT_CHARS",
    "PathTypeResult",
    "resolve_player_color_internal",
    "is_summary_birdseye_value",
    "resolve_summary_spinner_values",
    "detect_path_type_from_file",
    "format_type_label",
    "count_issue_markers",
    "was_truncated",
    "format_validation_status_summary",
    "cap_response_text",
    "resolve_summary_rank",
]

_SYMPTOM_INDEX_NAMES = [
    "SymptomId",
    "SymptomContext",
    "Symptom",
    "list_all_symptoms",
    "lookup_symptom",
    "list_auto_detected_symptoms",
    "list_llm_required_symptoms",
    "detect_auto_symptoms",
]

_TONES_NAMES = [
    "select_voice",
    "greeting_for_mode",
    "greeting_for_voice",
    "check_prohibited",
    "voice_summary",
    "modes_for_voice",
]

_JSON_TYPE_NAMES = [
    "JsonType",
    "detect_json_type",
    "is_karte",
    "is_summary",
    "normalize_summary_to_karte_shape",
    "extract_summary_game_count",
    "extract_summary_total_loss",
    "extract_summary_mistake_buckets",
    "extract_summary_weakness_patterns",
    "extract_summary_player_mistakes",
    "extract_summary_player_phase_losses",
]


def _assert_names_present(names: list[str], module, *, label: str) -> None:
    """Assert each name in *names* is exposed on *module*."""
    missing = [n for n in names if not hasattr(module, n)]
    assert not missing, f"{label}: missing names {missing}"


class TestCoachPackageExports:
    """Single regression net for ``katrain.core.coach``'s public surface."""

    def test_lexicon_reexports(self):
        _assert_names_present(_LEXICON_NAMES, coach_pkg, label="katrain.core.coach (lexicon)")

    def test_master_db_reexports(self):
        _assert_names_present(_MASTER_DB_NAMES, coach_pkg, label="katrain.core.coach (master_db)")
        _assert_names_present(_MASTER_DB_NAMES, master_db_mod, label="katrain.core.coach.master_db")

    def test_prompt_builder_reexports(self):
        _assert_names_present(_PROMPT_BUILDER_NAMES, coach_pkg, label="katrain.core.coach (prompt_builder)")

    def test_popup_logic_reexports(self):
        _assert_names_present(_POPUP_LOGIC_NAMES, coach_pkg, label="katrain.core.coach (popup_logic)")

    def test_symptom_index_reexports(self):
        _assert_names_present(_SYMPTOM_INDEX_NAMES, coach_pkg, label="katrain.core.coach (symptom_index)")

    def test_tones_reexports(self):
        _assert_names_present(_TONES_NAMES, coach_pkg, label="katrain.core.coach (tones)")

    def test_json_type_reexports(self):
        _assert_names_present(_JSON_TYPE_NAMES, coach_pkg, label="katrain.core.coach (json_type)")
