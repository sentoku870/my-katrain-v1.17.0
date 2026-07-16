"""Phase 145-C batch setup helper.

Phase 197 extraction: validates the input directory, creates output
sub-folders, collects the SGF file list, and initialises the
``EngineFailureTracker`` + supporting mutable state
(``game_stats_list``, ``games_for_curator``, …) consumed by later
pipeline stages.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

from katrain.core.batch.discovery import collect_sgf_files_recursive
from katrain.core.batch.orchestration._context import EngineFailureTracker
from katrain.core.batch.sgf_io import has_analysis


def _setup_batch(
    result: Any,
    katrain: Any,
    input_dir: str,
    output_dir: str | None,
    save_analyzed_sgf: bool,
    generate_karte: bool,
    generate_summary: bool,
    generate_curator: bool,
    skip_analyzed: bool,
    log_cb: Callable[[str], None] | None,
) -> (
    tuple[
        str,
        list[tuple[str, str]],
        int,
        str,
        list[dict[str, Any]] | None,
        list[tuple[Any, dict[str, Any]]] | None,
        list[int],
        dict[str, str],
        EngineFailureTracker,
    ]
    | None
):
    """Validate input, create output subdirs, collect SGF files, init trackers.

    Returns:
        Tuple of (output_dir, sgf_files, total, batch_timestamp, game_stats_list,
                  games_for_curator, selected_visits_list, karte_path_map, tracker)
        or None if validation failed.
    """

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    if not os.path.isdir(input_dir):
        log(f"Error: Input directory does not exist: {input_dir}")
        return None

    log("Using KataGo for analysis")

    output_dir = output_dir if output_dir else input_dir
    result.output_dir = output_dir
    os.makedirs(output_dir, exist_ok=True)

    if save_analyzed_sgf:
        os.makedirs(os.path.join(output_dir, "analyzed"), exist_ok=True)
    if generate_karte:
        os.makedirs(os.path.join(output_dir, "reports", "karte"), exist_ok=True)
    if generate_summary:
        os.makedirs(os.path.join(output_dir, "reports", "summary"), exist_ok=True)

    enabled_outputs = []
    if save_analyzed_sgf:
        enabled_outputs.append("Analyzed SGF")
    if generate_karte:
        enabled_outputs.append("Karte")
    if generate_summary:
        enabled_outputs.append("Summary")
    if generate_curator:
        enabled_outputs.append("Curator")
    if enabled_outputs:
        log(f"Enabled outputs: {', '.join(enabled_outputs)}")

    log(f"Scanning for SGF files in: {input_dir}")

    all_files = collect_sgf_files_recursive(input_dir, skip_analyzed=False, log_cb=None)
    sgf_files: list[tuple[str, str]] = []
    skip_count = 0

    for abs_path, rel_path in all_files:
        if skip_analyzed and has_analysis(abs_path):
            log(f"Skipping (already analyzed): {rel_path}")
            skip_count += 1
        else:
            sgf_files.append((abs_path, rel_path))

    result.skip_count = skip_count

    if not sgf_files:
        log(f"No SGF files to analyze in {input_dir}")
        return None

    log(f"Found {len(sgf_files)} SGF file(s) to analyze")
    if skip_count > 0:
        log(f"Skipped {skip_count} already-analyzed file(s)")
        log("  (Note: Skip checks KT property only, not visits/engine settings)")
    total = len(sgf_files)

    game_stats_list: list[dict[str, Any]] | None = [] if generate_summary else None
    games_for_curator: list[tuple[Any, dict[str, Any]]] | None = [] if generate_curator else None
    selected_visits_list: list[int] = []
    batch_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    karte_path_map: dict[str, str] = {}
    tracker = EngineFailureTracker(max_failures=3)

    return (
        output_dir,
        sgf_files,
        total,
        batch_timestamp,
        game_stats_list,
        games_for_curator,
        selected_visits_list,
        karte_path_map,
        tracker,
    )
