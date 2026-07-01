# katrain/core/engine_io.py
#
# I/O thread helpers for KataGoEngine (Phase 158+: engine.py split).
#
# Extracted from KataGoEngine into standalone module-level functions.
# Each function takes ``widget`` (the KataGoEngine instance) so that the
# class methods on KataGoEngine can remain thin one-line wrappers that
# preserve the public API and any references from subclasses or tests.
#
# These functions run as daemon threads started by KataGoEngine.start():
# - pipe_reader_thread: blocking readline() on stdout/stderr
# - read_stderr_thread: process stderr lines, fire status callbacks
# - write_stdin_thread: serialize write_queue -> KataGo stdin
# - analysis_read_thread: parse JSON, dispatch callbacks, update pending count
#
# Imports of KataGoEngine are TYPE_CHECKING-only to avoid runtime cycles.

from __future__ import annotations

import json
import queue
import time
import traceback
from typing import TYPE_CHECKING, Any

from katrain.core.constants import (
    KATAGO_EXCEPTION,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    OUTPUT_EXTRA_DEBUG,
    OUTPUT_KATAGO_STDERR,
    PONDERING_REPORT_DT,
)
from katrain.core.utils import json_truncate_arrays

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine


# =============================================================================
# Module-level helpers
# =============================================================================


def _ensure_str(line: bytes | str | None) -> str:
    """Normalize line to str, handling bytes/str/None."""
    if line is None:
        return ""
    if isinstance(line, bytes):
        return line.decode("utf-8", errors="replace")
    return str(line)


# =============================================================================
# Pipe reader (blocking I/O isolation)
# =============================================================================


def pipe_reader_thread(
    widget: KataGoEngine, pipe: Any, output_queue: queue.Queue[bytes | None], name: str
) -> None:
    """Read from pipe and put lines into queue (blocking I/O isolated here).

    This thread performs blocking readline() calls. When the process terminates
    or pipes are closed, readline() returns empty bytes (EOF).

    Args:
        pipe: File-like object (process.stdout or process.stderr)
        output_queue: Queue to put read lines into
        name: Thread name for logging
    """
    while not widget._shutdown_event.is_set():
        try:
            line = pipe.readline()
            if not line:
                break  # EOF or process terminated
            output_queue.put(line)
        except (OSError, ValueError):
            break  # Pipe closed or error
    # Signal consumer thread that this reader is done
    output_queue.put(None)
    widget.katrain.log(f"Pipe reader {name} finished", OUTPUT_DEBUG)


# =============================================================================
# Stderr consumer (status callbacks + error detection)
# =============================================================================


def read_stderr_thread(widget: KataGoEngine) -> None:
    """Process stderr lines from queue (non-blocking with timeout)."""
    while not widget._shutdown_event.is_set():
        try:
            raw_line = widget._stderr_queue.get(timeout=widget.IO_TIMEOUT)
            if raw_line is None:
                return  # Termination signal from reader thread
            line = _ensure_str(raw_line)
            if line:
                if "Uncaught exception" in line or "what()" in line:  # linux=what
                    msg = f"KataGo Engine Failed: {line[9:].strip()}"
                    widget._fire_engine_error(msg, KATAGO_EXCEPTION)
                    return
                try:
                    widget.katrain.log(line.strip(), OUTPUT_KATAGO_STDERR)
                    # Phase 120: Status callback for UI updates
                    if widget.status_callback:
                        lower_line = line.lower()
                        if "starting" in lower_line:
                            widget.status_callback("starting", line)
                        elif line.startswith("Tuning"):
                            widget.status_callback("tuning", line)
                        elif "ready" in lower_line:
                            widget.status_callback("ready", line)
                except Exception as e:  # noqa: BLE001 - thread exception, must log and continue
                    widget.katrain.log(
                        f"Error processing stderr: {line!r}: {e}\n{traceback.format_exc()}",
                        OUTPUT_ERROR,
                    )
        except queue.Empty:
            # Timeout - check if we should continue
            if widget._shutdown_event.is_set():
                return
            # No stderr activity is normal during idle periods
            continue
        except Exception as e:  # noqa: BLE001 - thread exception, must log and exit gracefully
            widget.katrain.log(
                f"Exception in stderr thread: {e}\n{traceback.format_exc()}",
                OUTPUT_ERROR,
            )
            return


# =============================================================================
# Stdin writer (TOCTOU-safe queue → process.stdin)
# =============================================================================


