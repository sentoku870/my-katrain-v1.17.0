"""
KataGo Engine Manager for KaTrain Qt.

Manages KataGo analysis process using QProcess for async I/O.
All operations run in the GUI thread using Qt's event loop.

Key features:
- QProcess-based async communication (no worker threads)
- Newline-delimited JSON buffering for robust parsing
- Query ID management for stale response filtering
- Clean startup/shutdown with proper error handling

Logging:
- Set KATRAIN_QT_LOGLEVEL=DEBUG for verbose output
- Default level is INFO (lifecycle events only)
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import QObject, Signal, Slot, QProcess

from .models import PositionSnapshot, CandidateMove, AnalysisResult, gtp_to_internal

# =============================================================================
# Logging Setup
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

MAX_CANDIDATES = 5
DEFAULT_MAX_VISITS = 1000
DEFAULT_KOMI = 6.5
DEFAULT_RULES = "japanese"
SETTINGS_FILE = "analysis_settings.json"

# Buffer safety limit (5 MB)
MAX_BUFFER_SIZE = 5 * 1024 * 1024


# =============================================================================
# Position Signature (for logging)
# =============================================================================

def position_signature(snapshot: PositionSnapshot) -> str:
    """
    Generate a short deterministic signature for a position.

    Format: "{next_player}|{stone_count}|{first_6_stones_sorted}"
    Example: "B|42|A1B,C3W,D4B,E5W,F6B,G7W"
    """
    stones = snapshot.stones
    stone_count = len(stones)

    # Sort stones by (col, row) and take first 6
    sorted_keys = sorted(stones.keys())[:6]
    stone_list = [f"{chr(65 + c)}{r + 1}{stones[(c, r)]}" for c, r in sorted_keys]

    return f"{snapshot.next_player}|{stone_count}|{','.join(stone_list)}"


# =============================================================================
# Settings Management
# =============================================================================

def get_settings_path() -> Path:
    """Return path to settings file (in katrain_qt directory)."""
    return Path(__file__).parent.parent / SETTINGS_FILE


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
    include_ownership: bool = True,
) -> dict:
    """
    Build KataGo analysis query from position snapshot.

    Uses initialStones approach:
    - All stones sent as initialStones
    - moves[] is empty
    - analyzeTurns = [0]

    This works for both SGF playback and new games.
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
        "includeOwnership": include_ownership,
    }


# =============================================================================
# Response Parser
# =============================================================================

def parse_response(
    response: dict,
    board_size: int = 19,
    max_candidates: int = MAX_CANDIDATES,
) -> List[CandidateMove]:
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

        # Extract PV (principal variation) as list of GTP strings
        pv_raw = info.get("pv", [])
        pv = pv_raw if isinstance(pv_raw, list) else []

        candidates.append(CandidateMove(
            col=col,
            row=row,
            rank=rank,  # Stable 1-indexed rank based on position after filtering
            score_lead=round(info.get("scoreLead", 0.0), 2),
            visits=info.get("visits", 0),
            winrate=round(info.get("winrate", 0.5), 4),
            pv=pv,
        ))

        # Stop after max_candidates valid moves
        if rank >= max_candidates:
            break

    return candidates


def extract_root_score_lead(
    response: dict,
    candidates: Optional[List[CandidateMove]] = None,
) -> Optional[float]:
    """
    Extract root score lead from KataGo response.

    Priority:
    1. response["rootInfo"]["scoreLead"] if present
    2. Fallback to best candidate's scoreLead (rank 1) if provided

    Args:
        response: KataGo JSON response
        candidates: Optional pre-parsed candidates list for fallback

    Returns:
        Score lead as float (to-play perspective), or None if not available
    """
    # Try rootInfo first
    root_info = response.get("rootInfo", {})
    if "scoreLead" in root_info:
        return round(float(root_info["scoreLead"]), 2)

    # Fallback to best candidate
    if candidates and len(candidates) > 0:
        return candidates[0].score_lead

    # Try moveInfos directly if no candidates provided
    move_infos = response.get("moveInfos", [])
    if move_infos and "scoreLead" in move_infos[0]:
        return round(float(move_infos[0]["scoreLead"]), 2)

    return None


