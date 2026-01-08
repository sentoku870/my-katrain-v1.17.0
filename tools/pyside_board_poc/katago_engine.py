"""
KataGo Engine Manager for PySide6 Go Board PoC+

Manages KataGo analysis process using QProcess for async I/O.
All operations run in the GUI thread using Qt's event loop.

Key features:
- QProcess-based async communication (no worker threads)
- Newline-delimited JSON buffering for robust parsing
- Query ID management for stale response filtering
- Clean startup/shutdown with proper error handling
"""

import json
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot, QProcess


# Try both import styles for flexibility
try:
    from models import PositionSnapshot, CandidateMove, gtp_to_internal
except ImportError:
    from .models import PositionSnapshot, CandidateMove, gtp_to_internal


# =============================================================================
# Constants
# =============================================================================

MAX_CANDIDATES = 5
DEFAULT_MAX_VISITS = 1000
DEFAULT_KOMI = 6.5
DEFAULT_RULES = "japanese"
SETTINGS_FILE = "poc_settings.json"


# =============================================================================
# Settings Management
# =============================================================================

def get_settings_path() -> Path:
    """Return path to settings file."""
    return Path(__file__).parent / SETTINGS_FILE


def load_settings() -> dict:
    """
    Load settings from JSON file and environment variables.
    Environment variables override file settings.
    """
    settings = {
        "katago_exe": "",
        "config_path": "",
        "model_path": "",
        "komi": DEFAULT_KOMI,
        "rules": DEFAULT_RULES,
        "max_visits": DEFAULT_MAX_VISITS,
    }

    # Load from file
    settings_path = get_settings_path()
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                file_settings = json.load(f)
                settings.update(file_settings)
        except (json.JSONDecodeError, IOError):
            pass

    # Environment variable overrides
    if os.environ.get("KATAGO_EXE"):
        settings["katago_exe"] = os.environ["KATAGO_EXE"]
    if os.environ.get("KATAGO_CONFIG"):
        settings["config_path"] = os.environ["KATAGO_CONFIG"]
    if os.environ.get("KATAGO_MODEL"):
        settings["model_path"] = os.environ["KATAGO_MODEL"]

    return settings


def save_settings(settings: dict):
    """Save settings to JSON file."""
    settings_path = get_settings_path()
    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except IOError:
        pass


# =============================================================================
# Query Builder
# =============================================================================

def build_query(
    snapshot: PositionSnapshot,
    query_id: str,
    max_visits: int = DEFAULT_MAX_VISITS,
    rules: str = DEFAULT_RULES,
) -> dict:
    """
    Build KataGo analysis query from position snapshot.

    Uses initialStones approach:
    - All stones sent as initialStones
    - moves[] is empty
    - analyzeTurns = [0]

    This works for both SGF playback and edit mode.
    """
    return {
        "id": query_id,
        "rules": rules,
        "komi": snapshot.komi,
        "boardXSize": snapshot.board_size,
        "boardYSize": snapshot.board_size,
        "initialStones": snapshot.to_initial_stones(),
        "initialPlayer": snapshot.next_player,
        "moves": [],
        "analyzeTurns": [0],
        "maxVisits": max_visits,
    }


# =============================================================================
# Response Parser
# =============================================================================

def parse_response(
    response: dict,
    board_size: int = 19,
    max_candidates: int = MAX_CANDIDATES,
) -> list[CandidateMove]:
    """
    Parse KataGo response into CandidateMove list.

    Args:
        response: KataGo JSON response
        board_size: Board size for coordinate conversion
        max_candidates: Maximum candidates to return

    Returns:
        List of CandidateMove with stable ranks 1..N
    """
    candidates = []
    move_infos = response.get("moveInfos", [])

    # Use enumerate for stable rank assignment (1-indexed)
    # KataGo's moveInfos are already sorted by strength, so position = rank
    rank = 0
    for info in move_infos:
        gtp_move = info.get("move", "")
        col, row = gtp_to_internal(gtp_move, board_size)

        # Skip pass moves (don't display in overlay)
        if col < 0:
            continue

        rank += 1
        candidates.append(CandidateMove(
            col=col,
            row=row,
            rank=rank,  # Stable 1-indexed rank based on position after filtering
            score_lead=round(info.get("scoreLead", 0.0), 2),
            visits=info.get("visits", 0),
        ))

        # Stop after max_candidates valid moves
        if rank >= max_candidates:
            break

    return candidates