def write_stdin_thread(widget: KataGoEngine) -> None:
    """Write queries to KataGo stdin (TOCTOU-safe).

    Flush only in a thread since it returns only when the other program reads.
    """
    while not widget._shutdown_event.is_set():
        # Local capture pattern for TOCTOU safety
        process = widget.katago_process
        if process is None:
            return
        try:
            item = widget.write_queue.get(block=True, timeout=0.1)
        except queue.Empty:
            continue
        # Check for termination signal (None)
        if item is None:
            return
        query: dict[str, Any]
        callback: Any
        error_callback: Any
        next_move: Any
        node: Any
        # Phase 159: Defensive unpacking. Production sends only valid 5-tuples
        # (see engine_query.send_query), but a malformed item (e.g. a 5-char
        # string from a buggy caller) would unpack into single characters and
        # then crash on query["id"] = ..., silently killing the writer thread.
        try:
            query, callback, error_callback, next_move, node = item
        except (TypeError, ValueError) as e:
            widget.katrain.log(
                f"Malformed write_queue item dropped: {type(item).__name__} ({e!r})",
                OUTPUT_ERROR,
            )
            continue
        old_ponder_query: dict[str, Any] | None = None  # To call terminate_query outside of lock
        with widget.thread_lock:
            if "id" not in query:
                widget.query_counter += 1
                query["id"] = f"QUERY:{str(widget.query_counter)}"

            ponder = query.pop(widget.PONDER_KEY, False)
            if ponder:  # handle pondering in here to be in lock and such
                pq: dict[str, Any] = widget.ponder_query or {}
                # basically we handle pondering by just asking for these queries a lot and ignoring duplicates
                # when a different ponder query comes in, e.g. due to selecting a roi or different node, switch
                differences = {
                    k: (pq.get(k), query.get(k))
                    for k in (query.keys() | pq.keys()) - {"id", "maxVisits", "reportDuringSearchEvery"}
                    if pq.get(k) != query.get(k)
                }
                if differences:
                    from katrain.core.engine_query import stop_pondering_unlocked  # late import

                    old_ponder_query = stop_pondering_unlocked(widget)
                    query["maxVisits"] = 10_000_000
                    query["reportDuringSearchEvery"] = PONDERING_REPORT_DT
                    widget.ponder_query = query
                else:
                    # Duplicate ponder query - discard without sending
                    # Must decrement counter since send_query already incremented it
                    from katrain.core.engine_query import decrement_pending_count

                    decrement_pending_count(widget)
                    continue

            terminate = query.get("action") == "terminate"
            if not terminate:
                widget.queries[query["id"]] = (callback, error_callback, time.time(), next_move, node)
            tag = "ponder " if ponder else ("terminate " if terminate else "")
            widget.katrain.log(f"Sending {tag}query {query['id']}: {json.dumps(query)}", OUTPUT_DEBUG)

        # Write to stdin outside lock (I/O should not be under lock)
        # Re-capture process reference after lock release
        process = widget.katago_process
        if process is None:
            return
        try:
            if process.stdin is None:
                return
            process.stdin.write((json.dumps(query) + "\n").encode())
            process.stdin.flush()
        except (OSError, AttributeError, ValueError, BrokenPipeError) as e:
            widget.katrain.log(f"Exception in writing to katago: {e}", OUTPUT_DEBUG)
            # Decrement pending count for non-terminate queries that failed to send
            if not terminate:
                from katrain.core.engine_query import decrement_pending_count

                decrement_pending_count(widget)
            return  # some other thread will take care of this
        # Terminate old ponder query outside of lock to avoid deadlock
        if old_ponder_query:
            widget.terminate_query(old_ponder_query["id"], ignore_further_results=False)


# =============================================================================
# Analysis consumer (JSON parse → callback dispatch)
# =============================================================================