def extract_root_winrate(
    response: dict,
    candidates: Optional[List[CandidateMove]] = None,
) -> Optional[float]:
    """
    Extract root winrate from KataGo response.

    Priority:
    1. response["rootInfo"]["winrate"] if present
    2. Fallback to best candidate's winrate (rank 1) if provided

    Args:
        response: KataGo JSON response
        candidates: Optional pre-parsed candidates list for fallback

    Returns:
        Winrate as float (to-play perspective, 0.0-1.0), or None if not available
    """
    # Try rootInfo first
    root_info = response.get("rootInfo", {})
    if "winrate" in root_info:
        return round(float(root_info["winrate"]), 4)

    # Fallback to best candidate
    if candidates and len(candidates) > 0:
        return candidates[0].winrate

    # Try moveInfos directly if no candidates provided
    move_infos = response.get("moveInfos", [])
    if move_infos and "winrate" in move_infos[0]:
        return round(float(move_infos[0]["winrate"]), 4)

    return None


def parse_ownership(
    response: dict,
    board_size: int = 19,
) -> Optional[List[List[float]]]:
    """
    Parse KataGo ownership array into a 2D grid.

    KataGo returns ownership as a flat array of size*size floats,
    ordered from bottom-left to top-right (GTP-style).
    We convert to Qt coordinates where row=0 is the top.

    Args:
        response: KataGo JSON response
        board_size: Board size

    Returns:
        2D list [row][col] where row=0 is top, or None if not available.
        Values range from -1.0 (strong White) to +1.0 (strong Black).
    """
    ownership_flat = response.get("ownership")
    if ownership_flat is None:
        return None

    expected_size = board_size * board_size
    if len(ownership_flat) != expected_size:
        return None

    # KataGo ownership is bottom-to-top, we need top-to-bottom (Qt)
    # ownership_flat[0..size-1] = bottom row (GTP row 1)
    # ownership_flat[(size-1)*size..size*size-1] = top row (GTP row size)
    # For Qt: row 0 = top, row size-1 = bottom
    grid = []
    for qt_row in range(board_size):
        # GTP row = board_size - qt_row (1-indexed), so array index = (board_size - 1 - qt_row) * board_size
        gtp_row_from_bottom = board_size - 1 - qt_row  # 0-indexed from bottom
        start_idx = gtp_row_from_bottom * board_size
        row_data = ownership_flat[start_idx : start_idx + board_size]
        grid.append(row_data)

    return grid


def build_analysis_result(
    query_id: str,
    response: dict,
    next_player: str,
    board_size: int = 19,
    max_candidates: int = MAX_CANDIDATES,
) -> AnalysisResult:
    """
    Build complete AnalysisResult from KataGo response.

    Scores and winrates are normalized to BLACK's perspective:
    - score_lead_black: Positive = Black ahead
    - winrate_black: Black's winning probability

    Args:
        query_id: Query ID for stale filtering
        response: KataGo JSON response
        next_player: "B" or "W" - who was to play
        board_size: Board size for coordinate conversion
        max_candidates: Maximum candidates to include

    Returns:
        AnalysisResult with normalized values
    """
    # Parse candidates
    candidates = parse_response(response, board_size, max_candidates)

    # Extract root values (to-play perspective)
    score_lead_to_play = extract_root_score_lead(response, candidates)
    winrate_to_play = extract_root_winrate(response, candidates)

    # Normalize to Black's perspective
    if score_lead_to_play is not None:
        score_lead_black = score_lead_to_play if next_player == "B" else -score_lead_to_play
    else:
        score_lead_black = None

    if winrate_to_play is not None:
        winrate_black = winrate_to_play if next_player == "B" else (1.0 - winrate_to_play)
    else:
        winrate_black = None

    # Get root visits
    root_info = response.get("rootInfo", {})
    root_visits = root_info.get("visits", 0)

    # Parse ownership grid
    ownership = parse_ownership(response, board_size)

    return AnalysisResult(
        query_id=query_id,
        candidates=candidates,
        score_lead_black=round(score_lead_black, 2) if score_lead_black is not None else None,
        winrate_black=round(winrate_black, 4) if winrate_black is not None else None,
        next_player=next_player,
        root_visits=root_visits,
        ownership=ownership,
    )


