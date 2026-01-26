import json
import os
import platform
import queue
import shlex
import subprocess
import threading
import time
import traceback
from typing import Callable, Dict, List, Optional

from katrain.common.platform import get_platform

from katrain.core.constants import (
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    OUTPUT_EXTRA_DEBUG,
    OUTPUT_KATAGO_STDERR,
    DATA_FOLDER,
    KATAGO_EXCEPTION,
    PONDERING_REPORT_DT,
)
from katrain.core.game_node import GameNode
from katrain.core.lang import i18n
from katrain.core.sgf_parser import Move
from katrain.core.utils import find_package_resource, json_truncate_arrays
from katrain.core.engine_query import build_analysis_query


def _ensure_str(line) -> str:
    """Normalize line to str, handling bytes/str/None."""
    if line is None:
        return ""
    if isinstance(line, bytes):
        return line.decode("utf-8", errors="replace")
    return line


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

    def __init__(self, katrain, config):
        self.katrain = katrain
        self.config = config

    @staticmethod
    def get_rules(ruleset):
        if ruleset.strip().startswith("{"):
            try:
                ruleset = json.loads(ruleset)
            except json.JSONDecodeError:
                pass
        if isinstance(ruleset, dict):
            return ruleset
        return KataGoEngine.RULESETS.get(str(ruleset).lower(), "japanese")

    def advance_showing_game(self):
        pass  # avoid transitional error

    def status(self):
        return ""  # avoid transitional error

    def get_engine_path(self, exe):
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
            self.on_error(i18n._("Kata exe not found").format(exe=exe), "KATAGO-EXE")
            return None
        elif not exepath:
            paths = os.getenv("PATH", ".").split(os.pathsep) + ["/opt/homebrew/bin/"]
            exe_with_paths = [os.path.join(path, exe) for path in paths if os.path.isfile(os.path.join(path, exe))]
            if not exe_with_paths:
                self.on_error(i18n._("Kata exe not found in path").format(exe=exe), "KATAGO-EXE")
                return None
            exe = exe_with_paths[0]
        return exe

    def on_error(self, message, code, allow_popup):
        # Subclasses should override to implement proper logging
        pass


