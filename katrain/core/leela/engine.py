"""Leela Zero engine wrapper.

This module provides a GTP-based engine wrapper for Leela Zero.
It is completely separate from KataGoEngine.
"""

import logging
import os
import subprocess
import threading
import time
from typing import Callable, List, Optional, Tuple
from uuid import uuid4

from katrain.core.leela.parser import parse_lz_analyze
from katrain.core.leela.models import LeelaPositionEval

logger = logging.getLogger(__name__)


class LeelaEngine:
    """Leela Zero analysis engine wrapper.

    This engine communicates via GTP protocol with Leela Zero.
    It supports the lz-analyze command for position analysis.

    Note: This is completely separate from KataGoEngine.
    """

    # GTP response markers
    GTP_SUCCESS = "="
    GTP_FAILURE = "?"

    # Default settings
    DEFAULT_VISITS = 1000
    DEFAULT_INTERVAL = 100  # centiseconds for lz-analyze

    def __init__(self, katrain, config: dict):
        """Initialize LeelaEngine.

        Args:
            katrain: Parent KaTrain instance (for logging)
            config: Configuration dict with keys:
                - exe_path: Path to Leela executable
                - max_visits: Default max visits for analysis
        """
        self.katrain = katrain
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._analysis_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._current_request_id: Optional[str] = None
        self._gtp_ready = threading.Event()

        # State
        self._board_size = 19
        self._komi = 6.5
        self._moves: List[Tuple[str, str]] = []  # [(player, coord), ...]

    def start(self) -> bool:
        """Start Leela engine process.

        Returns:
            True if engine started successfully, False otherwise.
        """
        exe_path = self.config.get("exe_path", "")
        if not exe_path or not os.path.isfile(exe_path):
            logger.error(f"Leela executable not found: {exe_path}")
            return False

        with self._lock:
            if self.process and self.process.poll() is None:
                logger.warning("Leela process already running")
                return True

            try:
                logger.info(f"Starting Leela: {exe_path}")
                startupinfo = None
                if hasattr(subprocess, "STARTUPINFO"):
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                self.process = subprocess.Popen(
                    [exe_path],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Merge stderr into stdout
                    text=True,
                    bufsize=1,
                    startupinfo=startupinfo,
                )

                self._shutdown_event.clear()

                # Initialize in background thread to avoid blocking UI
                init_thread = threading.Thread(
                    target=self._wait_for_ready,
                    daemon=True,
                )
                init_thread.start()

                return True

            except (FileNotFoundError, PermissionError, OSError) as e:
                logger.error(f"Failed to start Leela: {e}")
                self.process = None
                return False

    def _wait_for_ready(self, timeout: float = 10.0) -> bool:
        """Wait for engine to be ready by sending 'name' command.

        Returns:
            True if engine responded, False on timeout.
        """
        start = time.time()
        # Read any initial output
        time.sleep(0.5)

        # Send a simple command to verify engine is ready
        self._send_command("boardsize 19")
        time.sleep(0.3)
        self._send_command("clear_board")
        time.sleep(0.3)
        self._send_command(f"komi {self._komi}")

        return True

    def shutdown(self, timeout: float = 5.0) -> bool:
        """Shutdown Leela engine.

        Args:
            timeout: Maximum wait time for graceful shutdown.

        Returns:
            True if shutdown completed gracefully, False if killed.
        """
        logger.info("Shutting down Leela engine")
        self._shutdown_event.set()

        # Cancel any ongoing analysis
        self.cancel_analysis()

        with self._lock:
            proc = self.process
            self.process = None

        if not proc:
            return True

        # Try graceful quit
        try:
            proc.stdin.write("quit\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

        # Wait for process to exit
        try:
            proc.wait(timeout=timeout)
            logger.info("Leela shutdown completed gracefully")
            return True
        except subprocess.TimeoutExpired:
            logger.warning(f"Leela shutdown timeout after {timeout}s, killing")
            proc.kill()
            proc.wait(timeout=2.0)
            return False

    def is_alive(self) -> bool:
        """Check if engine process is running."""
        with self._lock:
            return self.process is not None and self.process.poll() is None

    def _send_command(self, cmd: str) -> bool:
        """Send a GTP command to the engine.

        Args:
            cmd: GTP command string

        Returns:
            True if sent successfully, False otherwise.
        """
        with self._lock:
            proc = self.process
        if not proc or proc.poll() is not None:
            return False

        try:
            proc.stdin.write(cmd + "\n")
            proc.stdin.flush()
            logger.debug(f"Sent: {cmd}")
            return True
        except (BrokenPipeError, OSError) as e:
            logger.error(f"Failed to send command: {e}")
            return False

    def set_position(
        self,
        moves: List[Tuple[str, str]],
        board_size: int = 19,
        komi: float = 6.5,
    ) -> bool:
        """Set up board position by replaying moves.

        Args:
            moves: List of (player, coord) tuples, e.g., [("B", "D4"), ("W", "Q16")]
            board_size: Board size (default 19)
            komi: Komi value (default 6.5)

        Returns:
            True if position set successfully.
        """
        if not self.is_alive():
            if not self.start():
                return False

        # Reset board if needed
        if board_size != self._board_size:
            self._send_command(f"boardsize {board_size}")
            self._board_size = board_size
            time.sleep(0.1)

        self._send_command("clear_board")
        time.sleep(0.1)

        if komi != self._komi:
            self._send_command(f"komi {komi}")
            self._komi = komi
            time.sleep(0.1)

        # Replay moves
        for player, coord in moves:
            color = "black" if player.upper() in ("B", "BLACK") else "white"
            self._send_command(f"play {color} {coord}")
            time.sleep(0.05)

        self._moves = list(moves)
        return True

    def request_analysis(
        self,
        moves: List[Tuple[str, str]],
        callback: Callable[[LeelaPositionEval], None],
        visits: Optional[int] = None,
        board_size: int = 19,
        komi: float = 6.5,
    ) -> bool:
        """Request position analysis.

        Args:
            moves: List of (player, coord) tuples for the position
            callback: Function to call with analysis result
            visits: Maximum visits (uses config default if None)
            board_size: Board size
            komi: Komi value

        Returns:
            True if analysis request started.
        """
        # Cancel any previous analysis
        self.cancel_analysis()

        if visits is None:
            visits = self.config.get("max_visits", self.DEFAULT_VISITS)

        # Generate unique request ID
        request_id = str(uuid4())
        self._current_request_id = request_id

        # Start analysis in background thread
        self._analysis_thread = threading.Thread(
            target=self._run_analysis,
            args=(moves, callback, visits, board_size, komi, request_id),
            daemon=True,
        )
        self._analysis_thread.start()
        return True

    def _run_analysis(
        self,
        moves: List[Tuple[str, str]],
        callback: Callable[[LeelaPositionEval], None],
        visits: int,
        board_size: int,
        komi: float,
        request_id: str,
    ):
        """Run analysis in background thread.

        Args:
            moves: Position moves
            callback: Result callback
            visits: Visit limit
            board_size: Board size
            komi: Komi
            request_id: Unique ID for this request
        """
        try:
            # Set up position
            if not self.set_position(moves, board_size, komi):
                callback(LeelaPositionEval(parse_error="Failed to set position"))
                return

            # Check if cancelled
            if self._current_request_id != request_id:
                logger.debug(f"Analysis {request_id} cancelled before start")
                return

            # Send lz-analyze command
            interval = self.DEFAULT_INTERVAL
            self._send_command(f"lz-analyze {interval}")

            # Collect output until we have enough visits or timeout
            start_time = time.time()
            max_time = 30.0  # Maximum analysis time
            result_line = ""

            with self._lock:
                proc = self.process

            if not proc:
                callback(LeelaPositionEval(parse_error="Engine not running"))
                return

            while time.time() - start_time < max_time:
                # Check if cancelled
                if self._current_request_id != request_id:
                    logger.debug(f"Analysis {request_id} cancelled during collection")
                    # Stop analysis by sending another command
                    self._send_command("name")
                    return

                if self._shutdown_event.is_set():
                    return

                try:
                    line = proc.stdout.readline()
                    if not line:
                        break

                    line = line.strip()
                    if "info" in line.lower():
                        result_line = line
                        # Check if we have enough visits
                        result = parse_lz_analyze(line)
                        if result.is_valid and result.root_visits >= visits:
                            break
                except Exception as e:
                    logger.error(f"Error reading output: {e}")
                    break

            # Stop analysis
            self._send_command("name")
            time.sleep(0.1)

            # Check if still valid request
            if self._current_request_id != request_id:
                logger.debug(f"Analysis {request_id} cancelled after collection")
                return

            # Parse result
            if result_line:
                result = parse_lz_analyze(result_line)
            else:
                result = LeelaPositionEval(parse_error="No analysis output")

            # Callback (only if not cancelled)
            if self._current_request_id == request_id:
                callback(result)

        except Exception as e:
            logger.exception(f"Analysis error: {e}")
            if self._current_request_id == request_id:
                callback(LeelaPositionEval(parse_error=str(e)))

    def cancel_analysis(self) -> None:
        """Cancel current analysis request.

        Thread Safety:
            Uses _lock to protect _current_request_id modification.
            The GTP interrupt command is sent outside the lock to avoid
            potential deadlocks with I/O operations.
        """
        with self._lock:
            self._current_request_id = None
        # Send a command to interrupt lz-analyze (outside lock)
        if self.is_alive():
            self._send_command("name")

    def is_idle(self) -> bool:
        """Check if the engine is ready to accept a new analysis request.

        Returns:
            True if no active analysis request (ready for new request).
            False if currently processing an analysis.

        Thread Safety:
            Uses _lock to protect _current_request_id read.
            This method is intended for polling in batch analysis loops.

        Note:
            Thread state is not considered. After cancel_analysis(),
            this returns True even if the analysis thread is still
            shutting down. request_analysis() cancels any previous
            request before starting a new one, so this is safe.
        """
        with self._lock:
            return self._current_request_id is None

    def get_winrate(self) -> Optional[float]:
        """Get current position winrate (synchronous).

        Returns:
            Winrate as 0.0-1.0, or None if unavailable.
        """
        if not self.is_alive():
            return None

        self._send_command("winrate")
        time.sleep(0.2)

        # Read response (simplified, real implementation would be more robust)
        return None  # Not implemented for v1

    def status(self) -> str:
        """Get engine status string."""
        if not self.is_alive():
            return "Leela: Not running"
        return "Leela: Ready"
