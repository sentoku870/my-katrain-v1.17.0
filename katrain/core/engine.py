# mypy: ignore-errors
#
# Phase 158+: This module's class is now a thin skeleton. I/O thread
# functions have been extracted to ``katrain.core.engine_io`` and query
# lifecycle methods have been extracted to ``katrain.core.engine_query``.
# Both helpers are imported lazily inside the wrapper methods to avoid
# runtime circular imports between the three modules.
# Note: This module contains Windows-specific code paths (subprocess.STARTF_USESHOWWINDOW).
# On Linux CI, mypy cannot resolve Windows API calls, but these are guarded by platform checks.
from __future__ import annotations

import contextlib
import json
import os
import platform
import queue
import shlex
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Any

from katrain.common.platform import get_platform
from katrain.core.constants import (
    DATA_FOLDER,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    OUTPUT_EXTRA_DEBUG,
)
from katrain.core.game_node import GameNode
from katrain.core.lang import i18n
from katrain.core.sgf_parser import Move
from katrain.core.utils import find_package_resource

# Maximum pending queries before rejecting new ones
MAX_PENDING_QUERIES = 100


def _ensure_str(line: bytes | str | None) -> str:
    """Normalize line to str, handling bytes/str/None."""
    if line is None:
        return ""
    if isinstance(line, bytes):
        return line.decode("utf-8", errors="replace")
    return str(line)