# =============================================================================
# KataGo Engine
# =============================================================================

class KataGoEngine(QObject):
    """
    KataGo analysis engine manager using QProcess.

    Signals:
        ready: Emitted when engine is ready to accept queries
        analysis_received(str, list): Emitted with (query_id, candidates)
        error_occurred(str): Emitted on errors
        status_changed(str): Emitted on status changes

    All operations run in the GUI thread using Qt's async I/O.
    """

    ready = Signal()
    analysis_received = Signal(str, list)  # (query_id, list[CandidateMove])
    error_occurred = Signal(str)
    status_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._process: Optional[QProcess] = None
        self._read_buffer: bytes = b""
        self._engine_started: bool = False
        self._engine_ready: bool = False

        # Paths (set via start_engine)
        self._exe_path: str = ""
        self._config_path: str = ""
        self._model_path: str = ""

        # Settings
        self._max_visits: int = DEFAULT_MAX_VISITS
        self._rules: str = DEFAULT_RULES
        self._board_size: int = 19

        # Pending request (if query sent before engine ready)
        self._pending_snapshot: Optional[PositionSnapshot] = None
        self._pending_query_id: Optional[str] = None

    def is_running(self) -> bool:
        """Check if engine process is running."""
        return (
            self._process is not None
            and self._process.state() == QProcess.Running
        )

    def is_ready(self) -> bool:
        """Check if engine is ready to accept queries."""
        return self._engine_ready

    def start_engine(
        self,
        exe_path: str,
        config_path: str,
        model_path: str,
        max_visits: int = DEFAULT_MAX_VISITS,
        rules: str = DEFAULT_RULES,
    ) -> bool:
        """
        Start KataGo analysis engine.

        Args:
            exe_path: Path to katago executable
            config_path: Path to analysis config file
            model_path: Path to neural network model

        Returns:
            True if process started, False on error
        """
        # Validate paths
        if not exe_path or not Path(exe_path).exists():
            self.error_occurred.emit(f"KataGo executable not found: {exe_path}")
            return False
        if not config_path or not Path(config_path).exists():
            self.error_occurred.emit(f"Config file not found: {config_path}")
            return False
        if not model_path or not Path(model_path).exists():
            self.error_occurred.emit(f"Model file not found: {model_path}")
            return False

        # Stop existing process if any
        if self._process is not None:
            self.stop_engine()

        # Store settings
        self._exe_path = exe_path
        self._config_path = config_path
        self._model_path = model_path
        self._max_visits = max_visits
        self._rules = rules

        # Reset state
        self._read_buffer = b""
        self._engine_started = False
        self._engine_ready = False
        self._pending_snapshot = None
        self._pending_query_id = None

        # Create process
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.SeparateChannels)

        # Connect signals
        self._process.started.connect(self._on_started)
        self._process.readyReadStandardOutput.connect(self._on_stdout_ready)
        self._process.readyReadStandardError.connect(self._on_stderr_ready)
        self._process.errorOccurred.connect(self._on_error)
        self._process.finished.connect(self._on_finished)

        # Build command
        args = [
            "analysis",
            "-config", config_path,
            "-model", model_path,
        ]

        self.status_changed.emit("Starting KataGo...")

        # Start process
        self._process.start(exe_path, args)

        return True

    def stop_engine(self):
        """Stop KataGo engine cleanly."""
        self._engine_started = False
        self._engine_ready = False
        self._pending_snapshot = None
        self._pending_query_id = None

        if self._process is None:
            return

        if self._process.state() == QProcess.Running:
            # Try graceful shutdown first
            self._process.closeWriteChannel()
            if not self._process.waitForFinished(1000):
                # Force terminate
                self._process.terminate()
                if not self._process.waitForFinished(1000):
                    # Force kill as last resort
                    self._process.kill()
                    self._process.waitForFinished(500)

        self._process.deleteLater()
        self._process = None
        self._read_buffer = b""

        self.status_changed.emit("KataGo stopped")

    def request_analysis(
        self,
        snapshot: PositionSnapshot,
        query_id: str,
    ):
        """
        Request analysis for a position.

        If engine is not ready yet, stores the request and sends it
        when engine becomes ready.

        Args:
            snapshot: Position to analyze
            query_id: Unique query ID for response matching
        """
        self._board_size = snapshot.board_size

        if not self._engine_ready:
            # Store for later (only keep latest)
            self._pending_snapshot = snapshot
            self._pending_query_id = query_id
            return

        self._send_query(snapshot, query_id)

    def _send_query(self, snapshot: PositionSnapshot, query_id: str):
        """Actually send query to KataGo process."""
        if not self.is_running():
            return

        query = build_query(
            snapshot,
            query_id,
            max_visits=self._max_visits,
            rules=self._rules,
        )

        try:
            query_json = json.dumps(query) + "\n"
            self._process.write(query_json.encode("utf-8"))
        except Exception as e:
            self.error_occurred.emit(f"Failed to send query: {e}")

    # -------------------------------------------------------------------------
    # QProcess Signal Handlers
    # -------------------------------------------------------------------------

    @Slot()
    def _on_started(self):
        """Handle process started signal."""
        self._engine_started = True
        self._engine_ready = True
        self.status_changed.emit("KataGo running")
        self.ready.emit()

        # Send any pending request
        if self._pending_snapshot is not None and self._pending_query_id is not None:
            self._send_query(self._pending_snapshot, self._pending_query_id)
            self._pending_snapshot = None
            self._pending_query_id = None

    @Slot()
    def _on_stdout_ready(self):
        """
        Handle stdout data from KataGo.

        Uses newline-delimited buffering for robust JSON parsing.
        Non-JSON lines are logged but don't cause errors.
        """
        if self._process is None:
            return

        # Append to buffer
        self._read_buffer += self._process.readAllStandardOutput().data()

        # Process complete lines
        while b"\n" in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split(b"\n", 1)
            line = line.strip()

            if not line:
                continue

            # Check if line looks like JSON
            if not line.startswith(b"{"):
                # Non-JSON line (e.g., startup message), ignore silently
                continue

            try:
                response = json.loads(line.decode("utf-8"))
                self._handle_response(response)
            except json.JSONDecodeError as e:
                # Only report error for JSON-looking lines
                self.error_occurred.emit(f"JSON parse error: {e}")
            except UnicodeDecodeError as e:
                self.error_occurred.emit(f"Decode error: {e}")

    def _handle_response(self, response: dict):
        """Process parsed KataGo response."""
        query_id = response.get("id", "")

        # Check for error response
        if "error" in response:
            self.error_occurred.emit(f"KataGo error: {response['error']}")
            return

        # Parse candidates
        candidates = parse_response(
            response,
            board_size=self._board_size,
            max_candidates=MAX_CANDIDATES,
        )

        self.analysis_received.emit(query_id, candidates)

    @Slot()
    def _on_stderr_ready(self):
        """Handle stderr data from KataGo."""
        if self._process is None:
            return

        data = self._process.readAllStandardError().data().decode("utf-8", errors="replace")
        data = data.strip()

        if not data:
            return

        # Check for important error keywords
        data_lower = data.lower()
        if "error" in data_lower or "failed" in data_lower or "exception" in data_lower:
            self.error_occurred.emit(f"KataGo: {data}")

    @Slot(QProcess.ProcessError)
    def _on_error(self, error: QProcess.ProcessError):
        """Handle process error."""
        self._engine_ready = False

        error_messages = {
            QProcess.FailedToStart: f"Failed to start KataGo: {self._exe_path}",
            QProcess.Crashed: "KataGo crashed unexpectedly",
            QProcess.Timedout: "KataGo operation timed out",
            QProcess.WriteError: "Failed to write to KataGo",
            QProcess.ReadError: "Failed to read from KataGo",
            QProcess.UnknownError: "Unknown KataGo error",
        }

        message = error_messages.get(error, f"KataGo error: {error}")
        self.error_occurred.emit(message)
        self.status_changed.emit("KataGo error")

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process finished."""
        self._engine_started = False
        self._engine_ready = False

        if exit_status == QProcess.CrashExit:
            self.error_occurred.emit(f"KataGo crashed with exit code {exit_code}")
        elif exit_code != 0:
            self.error_occurred.emit(f"KataGo exited with code {exit_code}")

        self.status_changed.emit("KataGo stopped")
