"""DEPRECATED backwards-compat shim for ``katrain.core.batch.orchestration``.

Phase 197: The 927-line ``orchestration.py`` module has moved to the
``katrain.core.batch.orchestration`` subpackage, split into
``_context`` / ``_setup`` / ``_process`` / ``_handle`` / ``_summary`` /
``_curator`` + ``__init__``. This module remains so existing imports
like ``from katrain.core.batch.orchestration import run_batch`` and
``from katrain.core.batch.orchestration import EngineFailureTracker``
keep working unchanged, but **new code should import from the new
subpackage**.

Both public and private symbols are re-exported here so the strings
parsed by ``tests/test_phase149_bug_fixes.py`` (and other source-level
checks) stay accurate.
"""

from __future__ import annotations

from katrain.core.batch.orchestration import (
    EngineFailureTracker,
    _AnalysisAborted,
    _BatchCuratorContext,
    _BatchFileContext,
    _BatchSummaryContext,
    _collect_stats_for_file,
    _generate_curator_outputs,
    _generate_karte_for_file,
    _generate_summaries,
    _handle_analysis_failure,
    _post_success_processing,
    _prepare_file_processing,
    _process_single_file,
    _record_engine_failure_and_maybe_abort,
    _run_analysis_with_circuit_breaker,
    _setup_batch,
    run_batch,
)

__all__ = [
    "run_batch",
    "EngineFailureTracker",
    "_AnalysisAborted",
    "_BatchFileContext",
    "_BatchSummaryContext",
    "_BatchCuratorContext",
    "_setup_batch",
    "_process_single_file",
    "_prepare_file_processing",
    "_run_analysis_with_circuit_breaker",
    "_record_engine_failure_and_maybe_abort",
    "_handle_analysis_failure",
    "_post_success_processing",
    "_generate_karte_for_file",
    "_collect_stats_for_file",
    "_generate_summaries",
    "_generate_curator_outputs",
]