class KataGoEngine(BaseEngine):
    """Starts and communicates with the KataGO analysis engine"""

    PONDER_KEY = "_kt_continuous"
    # Timeout for Queue.get() in consumer threads (seconds)
    IO_TIMEOUT = 5.0

    def __init__(self, katrain, config):
        super().__init__(katrain, config)

        self.allow_recovery = self.config.get("allow_recovery", True)  # if false, don't give popups
        self.queries = {}  # outstanding query id -> start time and callback
        self.ponder_query = None
        self.query_counter = 0
        self.katago_process = None
        self.base_priority = 0
        self.override_settings = {"reportAnalysisWinratesAs": "BLACK"}  # force these settings
        self.analysis_thread = None
        self.stderr_thread = None
        self.write_stdin_thread = None
        # Pipe reader threads (Phase 22: I/O timeout)
        self.stdout_reader_thread = None
        self.stderr_reader_thread = None
        self.shell = False
        self.write_queue = queue.Queue()
        # Output queues for non-blocking I/O (Phase 22)
        self._stdout_queue = queue.Queue()
        self._stderr_queue = queue.Queue()
        # Shutdown event (recreated on each start, not cleared)
        self._shutdown_event = threading.Event()
        self.thread_lock = threading.Lock()
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
                human_model_path = find_package_resource(config.get("humanlike_model",""))
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

    def on_error(self, message, code=None, allow_popup=True):
        self.katrain.log(message, OUTPUT_ERROR)
        if self.allow_recovery and allow_popup:
            self.katrain("engine_recovery_popup", message, code)

    def start(self):
        with self.thread_lock:
            # Recreate queues and shutdown event for clean restart
            self.write_queue = queue.Queue()
            self._stdout_queue = queue.Queue()
            self._stderr_queue = queue.Queue()
            # Important: recreate event (not clear()) to prevent old threads from resuming
            self._shutdown_event = threading.Event()
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
                self.on_error(i18n._("Starting Kata failed").format(command=self.command, error=e), code="c")
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
            self.stderr_thread = threading.Thread(
                target=self._read_stderr_thread, daemon=True, name="katago-stderr"
            )
            self.write_stdin_thread = threading.Thread(
                target=self._write_stdin_thread, daemon=True, name="katago-stdin"
            )
            # Start all threads
            self.stdout_reader_thread.start()
            self.stderr_reader_thread.start()
            self.analysis_thread.start()
            self.stderr_thread.start()
            self.write_stdin_thread.start()

    def on_new_game(self):
        self.base_priority += 1
        if not self.is_idle():
            with self.thread_lock:
                self.write_queue = queue.Queue()
                self.terminate_queries(only_for_node=None, lock=False)
                self.ponder_query = None
                self.queries = {}

    def terminate_queries(self, only_for_node=None, lock=True):
        if lock:
            with self.thread_lock:
                return self.terminate_queries(only_for_node=only_for_node, lock=False)
        for query_id, (_, _, _, _, node) in list(self.queries.items()):
            if only_for_node is None or only_for_node is node:
                self.terminate_query(query_id)

    def stop_pondering(self):
        """Stop pondering (public API, acquires lock)."""
        with self.thread_lock:
            pq = self._stop_pondering_unlocked()
        if pq:
            self.terminate_query(pq["id"], ignore_further_results=False)

    def _stop_pondering_unlocked(self):
        """Stop pondering without acquiring lock (caller must hold thread_lock)."""
        pq = self.ponder_query
        self.ponder_query = None
        return pq

    def terminate_query(self, query_id, ignore_further_results=True):
        """Terminate a query (thread-safe).

        Args:
            query_id: The query ID to terminate
            ignore_further_results: If True, remove from queries dict (ignore any future results)
        """
        self.katrain.log(f"Terminating query {query_id}", OUTPUT_DEBUG)

        if query_id is not None:
            self.send_query({"action": "terminate", "terminateId": query_id}, None, None)
            if ignore_further_results:
                with self.thread_lock:
                    self.queries.pop(query_id, None)

    def restart(self):
        self.queries = {}
        self.shutdown(finish=False)
        self.start()

    def check_alive(self, os_error="", exception_if_dead=False, maybe_open_recovery=False):
        ok = self.katago_process and self.katago_process.poll() is None
        if not ok and exception_if_dead:
            if self.katago_process:
                code = self.katago_process and self.katago_process.poll()
                if code == 3221225781:
                    died_msg = i18n._("Engine missing DLL")
                else:
                    died_msg = i18n._("Engine died unexpectedly").format(error=f"{os_error} status {code}")
                if code != 1:  # deliberate exit
                    self.on_error(died_msg, code, allow_popup=maybe_open_recovery)
                self.katago_process = None  # return from threads
            else:
                self.katrain.log(i18n._("Engine died unexpectedly").format(error=os_error), OUTPUT_DEBUG)
        return ok

    def wait_to_finish(self, timeout=30.0):
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

    def shutdown(self, finish=False):
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
                self.katrain.log(
                    "Engine shutdown: wait_to_finish timed out, proceeding to terminate", OUTPUT_DEBUG
                )

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

    def _safe_queue_put(self, q, item, context):
        """Put item to queue with timeout to prevent deadlock.

        Uses put_nowait() first, falls back to put(timeout=1.0) if full.
        Never blocks indefinitely.
        """
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

    def _safe_terminate(self, process):
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

    def _safe_close_pipes(self, process):
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

    def _join_threads_with_timeout(self):
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
                    self.katrain.log(
                        f"Thread {t.name} did not stop within 2s timeout", OUTPUT_DEBUG
                    )

    def _safe_force_kill(self, process):
        """Force kill process if still alive."""
        try:
            if process.poll() is None:
                self.katrain.log("Process still alive, forcing kill", OUTPUT_DEBUG)
                process.kill()
                try:
                    exit_code = process.wait(timeout=1.0)
                    self.katrain.log(f"Process killed: exit_code={exit_code}", OUTPUT_DEBUG)
                except subprocess.TimeoutExpired:
                    self.katrain.log(
                        "Process did not respond to kill - process may be orphaned", OUTPUT_ERROR
                    )
        except OSError as e:
            self.katrain.log(f"Shutdown: OSError during force kill: {e}", OUTPUT_DEBUG)
        except Exception as e:  # noqa: BLE001 - shutdown cleanup, must continue
            self.katrain.log(
                f"Shutdown: unexpected error during force kill: {type(e).__name__}: {e}",
                OUTPUT_EXTRA_DEBUG,
            )

    def is_idle(self):
        # Note: queue.empty() is best-effort and not strictly reliable.
        # This function is advisory; don't use for precise control flow.
        with self.thread_lock:
            return not self.queries and self.write_queue.empty()

    def queries_remaining(self):
        with self.thread_lock:
            return len(self.queries) + int(not self.write_queue.empty())

    def _pipe_reader_thread(self, pipe, output_queue, name):
        """Read from pipe and put lines into queue (blocking I/O isolated here).

        This thread performs blocking readline() calls. When the process terminates
        or pipes are closed, readline() returns empty bytes (EOF).

        Args:
            pipe: File-like object (process.stdout or process.stderr)
            output_queue: Queue to put read lines into
            name: Thread name for logging
        """
        while not self._shutdown_event.is_set():
            try:
                line = pipe.readline()
                if not line:
                    break  # EOF or process terminated
                output_queue.put(line)
            except (OSError, ValueError):
                break  # Pipe closed or error
        # Signal consumer thread that this reader is done
        output_queue.put(None)
        self.katrain.log(f"Pipe reader {name} finished", OUTPUT_DEBUG)

    def _read_stderr_thread(self):
        """Process stderr lines from queue (non-blocking with timeout)."""
        while not self._shutdown_event.is_set():
            try:
                raw_line = self._stderr_queue.get(timeout=self.IO_TIMEOUT)
                if raw_line is None:
                    return  # Termination signal from reader thread
                line = _ensure_str(raw_line)
                if line:
                    if "Uncaught exception" in line or "what()" in line:  # linux=what
                        msg = f"KataGo Engine Failed: {line[9:].strip()}"
                        self.on_error(msg, KATAGO_EXCEPTION)
                        return
                    try:
                        self.katrain.log(line.strip(), OUTPUT_KATAGO_STDERR)
                    except Exception as e:  # noqa: BLE001 - thread exception, must log and continue
                        self.katrain.log(
                            f"Error processing stderr: {line!r}: {e}\n{traceback.format_exc()}",
                            OUTPUT_ERROR,
                        )
            except queue.Empty:
                # Timeout - check if we should continue
                if self._shutdown_event.is_set():
                    return
                # No stderr activity is normal during idle periods
                continue
            except Exception as e:  # noqa: BLE001 - thread exception, must log and exit gracefully
                self.katrain.log(
                    f"Exception in stderr thread: {e}\n{traceback.format_exc()}",
                    OUTPUT_ERROR,
                )
                return

    def _analysis_read_thread(self):
        """Process analysis results from queue (non-blocking with timeout)."""
        while not self._shutdown_event.is_set():
            try:
                raw_line = self._stdout_queue.get(timeout=self.IO_TIMEOUT)
                if raw_line is None:
                    return  # Termination signal from reader thread
                line = _ensure_str(raw_line).strip()
            except queue.Empty:
                # Timeout - check if we should continue or handle timeout
                if self._shutdown_event.is_set():
                    return
                # Check if there are pending queries and process is dead
                with self.thread_lock:
                    has_pending_queries = bool(self.queries)
                if has_pending_queries and not self.check_alive():
                    self._handle_engine_timeout()
                    return
                # No pending queries or process alive - continue waiting
                continue
            except Exception as e:  # noqa: BLE001 - thread exception, must log and exit gracefully
                self.katrain.log(
                    f"Exception in analysis thread: {e}\n{traceback.format_exc()}",
                    OUTPUT_ERROR,
                )
                self.check_alive(os_error=str(e), exception_if_dead=True, maybe_open_recovery=True)
                return

            if not line:
                continue

            if "Uncaught exception" in line:
                msg = f"KataGo Engine Failed: {line}"
                self.on_error(msg, KATAGO_EXCEPTION)
                return
            if not line:
                continue
            try:
                analysis = json.loads(line)
                if "id" not in analysis:
                    self.katrain.log(f"Error without ID {analysis} received from KataGo", OUTPUT_ERROR)
                    continue
                query_id = analysis["id"]

                # Retrieve query data under lock to prevent race conditions
                # Callbacks are executed outside the lock to avoid deadlocks
                callback = None
                error_callback = None
                start_time = None
                next_move = None
                should_delete = False
                query_found = False

                with self.thread_lock:
                    if query_id not in self.queries:
                        # Query was already removed by terminate_queries() or on_new_game()
                        # This is a normal case when switching games or canceling analysis
                        if analysis.get("action") != "terminate":
                            self.katrain.log(
                                f"Query result {query_id} discarded -- recent new game or node reset?", OUTPUT_DEBUG
                            )
                        continue
                    query_found = True
                    callback, error_callback, start_time, next_move, _ = self.queries[query_id]
                    if "error" in analysis:
                        del self.queries[query_id]
                        should_delete = True
                    elif "warning" in analysis or "terminateId" in analysis:
                        pass  # No deletion needed for warnings/terminate confirmations
                    else:
                        partial_result = analysis.get("isDuringSearch", False)
                        if not partial_result:
                            del self.queries[query_id]
                            should_delete = True

                # Process results outside the lock
                if "error" in analysis:
                    if error_callback:
                        error_callback(analysis)
                    elif not (next_move and "Illegal move" in analysis["error"]):  # sweep
                        self.katrain.log(f"{analysis} received from KataGo", OUTPUT_ERROR)
                elif "warning" in analysis:
                    self.katrain.log(f"{analysis} received from KataGo", OUTPUT_DEBUG)
                elif "terminateId" in analysis:
                    self.katrain.log(f"{analysis} received from KataGo", OUTPUT_DEBUG)
                else:
                    partial_result = analysis.get("isDuringSearch", False)
                    time_taken = time.time() - start_time
                    results_exist = not analysis.get("noResults", False)
                    self.katrain.log(
                        f"[{time_taken:.1f}][{query_id}][{'....' if partial_result else 'done'}] KataGo analysis received: {len(analysis.get('moveInfos',[]))} candidate moves, {analysis['rootInfo']['visits'] if results_exist else 'n/a'} visits",
                        OUTPUT_DEBUG,
                    )
                    self.katrain.log(json_truncate_arrays(analysis), OUTPUT_EXTRA_DEBUG)
                    try:
                        if callback and results_exist:
                            callback(analysis, partial_result)
                    except Exception as e:  # noqa: BLE001 - callback exception, must log and continue
                        self.katrain.log(
                            f"Error in engine callback for query {query_id}: {e}\n{traceback.format_exc()}",
                            OUTPUT_ERROR,
                        )
                if getattr(self.katrain, "update_state", None):  # easier mocking etc
                    self.katrain.update_state()
            except Exception as e:  # noqa: BLE001 - thread exception, must log and continue processing
                self.katrain.log(
                    f"Unexpected exception {e} while processing KataGo output {line}\n{traceback.format_exc()}",
                    OUTPUT_ERROR,
                )

    def _handle_engine_timeout(self):
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
            self.on_error("Engine timeout", code="timeout", allow_popup=True)

    def _write_stdin_thread(self):
        """Write queries to KataGo stdin (TOCTOU-safe).

        Flush only in a thread since it returns only when the other program reads.
        """
        while not self._shutdown_event.is_set():
            # Local capture pattern for TOCTOU safety
            process = self.katago_process
            if process is None:
                return
            try:
                item = self.write_queue.get(block=True, timeout=0.1)
            except queue.Empty:
                continue
            # Check for termination signal (None)
            if item is None:
                return
            query, callback, error_callback, next_move, node = item
            old_ponder_query = None  # To call terminate_query outside of lock
            with self.thread_lock:
                if "id" not in query:
                    self.query_counter += 1
                    query["id"] = f"QUERY:{str(self.query_counter)}"

                ponder = query.pop(self.PONDER_KEY, False)
                if ponder:  # handle pondering in here to be in lock and such
                    pq = self.ponder_query or {}
                    # basically we handle pondering by just asking for these queries a lot and ignoring duplicates
                    # when a different ponder query comes in, e.g. due to selecting a roi or different node, switch
                    differences = {
                        k: (pq.get(k), query.get(k))
                        for k in (query.keys() | pq.keys()) - {"id", "maxVisits", "reportDuringSearchEvery"}
                        if pq.get(k) != query.get(k)
                    }
                    if differences:
                        old_ponder_query = self._stop_pondering_unlocked()
                        query["maxVisits"] = 10_000_000
                        query["reportDuringSearchEvery"] = PONDERING_REPORT_DT
                        self.ponder_query = query
                    else:
                        continue

                terminate = query.get("action") == "terminate"
                if not terminate:
                    self.queries[query["id"]] = (callback, error_callback, time.time(), next_move, node)
                tag = "ponder " if ponder else ("terminate " if terminate else "")
                self.katrain.log(f"Sending {tag}query {query['id']}: {json.dumps(query)}", OUTPUT_DEBUG)

            # Write to stdin outside lock (I/O should not be under lock)
            # Re-capture process reference after lock release
            process = self.katago_process
            if process is None:
                return
            try:
                process.stdin.write((json.dumps(query) + "\n").encode())
                process.stdin.flush()
            except (OSError, AttributeError, ValueError, BrokenPipeError) as e:
                self.katrain.log(f"Exception in writing to katago: {e}", OUTPUT_DEBUG)
                return  # some other thread will take care of this
            # Terminate old ponder query outside of lock to avoid deadlock
            if old_ponder_query:
                self.terminate_query(old_ponder_query["id"], ignore_further_results=False)

    def send_query(self, query, callback, error_callback, next_move=None, node=None):
        self.write_queue.put((query, callback, error_callback, next_move, node))

    def request_analysis(
        self,
        analysis_node: GameNode,
        callback: Callable,
        error_callback: Optional[Callable] = None,
        visits: int = None,
        analyze_fast: bool = False,
        time_limit=True,
        find_alternatives: bool = False,
        region_of_interest: Optional[List] = None,
        priority: int = 0,
        ponder=False,  # infinite visits, cancellable
        ownership: Optional[bool] = None,
        next_move: Optional[GameNode] = None,
        extra_settings: Optional[Dict] = None,
        include_policy=True,
        report_every: Optional[float] = None,
    ):
        # Check for unsupported AE commands
        nodes = analysis_node.nodes_from_root
        clear_placements = [m for node in nodes for m in node.clear_placements]
        if clear_placements:  # TODO: support these
            self.katrain.log(f"Not analyzing node {analysis_node} as there are AE commands in the path", OUTPUT_DEBUG)
            return

        # Resolve ownership
        if ownership is None:
            ownership = self.config["_enable_ownership"] and not next_move

        # Resolve visits with analysis_focus and analyze_fast
        if visits is None:
            visits = self.config["max_visits"]

            # analysis_focus に基づいて visits を調整
            focus = self.config.get("analysis_focus")
            if focus:
                # 優先しない色のターンの場合、fast_visits を使用
                if (focus == "black" and analysis_node.next_player == "W") or \
                   (focus == "white" and analysis_node.next_player == "B"):
                    if self.config.get("fast_visits"):
                        visits = self.config["fast_visits"]
            elif analyze_fast and self.config.get("fast_visits"):
                # analysis_focus がない場合のデフォルト処理（analyze_fast時）
                visits = self.config["fast_visits"]

        # Build query using engine_query module (Phase 68)
        query = build_analysis_query(
            analysis_node=analysis_node,
            visits=visits,
            ponder=ponder,
            ownership=ownership,
            rules=self.get_rules(analysis_node.ruleset),
            base_priority=self.base_priority,
            priority=priority,
            override_settings=self.override_settings,
            wide_root_noise=self.config["wide_root_noise"],
            max_time=self.config.get("max_time"),
            time_limit=time_limit,
            next_move=next_move,
            find_alternatives=find_alternatives,
            region_of_interest=region_of_interest,
            extra_settings=extra_settings,
            include_policy=include_policy,
            report_every=report_every,
            ponder_key=self.PONDER_KEY,
        )

        self.send_query(query, callback, error_callback, next_move, analysis_node)
        analysis_node.analysis_visits_requested = max(analysis_node.analysis_visits_requested, visits)
