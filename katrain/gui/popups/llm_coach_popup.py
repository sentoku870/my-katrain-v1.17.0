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
from typing import TYPE_CHECKING, Any

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from katrain.core.lang import i18n
from katrain.gui.popups._base import I18NPopup
from katrain.gui.theme import Theme
from katrain.gui.widgets.filebrowser import I18NFileBrowser

if TYPE_CHECKING:
    pass


# Phase 226-B (B1): cap how many times ``_populate_rank_and_perspective``
# re-schedules itself when the karte path is still empty. Without this
# cap the popup would re-schedule forever (and keep referencing widgets
# of a popup the user has already dismissed).
_MAX_RANK_DETECT_RETRIES = 5
_RETRY_INTERVAL = 0.2


class LLMCoachPopupContent(BoxLayout):
    """Body widget of the LLM Coach popup (Phase 225).

    All widget IDs referenced here (``karte_path_input``, ``rank_input``,
    ``response_input``, ``status_label``, ``result_label``) are bound in
    the matching KV file ``katrain/gui/kv/llm_coach_popup.kv``.
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
    perspective_value = StringProperty("auto")
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
        """
        karte_path = self._read_text("karte_path_input")
        if not karte_path:
            # Phase 226-B (B1): cap retries so we don't loop forever
            # when the karte path never gets filled in.
            if self._rank_detect_retries < _MAX_RANK_DETECT_RETRIES:
                self._rank_detect_retries += 1
                self._schedule_once(self._populate_rank_and_perspective, _RETRY_INTERVAL)
            return

        # Default user lookup (so we can debug why it picked a side).
        default_user = None
        default_user_rank = None
        player_rank_setting = None
        if self.katrain is not None:
            settings = self.katrain.config("mykatrain_settings") or {}
            default_user = settings.get("default_user_name", "")
            # Phase 225.8: default_user_rank fallback
            default_user_rank = settings.get("default_user_rank", "")
            # Phase 229-D: also consult the global ``general/player_rank``
            # setting added by the analysis-tab unification.  It sits
            # between Karte/SGF and ``default_user_rank`` in the
            # priority chain (general settings express "what the user
            # tells the engine to use" while ``default_user_rank`` is
            # a per-user fallback kept for backward compatibility).
            player_rank_setting = self.katrain.config("general/player_rank") or ""

        # Phase 227-D: ensure the type detection has run before we
        # try to dispatch. If the path is unreadable, fall back to
        # karte behaviour.
        #
        # Phase 241-B (revised): only re-detect when ``self.path_type``
        # is unset. The previous logic always re-detected, which
        # overwrote the user's spinner choice in
        # ``_populate_summary_perspective`` (Phase 231-E) and also
        # forced tests that pre-set ``path_type = "karte"`` to hit the
        # unknown-path guard because the test JSONs use minimal stub
        # data that doesn't match the strict karte/summary detector.
        # ``on_kv_post`` already calls ``_refresh_type_label`` (which
        # runs the detector) at 0.4s, so by the time this method runs
        # the type is normally already cached. Re-detecting here is
        # only needed when the path was set manually (e.g. via the
        # ``on_path_changed`` callback that also calls this method).
        if self.path_type == "unknown":
            self._detect_path_type(karte_path)
        if self.path_type == "summary":
            self._populate_summary_perspective(karte_path, default_user, default_user_rank)
            return

        # Phase 241-B: when the path is set but the JSON is neither a
        # Karte nor a Summary (e.g. a hand-written JSON, a JSON the
        # user exported from a different tool, or a malformed file
        # that ``detect_json_type`` couldn't classify), do NOT fall
        # through to the Karte path. The Karte ``detect_player_info``
        # call would silently return an empty dict and the user would
        # see a confusing ``auto-detect-failed`` status with no
        # explanation. Instead, surface a clear "unknown path" status
        # and stop here.
        if self.path_type == "unknown":
            self._set_status(
                i18n._("mykatrain:llm-coach:unknown-path").format(path=karte_path),
                error=True,
            )
            return

        # Default path: karte
        try:
            from katrain.gui.features.llm_coach import (
                detect_player_color_for_user,
                detect_player_info,
            )

            info = detect_player_info(self.katrain, karte_path)
        except Exception as exc:
            self._set_status(
                i18n._("mykatrain:llm-coach:auto-detect-failed").format(error=str(exc)),
                error=True,
            )
            return

        # ---- Rank auto-fill ----
        # Phase 229-D: extracted into a pure helper so the priority chain
        # is testable without Kivy.
        detected = resolve_rank_fallback_chain(
            info,
            self.perspective_value,
            general_player_rank=player_rank_setting,
            default_user_rank=default_user_rank,
        )
        if detected:
            self.detected_rank = detected
            current = self._read_text("rank_input")
            if not current:
                self._set_widget_text("rank_input", detected)
            self._refresh_rank_hint()
        else:
            self._refresh_rank_hint()

        # ---- Player color auto-fill ----
        # Phase 226-B (B4 + B5): pass the already-loaded ``info`` into
        # ``detect_player_color_for_user`` so we don't re-read the JSON
        # a second time. Surface any exception via the same
        # ``auto-detect-failed`` status as the info loader (previously
        # the colour detector silently swallowed errors).
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

        # Phase 225.7: surface the resolved default_user in the status
        # line so the user can confirm what name was matched against
        # the Karte/SGF.
        if default_user:
            black_name = (info.get("black") or {}).get("name") or "?"
            white_name = (info.get("white") or {}).get("name") or "?"
            # Phase 226-B (B2): use i18n keys for the colour label
            # instead of hard-coded Japanese strings. Previously the
            # English locale still showed "黒 (B)" here.
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
        else:
            # Phase 226-I: without ``default_user_name`` the auto
            # detector can never pick a side. Surface the reason in
            # the status line so the user knows why their perspective
            # spinner keeps falling back to "auto (no detection)".
            self._set_status(
                i18n._("mykatrain:llm-coach:auto-detect-no-default-user"),
                error=True,
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

    # ---- Phase 227-D: Summary mode helpers -----------------------------

    def _detect_path_type(self, path: str) -> str:
        """Detect whether ``path`` is a karte or summary JSON.

        Sets ``self.path_type`` and returns the same value. Errors
        during detection (file missing, malformed JSON) are mapped to
        ``"unknown"`` so the UI can fall back to karte behaviour.
        """
        from katrain.core.coach import detect_json_type

        if not path:
            self.path_type = "unknown"
            return self.path_type
        try:
            import json

            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                self.path_type = "unknown"
                return self.path_type
            self.path_type = detect_json_type(data)
        except (OSError, ValueError):
            self.path_type = "unknown"
        except Exception:  # noqa: BLE001 — defensive
            self.path_type = "unknown"
        return self.path_type

    def _populate_summary_perspective(
        self,
        summary_path: str,
        default_user: str | None,
        default_user_rank: str | None,
    ) -> None:
        """Phase 227-D: load summary players and rebuild the perspective spinner.

        Reads the player list from the summary JSON, populates
        ``self.summary_players`` and updates the spinner's
        ``values`` list. The default selection is the matched player
        (default_user → first alphabetical), with index 0 reserved
        for the bird's-eye "全体俯瞰" option.
        """
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        try:
            info = detect_player_info_for_summary(summary_path, default_user_name=default_user or None)
        except Exception as exc:
            self._set_status(
                i18n._("mykatrain:llm-coach:auto-detect-failed").format(error=str(exc)),
                error=True,
            )
            return

        # Build the perspective selector values:
        #   index 0          → "全体俯瞰" (bird's-eye)
        #   index 1..N       → each player (name + optional rank), with the
        #                       matched player placed first so the spinner
        #                       defaults to the focus player at index 1.
        players = info.get("all_players", []) or []
        matched = info.get("matched_player", {}) or {}
        matched_name = matched.get("name") if isinstance(matched, dict) else None
        if matched_name:
            ordered = [matched_name] + [p["name"] for p in players if p.get("name") and p["name"] != matched_name]
        else:
            ordered = [p["name"] for p in players]
        ordered = [name for name in ordered if name]
        rank_lookup = {p["name"]: p.get("rank") for p in players if isinstance(p, dict) and p.get("name")}
        self.summary_players = [(name, rank_lookup.get(name)) for name in ordered]
        birdseye = i18n._("mykatrain:llm-coach:summary-perspective-birdseye")
        values: list[str] = [birdseye]
        for name, rank in self.summary_players:
            label = f"{name} ({rank})" if rank else name
            values.append(label)

        spinner = self._get_widget("perspective_select")
        if spinner is not None:
            # Phase 241-E: if the user has already manually picked a
            # perspective via the spinner, preserve their choice across
            # re-populations. The previous logic always overwrote
            # ``summary_perspective_index`` with the auto-detected
            # value, which clobbered manual changes that happened
            # during the 0.2s/0.4s clock-delayed population window.
            user_preserved = self._summary_perspective_user_set and 0 < self.summary_perspective_index <= len(
                self.summary_players
            )
            spinner.values = values
            if user_preserved:
                # Keep the previously-selected player; only re-resolve
                # the internal value so the rank hint stays accurate.
                idx = self.summary_perspective_index
            else:
                # Default selection: matched player at index 1 when
                # present, otherwise bird's-eye (index 0).
                idx = 1 if info.get("default_user_matched") and self.summary_players else 0
                self.summary_perspective_index = idx
            try:
                spinner.text = values[self.summary_perspective_index]
            except (IndexError, AttributeError):
                spinner.text = values[0]
            internal_value = _summary_index_to_internal(self.summary_perspective_index, self.summary_players)
            # ``perspective_value`` is a StringProperty (no None allowed).
            # Phase 241-D: bird's-eye view carries the dedicated sentinel
            # string so downstream consumers can distinguish it from
            # out-of-range (which becomes empty string, treated as a
            # bug condition by ``_resolve_player_color``).
            if internal_value is None:
                self.perspective_value = ""
            elif internal_value == _SUMMARY_BIRDSEYE_SENTINEL:
                self.perspective_value = ""  # displayed as "auto"
            else:
                self.perspective_value = internal_value

        # ---- Rank auto-fill from matched player ----
        matched = info.get("matched_player", {}) or {}
        detected_rank = matched.get("rank")
        if not detected_rank and default_user_rank:
            detected_rank = default_user_rank
        if detected_rank:
            self.detected_rank = detected_rank
            current = self._read_text("rank_input")
            if not current:
                self._set_widget_text("rank_input", detected_rank)
            self._refresh_rank_hint()
        else:
            self.detected_rank = None
            self._refresh_rank_hint()

        # Update the perspective hint to the matched player name
        self._refresh_summary_perspective_hint(matched.get("name"))

        # Update the status line for summary
        games = 0
        try:
            import json

            with open(summary_path, encoding="utf-8") as f:
                data = json.load(f)
            games = (data.get("meta") or {}).get("games_analyzed", 0) or 0
        except Exception:  # noqa: BLE001
            pass
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
            self.perspective_value = ""
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

        - ``type_label.text`` (single karte / multi-game summary / unknown)
        - ``generate_button.text`` (changes for summary mode)

        Does NOT re-populate the rank/perspective selectors — that
        happens in :meth:`_populate_rank_and_perspective`.
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
        games = 0
        if self.path_type == "summary":
            try:
                import json

                with open(karte_path, encoding="utf-8") as f:
                    data = json.load(f)
                games = (data.get("meta") or {}).get("games_analyzed", 0) or 0
            except Exception:  # noqa: BLE001
                pass
        if type_label is not None:
            if self.path_type == "karte":
                type_label.text = i18n._("mykatrain:llm-coach:type-label-single")
            elif self.path_type == "summary":
                type_label.text = i18n._("mykatrain:llm-coach:type-label-multi").format(games=games)
            else:
                type_label.text = i18n._("mykatrain:llm-coach:type-label-unknown")
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

    # ---- Button handlers ----------------------------------------------

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
        import re

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

    def on_validate(self) -> None:
        """Validate the user-pasted LLM response and show the report.

        Phase 225.5: write the full Markdown report to ``result_label``
        (the ScrollView) AND a one-line summary to ``status_label`` so
        the user immediately sees the issue counts without scrolling.

        Phase 227-D: dispatch on path type. Summary files use
        :func:`validate_summary_llm_response` which checks pattern
        categories, phase labels, and game-ID references instead of
        per-move numbers.
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

        # Count issues so the status line can summarise without scrolling.
        high = markdown.count("[HIGH]")
        medium = markdown.count("[MEDIUM]")
        low = markdown.count("[LOW]")
        total = high + medium + low
        if is_clean:
            if total == 0:
                self._set_status(i18n._("mykatrain:llm-coach:validation-clean"))
            else:
                # Validator says clean but report still has markers
                # (e.g. referenced symptom IDs that couldn't be matched).
                self._set_status(i18n._("mykatrain:llm-coach:validation-clean-with-notes").format(count=total))
        else:
            self._set_status(
                i18n._("mykatrain:llm-coach:validation-issues-with-count").format(
                    high=high, medium=medium, low=low, total=total
                )
            )

    def _on_validate_summary(self, karte_path: str, response_text: str, rank: str | None) -> None:
        """Phase 227-D: summary-mode validation handler.

        Delegates to :func:`validate_summary_llm_response` and surfaces
        the report Markdown in the result label / status line.
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
        high = markdown.count("[HIGH]")
        medium = markdown.count("[MEDIUM]")
        low = markdown.count("[LOW]")
        total = high + medium + low
        if is_clean:
            if total == 0:
                self._set_status(i18n._("mykatrain:llm-coach:validation-clean"))
            else:
                self._set_status(i18n._("mykatrain:llm-coach:validation-clean-with-notes").format(count=total))
        else:
            self._set_status(
                i18n._("mykatrain:llm-coach:validation-issues-with-count").format(
                    high=high, medium=medium, low=low, total=total
                )
            )

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

    # ---- Internal helpers ---------------------------------------------

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

    content = LLMCoachPopupContent(katrain=ctx)
    # Phase 225.7: wider popup so the LLM response input doesn't
    # overflow and the action buttons don't overlap.
    popup = I18NPopup(
        title_key="mykatrain:llm-coach:title",
        size=[dp(900), dp(720)],
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


# Phase 227-D: helper that maps the summary-perspective spinner index
# to a stable internal value. Index 0 = bird's-eye, 1..N = players.
# Returns the player name (string) for the focused player, or
# ``None`` for bird's-eye. Mirrors the ``_spinner_text_to_internal``
# pattern for karte mode but uses the index instead of localised text.
#
# Phase 241-D: the bird's-eye / out-of-range ambiguity is resolved via
# a dedicated sentinel string. Previously both cases returned
# ``None`` and downstream consumers (e.g. ``_resolve_player_color``)
# could not distinguish a deliberate "no focus" choice from a
# defensive fallback triggered by a stale spinner index. The new
# ``_SUMMARY_BIRDSEYE_SENTINEL`` is an unambiguous string that never
# collides with a real player name.
_SUMMARY_BIRDSEYE_SENTINEL: str = "__birdseye__"


def _summary_index_to_internal(
    index: int,
    players: list[tuple[str, str | None]],
) -> str | None:
    """Map summary perspective spinner index to a player name or the
    bird's-eye sentinel.

    Returns:
        - The bird's-eye sentinel (``"__birdseye__"``) when ``index == 0``
        - The player's ``name`` when ``0 < index <= len(players)``
        - ``None`` when the index is out of range (defensive fallback
          for stale spinner state). Callers should treat ``None`` as
          a bug condition and re-detect the perspective.
    """
    if index <= 0:
        return _SUMMARY_BIRDSEYE_SENTINEL
    if index > len(players):
        return None
    return players[index - 1][0]


def is_summary_birdseye(value: str | None) -> bool:
    """Phase 241-D: check whether a value is the bird's-eye sentinel.

    Centralised here so callers (popup handlers, tests) don't have to
    import the sentinel constant directly. Returns ``False`` for
    ``None`` (no value at all is NOT bird's-eye, it's a bug state).
    """
    return value == _SUMMARY_BIRDSEYE_SENTINEL


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


def _resolve_player_color(perspective_value: str, detected: str | None) -> str | None:
    """Resolve the user's perspective spinner selection to a "B"/"W"/None.

    Phase 226-B (B3): ``perspective_value`` is the stable internal value
    (``"auto"`` / ``"B"`` / ``"W"``), not the localised label.
    """
    val = perspective_value or "auto"
    if val == "B":
        return "B"
    if val == "W":
        return "W"
    # auto: prefer detected, else None
    return detected
