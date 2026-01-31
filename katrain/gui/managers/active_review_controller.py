"""Active Review Controller (Phase 97).

Manages Active Review mode lifecycle and user interaction.
Extracted from KaTrainGui for improved testability.
"""

from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple

if TYPE_CHECKING:
    from katrain.core.game import Game
    from katrain.core.study.active_review import GuessEvaluation
    from katrain.core.study.review_session import ReviewSession, SessionSummary
    from katrain.gui.controlspanel import ControlsPanel
    from katrain.gui.features.context import FeatureContext


# Type aliases for UI callbacks (must match real function signatures)
# Signature mismatch will raise TypeError at runtime
ShowFeedbackFn = Callable[
    [
        Any,  # katrain: KaTrainGui instance (via get_ctx)
        "GuessEvaluation",
        bool,  # allow_retry
        Optional[Callable[[], None]],  # on_retry
        Optional[Callable[[], Optional[str]]],  # on_hint_request
    ],
    None,
]
ShowSummaryFn = Callable[[Any, "SessionSummary"], None]  # (katrain, summary)


class ActiveReviewController:
    """Active Review mode controller (Phase 97).

    Responsibilities:
    - Session lifecycle management (_session)
    - User guess evaluation (handle_guess)
    - Summary display coordination (_end_review)

    Design:
    - Import/instantiation: Kivy-free (unit testable)
    - UI callbacks injected for testability (show_feedback_fn, show_summary_fn)
    - Dependency injection pattern (like SummaryManager)

    Lifecycle invariant (weak form):
    - mode=False => session=None
    - session!=None => mode=True
    - mode=True may have session=None temporarily until on_mode_change(True) is called

    get_ctx contract:
    - Must return KaTrainGui instance (self), as UI callbacks expect KaTrainGui
    """

    def __init__(
        self,
        get_ctx: Callable[[], "FeatureContext"],
        get_config: Callable[..., Any],  # config(setting, default=None)
        get_game: Callable[[], Optional["Game"]],
        get_controls: Callable[[], Optional["ControlsPanel"]],
        get_mode: Callable[[], bool],
        set_mode: Callable[[bool], None],
        logger: Callable[..., None],  # log(message, level=OUTPUT_INFO)
        show_feedback_fn: Optional[ShowFeedbackFn] = None,
        show_summary_fn: Optional[ShowSummaryFn] = None,
    ) -> None:
        """Initialize with dependency injection.

        Args:
            get_ctx: Returns KaTrainGui instance (required for UI callbacks)
            get_config: config(setting, default=None) accessor
            get_game: Returns current Game or None
            get_controls: Returns ControlsPanel or None
            get_mode: Returns active_review_mode value
            set_mode: Sets active_review_mode value
            logger: log(message, level) function
            show_feedback_fn: UI callback for guess feedback (default: lazy import)
            show_summary_fn: UI callback for session summary (default: lazy import)
        """
        self._get_ctx = get_ctx
        self._get_config = get_config
        self._get_game = get_game
        self._get_controls = get_controls
        self._get_mode = get_mode
        self._set_mode = set_mode
        self._logger = logger

        # UI callbacks (injected or default via lazy import)
        self._show_feedback_fn = show_feedback_fn
        self._show_summary_fn = show_summary_fn

        self._session: Optional["ReviewSession"] = None

    def _get_show_feedback(self) -> ShowFeedbackFn:
        """Get feedback UI function (lazy import if not injected)."""
        if self._show_feedback_fn is not None:
            return self._show_feedback_fn
        from katrain.gui.features.active_review_ui import show_guess_feedback

        return show_guess_feedback

    def _get_show_summary(self) -> ShowSummaryFn:
        """Get summary UI function (lazy import if not injected)."""
        if self._show_summary_fn is not None:
            return self._show_summary_fn
        from katrain.gui.features.active_review_summary import show_session_summary

        return show_session_summary

    @property
    def session(self) -> Optional["ReviewSession"]:
        """Current review session (read-only).

        Returns:
            ReviewSession if Active Review is active, None otherwise.

        Note:
            Callers should not modify the returned session directly.
            Use controller methods (toggle, handle_guess, etc.) instead.
        """
        return self._session

    def is_fog_active(self) -> bool:
        """Check if Fog of War is active (hides AI hints).

        Returns:
            True if Active Review mode is ON, False otherwise.
        """
        return self._get_mode()

    def disable_if_needed(self) -> None:
        """Disable Active Review mode if currently active.

        Called when switching to PLAY mode, loading SGF, or starting Quiz.
        Does not show summary popup.

        Parity: Equivalent to old _disable_active_review_if_needed().
        """
        self._end_review(show_summary=False)

    def toggle(self) -> None:
        """Toggle Active Review mode.

        ON -> OFF: Shows summary popup if session has results.
        OFF -> ON: Sets mode property (Kivy observer creates session via on_mode_change).
        """
        if self._get_mode():
            self._end_review(show_summary=True)
        else:
            self._set_mode(True)  # Kivy observer will call on_mode_change(True)

    def on_mode_change(self, value: bool) -> None:
        """Handle active_review_mode property changes.

        Called by KaTrainGui's Kivy property observer.

        IMPORTANT:
        - Does NOT call _end_review() to avoid recursion.
        - ON (value=True): Creates new session only if _session is None (idempotent)
        - OFF (value=False): Clears session only (no summary)

        Args:
            value: New mode value (True=ON, False=OFF)
        """
        from katrain.core.study.review_session import ReviewSession

        if value:  # ON
            # Idempotent: only create session if not already exists
            if self._session is None:
                skill_preset = self._get_config("general/skill_preset", "standard") or "standard"
                self._session = ReviewSession(skill_preset)
        else:  # OFF
            # Clear session only - do NOT call _end_review() (recursion risk)
            self._session = None

    def handle_guess(self, coords: Tuple[int, int]) -> None:
        """Handle user's guess in Active Review mode.

        Args:
            coords: Board coordinates (col, row) tuple

        Behavior:
        - Checks if node is ready for review
        - Evaluates guess against AI candidates
        - Records result to session
        - Shows feedback popup (retry/hint for bad grades)

        Note:
            Uses private access to ReviewSession._pending_move_number
            for compatibility with existing behavior.
        """
        from katrain.core.constants import STATUS_INFO
        from katrain.core.lang import i18n
        from katrain.core.study.active_review import (
            ActiveReviewer,
            GuessGrade,
            get_hint_for_best_move,
            is_review_ready,
        )

        game = self._get_game()
        if not game:
            return

        node = game.current_node

        # Node change detection: abort pending if move_number differs
        # NOTE: _pending_move_number is private - maintained for compatibility
        if self._session and self._session.has_pending:
            pending_move = self._session._pending_move_number
            if node.move_number != pending_move:
                self._session.abort_pending()

        # Check if node is ready for review
        ready_result = is_review_ready(node)
        if not ready_result.ready:
            if ready_result.message_key:
                msg = i18n._(ready_result.message_key)
                if ready_result.visits > 0:
                    msg = msg.format(visits=ready_result.visits)
                controls = self._get_controls()
                if controls:
                    controls.set_status(msg, STATUS_INFO)
            return

        # Session tracking: begin new position if not in retry
        is_retry = self._session and self._session.has_pending
        if self._session and not is_retry:
            self._session.begin_position(node.move_number)

        # Evaluate the guess
        skill_preset = self._get_config("general/skill_preset", "standard") or "standard"
        reviewer = ActiveReviewer(skill_preset)
        evaluation = reviewer.evaluate_guess(coords, node)

        # Determine if retry is allowed
        bad_grades = (GuessGrade.BLUNDER, GuessGrade.SLACK, GuessGrade.NOT_IN_CANDIDATES)
        allow_retry = not is_retry and evaluation.grade in bad_grades

        # Define callbacks for retry/hint
        def on_retry() -> None:
            if self._session:
                self._session.mark_retry()

        def on_hint_request() -> Optional[str]:
            if self._session:
                self._session.mark_hint_used()
            lang = self._get_config("general/lang", "en") or "en"
            return get_hint_for_best_move(node, lang)

        # Record final guess if not allowing retry
        if not allow_retry:
            if self._session:
                self._session.record_final_guess(evaluation)

        # Show feedback popup via injected/default callback
        show_feedback = self._get_show_feedback()
        show_feedback(
            self._get_ctx(),
            evaluation,
            allow_retry,
            on_retry if allow_retry else None,
            on_hint_request if allow_retry else None,
        )

    def _end_review(self, show_summary: bool) -> None:
        """End Active Review mode (internal).

        Args:
            show_summary: True to display summary popup

        Note:
            All intentional Active Review terminations (toggle OFF, disable)
            go through this method. This method calls set_mode(False), which
            triggers on_mode_change(False) to clear the session (redundantly but safely).

        Parity with old _end_active_review():
        - Early return if mode is OFF: check
        - Summary display condition: check
        - Session clear: check
        - Mode OFF: check
        """
        if not self._get_mode():
            return

        # Show summary (conditional) - uses public API: session.results, session.get_summary()
        if show_summary and self._session and self._session.results:
            summary = self._session.get_summary()
            show_summary_fn = self._get_show_summary()
            show_summary_fn(self._get_ctx(), summary)

        # Clear session and turn off mode
        self._session = None
        self._set_mode(False)