def analysis_read_thread(widget: KataGoEngine) -> None:
    """Process analysis results from queue (non-blocking with timeout)."""
    while not widget._shutdown_event.is_set():
        try:
            raw_line = widget._stdout_queue.get(timeout=widget.IO_TIMEOUT)
            if raw_line is None:
                return  # Termination signal from reader thread
            line = _ensure_str(raw_line).strip()
        except queue.Empty:
            # Timeout - check if we should continue or handle timeout
            if widget._shutdown_event.is_set():
                return
            # Check if there are pending queries and process is dead
            with widget.thread_lock:
                has_pending_queries = bool(widget.queries)
            if has_pending_queries and not widget.check_alive():
                widget._handle_engine_timeout()
                return
            # No pending queries or process alive - continue waiting
            continue
        except Exception as e:  # noqa: BLE001 - thread exception, must log and exit gracefully
            widget.katrain.log(
                f"Exception in analysis thread: {e}\n{traceback.format_exc()}",
                OUTPUT_ERROR,
            )
            widget.check_alive(os_error=str(e), exception_if_dead=True, maybe_open_recovery=True)
            return

        if not line:
            continue

        if "Uncaught exception" in line:
            msg = f"KataGo Engine Failed: {line}"
            widget._fire_engine_error(msg, KATAGO_EXCEPTION)
            return
        if not line:
            continue
        query_found = False
        try:
            analysis = json.loads(line)
            if "id" not in analysis:
                widget.katrain.log(f"Error without ID {analysis} received from KataGo", OUTPUT_ERROR)
                continue
            query_id = analysis["id"]

            # Retrieve query data under lock to prevent race conditions
            # Callbacks are executed outside the lock to avoid deadlocks
            callback = None
            error_callback = None
            start_time = None
            next_move = None

            with widget.thread_lock:
                if query_id not in widget.queries:
                    # Query was already removed by terminate_queries() or on_new_game()
                    # This is a normal case when switching games or canceling analysis
                    if analysis.get("action") != "terminate":
                        widget.katrain.log(
                            f"Query result {query_id} discarded -- recent new game or node reset?", OUTPUT_DEBUG
                        )
                    # Phase 98 fix: Decrement pending count even for discarded queries
                    from katrain.core.engine_query import decrement_pending_count

                    decrement_pending_count(widget)
                    continue
                query_found = True
                callback, error_callback, start_time, next_move, _ = widget.queries[query_id]
                if "error" in analysis:
                    del widget.queries[query_id]
                elif "warning" in analysis or "terminateId" in analysis:
                    pass  # No deletion needed for warnings/terminate confirmations
                else:
                    partial_result = analysis.get("isDuringSearch", False)
                    if not partial_result:
                        del widget.queries[query_id]

            # Process results outside the lock
            from katrain.core.engine_query import (
                decrement_pending_count,
                invoke_error_callback,
            )
            from katrain.core.notify_helpers import maybe_notify_analysis_complete

            if "error" in analysis:
                if error_callback:
                    invoke_error_callback(widget, error_callback, analysis)
                elif not (next_move and "Illegal move" in analysis["error"]):  # sweep
                    widget.katrain.log(f"{analysis} received from KataGo", OUTPUT_ERROR)
                # Decrement pending count on error completion
                decrement_pending_count(widget)
            elif "warning" in analysis or "terminateId" in analysis:
                widget.katrain.log(f"{analysis} received from KataGo", OUTPUT_DEBUG)
            else:
                partial_result = analysis.get("isDuringSearch", False)
                time_taken = time.time() - start_time
                results_exist = not analysis.get("noResults", False)
                widget.katrain.log(
                    f"[{time_taken:.1f}][{query_id}][{'....' if partial_result else 'done'}] KataGo analysis received: {len(analysis.get('moveInfos', []))} candidate moves, {analysis['rootInfo']['visits'] if results_exist else 'n/a'} visits",
                    OUTPUT_DEBUG,
                )
                widget.katrain.log(json_truncate_arrays(analysis), OUTPUT_EXTRA_DEBUG)
                try:
                    if callback and results_exist:
                        callback(analysis, partial_result)
                except Exception as e:  # noqa: BLE001 - callback exception, must log and continue
                    widget.katrain.log(
                        f"Error in engine callback for query {query_id}: {e}\n{traceback.format_exc()}",
                        OUTPUT_ERROR,
                    )
                # Decrement pending count on success completion (non-partial only)
                if not partial_result:
                    decrement_pending_count(widget)

                # Phase 105: ANALYSIS_COMPLETE通知（キーワード引数必須）
                maybe_notify_analysis_complete(
                    katrain=widget.katrain,
                    partial_result=partial_result,
                    results_exist=results_exist,
                    query_id=query_id,
                )

            if getattr(widget.katrain, "update_state", None):  # easier mocking etc
                widget.katrain.update_state()
        except Exception as e:  # noqa: BLE001 - thread exception, must log and continue processing
            widget.katrain.log(
                f"Unexpected exception {e} while processing KataGo output {line}\n{traceback.format_exc()}",
                OUTPUT_ERROR,
            )
            # Decrement pending count if query was found but processing failed
            if query_found:
                from katrain.core.engine_query import decrement_pending_count

                decrement_pending_count(widget)
