"""DEPRECATED: Batch helper functions have been split into per-concern modules.

This module is kept as a backward-compatible re-export shim. New code should
import from the specific submodules:

    - katrain.core.batch.visits          -> choose_visits_for_sgf
    - katrain.core.batch.loss            -> get_canonical_loss
    - katrain.core.batch.inputs          -> parse_timeout_input, safe_int, DEFAULT_TIMEOUT_SECONDS
    - katrain.core.batch.io_safe         -> safe_write_file
    - katrain.core.batch.sgf_io          -> read/parse_sgf_with_fallback, has_analysis, ENCODINGS_TO_TRY
    - katrain.core.batch.discovery       -> collect_sgf_files, collect_sgf_files_recursive
    - katrain.core.batch.engine_polling  -> wait_for_analysis
    - katrain.core.batch.filenames       -> sanitize_filename, normalize_player_name, get_unique_filename
    - katrain.core.batch.leela_gate      -> needs_leela_karte_warning
    - katrain.core.batch.markdown_fmt    -> format_* and escape_markdown_*

Importing from this module issues a DeprecationWarning.

All functions are pure or take injected dependencies (no module-level imports
of heavy core modules like engine/game). This module is Kivy-independent.
"""

from __future__ import annotations

import warnings as _warnings

from katrain.core.batch.discovery import collect_sgf_files, collect_sgf_files_recursive
from katrain.core.batch.engine_polling import wait_for_analysis
from katrain.core.batch.filenames import (
    get_unique_filename,
    normalize_player_name,
    sanitize_filename,
)
from katrain.core.batch.inputs import (
    DEFAULT_TIMEOUT_SECONDS,
    parse_timeout_input,
    safe_int,
)
from katrain.core.batch.io_safe import safe_write_file
from katrain.core.batch.leela_gate import needs_leela_karte_warning
from katrain.core.batch.loss import get_canonical_loss
from katrain.core.batch.markdown_fmt import (
    _ensure_balanced_brackets,
    _smart_truncate,
    escape_markdown_brackets,
    escape_markdown_table_cell,
    format_game_display_label,
    format_game_link_target,
    format_wr_gap,
    make_markdown_link_target,
    truncate_game_name,
)
from katrain.core.batch.sgf_io import (
    ENCODINGS_TO_TRY,
    has_analysis,
    parse_sgf_with_fallback,
    read_sgf_with_fallback,
)
from katrain.core.batch.visits import choose_visits_for_sgf

# Private-name aliases (for backward compatibility with internal callers/tests)
_get_canonical_loss = get_canonical_loss
_safe_int = safe_int
_safe_write_file = safe_write_file
_sanitize_filename = sanitize_filename
_get_unique_filename = get_unique_filename
_normalize_player_name = normalize_player_name

__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "ENCODINGS_TO_TRY",
    "_ensure_balanced_brackets",
    "_get_canonical_loss",
    "_get_unique_filename",
    "_normalize_player_name",
    "_safe_int",
    "_safe_write_file",
    "_sanitize_filename",
    "_smart_truncate",
    "choose_visits_for_sgf",
    "collect_sgf_files",
    "collect_sgf_files_recursive",
    "escape_markdown_brackets",
    "escape_markdown_table_cell",
    "format_game_display_label",
    "format_game_link_target",
    "format_wr_gap",
    "get_canonical_loss",
    "get_unique_filename",
    "has_analysis",
    "make_markdown_link_target",
    "needs_leela_karte_warning",
    "normalize_player_name",
    "parse_sgf_with_fallback",
    "parse_timeout_input",
    "read_sgf_with_fallback",
    "safe_int",
    "safe_write_file",
    "sanitize_filename",
    "truncate_game_name",
    "wait_for_analysis",
]

_warnings.warn(
    "katrain.core.batch.helpers is deprecated; import from the specific "
    "submodule (e.g. katrain.core.batch.filenames, katrain.core.batch.markdown_fmt).",
    DeprecationWarning,
    stacklevel=2,
)
