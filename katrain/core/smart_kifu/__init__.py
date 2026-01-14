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

from katrain.core.smart_kifu.models import (
    # Enums
    Context,
    ViewerPreset,
    Confidence,
    # Dataclasses
    GameSource,
    GameEntry,
    TrainingSetManifest,
    EngineProfileSnapshot,
    BucketProfile,
    ContextProfile,
    PlayerProfile,
    ImportResult,
    # Constants
    CONFIDENCE_HIGH_MIN_SAMPLES,
    CONFIDENCE_HIGH_MIN_ANALYZED_RATIO,
    CONFIDENCE_MEDIUM_MIN_SAMPLES,
    CONFIDENCE_MEDIUM_MIN_ANALYZED_RATIO,
)

# =============================================================================
# Explicit imports from logic.py
# =============================================================================

from katrain.core.smart_kifu.logic import (
    # Bucket
    compute_bucket_key,
    # Engine Profile
    compute_engine_profile_id,
    # Game ID
    compute_game_id,
    # Analyzed Ratio
    iter_main_branch_nodes,
    compute_analyzed_ratio_from_game,
    # Confidence
    compute_confidence,
    # Viewer Level
    estimate_viewer_level,
    map_viewer_level_to_preset,
    # Handicap
    suggest_handicap_adjustment,
)

# =============================================================================
# Explicit imports from io.py
# =============================================================================

from katrain.core.smart_kifu.io import (
    # Directory
    get_smart_kifu_dir,
    get_training_sets_dir,
    get_profiles_dir,
    ensure_smart_kifu_dirs,
    # Training Set
    list_training_sets,
    load_manifest,
    save_manifest,
    create_training_set,
    # Player Profile
    load_player_profile,
    save_player_profile,
    # SGF Import
    import_sgf_to_training_set,
    import_sgf_folder,
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
    # Dataclasses
    "GameSource",
    "GameEntry",
    "TrainingSetManifest",
    "EngineProfileSnapshot",
    "BucketProfile",
    "ContextProfile",
    "PlayerProfile",
    "ImportResult",
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
]
