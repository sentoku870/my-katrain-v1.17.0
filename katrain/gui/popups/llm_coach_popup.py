"""Phase 225: LLM Coach popup content widget.

Layout (defined in ``katrain/gui/kv/llm_coach_popup.kv``)::

    Karte JSON: [/path/to/karte_xxx.json    ] [参照]
    棋力 (rank): [5k     ]
    [プロンプト生成 & コピー]  [応答をクリア]

    ─── LLM 応答 ───
    ┌─────────────────────────────┐
    │ (paste LLM response here)   │
    │                             │
    └─────────────────────────────┘
    [検証実行]  [検証結果をコピー]

    ─── 検証結果 ───
    ┌─────────────────────────────┐
    │ **Status**: Clean           │
    │ **HIGH**: 0 · ...           │
    └─────────────────────────────┘

Phase 225 deliberately stays manual-paste: the popup never makes network
calls. The user copies the prompt, pastes it into Claude / ChatGPT /
Gemini, then pastes the answer back here for validation. API integration
is Phase 224 (deferred).
"""

from __future__ import annotations

import contextlib
import json
import re
from typing import TYPE_CHECKING, Any

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from katrain.core.coach.popup_logic import (
    MAX_RESPONSE_INPUT_CHARS as _MAX_RESPONSE_INPUT_CHARS,
)
from katrain.core.coach.popup_logic import (
    PERSPECTIVE_AUTO as _PERSPECTIVE_AUTO_INTERNAL,
)
from katrain.core.coach.popup_logic import (
    PERSPECTIVE_BLACK as _PERSPECTIVE_BLACK_INTERNAL,
)
from katrain.core.coach.popup_logic import (
    PERSPECTIVE_WHITE as _PERSPECTIVE_WHITE_INTERNAL,
)
from katrain.core.coach.popup_logic import (
    SUMMARY_BIRDSEYE_SENTINEL as _SUMMARY_BIRDSEYE_SENTINEL,
)
from katrain.core.coach.popup_logic import (
    _summary_index_to_internal,
    cap_response_text,
    count_issue_markers,
    detect_path_type_from_file,
    format_type_label,
    format_validation_status_summary,
    resolve_summary_spinner_values,
    was_truncated,
)
from katrain.core.coach.popup_logic import (
    is_summary_birdseye_value as is_summary_birdseye,
)
from katrain.core.coach.popup_logic import (
    resolve_player_color_internal as _resolve_player_color,
)
from katrain.core.lang import i18n
from katrain.gui.popups._base import I18NPopup
from katrain.gui.theme import Theme
from katrain.gui.widgets.filebrowser import I18NFileBrowser

if TYPE_CHECKING:
    pass


# Phase 243: re-export public module names so that ``from
# katrain.gui.popups.llm_coach_popup import X`` works for tests that
# historically depended on the popup-side constants. The actual
# implementations live in :mod:`katrain.core.coach.popup_logic`; this
# file only re-exports them with their historical names so that
# downstream tests don't have to chase the rename.
#
# Without ``__all__`` here, ruff F401 silently strips the as-imports
# above on every reformat cycle (the names are technically unused
# inside the popup module).
__all__ = [
    "_MAX_RESPONSE_INPUT_CHARS",
    "_PERSPECTIVE_AUTO_INTERNAL",
    "_PERSPECTIVE_BLACK_INTERNAL",
    "_PERSPECTIVE_WHITE_INTERNAL",
    "_SUMMARY_BIRDSEYE_SENTINEL",
    "_resolve_player_color",
    "is_summary_birdseye",
]


# Phase 226-B (B1): cap how many times ``_populate_rank_and_perspective``
# re-schedules itself when the karte path is still empty. Without this
# cap the popup would re-schedule forever (and keep referencing widgets
# of a popup the user has already dismissed).
_MAX_RANK_DETECT_RETRIES = 2
_RETRY_INTERVAL = 0.2

# Phase 242-B: minimum interval between rapid validation requests to
# prevent accidental double-clicks. The button is disabled during this
# window so the user gets visual feedback that the validator is
# running.
_VALIDATE_COOLDOWN_SECS = 0.3