# =============================================================================
# KataGo Engine
# =============================================================================

class KataGoEngine(QObject):
    """
    KataGo analysis engine manager using QProcess.

    Signals:
        ready: Emitted when engine is ready to accept queries
        analysis_received(AnalysisResult): Emitted with complete analysis result
        error_occurred(str): Emitted on errors
        status_changed(str): Emitted on status changes

    All operations run in the GUI thread using Qt's async I/O.
    """

    ready = Signal()
    analysis_received = Signal(object)  # AnalysisResult
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

        # Track current query's next_player for response normalization
        self._current_next_player: str = "B"

        # Logging stats
        self._non_json_lines_ignored: int = 0

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
            max_visits: Maximum visits per query
            rules: Game rules (japanese, chinese, etc.)

        Returns:
            True if process started, False on error
        """
        # Log engine start attempt
        logger.info(
            "engine_start: exe=%s, config=%s, model=%s, visits=%d",
            Path(exe_path).name if exe_path else "(none)",
            Path(config_path).name if config_path else "(none)",
            Path(model_path).name if model_path else "(none)",
            max_visits,
        )

        # Validate paths
        if not exe_path or not Path(exe_path).exists():
            logger.error("engine_start_failed: exe not found: %s", exe_path)
            self.error_occurred.emit(f"KataGo executable not found: {exe_path}")
            return False
        if not config_path or not Path(config_path).exists():
            logger.error("engine_start_failed: config not found: %s", config_path)
            self.error_occurred.emit(f"Config file not found: {config_path}")
            return False
        if not model_path or not Path(model_path).exists():
            logger.error("engine_start_failed: model not found: %s", model_path)
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
        self._non_json_lines_ignored = 0

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
        """Stop KataGo engine cleanly using 3-stage shutdown."""
        logger.info("engine_stop: initiating shutdown")

        self._engine_started = False
        self._engine_ready = False
        self._pending_snapshot = None
        self._pending_query_id = None

        if self._process is None:
            logger.debug("engine_stop: no process to stop")
            return

        if self._process.state() == QProcess.Running:
            # Stage 1: Graceful shutdown (close stdin)
            logger.debug("engine_stop: stage1 - closeWriteChannel")
            self._process.closeWriteChannel()
            if not self._process.waitForFinished(1000):
                # Stage 2: Terminate (SIGTERM)
                logger.debug("engine_stop: stage2 - terminate")
                self._process.terminate()
                if not self._process.waitForFinished(1000):
                    # Stage 3: Kill (SIGKILL)
                    logger.warning("engine_stop: stage3 - kill (forced)")
                    self._process.kill()
                    self._process.waitForFinished(500)

        self._process.deleteLater()
        self._process = None
        self._read_buffer = b""

        logger.info("engine_stop: shutdown complete")
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
        self._current_next_player = snapshot.next_player

        if not self._engine_ready:
            # Store for later (only keep latest)
            logger.debug("query_pending: id=%s (engine not ready)", query_id)
            self._pending_snapshot = snapshot
            self._pending_query_id = query_id
            return

        self._send_query(snapshot, query_id)

    def _send_query(self, snapshot: PositionSnapshot, query_id: str):
        """Actually send query to KataGo process."""
        if not self.is_running():
            logger.warning("query_dropped: id=%s (engine not running)", query_id)
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
            logger.debug(
                "query_sent: id=%s, sig=%s",
                query_id,
                position_signature(snapshot),
            )
        except Exception as e:
            logger.error("query_send_failed: id=%s, error=%s", query_id, e)
            self.error_occurred.emit(f"Failed to send query: {e}")

    # -------------------------------------------------------------------------
    # QProcess Signal Handlers
    # -------------------------------------------------------------------------

    @Slot()
    def _on_started(self):
        """Handle process started signal."""
        self._engine_started = True
        self._engine_ready = True
        logger.info("engine_ready: KataGo process started and ready")
        self.status_changed.emit("KataGo running")
        self.ready.emit()

        # Send any pending request
        if self._pending_snapshot is not None and self._pending_query_id is not None:
            logger.debug("query_pending_flush: id=%s", self._pending_query_id)
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
        new_data = self._process.readAllStandardOutput().data()
        self._read_buffer += new_data

        # Safety check: prevent runaway buffer growth
        if len(self._read_buffer) > MAX_BUFFER_SIZE:
            logger.warning(
                "buffer_overflow: size=%d bytes, truncating",
                len(self._read_buffer),
            )
            # Keep only the last portion that might contain valid data
            self._read_buffer = self._read_buffer[-MAX_BUFFER_SIZE // 2:]

        # Process complete lines
        while b"\n" in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split(b"\n", 1)
            line = line.strip()

            if not line:
                continue

            # Check if line looks like JSON
            if not line.startswith(b"{"):
                # Non-JSON line (e.g., startup message), ignore silently
                self._non_json_lines_ignored += 1
                logger.debug("non_json_line_ignored: %s", line[:50])
                continue

            try:
                response = json.loads(line.decode("utf-8"))
                self._handle_response(response)
            except json.JSONDecodeError as e:
                # Only report error for JSON-looking lines
                logger.error("parse_error: JSON decode failed: %s", e)
                self.error_occurred.emit(f"JSON parse error: {e}")
            except UnicodeDecodeError as e:
                logger.error("parse_error: Unicode decode failed: %s", e)
                self.error_occurred.emit(f"Decode error: {e}")

    def _handle_response(self, response: dict):
        """Process parsed KataGo response."""
        query_id = response.get("id", "")

        # Check for error response
        if "error" in response:
            logger.error("katago_error: id=%s, error=%s", query_id, response['error'])
            self.error_occurred.emit(f"KataGo error: {response['error']}")
            return

        # Build complete analysis result with normalized scores
        result = build_analysis_result(
            query_id=query_id,
            response=response,
            next_player=self._current_next_player,
            board_size=self._board_size,
            max_candidates=MAX_CANDIDATES,
        )

        logger.debug(
            "response_received: id=%s, candidates=%d, score_lead_black=%s, winrate_black=%s",
            query_id,
            len(result.candidates),
            result.score_lead_black,
            result.winrate_black,
        )
        self.analysis_received.emit(result)

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
            logger.error("engine_stderr: %s", data[:200])
            self.error_occurred.emit(f"KataGo: {data}")
        else:
            logger.debug("engine_stderr: %s", data[:100])

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
        logger.error("engine_error: %s", message)
        self.error_occurred.emit(message)
        self.status_changed.emit("KataGo error")

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process finished."""
        self._engine_started = False
        self._engine_ready = False

        if exit_status == QProcess.CrashExit:
            logger.error("engine_crashed: exit_code=%d", exit_code)
            self.error_occurred.emit(f"KataGo crashed with exit code {exit_code}")
        elif exit_code != 0:
            logger.warning("engine_exited: exit_code=%d", exit_code)
            self.error_occurred.emit(f"KataGo exited with code {exit_code}")
        else:
            logger.info("engine_finished: clean exit")

        # Log stats
        if self._non_json_lines_ignored > 0:
            logger.debug("session_stats: non_json_lines_ignored=%d", self._non_json_lines_ignored)

        self.status_changed.emit("KataGo stopped")
