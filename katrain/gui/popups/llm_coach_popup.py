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


# How long the "コピー済み" / "コピー失敗" label sticks before reverting.
_COPY_FEEDBACK_SECONDS = 2.0


class LLMCcoachPopupContent(BoxLayout):
    """Body widget of the LLM Coach popup (Phase 225).

    All widget IDs referenced here (``karte_path_input``, ``rank_input``,
    ``response_input``, ``status_label``, ``result_label``) are bound in
    the matching KV file ``katrain/gui/kv/llm_coach_popup.kv``.
    """

    katrain = ObjectProperty(None, allownone=True)
    popup = ObjectProperty(None, allownone=True)

    karte_path_input = ObjectProperty(None, allownone=True)
    rank_input = ObjectProperty(None, allownone=True)
    response_input = ObjectProperty(None, allownone=True)
    status_label = ObjectProperty(None, allownone=True)
    result_label = ObjectProperty(None, allownone=True)
    generate_button = ObjectProperty(None, allownone=True)
    validate_button = ObjectProperty(None, allownone=True)

    status_text = StringProperty("")

    # ---- Lifecycle -----------------------------------------------------

    def on_kv_post(self, *_args: Any) -> None:
        """Auto-fill the karte path once the KV tree is attached.

        Runs on the Kivy main thread (``Clock.schedule_once``) so the
        filesystem walk doesn't block startup.
        """
        Clock.schedule_once(lambda _dt: self._populate_initial_karte_path(), 0)

    def _populate_initial_karte_path(self) -> None:
        if self.karte_path_input is None:
            return
        if self.karte_path_input.text:
            return  # user typed something already
        try:
            from katrain.gui.features.llm_coach import find_latest_karte

            latest = find_latest_karte(self.katrain) if self.katrain is not None else None
        except Exception:
            latest = None
        if latest is not None:
            self.karte_path_input.text = str(latest)

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
            chosen = (instance.filename or "").strip() or (
                instance.selection[0] if instance.selection else ""
            )
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
        """
        from katrain.gui.features.llm_coach import build_llm_prompt

        karte_path = self._read_text("karte_path_input")
        rank = self._read_text("rank_input") or None
        if not karte_path:
            self._set_status(i18n._("mykatrain:llm-coach:no-karte"), error=True)
            return
        ok, content = build_llm_prompt(
            self.katrain,
            karte_path,
            rank=rank,
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

    def on_clear_response(self) -> None:
        self._set_widget_text("response_input", "")
        self._set_status(i18n._("mykatrain:llm-coach:response-cleared"))

    def on_validate(self) -> None:
        """Validate the user-pasted LLM response and show the report.

        Phase 225.5: write the full Markdown report to ``result_label``
        (the ScrollView) AND a one-line summary to ``status_label`` so
        the user immediately sees the issue counts without scrolling.
        """
        from katrain.gui.features.llm_coach import validate_llm_response

        karte_path = self._read_text("karte_path_input")
        rank = self._read_text("rank_input") or None
        response_text = self._read_text("response_input")
        if not karte_path:
            self._set_status(i18n._("mykatrain:llm-coach:no-karte"), error=True)
            return
        if not response_text:
            self._set_status(i18n._("mykatrain:llm-coach:no-response"), error=True)
            return
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
                self._set_status(
                    i18n._("mykatrain:llm-coach:validation-clean-with-notes").format(
                        count=total
                    )
                )
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
    """
    from kivy.metrics import dp

    content = LLMCcoachPopupContent(katrain=ctx)
    popup = I18NPopup(
        title_key="mykatrain:llm-coach:title",
        size=[dp(700), dp(620)],
        content=content,
    ).__self__
    content.popup = popup
    popup.open()
    return popup