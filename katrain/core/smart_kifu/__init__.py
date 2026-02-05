"""Smart Kifu Learning (Phase 13).

This package provides smart kifu learning functionality:
- Training Set management
- Player Profile tracking
- vs_katago practice reporting

v0.2 Scope:
- Phase 1: Training Set + Player Profile
- Phase 2: vs_katago practice report + handicap suggestion

Usage:
    from katrain.core.smart_kifu import (
        # Models
        Context,
        ViewerPreset,
        Confidence,
        GameEntry,
        TrainingSetManifest,
        PlayerProfile,
        ImportResult,
        # Logic
        compute_bucket_key,
        compute_engine_profile_id,
        compute_game_id,
        compute_confidence,
        # I/O
        load_manifest,
        save_manifest,
        load_player_profile,
        save_player_profile,
        import_sgf_folder,
    )
"""

# =============================================================================
# Explicit imports from models.py
# =============================================================================

# =============================================================================
# Explicit imports from io.py
# =============================================================================
from katrain.core.smart_kifu.io import (
    create_training_set,
    ensure_smart_kifu_dirs,
    get_profiles_dir,
    # Directory
    get_smart_kifu_dir,
    get_training_sets_dir,
    import_analyzed_sgf_folder,
    import_sgf_folder,
    # SGF Import
    import_sgf_to_training_set,
    # Training Set
    list_training_sets,
    load_manifest,
    # Player Profile
    load_player_profile,
    save_manifest,
    save_player_profile,
)

# =============================================================================
# Explicit imports from logic.py
# =============================================================================
from katrain.core.smart_kifu.logic import (
    compute_analyzed_ratio_from_game,
    compute_analyzed_ratio_from_sgf_file,
    # Bucket
    compute_bucket_key,
    # Confidence
    compute_confidence,
    # Engine Profile
    compute_engine_profile_id,
    # Game ID
    compute_game_id,
    # Training Set Summary
    compute_training_set_summary,
    # Viewer Level
    estimate_viewer_level,
    has_analysis_data,
    # Analyzed Ratio
    iter_main_branch_nodes,
    map_viewer_level_to_preset,
    # Handicap
    suggest_handicap_adjustment,
)
from katrain.core.smart_kifu.models import (
    CONFIDENCE_HIGH_MIN_ANALYZED_RATIO,
    # Constants
    CONFIDENCE_HIGH_MIN_SAMPLES,
    CONFIDENCE_MEDIUM_MIN_ANALYZED_RATIO,
    CONFIDENCE_MEDIUM_MIN_SAMPLES,
    BucketProfile,
    Confidence,
    # Enums
    Context,
    ContextProfile,
    EngineProfileSnapshot,
    GameEntry,
    # Dataclasses
    GameSource,
    ImportErrorCode,
    ImportResult,
    PlayerProfile,
    TrainingSetManifest,
    TrainingSetSummary,
    ViewerPreset,
)

# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # === models.py ===
    # Enums
    "Context",
    "ViewerPreset",
    "Confidence",
    "ImportErrorCode",
    # Dataclasses
    "GameSource",
    "GameEntry",
    "TrainingSetManifest",
    "EngineProfileSnapshot",
    "BucketProfile",
    "ContextProfile",
    "PlayerProfile",
    "ImportResult",
    "TrainingSetSummary",
    # Constants
    "CONFIDENCE_HIGH_MIN_SAMPLES",
    "CONFIDENCE_HIGH_MIN_ANALYZED_RATIO",
    "CONFIDENCE_MEDIUM_MIN_SAMPLES",
    "CONFIDENCE_MEDIUM_MIN_ANALYZED_RATIO",
    # === logic.py ===
    # Bucket
    "compute_bucket_key",
    # Engine Profile
    "compute_engine_profile_id",
    # Game ID
    "compute_game_id",
    # Analyzed Ratio
    "iter_main_branch_nodes",
    "compute_analyzed_ratio_from_game",
    "has_analysis_data",
    "compute_analyzed_ratio_from_sgf_file",
    # Training Set Summary
    "compute_training_set_summary",
    # Confidence
    "compute_confidence",
    # Viewer Level
    "estimate_viewer_level",
    "map_viewer_level_to_preset",
    # Handicap
    "suggest_handicap_adjustment",
    # === io.py ===
    # Directory
    "get_smart_kifu_dir",
    "get_training_sets_dir",
    "get_profiles_dir",
    "ensure_smart_kifu_dirs",
    # Training Set
    "list_training_sets",
    "load_manifest",
    "save_manifest",
    "create_training_set",
    # Player Profile
    "load_player_profile",
    "save_player_profile",
    # SGF Import
    "import_sgf_to_training_set",
    "import_sgf_folder",
    "import_analyzed_sgf_folder",
]