def _identity_scheduler(fn: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    """Default scheduler: invoke the callable inline (used in headless/test).

    Accepts arbitrary positional/keyword args because real Kivy Clock.schedule_once
    passes a `_dt` argument that we must tolerate.
    """
    fn(*args, **kwargs)


class BaseEngine:
    RULESETS_ABBR = [
        ("jp", "japanese"),
        ("cn", "chinese"),
        ("ko", "korean"),
        ("aga", "aga"),
        ("tt", "tromp-taylor"),
        ("nz", "new zealand"),
        ("stone_scoring", "stone_scoring"),
    ]
    RULESETS = {fromkey: name for abbr, name in RULESETS_ABBR for fromkey in [abbr, name]}

    def __init__(
        self,
        katrain: Any,
        config: dict[str, Any],
        error_callback: Callable[[str, str | None, bool], None] | None = None,
        main_thread_scheduler: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        self.katrain = katrain
        self.config = config
        self._error_callback = error_callback
        # Default scheduler: identity (call inline). Used for UI-thread dispatch.
        # GUI layer injects kivy.clock.Clock.schedule_once to make callbacks main-thread-safe.
        # The scheduler takes a zero-arg callable; it may invoke it with any extra args
        # (e.g. Kivy's Clock passes _dt), so our wrappers below use *args/**kwargs.
        self._main_thread_scheduler: Callable[..., None] = main_thread_scheduler or _identity_scheduler

    @staticmethod
    def get_rules(ruleset: str | dict[str, Any]) -> str | dict[str, Any]:
        if isinstance(ruleset, str) and ruleset.strip().startswith("{"):
            with contextlib.suppress(json.JSONDecodeError):
                ruleset = json.loads(ruleset)
        if isinstance(ruleset, dict):
            return ruleset
        return KataGoEngine.RULESETS.get(str(ruleset).lower(), "japanese")

    def advance_showing_game(self) -> None:
        pass  # avoid transitional error

    def status(self) -> str:
        return ""  # avoid transitional error

    def get_engine_path(self, exe: str) -> str | None:
        if not exe:
            if get_platform() == "win":
                exe = "katrain/KataGo/katago.exe"
            elif get_platform() == "linux":
                exe = "katrain/KataGo/katago"
            else:
                exe = find_package_resource("katrain/KataGo/katago-osx")  # github actions built
                if not os.path.isfile(exe) or "arm64" in platform.version().lower():
                    exe = "katago"  # e.g. MacOS after brewing
        if exe.startswith("katrain"):
            exe = find_package_resource(exe)
        exepath, exename = os.path.split(exe)

        if exepath and not os.path.isfile(exe):
            self._fire_engine_error(i18n._("Kata exe not found").format(exe=exe), "KATAGO-EXE", True)
            return None
        elif not exepath:
            paths = os.getenv("PATH", ".").split(os.pathsep) + ["/opt/homebrew/bin/"]
            exe_with_paths = [os.path.join(path, exe) for path in paths if os.path.isfile(os.path.join(path, exe))]
            if not exe_with_paths:
                self._fire_engine_error(i18n._("Kata exe not found in path").format(exe=exe), "KATAGO-EXE", True)
                return None
            exe = exe_with_paths[0]
        return exe

    def on_error(self, message: str, code: str, allow_popup: bool = True) -> None:
        # Subclasses should override to implement proper logging
        pass

    def _fire_engine_error(self, message: str, code: str | None = None, allow_popup: bool = True) -> None:
        """Dispatch an engine-level error.

        BaseEngine default: forward to on_error() (which is also a no-op by default).
        KataGoEngine overrides to use the injected error_callback or fall back to on_error.
        """
        self.on_error(message, code, allow_popup)

    def is_alive(self) -> bool:
        """Lightweight health check for UI layer; does not raise or open popups.

        Subclasses with a subprocess (e.g. KataGoEngine) override this to check
        the actual process state. Default returns False (no process).
        """
        return False

    def set_analysis_focus(self, focus: list[int | None] | None) -> None:
        """Set or clear the analysis focus region.

        Args:
            focus: Rectangle [x1, y1, x2, y2] to restrict analysis, or None to clear
                   (the engine will analyze the whole board).
        """
        if focus is None:
            self.config.pop("analysis_focus", None)
        else:
            self.config["analysis_focus"] = focus


class KataGoEngine(BaseEngine):
    """Starts and communicates with the KataGo analysis engine.

    Phase 158+: The thread functions (pipe_reader, stderr, write_stdin,
    analysis_read) have been extracted to ``engine_io.py``, and the query
    lifecycle methods (send_query, request_analysis, terminate_query, etc.)
    have been extracted to ``engine_query.py``. This class retains the
    process lifecycle (start/shutdown/init) and provides thin wrappers that
    delegate to the helper modules. The public API is preserved.
    """

    PONDER_KEY = "_kt_continuous"
    # Timeout for Queue.get() in consumer threads (seconds)
    IO_TIMEOUT = 5.0

    def __init__(
        self,
        katrain: Any,
        config: dict[str, Any],
        status_callback: Callable[[str, str], None] | None = None,
        error_callback: Callable[[str, str | None, bool], None] | None = None,
        main_thread_scheduler: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        super().__init__(katrain, config, error_callback, main_thread_scheduler)
        self.status_callback = status_callback

        self.allow_recovery = self.config.get("allow_recovery", True)  # if false, don't give popups
        self.queries: dict[str, Any] = {}  # outstanding query id -> start time and callback
        self.ponder_query: dict[str, Any] | None = None
        self.query_counter = 0
        self.katago_process: subprocess.Popen[bytes] | None = None
        self.base_priority = 0
        self.override_settings: dict[str, str] = {"reportAnalysisWinratesAs": "BLACK"}  # force these settings
        self.analysis_thread: threading.Thread | None = None
        self.stderr_thread: threading.Thread | None = None
        self.write_stdin_thread: threading.Thread | None = None
        # Pipe reader threads (Phase 22: I/O timeout)
        self.stdout_reader_thread: threading.Thread | None = None
        self.stderr_reader_thread: threading.Thread | None = None
        self.shell = False
        self.write_queue: queue.Queue[
            tuple[dict[str, Any], Callable[..., None] | None, Callable[..., None] | None, Move | None, GameNode | None]
            | None
        ] = queue.Queue()
        # Output queues for non-blocking I/O (Phase 22)
        self._stdout_queue: queue.Queue[bytes | None] = queue.Queue()
        self._stderr_queue: queue.Queue[bytes | None] = queue.Queue()
        # Shutdown event (recreated on each start, not cleared)
        self._shutdown_event = threading.Event()
        # Phase 159: RLock for safe reentrancy in terminate_queries()
        # (terminate_queries() acquires thread_lock, then calls terminate_query()
        # which also acquires thread_lock to pop from queries dict).
        # RLock is the only correct choice given the current control flow; the
        # alternative would be to restructure terminate_queries() to release
        # the lock before calling terminate_query(), tracked separately.
        self.thread_lock = threading.RLock()
        # Pending query counter for backlog protection (Phase 95B)
        self._pending_query_count = 0
        self._pending_query_lock = threading.Lock()
        if config.get("altcommand", ""):
            self.command = config["altcommand"]
            self.shell = True
        else:
            model = find_package_resource(config["model"])
            cfg = find_package_resource(config["config"])
            exe = self.get_engine_path(config.get("katago", "").strip())

            if not exe:
                return

            # Add human model to command if provided
            if config.get("humanlike_model", ""):
                human_model_path = find_package_resource(config.get("humanlike_model", ""))
                if os.path.isfile(human_model_path):
                    self.command = shlex.split(
                        f'"{exe}" analysis -model "{model}" -human-model "{human_model_path}" -config "{cfg}" -override-config "homeDataDir={os.path.expanduser(DATA_FOLDER)}"'
                    )
                else:
                    self.katrain.log(f"Human model not found at {human_model_path}", -1)
                    # Fall back to regular command without human model
                    self.command = shlex.split(
                        f'"{exe}" analysis -model "{model}" -config "{cfg}" -override-config "homeDataDir={os.path.expanduser(DATA_FOLDER)}"'
                    )
            else:
                # Regular command without human model
                self.command = shlex.split(
                    f'"{exe}" analysis -model "{model}" -config "{cfg}" -override-config "homeDataDir={os.path.expanduser(DATA_FOLDER)}"'
                )
        self.start()

    def on_error(self, message: str, code: str | None = None, allow_popup: bool = True) -> None:
        self.katrain.log(message, OUTPUT_ERROR)
        if self.allow_recovery and allow_popup:
            self.katrain("engine_recovery_popup", message, code)

    def _fire_engine_error(self, message: str, code: str | None = None, allow_popup: bool = True) -> None:
        """Dispatch an engine-level error through the configured callback chain.

        Resolution order:
        1. If error_callback was injected via constructor -> schedule on main thread
        2. Else fall back to self.on_error method (backward-compat: tests may monkey-patch)

        The main_thread_scheduler is the same one used by per-query error callbacks
        (_invoke_error_callback), injected by the GUI layer to make callbacks
        UI-thread-safe without coupling core to Kivy.
        """
        if self._error_callback is not None:
            try:
                # *args/**kwargs so the wrapper tolerates schedulers that pass _dt (Kivy)
                self._main_thread_scheduler(
                    lambda *_a, **_kw: self._error_callback(message, code, allow_popup)
                )
            except Exception as e:  # noqa: BLE001 - last-resort error path
                self.katrain.log(f"Error in engine error_callback: {e}", OUTPUT_ERROR)
            return
        # Backward-compat path: delegate to on_error (may be monkey-patched by tests)
        try:
            self.on_error(message, code, allow_popup)
        except Exception as e:  # noqa: BLE001 - last-resort error path
            self.katrain.log(f"Error in on_error handler: {e}", OUTPUT_ERROR)

    def start(self) -> None:
        with self.thread_lock:
            # Recreate queues and shutdown event for clean restart
            self.write_queue = queue.Queue()
            self._stdout_queue = queue.Queue()
            self._stderr_queue = queue.Queue()
            # Important: recreate event (not clear()) to prevent old threads from resuming
            self._shutdown_event = threading.Event()
            # Reset pending query counter on start/restart
            with self._pending_query_lock:
                self._pending_query_count = 0
            try:
                self.katrain.log(f"Starting KataGo with {self.command}", OUTPUT_DEBUG)
                startupinfo = None
                if hasattr(subprocess, "STARTUPINFO"):
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # stop command box popups on win/pyinstaller
                self.katago_process = subprocess.Popen(
                    self.command,
                    startupinfo=startupinfo,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=self.shell,
                )
            except (FileNotFoundError, PermissionError, OSError) as e:
                self._fire_engine_error(i18n._("Starting Kata failed").format(command=self.command, error=e), code="c")
                return  # don't start
            # Pipe reader threads (blocking I/O isolated here)
            self.stdout_reader_thread = threading.Thread(
                target=self._pipe_reader_thread,
                args=(self.katago_process.stdout, self._stdout_queue, "stdout"),
                daemon=True,
                name="katago-stdout-reader",
            )
            self.stderr_reader_thread = threading.Thread(
                target=self._pipe_reader_thread,
                args=(self.katago_process.stderr, self._stderr_queue, "stderr"),
                daemon=True,
                name="katago-stderr-reader",
            )
            # Consumer threads (non-blocking queue reads)
            self.analysis_thread = threading.Thread(
                target=self._analysis_read_thread, daemon=True, name="katago-analysis"
            )
            self.stderr_thread = threading.Thread(target=self._read_stderr_thread, daemon=True, name="katago-stderr")
            self.write_stdin_thread = threading.Thread(
                target=self._write_stdin_thread, daemon=True, name="katago-stdin"
            )
            # Start all threads
            self.stdout_reader_thread.start()
            self.stderr_reader_thread.start()
            self.analysis_thread.start()
            self.stderr_thread.start()
            self.write_stdin_thread.start()

    def on_new_game(self) -> None:
        self.base_priority += 1
        if not self.is_idle():
            with self.thread_lock:
                self.write_queue = queue.Queue()
                self.terminate_queries(only_for_node=None, lock=False)
                self.ponder_query = None
                self.queries = {}
            # Phase 98 fix: Reset pending counter when queries are cleared
            # This is safe because all responses for cleared queries will be ignored
            with self._pending_query_lock:
                self._pending_query_count = 0

    def terminate_queries(self, only_for_node: GameNode | None = None, lock: bool = True) -> None:
        from katrain.core.engine_query import terminate_queries as _terminate_queries

        _terminate_queries(self, only_for_node=only_for_node, lock=lock)

    def stop_pondering(self) -> None:
        from katrain.core.engine_query import stop_pondering as _stop

        _stop(self)

    def _stop_pondering_unlocked(self) -> dict[str, Any] | None:
        from katrain.core.engine_query import stop_pondering_unlocked as _stop

        return _stop(self)

    def terminate_query(self, query_id: str, ignore_further_results: bool = True) -> None:
        from katrain.core.engine_query import terminate_query as _terminate

        _terminate(self, query_id, ignore_further_results=ignore_further_results)

    def restart(self) -> None:
        with self.thread_lock:
            self.queries = {}
        # Reset pending counter before shutdown
        with self._pending_query_lock:
            self._pending_query_count = 0
        self.shutdown(finish=False)
        self.start()

    def check_alive(
        self, os_error: str = "", exception_if_dead: bool = False, maybe_open_recovery: bool = False
    ) -> bool:
        ok: bool = self.katago_process is not None and self.katago_process.poll() is None
        if not ok and exception_if_dead:
            if self.katago_process:
                code = self.katago_process.poll()
                if code == 3221225781:
                    died_msg = i18n._("Engine missing DLL")
                else:
                    died_msg = i18n._("Engine died unexpectedly").format(error=f"{os_error} status {code}")
                if code != 1:  # deliberate exit
                    self._fire_engine_error(died_msg, str(code) if code is not None else None, allow_popup=maybe_open_recovery)
                self.katago_process = None  # return from threads
            else:
                self.katrain.log(i18n._("Engine died unexpectedly").format(error=os_error), OUTPUT_DEBUG)
        return ok

    def wait_to_finish(self, timeout: float = 30.0) -> bool:
        """Wait for queries to complete with timeout (thread-safe).

        Args:
            timeout: Maximum wait time in seconds (default: 30.0)

        Returns:
            True if all queries completed, False if timeout reached.

        Timeout behavior:
            - Logs a debug message with remaining query count
            - Returns False (does NOT force-kill anything)
            - Caller (shutdown) proceeds to terminate the process anyway
        """
        start = time.time()
        while True:
            # Check queries with lock
            with self.thread_lock:
                remaining = len(self.queries)
            if remaining == 0:
                return True
            # Check process status (local capture for TOCTOU safety)
            process = self.katago_process
            if process is None or process.poll() is not None:
                return True
            # Check timeout
            if time.time() - start > timeout:
                self.katrain.log(
                    f"wait_to_finish: timeout after {timeout}s, {remaining} queries remaining",
                    OUTPUT_DEBUG,
                )
                return False
            time.sleep(0.1)

    def shutdown(self, finish: bool = False) -> None:
        """Shutdown engine safely.

        This method guarantees completion - all exceptions are logged and swallowed.
        Queue operations use timeouts to prevent deadlock.

        Shutdown sequence (order matters):
        1. Set _shutdown_event -> notify consumer threads to stop
        2. Put None to write_queue -> notify writer thread to stop (non-blocking)
        3. process.terminate() -> start process termination
        4. Close pipes explicitly -> guarantee EOF for reader threads
        5. Join threads with timeout -> wait for graceful shutdown
        6. process.kill() if still alive -> force kill (suspended process workaround)
        7. Set katago_process = None (last step)
        """
        self.katrain.log(f"Engine shutdown starting (finish={finish})", OUTPUT_DEBUG)
        process = self.katago_process
        if finish and process:
            completed = self.wait_to_finish()
            if not completed:
                self.katrain.log("Engine shutdown: wait_to_finish timed out, proceeding to terminate", OUTPUT_DEBUG)

        # Step 1: Signal shutdown to consumer threads
        self._shutdown_event.set()

        # Step 2: Signal writer thread to stop (non-blocking to prevent deadlock)
        self._safe_queue_put(self.write_queue, None, "write_queue termination")

        if process:
            # Step 3: Terminate process (start graceful shutdown)
            self._safe_terminate(process)

            # Step 4: Close pipes explicitly (guarantee EOF for readline())
            self._safe_close_pipes(process)

            # Step 5: Wait for threads to finish (short timeout)
            if finish is not None:  # don't care if exiting app
                self._join_threads_with_timeout()

            # Step 6: Force kill if still alive (suspended process workaround)
            self._safe_force_kill(process)

            # Step 7: Clear process reference (last step)
            self.katago_process = None
            self.katrain.log("Terminated KataGo process", OUTPUT_DEBUG)

        self.katrain.log("Engine shutdown complete", OUTPUT_DEBUG)

    def _safe_queue_put(self, q: queue.Queue[Any], item: Any, context: str) -> None:
        """Put item to queue with timeout to prevent deadlock."""
        try:
            q.put_nowait(item)
        except queue.Full:
            # Queue is full - try with timeout
            try:
                q.put(item, timeout=1.0)
            except queue.Full:
                self.katrain.log(
                    f"Shutdown: queue still full after timeout during {context}, skipping",
                    OUTPUT_DEBUG,
                )
        except Exception as e:  # noqa: BLE001 - shutdown cleanup, must continue
            self.katrain.log(
                f"Shutdown: unexpected error during {context}: {type(e).__name__}: {e}",
                OUTPUT_EXTRA_DEBUG,
            )

    def _safe_terminate(self, process: subprocess.Popen[bytes]) -> None:
        """Request graceful process termination."""
        self.katrain.log("Terminating KataGo process", OUTPUT_DEBUG)
        try:
            process.terminate()
        except OSError as e:
            self.katrain.log(f"Shutdown: OSError during terminate: {e}", OUTPUT_DEBUG)
        except Exception as e:  # noqa: BLE001 - shutdown cleanup, must continue
            self.katrain.log(
                f"Shutdown: unexpected error during terminate: {type(e).__name__}: {e}",
                OUTPUT_EXTRA_DEBUG,
            )

    def _safe_close_pipes(self, process: subprocess.Popen[bytes]) -> None:
        """Close stdin/stdout/stderr pipes."""
        for name, pipe in [
            ("stdin", process.stdin),
            ("stdout", process.stdout),
            ("stderr", process.stderr),
        ]:
            if pipe:
                try:
                    pipe.close()
                except BrokenPipeError:
                    self.katrain.log(f"Shutdown: pipe {name} already broken", OUTPUT_EXTRA_DEBUG)
                except OSError as e:
                    self.katrain.log(f"Shutdown: OSError closing {name}: {e}", OUTPUT_DEBUG)
                except Exception as e:  # noqa: BLE001 - shutdown cleanup, must continue
                    self.katrain.log(
                        f"Shutdown: unexpected error closing {name}: {type(e).__name__}: {e}",
                        OUTPUT_EXTRA_DEBUG,
                    )

    def _join_threads_with_timeout(self) -> None:
        """Wait for all threads to finish with timeout."""
        all_threads = [
            self.stdout_reader_thread,
            self.stderr_reader_thread,
            self.analysis_thread,
            self.stderr_thread,
            self.write_stdin_thread,
        ]
        for t in all_threads:
            if t and t.is_alive():
                t.join(timeout=2.0)
                if t.is_alive():
                    self.katrain.log(f"Thread {t.name} did not stop within 2s timeout", OUTPUT_DEBUG)

    def _safe_force_kill(self, process: subprocess.Popen[bytes]) -> None:
        """Force kill process if still alive."""
        try:
            if process.poll() is None:
                self.katrain.log("Process still alive, forcing kill", OUTPUT_DEBUG)
                process.kill()
                try:
                    exit_code = process.wait(timeout=1.0)
                    self.katrain.log(f"Process killed: exit_code={exit_code}", OUTPUT_DEBUG)
                except subprocess.TimeoutExpired:
                    self.katrain.log("Process did not respond to kill - process may be orphaned", OUTPUT_ERROR)
        except OSError as e:
            self.katrain.log(f"Shutdown: OSError during force kill: {e}", OUTPUT_DEBUG)
        except Exception as e:  # noqa: BLE001 - shutdown cleanup, must continue
            self.katrain.log(
                f"Shutdown: unexpected error during force kill: {type(e).__name__}: {e}",
                OUTPUT_EXTRA_DEBUG,
            )

    def is_idle(self) -> bool:
        # Note: queue.empty() is best-effort and not strictly reliable.
        # This function is advisory; don't use for precise control flow.
        with self.thread_lock:
            return not self.queries and self.write_queue.empty()

    def is_alive(self) -> bool:
        """Lightweight health check; thin wrapper over check_alive().

        Does not raise, does not open popups, does not modify state.
        Safe for UI layer to call frequently (e.g. on every status update).
        """
        return self.check_alive()

    def queries_remaining(self) -> int:
        with self.thread_lock:
            return len(self.queries) + int(not self.write_queue.empty())

    # =================================================================
    # I/O threads (delegated to engine_io)
    # =================================================================

    def _pipe_reader_thread(self, pipe: Any, output_queue: queue.Queue[bytes | None], name: str) -> None:
        from katrain.core.engine_io import pipe_reader_thread as _impl

        _impl(self, pipe, output_queue, name)

    def _read_stderr_thread(self) -> None:
        from katrain.core.engine_io import read_stderr_thread as _impl

        _impl(self)

    def _analysis_read_thread(self) -> None:
        from katrain.core.engine_io import analysis_read_thread as _impl

        _impl(self)

    def _write_stdin_thread(self) -> None:
        from katrain.core.engine_io import write_stdin_thread as _impl

        _impl(self)

    # =================================================================
    # Query lifecycle (delegated to engine_query)
    # =================================================================

    def _invoke_error_callback(self, error_callback: Callable[..., None] | None, error_msg: dict[str, Any]) -> None:
        from katrain.core.engine_query import invoke_error_callback as _impl

        _impl(self, error_callback, error_msg)

    def _decrement_pending_count(self) -> None:
        from katrain.core.engine_query import decrement_pending_count as _impl

        _impl(self)

    def get_pending_count(self) -> int:
        from katrain.core.engine_query import get_pending_count as _impl

        return _impl(self)

    def has_query_capacity(self, headroom: int = 10) -> bool:
        from katrain.core.engine_query import has_query_capacity as _impl

        return _impl(self, headroom)

    def send_query(
        self,
        query: dict[str, Any],
        callback: Callable[..., None] | None,
        error_callback: Callable[..., None] | None,
        next_move: Move | None = None,
        node: GameNode | None = None,
    ) -> bool:
        from katrain.core.engine_query import send_query as _impl

        return _impl(self, query, callback, error_callback, next_move, node)

    def request_analysis(
        self,
        analysis_node: GameNode,
        callback: Callable[..., None],
        error_callback: Callable[..., None] | None = None,
        visits: int | None = None,
        analyze_fast: bool = False,
        time_limit: bool = True,
        find_alternatives: bool = False,
        region_of_interest: list[int] | None = None,
        priority: int = 0,
        ponder: bool = False,
        ownership: bool | None = None,
        next_move: Move | None = None,
        extra_settings: dict[str, Any] | None = None,
        include_policy: bool = True,
        report_every: float | None = None,
    ) -> None:
        from katrain.core.engine_query import request_analysis as _impl

        _impl(
            self,
            analysis_node,
            callback,
            error_callback,
            visits,
            analyze_fast,
            time_limit,
            find_alternatives,
            region_of_interest,
            priority,
            ponder,
            ownership,
            next_move,
            extra_settings,
            include_policy,
            report_every,
        )

    def _handle_engine_timeout(self) -> None:
        """Handle engine timeout (called from background thread).

        Called when analysis thread detects that:
        1. Queue.get() timed out
        2. There are pending queries
        3. Process is no longer alive

        This triggers shutdown and optionally shows recovery popup.
        Note: Recovery popup is shown via katrain callback which handles UI threading.
        """
        self.katrain.log("Engine response timeout detected", OUTPUT_ERROR)
        # Shutdown without waiting (already dead)
        self.shutdown(finish=False)
        # Show recovery popup via katrain callback (handles UI threading internally)
        if self.allow_recovery:
            self._fire_engine_error("Engine timeout", code="timeout", allow_popup=True)

    # =================================================================
    # Backend / query utilities (kept inline - small)
    # =================================================================

    def get_backend_type(self) -> str:
        """Get backend type for display (best-effort heuristic).

        This is for display purposes only and not definitive.
        The actual backend is determined by the KataGo binary.

        Returns:
            One of: "OpenCL", "CUDA", "Eigen", "TensorRT", "Unknown"
        """
        exe_path = self.get_engine_path(self.config.get("katago", ""))
        if not exe_path:
            return "Unknown"

        basename = os.path.basename(exe_path).lower()

        if "opencl" in basename:
            return "OpenCL"
        if "cuda" in basename:
            return "CUDA"
        if "eigen" in basename or "cpu" in basename:
            return "Eigen"
        if "tensorrt" in basename:
            return "TensorRT"

        # Default assumption based on bundled binaries
        return "OpenCL"

    def create_minimal_analysis_query(self) -> dict[str, Any]:
        """Create a minimal analysis query for testing.

        Used for auto mode test analysis:
        - 9x9 empty board
        - 10 visits only
        - No ownership, no ponder

        Returns:
            Query dict ready to send to KataGo.
        """
        query_id = f"test_analysis_{time.time()}"

        return {
            "id": query_id,
            "rules": self.get_rules("chinese"),
            "komi": 7.5,
            "boardXSize": 9,
            "boardYSize": 9,
            "initialStones": [],
            "moves": [],
            "maxVisits": 10,
            "includeOwnership": False,
            "includePolicy": False,
        }