class LLMCoachPopupContent(BoxLayout):
    """Body widget of the LLM Coach popup (Phase 225).

    All widget IDs referenced here (``karte_path_input``, ``rank_input``,
    ``response_input``, ``status_label``, ``result_label``) are bound in
    the matching KV file ``katrain/gui/kv/llm_coach_popup.kv``.

    **Method groups (Phase 272-D):**

    1. **Lifecycle** — ``__init__`` / ``on_kv_post`` / ``cancel_pending_clocks`` /
       ``_schedule_once`` — boot the widget, defer post-KV work, and
       cancel pending Clock events on dismiss.
    2. **Karte path bootstrap** — ``_populate_initial_karte_path`` /
       ``_detect_path_type`` / ``on_path_changed`` / ``_refresh_type_label``
       — wire the Karte path TextInput and detect whether the path points
       to a single-game karte or a multi-game summary.
    3. **Rank & perspective (single-game)** — ``_populate_rank_and_perspective``
       / ``_refresh_rank_hint`` / ``_refresh_perspective_hint`` /
       ``on_perspective_changed`` — fill in the rank / perspective widgets
       for a single karte.
    4. **Summary perspective (multi-game)** — ``_populate_summary_perspective``
       / ``on_summary_perspective_changed`` /
       ``_refresh_summary_perspective_hint`` — fill in the player picker
       for a multi-game summary and toggle the (n局) badge.
    5. **Generate actions** — ``on_browse_karte`` / ``on_generate_and_copy``
       / ``_on_generate_summary`` — open the file browser, build the
       LLM prompt (single-game or summary), copy it to the clipboard.
    6. **Response handling** — ``on_clear_response`` / ``_on_response_text``
       — clear the LLM response TextInput and observe text changes.
    7. **Validate actions** — ``on_validate`` / ``_on_validate_summary``
       / ``on_copy_result`` — run the validator (single-game or
       summary) and copy the resulting Markdown to the clipboard.
    8. **Widget helpers** — ``_get_widget`` / ``_read_text`` /
       ``_set_widget_text`` / ``_set_status`` / ``_set_result`` — small
       accessors for ids-based widget lookups; Phase 225.3 / 225.5
       introduced the ids-based indirection so the popup works even
       when Kivy's ObjectProperty binding lags.
    """

    katrain = ObjectProperty(None, allownone=True)
    popup = ObjectProperty(None, allownone=True)

    karte_path_input = ObjectProperty(None, allownone=True)
    rank_input = ObjectProperty(None, allownone=True)
    rank_auto_label = ObjectProperty(None, allownone=True)
    perspective_select = ObjectProperty(None, allownone=True)
    perspective_auto_label = ObjectProperty(None, allownone=True)
    response_input = ObjectProperty(None, allownone=True)
    status_label = ObjectProperty(None, allownone=True)
    result_label = ObjectProperty(None, allownone=True)
    generate_button = ObjectProperty(None, allownone=True)
    validate_button = ObjectProperty(None, allownone=True)

    status_text = StringProperty("")
    # Phase 225.6 / Phase 226-B (B3): the *internal* perspective value
    # is always one of ``"auto"`` / ``"B"`` / ``"W"`` regardless of the
    # localised spinner text. Previously the code read back the
    # localised spinner ``text`` and matched with ``startswith("黒")``,
    # which broke if the localised label ever changed. The spinner's
    # ``text`` is now treated as display-only.
    perspective_value = StringProperty(_PERSPECTIVE_AUTO_INTERNAL)
    # The detected rank from the Karte/SGF, used to display a small
    # "(auto-detected: ...)" hint next to the manual rank input.
    detected_rank: str | None = None
    detected_player_color: str | None = None

    # Phase 226-B (B1): pending Clock events and retry counter. The
    # popup binds ``on_dismiss`` (via the wrapping I18NPopup) to
    # ``cancel_pending_clocks`` so we stop touching dismissed widgets.
    # These are class-level type hints only — actual mutable state is
    # initialised per-instance in ``__init__`` to avoid sharing across
    # popup instances.
    _pending_clock_events: list[Any]
    _rank_detect_retries: int

    def __init__(self, **kwargs: Any) -> None:
        # Each instance gets its own mutable lists so multiple popups
        # don't share state. These MUST be initialised BEFORE
        # ``super().__init__`` because Kivy's ``Widget.__init__`` calls
        # ``dispatch('on_kv_post', self)`` internally, and ``on_kv_post``
        # immediately calls ``_schedule_once`` which touches
        # ``self._pending_clock_events``. Without this ordering we get
        # ``AttributeError: 'LLMCoachPopupContent' object has no
        # attribute '_pending_clock_events'`` on popup open.
        self._pending_clock_events: list[Any] = []
        self._rank_detect_retries: int = 0
        # Phase 227-D: detected path type. ``"karte"`` / ``"summary"``
        # / ``"unknown"``. Drives the type_label, generate button text
        # and dispatcher in ``on_generate_and_copy``.
        self.path_type: str = "unknown"
        # Phase 243: auxiliary fields captured by ``detect_path_type_from_file``
        # so ``_refresh_type_label`` does not need to re-read the JSON.
        self.path_schema_version: str | None = None
        self.path_games_analyzed: int = 0
        # Phase 227-D: cached list of (name, rank) tuples for the
        # summary perspective selector. Populated from
        # ``detect_player_info_for_summary`` when the path is a summary.
        self.summary_players: list[tuple[str, str | None]] = []
        # Phase 227-D: index of the currently selected player in
        # ``summary_players`` (0 = bird's-eye "全体俯瞰"). Drives the
        # ``player_name`` argument to ``build_summary_llm_prompt``.
        self.summary_perspective_index: int = 0
        # Phase 241-E: user has manually interacted with the summary
        # perspective spinner. When ``True``, the population
        # scheduler in :meth:`on_kv_post` must NOT overwrite the
        # user's selection (a previous version had a race where the
        # 0.4s-delayed auto-populate would clobber a manual change
        # made during the delay window).
        self._summary_perspective_user_set: bool = False
        super().__init__(**kwargs)

    # ---- Lifecycle -----------------------------------------------------

    def on_kv_post(self, *_args: Any) -> None:
        """Auto-fill the karte path once the KV tree is attached.

        Phase 225.7: chain the two populators so rank/perspective
        detection runs AFTER the karte path has been auto-filled. Each
        step uses a slightly later clock tick to guarantee ordering.

        Phase 226-B (B1): every scheduled event is tracked in
        ``_pending_clock_events`` so ``cancel_pending_clocks`` can
        unschedule them when the popup is dismissed.

        Phase 227-D: chain a third pass that runs type detection and
        UI adaptation (type label + button text) once the karte path
        is known.
        """
        self._schedule_once(self._populate_initial_karte_path, 0)
        # Defer the second pass so we read the karte path AFTER it has
        # been written by the first pass. Without this, _read_text
        # could see an empty field on slow hardware.
        self._schedule_once(self._populate_rank_and_perspective, 0.2)
        # Phase 227-D: type detection runs AFTER the path is filled so
        # we know what to render in the type label / button.
        self._schedule_once(self._refresh_type_label, 0.4)

    def cancel_pending_clocks(self, *_args: Any) -> None:
        """Phase 226-B (B1): unschedule any pending Clock events.

        Safe to call multiple times. Should be wired to the wrapping
        popup's ``on_dismiss`` handler so the popup stops touching
        widgets once the user closes it.
        """
        for ev in self._pending_clock_events:
            with contextlib.suppress(Exception):
                Clock.unschedule(ev)
        self._pending_clock_events: list[Any] = []

    def _schedule_once(self, callback: Any, timeout: float) -> Any:
        """Phase 226-B (B1): ``Clock.schedule_once`` with tracking."""
        ev: Any = Clock.schedule_once(callback, timeout)
        self._pending_clock_events.append(ev)
        return ev

    # ---- Karte path bootstrap -----------------------------------------

    def _populate_initial_karte_path(self, *_args: Any) -> None:
        if self.karte_path_input is None:
            return
        if self.karte_path_input.text:
            return  # user typed something already
        try:
            # Phase 227-D: switched from ``find_latest_karte`` (karte-only)
            # to ``find_latest_llm_input_for_ctx`` (karte + summary both)
            # so the popup auto-fills the right file type. Phase 241-G
            # removed the legacy ``find_latest_karte`` helper entirely.
            from katrain.gui.features.llm_coach import find_latest_llm_input_for_ctx

            latest = find_latest_llm_input_for_ctx(self.katrain) if self.katrain is not None else None
        except Exception:
            latest = None
        if latest is not None:
            self.karte_path_input.text = str(latest)

    # ---- Rank & perspective (single-game) ----------------------------

    def _populate_rank_and_perspective(self, *_args: Any) -> None:
        """Phase 225.6/225.7/225.8/226-B + Phase 227-D: detect rank + perspective.

        Dispatches on the detected path type:

        - **karte**: original Phase 225.6 logic. Reads black/white
          player info from ``meta.player_info`` (or SGF fallback),
          resolves the perspective to a ``"B"``/``"W"`` spinner value,
          and surfaces the matched player in the status line.
        - **summary**: Phase 227-D. Reads the player list from
          ``players.<name>`` and populates the perspective selector
          with one entry per player (plus "全体俯瞰" as default).
          Rank is taken from the matched player.

        Detection priority (karte):
        1. Karte JSON's ``meta.player_info`` block (or source SGF)
        2. **Phase 225.8**: mykatrain settings ``default_user_rank``
           when no Karte/SGF info is available
        3. Manual input by the user (always wins)

        Phase 225.7: schedule this AFTER karte path has been written.
        Phase 226-B (B1): retry at most ``_MAX_RANK_DETECT_RETRIES`` times.
        Phase 226-B (B4): ``detect_player_info`` is called once and the
        result is passed to ``detect_player_color_for_user``.
        Phase 227-D: dispatch on path_type and adapt perspective widget.

        Phase 272-E: the 178-line body was split into 6 focused
        helpers (``_schedule_retry_if_under_limit`` /
        ``_read_player_settings`` / ``_dispatch_to_path_handler`` /
        ``_populate_karte_player_info`` /
        ``_apply_karte_rank_fallback`` /
        ``_detect_and_apply_player_color`` /
        ``_update_karte_status_summary``) so each step is
        independently auditable. Behaviour is unchanged.
        """
        karte_path = self._read_text("karte_path_input")
        if not karte_path:
            # Phase 226-B (B1): cap retries so we don't loop forever
            # when the karte path never gets filled in.
            self._schedule_retry_if_under_limit()
            return

        settings = self._read_player_settings()
        if not self._dispatch_to_path_handler(karte_path, settings):
            return  # dispatched to summary or unknown-path guard handled it

        # Karrte path (single-game): rank + color + status update
        self._populate_karte_player_info(karte_path, settings)

    def _schedule_retry_if_under_limit(self) -> None:
        """Phase 272-E: retry the rank/perspective population when the karte path is still empty.

        Capped at ``_MAX_RANK_DETECT_RETRIES`` so a missing path
        (e.g. user hasn't picked a file yet) doesn't loop forever.
        """
        if self._rank_detect_retries < _MAX_RANK_DETECT_RETRIES:
            self._rank_detect_retries += 1
            self._schedule_once(self._populate_rank_and_perspective, _RETRY_INTERVAL)

    def _read_player_settings(self) -> dict[str, str]:
        """Phase 272-E: snapshot the per-user rank settings we need for the rank fallback chain.

        Reads three sources (Phase 229-D 3-tier priority):

        - ``mykatrain_settings.default_user_name`` — for the
          perspective colour match (Phase 225.6).
        - ``mykatrain_settings.default_user_rank`` — last-resort
          rank fallback (Phase 225.8).
        - ``general/player_rank`` — analysis-tab "what the user
          tells the engine to use" setting (Phase 229-D).  This
          sits between Karte/SGF and ``default_user_rank`` in the
          chain.
        """
        if self.katrain is None:
            return {"default_user": "", "default_user_rank": "", "general_player_rank": ""}
        settings = self.katrain.config("mykatrain_settings") or {}
        return {
            "default_user": settings.get("default_user_name", ""),
            "default_user_rank": settings.get("default_user_rank", ""),
            "general_player_rank": self.katrain.config("general/player_rank") or "",
        }

    def _dispatch_to_path_handler(self, karte_path: str, settings: dict[str, str]) -> bool:
        """Phase 272-E: decide whether to handle the path here (karrte) or hand off to a sibling helper.

        Returns ``True`` when the caller should proceed to the
        karrte branch, ``False`` when the path was dispatched to
        ``_populate_summary_perspective`` or rejected as unknown.

        Phase 227-D: ensure the type detection has run before we
        try to dispatch. If the path is unreadable, fall back to
        karrte behaviour.

        Phase 241-B (revised): only re-detect when ``self.path_type``
        is unset. The previous logic always re-detected, which
        overwrote the user's spinner choice in
        ``_populate_summary_perspective`` (Phase 231-E) and also
        forced tests that pre-set ``path_type = "karte"`` to hit the
        unknown-path guard because the test JSONs use minimal stub
        data that doesn't match the strict karte/summary detector.
        ``on_kv_post`` already calls ``_refresh_type_label`` (which
        runs the detector) at 0.4s, so by the time this method runs
        the type is normally already cached. Re-detecting here is
        only needed when the path was set manually (e.g. via the
        ``on_path_changed`` callback that also calls this method).
        """
        if self.path_type == "unknown":
            self._detect_path_type(karte_path)
        if self.path_type == "summary":
            self._populate_summary_perspective(
                karte_path,
                settings["default_user"],
                settings["default_user_rank"],
                general_player_rank=settings["general_player_rank"],
            )
            return False
        # Phase 241-B: when the path is set but the JSON is neither a
        # Karrte nor a Summary (e.g. a hand-written JSON, a JSON the
        # user exported from a different tool, or a malformed file
        # that ``detect_json_type`` couldn't classify), do NOT fall
        # through to the Karrte path. The Karrte ``detect_player_info``
        # call would silently return an empty dict and the user would
        # see a confusing ``auto-detect-failed`` status with no
        # explanation. Instead, surface a clear "unknown path" status
        # and stop here.
        if self.path_type == "unknown":
            self._set_status(
                i18n._("mykatrain:llm-coach:unknown-path").format(path=karte_path),
                error=True,
            )
            return False
        return True

    def _populate_karte_player_info(self, karte_path: str, settings: dict[str, str]) -> None:
        """Phase 272-E: rank + color + status update for a single-game Karrte JSON.

        Default path of ``_populate_rank_and_perspective``.
        """
        try:
            from katrain.gui.features.llm_coach import detect_player_info

            info = detect_player_info(self.katrain, karte_path)
        except Exception as exc:
            self._set_status(
                i18n._("mykatrain:llm-coach:auto-detect-failed").format(error=str(exc)),
                error=True,
            )
            return

        # Phase 229-D: extracted into a pure helper so the priority chain
        # is testable without Kivy.
        self._apply_karte_rank_fallback(
            info,
            general_player_rank=settings["general_player_rank"],
            default_user_rank=settings["default_user_rank"],
        )

        # Phase 226-B (B4 + B5): pass the already-loaded ``info`` into
        # ``detect_player_color_for_user`` so we don't re-read the JSON
        # a second time.
        color = self._detect_and_apply_player_color(karte_path, info)

        # Phase 225.7: surface the resolved default_user in the status
        # line so the user can confirm what name was matched against
        # the Karrte/SGF.
        self._update_karte_status_summary(settings["default_user"], info, color)

    def _apply_karte_rank_fallback(
        self,
        info: dict[str, Any],
        *,
        general_player_rank: str,
        default_user_rank: str,
    ) -> None:
        """Phase 272-E: run the 3-tier rank fallback chain for a Karrte JSON.

        The chain itself is the Kivy-free
        :func:`katrain.core.coach.popup_logic.resolve_rank_fallback_chain`.
        Here we only own the UI side: write back to the rank input
        if the user hasn't typed anything yet, and refresh the hint.
        """
        detected = resolve_rank_fallback_chain(
            info,
            self.perspective_value,
            general_player_rank=general_player_rank,
            default_user_rank=default_user_rank,
        )
        if detected:
            self.detected_rank = detected
            current = self._read_text("rank_input")
            if not current:
                self._set_widget_text("rank_input", detected)
        self._refresh_rank_hint()

    def _detect_and_apply_player_color(self, karte_path: str, info: dict[str, Any]) -> str | None:
        """Phase 272-E: resolve the player colour for a Karrte JSON and update the hint.

        Returns the resolved colour (``"B"``/``"W"``) or ``None`` if
        detection failed. Exceptions are surfaced via
        ``auto-detect-failed`` (Phase 226-B B5: previously the colour
        detector silently swallowed errors).
        """
        from katrain.gui.features.llm_coach import detect_player_color_for_user

        try:
            color, _ = detect_player_color_for_user(self.katrain, karte_path, player_info=info)
        except Exception as exc:
            self._set_status(
                i18n._("mykatrain:llm-coach:auto-detect-failed").format(error=str(exc)),
                error=True,
            )
            color = None
        if color in ("B", "W"):
            self.detected_player_color = color
        self._refresh_perspective_hint()
        return color

    def _update_karte_status_summary(
        self,
        default_user: str,
        info: dict[str, Any],
        color: str | None,
    ) -> None:
        """Phase 272-E: surface the Karrte detection result in the status line.

        Phase 226-B (B2): use i18n keys for the colour label
        instead of hard-coded Japanese strings. Previously the
        English locale still showed "黒 (B)" here.

        Phase 226-I: without ``default_user_name`` the auto
        detector can never pick a side. Surface the reason in
        the status line so the user knows why their perspective
        spinner keeps falling back to "auto (no detection)".
        """
        if not default_user:
            self._set_status(
                i18n._("mykatrain:llm-coach:auto-detect-no-default-user"),
                error=True,
            )
            return
        black_name = (info.get("black") or {}).get("name") or "?"
        white_name = (info.get("white") or {}).get("name") or "?"
        if color == "B":
            color_label = i18n._("mykatrain:llm-coach:perspective-black")
        elif color == "W":
            color_label = i18n._("mykatrain:llm-coach:perspective-white")
        else:
            color_label = "?"
        self._set_status(
            i18n._("mykatrain:llm-coach:auto-detect-summary").format(
                user=default_user,
                black=black_name,
                white=white_name,
                color=color_label,
            )
        )

    def _refresh_rank_hint(self) -> None:
        label = self._get_widget("rank_auto_label")
        if label is None:
            return
        if self.detected_rank:
            label.text = i18n._("mykatrain:llm-coach:rank-auto").format(rank=self.detected_rank)
        else:
            label.text = ""

    def _refresh_perspective_hint(self) -> None:
        label = self._get_widget("perspective_auto_label")
        if label is None:
            return
        detected = self.detected_player_color
        if detected == "B":
            text = i18n._("mykatrain:llm-coach:perspective-auto-detected").format(
                color=i18n._("mykatrain:llm-coach:perspective-black")
            )
        elif detected == "W":
            text = i18n._("mykatrain:llm-coach:perspective-auto-detected").format(
                color=i18n._("mykatrain:llm-coach:perspective-white")
            )
        else:
            text = i18n._("mykatrain:llm-coach:perspective-auto-fallback")
        label.text = text

    def on_perspective_changed(self, *_args: Any) -> None:
        """KV-side callback: spinner selection changed -> re-detect rank.

        Phase 226-B (B3): the spinner's ``text`` is the localised label
        (e.g. ``"黒 (B)"`` / ``"白 (W)"`` / ``"自動"``) and depends on
        the active language. We reverse-map it to the stable internal
        value ``"B"`` / ``"W"`` / ``"auto"`` so the rest of the code
        never has to ``startswith("黒")`` again.

        Phase 227-D: for summary mode, the spinner shows player
        names (or "全体俯瞰"). We don't reverse-map the text — we use
        the spinner's index directly via :meth:`on_summary_perspective_changed`.
        """
        if self.path_type == "summary":
            # The summary selector has its own callback; this branch
            # is a defensive fallback in case Kivy fires on_text
            # before the dedicated handler is wired.
            self.on_summary_perspective_changed()
            return
        # Read the spinner value via ids (defensive against stale ref).
        spinner = self._get_widget("perspective_select")
        if spinner is None:
            return
        raw = getattr(spinner, "text", "") or ""
        self.perspective_value = _spinner_text_to_internal(raw)
        self._populate_rank_and_perspective()

    # ---- Karte path detection ------------------------------------------

    def _detect_path_type(self, path: str) -> str:
        """Detect whether ``path`` is a karte or summary JSON.

        Sets ``self.path_type`` (and ``self.path_schema_version`` /
        ``self.path_games_analyzed``) and returns the same value.
        Errors during detection (file missing, malformed JSON) are
        mapped to ``"unknown"`` so the UI can fall back to karte
        behaviour.

        Phase 243: delegates the JSON parse + ``detect_json_type`` call
        to :func:`katrain.core.coach.popup_logic.detect_path_type_from_file`
        so the logic is Kivy-free and testable in headless CI.
        """
        result = detect_path_type_from_file(path)
        self.path_type = result.path_type
        self.path_schema_version = result.schema_version
        self.path_games_analyzed = result.games_analyzed
        return self.path_type

    def _populate_summary_perspective(
        self,
        summary_path: str,
        default_user: str | None,
        default_user_rank: str | None,
        *,
        general_player_rank: str | None = None,
    ) -> None:
        """Phase 227-D: load summary players and rebuild the perspective spinner.

        Reads the player list from the summary JSON, populates
        ``self.summary_players`` and updates the spinner's
        ``values`` list. The default selection is the matched player
        (default_user → first alphabetical), with index 0 reserved
        for the bird's-eye "全体俯瞰" option.

        Phase 272-E: the 143-line body was split into 6 focused
        helpers (``_detect_summary_player_info`` /
        ``_build_summary_player_pairs`` / ``_update_summary_spinner`` /
        ``_resolve_summary_spinner_index`` /
        ``_update_perspective_value_from_summary_index`` /
        ``_apply_summary_rank_fallback`` / ``_update_summary_status``)
        so each step is independently auditable. Behaviour is
        unchanged.
        """
        info = self._detect_summary_player_info(summary_path, default_user)
        if info is None:
            return  # status already set by helper

        matched = info.get("matched_player", {}) or {}
        matched_name = matched.get("name") if isinstance(matched, dict) else None

        # Phase 243: pure value-list construction delegated to
        # :func:`katrain.core.coach.popup_logic.resolve_summary_spinner_values`
        # so the matched-player-first ordering and the "name (rank)" /
        # "name" label formatting are Kivy-free and testable in
        # headless CI. The popup only keeps the ``default_user_matched``
        # aware index selection below.
        self.summary_players = self._build_summary_player_pairs(info)

        self._update_summary_spinner(info, matched_name)
        self._apply_summary_rank_fallback(info, general_player_rank, default_user_rank)

        # Update the perspective hint to the matched player name
        self._refresh_summary_perspective_hint(matched.get("name"))

        self._update_summary_status(summary_path, info, matched, default_user)

    def _detect_summary_player_info(self, summary_path: str, default_user: str | None) -> dict[str, Any] | None:
        """Phase 272-E: read the summary JSON's player list and matched player.

        Returns the parsed info dict, or ``None`` if the read failed
        (the helper surfaces an ``auto-detect-failed`` status first).
        """
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        try:
            return detect_player_info_for_summary(summary_path, default_user_name=default_user or None)
        except Exception as exc:
            self._set_status(
                i18n._("mykatrain:llm-coach:auto-detect-failed").format(error=str(exc)),
                error=True,
            )
            return None

    def _build_summary_player_pairs(self, info: dict[str, Any]) -> list[tuple[str, str | None]]:
        """Phase 272-E: project the summary's ``all_players`` into ``(name, rank)`` tuples.

        Drops entries without a ``name`` field and normalises the
        name to ``str`` (the SGF BR/WR fallback in
        :func:`detect_player_info_for_summary` may leave ints in
        place of names for some legacy kifu formats).
        """
        players_raw = info.get("all_players", []) or []
        return [(str(p["name"]), p.get("rank")) for p in players_raw if isinstance(p, dict) and p.get("name")]

    def _update_summary_spinner(self, info: dict[str, Any], matched_name: str | None) -> None:
        """Phase 272-E: rebuild the perspective spinner values + default index.

        Layout of ``spinner.values``:
        - index 0          → "全体俯瞰" (bird's-eye)
        - index 1..N       → each player (matched player first so the
                              default selection is the focus player)
        """
        values, _default_idx = resolve_summary_spinner_values(
            self.summary_players,
            matched_player=matched_name,
            birdseye_label=i18n._("mykatrain:llm-coach:summary-perspective-birdseye"),
        )
        spinner = self._get_widget("perspective_select")
        if spinner is None:
            return
        spinner.values = values
        self._resolve_summary_spinner_index(info)
        try:
            spinner.text = values[self.summary_perspective_index]
        except (IndexError, AttributeError):
            spinner.text = values[0]
        self._update_perspective_value_from_summary_index()

    def _resolve_summary_spinner_index(self, info: dict[str, Any]) -> None:
        """Phase 272-E: pick which spinner index to land on.

        Phase 241-E: if the user has already manually picked a
        perspective via the spinner, preserve their choice across
        re-populations. The previous logic always overwrote
        ``summary_perspective_index`` with the auto-detected
        value, which clobbered manual changes that happened
        during the 0.2s/0.4s clock-delayed population window.
        """
        user_preserved = self._summary_perspective_user_set and 0 < self.summary_perspective_index <= len(
            self.summary_players
        )
        if user_preserved:
            # Keep the previously-selected player; only re-resolve
            # the internal value so the rank hint stays accurate.
            return
        # Default selection: matched player at index 1 when
        # present, otherwise bird's-eye (index 0).
        self.summary_perspective_index = 1 if info.get("default_user_matched") and self.summary_players else 0

    def _update_perspective_value_from_summary_index(self) -> None:
        """Phase 272-E: project the spinner index back into ``perspective_value``.

        ``perspective_value`` is a Kivy ``StringProperty`` (no
        ``None`` allowed). Phase 241-D: bird's-eye view carries the
        dedicated sentinel string so downstream consumers can
        distinguish it from out-of-range (which becomes empty string,
        treated as a bug condition by ``_resolve_player_color``).
        """
        internal_value = _summary_index_to_internal(self.summary_perspective_index, self.summary_players)
        if internal_value is None or internal_value == _SUMMARY_BIRDSEYE_SENTINEL:
            self.perspective_value = _PERSPECTIVE_AUTO_INTERNAL  # displayed as "auto"
        else:
            self.perspective_value = internal_value

    def _apply_summary_rank_fallback(
        self,
        info: dict[str, Any],
        general_player_rank: str | None,
        default_user_rank: str | None,
    ) -> None:
        """Phase 272-E: 3-tier priority chain for the rank auto-fill on summary kifu.

        Phase 269 follow-up: via the Kivy-free
        :func:`katrain.core.coach.popup_logic.resolve_summary_rank`
        helper. Previously the Summary path skipped
        ``general/player_rank``, so a 4d user whose Summary JSON's
        matched player carried a "5k" rank (e.g. inferred from a
        SGF BR/WR property) saw the spinner default to 5k instead
        of honouring the analysis-tab setting.
        """
        from katrain.core.coach.popup_logic import resolve_summary_rank

        detected_rank = resolve_summary_rank(
            info,
            general_player_rank=general_player_rank,
            default_user_rank=default_user_rank,
        )
        self.detected_rank = detected_rank
        if detected_rank:
            current = self._read_text("rank_input")
            if not current:
                self._set_widget_text("rank_input", detected_rank)
        self._refresh_rank_hint()

    def _update_summary_status(
        self,
        summary_path: str,
        info: dict[str, Any],
        matched: dict[str, Any],
        default_user: str | None,
    ) -> None:
        """Phase 272-E: surface the summary-detection result in the status line."""
        games = self._read_summary_games_count(summary_path)
        if default_user and matched.get("name"):
            self._set_status(
                i18n._("mykatrain:llm-coach:summary-perspective-summary").format(
                    user=default_user,
                    player=matched.get("name"),
                    games=games,
                )
            )
        else:
            self._set_status(
                i18n._("mykatrain:llm-coach:auto-detect-no-default-user"),
                error=not bool(matched.get("name")),
            )

    def _read_summary_games_count(self, summary_path: str) -> int:
        """Phase 272-E: read ``meta.games_analyzed`` from the summary JSON, tolerating I/O errors."""
        try:
            with open(summary_path, encoding="utf-8") as f:
                data = json.load(f)
            return (data.get("meta") or {}).get("games_analyzed", 0) or 0
        except Exception:  # noqa: BLE001
            return 0

    def on_summary_perspective_changed(self, *_args: Any) -> None:
        """KV-side callback: summary perspective spinner selection changed.

        Maps the spinner's currently-displayed text back to the index
        in ``self.summary_players`` (or 0 for bird's-eye) and stores
        it in ``self.summary_perspective_index``.

        Phase 241-E: set ``_summary_perspective_user_set`` so the
        population scheduler doesn't clobber the user's manual change
        if it fires later (e.g. a re-detection of the path type).
        """
        spinner = self._get_widget("perspective_select")
        if spinner is None:
            return
        values = getattr(spinner, "values", []) or []
        raw = getattr(spinner, "text", "") or ""
        try:
            idx = values.index(raw)
        except ValueError:
            idx = 0
        self.summary_perspective_index = idx
        self._summary_perspective_user_set = True
        internal_value = _summary_index_to_internal(self.summary_perspective_index, self.summary_players)
        # ``perspective_value`` is a StringProperty; bird's-eye maps to
        # the empty string (consumers treat it as "auto"). Phase 241-D:
        # out-of-range also becomes empty so stale spinner state is
        # visible to the downstream _resolve_player_color helper.
        if internal_value is None or internal_value == _SUMMARY_BIRDSEYE_SENTINEL:
            self.perspective_value = _PERSPECTIVE_AUTO_INTERNAL
        else:
            self.perspective_value = internal_value
        # Update the rank hint if the user picks a different player
        if 0 < idx <= len(self.summary_players):
            _, rank = self.summary_players[idx - 1]
            if rank:
                self.detected_rank = rank
                current = self._read_text("rank_input")
                if not current:
                    self._set_widget_text("rank_input", rank)
                self._refresh_rank_hint()

    def _refresh_summary_perspective_hint(self, player_name: str | None) -> None:
        """Phase 227-D: update the small hint under the perspective spinner."""
        label = self._get_widget("perspective_auto_label")
        if label is None:
            return
        if player_name:
            label.text = i18n._("mykatrain:llm-coach:perspective-auto-detected").format(color=player_name)
        else:
            label.text = i18n._("mykatrain:llm-coach:perspective-auto-fallback")

    def _refresh_type_label(self, *_args: Any) -> None:
        """Phase 227-D: update the type label and generate button text.

        Called on every path change. Reads the karte path, runs type
        detection, and updates:

        - ``type_label.text`` (single karte / multi-game summary / unknown
          + schema_version suffix, Phase 242-B)
        - ``generate_button.text`` (changes for summary mode)

        Phase 243: delegates type_label construction to
        :func:`katrain.core.coach.popup_logic.format_type_label` so the
        schema_version suffix + games_analyzed formatting are
        Kivy-free testable helpers. The popup only handles the
        "empty path" / "set button text" branches that are pure
        widget glue.
        """
        karte_path = self._read_text("karte_path_input")
        type_label = self._get_widget("type_label")
        gen_button = self._get_widget("generate_button")
        if not karte_path:
            if type_label is not None:
                type_label.text = ""
            if gen_button is not None:
                gen_button.text = i18n._("mykatrain:llm-coach:build-prompt")
            return
        self._detect_path_type(karte_path)
        if type_label is not None:
            type_label.text = format_type_label(
                self.path_type,
                games_analyzed=self.path_games_analyzed,
                schema_version=self.path_schema_version,
                single_label=i18n._("mykatrain:llm-coach:type-label-single"),
                multi_label=i18n._("mykatrain:llm-coach:type-label-multi"),
                unknown_label=i18n._("mykatrain:llm-coach:type-label-unknown"),
            )
        if gen_button is not None:
            if self.path_type == "summary":
                gen_button.text = i18n._("mykatrain:llm-coach:summary-build-button")
            else:
                gen_button.text = i18n._("mykatrain:llm-coach:build-prompt")

    def on_path_changed(self, *_args: Any) -> None:
        """KV-side callback: user pressed Enter in the path input field.

        Phase 227-D: re-run type detection + rank/perspective
        population. The path may have changed since the initial auto-fill.

        Phase 241-E: reset ``_summary_perspective_user_set`` so a
        different summary file gets fresh auto-population rather
        than preserving the previous file's manual override.
        """
        self._refresh_type_label()
        # Reset the retry counter so we get a fresh chance to populate
        # once a non-empty path is in place.
        self._rank_detect_retries = 0
        # Phase 241-E: a new path means a new player list, so the
        # user's previous spinner choice may not be valid anymore.
        self._summary_perspective_user_set = False
        if self._read_text("karte_path_input"):
            self._populate_rank_and_perspective()

    # ---- User actions (browse / generate / validate) ------------------

    def on_browse_karte(self) -> None:
        """Open an I18NFileBrowser dialog filtered to ``*.json``.

        The selected path is written back to ``karte_path_input``.
        Phase 225.2: bind to ``on_success`` (the OK button event), not
        ``on_submit`` (which only fires on double-click). The user
        reported the OK button did nothing because the double-click
        handler was the only listener attached.

        Phase 225.5: always call ``picker.dismiss()`` on every event
        path so the dialog closes even when the user opens it with no
        selection. The chosen path is written via ``self._set_widget_text``
        (ids-first) to dodge the same stale-reference class of bugs.
        """
        from kivy.metrics import dp

        def _on_pick(instance: Any, *_args: Any) -> None:
            # ``filename`` is set when the user picks via OK; ``selection``
            # is set when the user picks via double-click.
            chosen = (instance.filename or "").strip() or (instance.selection[0] if instance.selection else "")
            if chosen:
                self._set_widget_text("karte_path_input", str(chosen))
            # Always close the picker so the user isn't stuck on it.
            picker.dismiss()

        browser = I18NFileBrowser(
            filters=["*.json", "*.JSON"],
            select_string=i18n._("button:ok"),
        )
        browser.bind(on_success=_on_pick, on_submit=_on_pick)

        picker = I18NPopup(
            title_key="mykatrain:llm-coach:browse-title",
            size=[dp(700), dp(500)],
            content=browser,
        )
        picker.open()

    def on_generate_and_copy(self) -> None:
        """Build the LLM prompt and copy the Markdown to the clipboard.

        Phase 225.3: read the karte path via ``self.ids`` so we always
        touch the actual Kivy widget reference (avoids the rare case
        where a stale ``self.karte_path_input`` reads back empty even
        though the field visibly contains text).

        Phase 225.6: also pass ``player_color`` resolved from the
        perspective spinner + the auto-detected Karte/SGF colour.

        Phase 226-E (E3): ``avg_points_lost`` is intentionally omitted
        from the GUI. The popup relies on the Karte's own
        ``summary.avg_points_lost`` value (read by
        ``core.coach.cli.build_prompt``). The CLI exposes the
        override knob but the GUI does not — adding a numeric input
        was judged outside the Phase 225/226 scope (would require
        validation, error handling, and a new i18n key set).

        Phase 227-D: dispatch on the detected path type. For karte
        the existing flow runs. For summary, the multi-game
        :func:`build_summary_llm_prompt` is invoked with the player
        name resolved from the perspective selector.
        """
        karte_path = self._read_text("karte_path_input")
        rank = self._read_text("rank_input") or None
        if not karte_path:
            self._set_status(i18n._("mykatrain:llm-coach:no-karte"), error=True)
            return

        # Phase 227-D: re-detect type if it has not been set yet
        # (e.g. user typed the path manually without on_text_validate)
        if self.path_type not in ("karte", "summary"):
            self._detect_path_type(karte_path)

        if self.path_type == "summary":
            self._on_generate_summary(karte_path, rank)
            return

        # Phase 241-B: same guard as in ``_populate_rank_and_perspective``.
        # If the JSON is unrecognised, refuse to build a prompt
        # silently — the user needs to know the file is the wrong
        # type. Without this, ``build_llm_prompt`` would crash inside
        # the coach core on an unexpected JSON shape.
        if self.path_type == "unknown":
            self._set_status(
                i18n._("mykatrain:llm-coach:unknown-path").format(path=karte_path),
                error=True,
            )
            return

        # Default: karte path (Phase 225.6)
        from katrain.gui.features.llm_coach import build_llm_prompt

        player_color = _resolve_player_color(self.perspective_value, self.detected_player_color)
        ok, content = build_llm_prompt(
            self.katrain,
            karte_path,
            rank=rank,
            player_color=player_color,
        )
        if not ok:
            self._set_status(content, error=True)
            self._set_result(content)
            return
        try:
            Clipboard.copy(content)
        except Exception as exc:  # noqa: BLE001 — clipboard backend may differ per OS
            self._set_status(
                i18n._("mykatrain:llm-coach:copy-failed").format(error=str(exc)),
                error=True,
            )
            return
        self._set_status(
            i18n._("mykatrain:llm-coach:copy-success").format(chars=len(content)),
        )
        self._set_result(content)

    def _on_generate_summary(self, karte_path: str, rank: str | None) -> None:
        """Phase 227-D: summary-mode handler for the generate button.

        Resolves the player name from the perspective selector and
        delegates to :func:`build_summary_llm_prompt`. The success
        status message includes games/patterns counts so the user
        can confirm the prompt covers the expected scope.
        """
        from katrain.gui.features.llm_coach import build_summary_llm_prompt

        # Resolve player name from spinner index
        player_name: str | None = None
        idx = self.summary_perspective_index
        if 0 < idx <= len(self.summary_players):
            player_name = self.summary_players[idx - 1][0]
        ok, content = build_summary_llm_prompt(
            self.katrain,
            karte_path,
            rank=rank,
            player_name=player_name,
        )
        if not ok:
            self._set_status(content, error=True)
            self._set_result(content)
            return
        try:
            Clipboard.copy(content)
        except Exception as exc:  # noqa: BLE001
            self._set_status(
                i18n._("mykatrain:llm-coach:copy-failed").format(error=str(exc)),
                error=True,
            )
            return
        # Count games/patterns from the rendered prompt so we can show
        # a richer status line. The regex is intentionally lenient —
        # exact numbers are not critical for UX.
        games_match = re.search(r"\*\*(\d+)\s*局\*\*", content)
        games = int(games_match.group(1)) if games_match else 0
        patterns_match = re.search(r"top\s+(\d+)", content)
        patterns = int(patterns_match.group(1)) if patterns_match else 0
        self._set_status(
            i18n._("mykatrain:llm-coach:summary-copy-success").format(
                chars=len(content),
                games=games,
                patterns=patterns,
            )
        )
        self._set_result(content)

    def on_clear_response(self) -> None:
        self._set_widget_text("response_input", "")
        self._set_status(i18n._("mykatrain:llm-coach:response-cleared"))

    def _on_response_text(self, text: str) -> None:
        """Phase 242-B: cap response_input size to prevent UI freeze.

        The KV file binds ``on_text`` of the response_input to this
        method. When the pasted text exceeds ``_MAX_RESPONSE_INPUT_CHARS``
        we truncate and surface a status warning. We don't try to undo
        the paste (Kivy's TextInput is hard to roll back cleanly) —
        instead we just inform the user that the tail was dropped.

        Phase 243: truncation + status message generation delegates to
        :func:`katrain.core.coach.popup_logic.cap_response_text` so
        the cap limit and the warning i18n key live in one place.
        """
        new_text, status = cap_response_text(text)
        if status is None:
            return
        # Replace the field's text via ids to avoid recursion into
        # _on_response_text itself. Kivy's TextInput is text-driven,
        # so the new write triggers on_text again, but with a length
        # below the cap, so we exit cleanly.
        self._set_widget_text("response_input", new_text)
        self._set_status(status, error=True)

    def on_validate(self) -> None:
        """Validate the user-pasted LLM response and show the report.

        Phase 225.5: write the full Markdown report to ``result_label``
        (the ScrollView) AND a one-line summary to ``status_label`` so
        the user immediately sees the issue counts without scrolling.

        Phase 227-D: dispatch on path type. Summary files use
        :func:`validate_summary_llm_response` which checks pattern
        categories, phase labels, and game-ID references instead of
        per-move numbers.

        Phase 242-B: also surface a truncation warning when the
        validator's report was cut off at ``_MAX_REPORT_CHARS`` so
        the user knows the displayed issue counts are incomplete.
        """
        karte_path = self._read_text("karte_path_input")
        rank = self._read_text("rank_input") or None
        response_text = self._read_text("response_input")
        if not karte_path:
            self._set_status(i18n._("mykatrain:llm-coach:no-karte"), error=True)
            return
        if not response_text:
            self._set_status(i18n._("mykatrain:llm-coach:no-response"), error=True)
            return

        if self.path_type not in ("karte", "summary"):
            self._detect_path_type(karte_path)
        if self.path_type == "summary":
            self._on_validate_summary(karte_path, response_text, rank)
            return

        # Phase 241-B: same guard for the validate path. Validation
        # against an unrecognised JSON would run the Karte validator
        # over the wrong data and produce meaningless warnings.
        if self.path_type == "unknown":
            self._set_status(
                i18n._("mykatrain:llm-coach:unknown-path").format(path=karte_path),
                error=True,
            )
            return

        from katrain.gui.features.llm_coach import validate_llm_response

        is_clean, markdown = validate_llm_response(
            self.katrain,
            karte_path,
            response_text,
            rank=rank,
        )
        # Always render the full report into the ScrollView first.
        self._set_result(markdown)

        # Phase 243: count + status formatting delegates to popup_logic
        # so the issue counters and truncation warning logic are
        # Kivy-free and exercised by the popup_logic test suite.
        high, medium, low = count_issue_markers(markdown)
        status = format_validation_status_summary(
            is_clean=is_clean,
            high=high,
            medium=medium,
            low=low,
            truncated=was_truncated(markdown),
        )
        self._set_status(status)

    def _on_validate_summary(self, karte_path: str, response_text: str, rank: str | None) -> None:
        """Phase 227-D: summary-mode validation handler.

        Delegates to :func:`validate_summary_llm_response` and surfaces
        the report Markdown in the result label / status line.

        Phase 242-B: detect truncation via :func:`was_truncated` so the
        user sees a warning when the report exceeds the cap.
        Phase 243: status formatting delegates to popup_logic.
        """
        from katrain.gui.features.llm_coach import validate_summary_llm_response

        # Resolve player name from spinner index (must match the value
        # used in ``_on_generate_summary`` so the validator sees the
        # same prompt config).
        player_name: str | None = None
        idx = self.summary_perspective_index
        if 0 < idx <= len(self.summary_players):
            player_name = self.summary_players[idx - 1][0]
        is_clean, markdown = validate_summary_llm_response(
            self.katrain,
            karte_path,
            response_text,
            rank=rank,
            player_name=player_name,
        )
        self._set_result(markdown)
        high, medium, low = count_issue_markers(markdown)
        status = format_validation_status_summary(
            is_clean=is_clean,
            high=high,
            medium=medium,
            low=low,
            truncated=was_truncated(markdown),
        )
        self._set_status(status)

    def on_copy_result(self) -> None:
        """Copy the validation Markdown to the clipboard.

        Phase 225.5: read via ``self._read_text("result_label")`` so we
        always see the latest text the validator wrote, even if the
        ``self.result_label`` ObjectProperty happens to be a stale
        reference (the case that previously made the button report
        "コピーできる検証結果がありません" right after a successful
        validation).
        """
        result_text = self._read_text("result_label")
        if not result_text:
            self._set_status(i18n._("mykatrain:llm-coach:no-result"), error=True)
            return
        try:
            Clipboard.copy(result_text)
        except Exception as exc:  # noqa: BLE001
            self._set_status(
                i18n._("mykatrain:llm-coach:copy-failed").format(error=str(exc)),
                error=True,
            )
            return
        self._set_status(i18n._("mykatrain:llm-coach:result-copied"))

    # ---- Widget helpers ------------------------------------------------

    def _get_widget(self, widget_id: str) -> Any:
        """Resolve a child widget by KV ``id`` via ``self.ids``.

        Phase 225.5: the ObjectProperty reference (e.g.
        ``self.karte_path_input``) can lag behind the actual KV-bound
        widget when the popup re-creates the tree mid-frame. Going
        through ``self.ids`` always hits the live widget. Returns the
        widget instance, or ``None`` if missing.
        """
        widget = self.ids.get(widget_id) if hasattr(self, "ids") else None
        if widget is None:
            widget = getattr(self, widget_id, None)
        return widget

    def _read_text(self, widget_id: str) -> str:
        """Safely read the stripped ``text`` of a child widget by id."""
        widget = self._get_widget(widget_id)
        if widget is None:
            return ""
        try:
            return str(widget.text or "").strip()
        except AttributeError:
            return ""

    def _set_widget_text(self, widget_id: str, text: str) -> None:
        """Set the ``text`` of a child widget by id."""
        widget = self._get_widget(widget_id)
        if widget is not None:
            widget.text = text

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status_text = text
        # Phase 225.5: ids-first to dodge stale ObjectProperty references
        status_label = self._get_widget("status_label")
        if status_label is not None:
            status_label.text = text
            error_color = (
                getattr(Theme, "ERROR_COLOR", (1.0, 0.3, 0.3, 1.0))
                if error
                else getattr(Theme, "TEXT_COLOR", (0.9, 0.9, 0.9, 1.0))
            )
            status_label.color = error_color

    def _set_result(self, text: str) -> None:
        # Phase 225.5: ids-first so the Markdown actually lands in the
        # ScrollView even when ``self.result_label`` is stale.
        result_label = self._get_widget("result_label")
        if result_label is not None:
            result_label.text = text


