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
        """
        from kivy.metrics import dp

        def _on_success(instance: Any, *_args: Any) -> None:
            # I18NFileBrowser exposes the chosen path via its
            # ``filename`` StringProperty (set when ``button_clicked``
            # fires ``on_success``). Fall back to ``selection`` if the
            # caller double-clicked a row instead.
            chosen = instance.filename or (
                instance.selection[0] if instance.selection else ""
            )
            if not chosen:
                return
            if self.karte_path_input is not None:
                self.karte_path_input.text = str(chosen)
            picker.dismiss()

        browser = I18NFileBrowser(
            filters=["*.json", "*.JSON"],
            select_string=i18n._("button:ok"),
        )
        # Both events: OK button (on_success) and double-click (on_submit).
        # See ``I18NFileBrowser.button_clicked`` and the I18NFileChooserListView
        # ``on_submit`` binding inside ``filebrowser.py``.
        browser.bind(on_success=_on_success, on_submit=_on_success)

        picker = I18NPopup(
            title_key="mykatrain:llm-coach:browse-title",
            size=[dp(700), dp(500)],
            content=browser,
        )
        picker.open()

    def on_generate_and_copy(self) -> None:
        """Build the LLM prompt and copy the Markdown to the clipboard."""
        from katrain.gui.features.llm_coach import build_llm_prompt

        if self.karte_path_input is None or not self.karte_path_input.text.strip():
            self._set_status(i18n._("mykatrain:llm-coach:no-karte"), error=True)
            return
        rank = (self.rank_input.text or "").strip() or None if self.rank_input is not None else None
        ok, content = build_llm_prompt(
            self.katrain,
            self.karte_path_input.text.strip(),
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
        if self.response_input is not None:
            self.response_input.text = ""
        self._set_status(i18n._("mykatrain:llm-coach:response-cleared"))

    def on_validate(self) -> None:
        """Validate the user-pasted LLM response and show the report."""
        from katrain.gui.features.llm_coach import validate_llm_response

        if self.karte_path_input is None or not self.karte_path_input.text.strip():
            self._set_status(i18n._("mykatrain:llm-coach:no-karte"), error=True)
            return
        if self.response_input is None or not self.response_input.text.strip():
            self._set_status(i18n._("mykatrain:llm-coach:no-response"), error=True)
            return
        rank = (self.rank_input.text or "").strip() or None if self.rank_input is not None else None
        is_clean, markdown = validate_llm_response(
            self.katrain,
            self.karte_path_input.text.strip(),
            self.response_input.text,
            rank=rank,
        )
        if is_clean:
            self._set_status(i18n._("mykatrain:llm-coach:validation-clean"))
        else:
            self._set_status(i18n._("mykatrain:llm-coach:validation-issues"))
        self._set_result(markdown)

    def on_copy_result(self) -> None:
        if self.result_label is None or not self.result_label.text:
            self._set_status(i18n._("mykatrain:llm-coach:no-result"), error=True)
            return
        try:
            Clipboard.copy(self.result_label.text)
        except Exception as exc:  # noqa: BLE001
            self._set_status(
                i18n._("mykatrain:llm-coach:copy-failed").format(error=str(exc)),
                error=True,
            )
            return
        self._set_status(i18n._("mykatrain:llm-coach:result-copied"))

    # ---- Internal helpers ---------------------------------------------

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status_text = text
        if self.status_label is not None:
            self.status_label.text = text
            self.status_label.color = (
                Theme.ERROR_COLOR if error else Theme.TEXT_COLOR
            ) if hasattr(Theme, "ERROR_COLOR") else (1, 0.3, 0.3, 1) if error else Theme.TEXT_COLOR

    def _set_result(self, text: str) -> None:
        if self.result_label is not None:
            self.result_label.text = text


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