def open_llm_coach_popup(ctx: Any) -> Any:
    """Open the LLM Coach popup anchored to the given KaTrainGui context.

    Returns the popup instance so tests can inspect it.

    Phase 226-B (B1): wire ``cancel_pending_clocks`` to ``on_dismiss``
    so any pending Clock events (rank/perspective retry loop) are
    unscheduled when the popup closes. Without this, a slow retry loop
    could keep referencing widgets of a dismissed popup.
    """
    from kivy.metrics import dp

    from katrain.gui.popups._base import clamp_popup_size

    content = LLMCoachPopupContent(katrain=ctx)
    # Phase 225.7: wider popup so the LLM response input doesn't
    # overflow and the action buttons don't overlap.
    # Phase 287-E: clamp to 90% of the current window.
    popup = I18NPopup(
        title_key="mykatrain:llm-coach:title",
        size=clamp_popup_size([dp(900), dp(720)]),
        content=content,
    ).__self__
    content.popup = popup
    # Phase 226-B (B1): clean up pending Clock events on dismiss.
    popup.bind(on_dismiss=content.cancel_pending_clocks)
    popup.open()
    return popup


# --- Helper (kept at module scope so tests can import) -----------------


# Phase 226-B (B3): mapping from the localised spinner label back to the
# stable internal value. We look up the i18n keys at call time so the
# mapping stays correct even if the user switches languages at runtime.
def _spinner_text_to_internal(text: str) -> str:
    """Reverse-map a localised spinner label to ``"auto"``/``"B"``/``"W"``.

    Falls back to ``"auto"`` when the text doesn't match any of the
    three known labels (e.g. on partial matches or future i18n edits).
    """
    if not text:
        return "auto"
    if text == i18n._("mykatrain:llm-coach:perspective-black"):
        return "B"
    if text == i18n._("mykatrain:llm-coach:perspective-white"):
        return "W"
    return "auto"


def _pick_detected_rank(info: dict[str, Any], perspective_value: str) -> str | None:
    """Pick the rank to show for the active perspective (Phase 229-D moved here)."""
    from katrain.gui.features.llm_coach import _pick_detected_rank as _impl

    return _impl(info, perspective_value)


def resolve_rank_fallback_chain(
    info: dict[str, Any] | None,
    perspective_value: str,
    *,
    general_player_rank: str | None = None,
    default_user_rank: str | None = None,
) -> str | None:
    """Re-exported from :func:`katrain.gui.features.llm_coach.resolve_rank_fallback_chain`."""
    from katrain.gui.features.llm_coach import resolve_rank_fallback_chain as _impl

    return _impl(
        info,
        perspective_value,
        general_player_rank=general_player_rank,
        default_user_rank=default_user_rank,
    )
