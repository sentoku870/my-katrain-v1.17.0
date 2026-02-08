# katrain/gui/features/batch_core.py
#
# バッチ解析コアロジックモジュール
#
# __main__.py から抽出したバッチ解析のコアロジックを配置します。
# - collect_batch_options: UIウィジェットからオプションを収集
# - create_log_callback: スレッドセーフなログコールバック作成
# - create_progress_callback: スレッドセーフな進行状況コールバック作成
# - create_summary_callback: 完了時のサマリ表示コールバック作成
# - run_batch_in_thread: バックグラウンドスレッドでバッチ実行

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from kivy.clock import Clock

from katrain.core import eval_metrics
from katrain.core.batch import (
    DEFAULT_TIMEOUT_SECONDS,
    BatchResult,
    needs_leela_karte_warning,  # noqa: F401
    parse_timeout_input,
    run_batch,
)
from katrain.core.batch import (
    safe_int as _safe_int,
)
from katrain.core.constants import STATUS_ERROR  # noqa: F401
from katrain.core.lang import i18n
from katrain.gui.features.types import BatchOptions, BatchWidgets

logger = logging.getLogger(__name__)


# NOTE: _safe_int is now imported from katrain.core.batch.helpers (Phase 42-A)
# Aliased as _safe_int to maintain existing local references


if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def collect_batch_options(
    widgets: BatchWidgets,
    get_player_filter_fn: Callable[[], str | None],
) -> BatchOptions:
    """UIウィジェットからバッチオプションを収集

    Args:
        widgets: ウィジェット辞書（input_input, output_input, visits_input, etc.）
        get_player_filter_fn: プレイヤーフィルター取得関数

    Returns:
        バッチオプション辞書
    """
    input_dir = widgets["input_input"].text.strip()
    output_dir = widgets["output_input"].text.strip() or None
    visits_text = widgets["visits_input"].text.strip()
    visits = _safe_int(visits_text, default=None)

    # Parse timeout with support for "None" (no timeout)
    timeout_text = widgets["timeout_input"].text
    timeout = parse_timeout_input(timeout_text, default=DEFAULT_TIMEOUT_SECONDS, log_cb=None)

    skip_analyzed = widgets["skip_checkbox"].active

    # Output options
    save_analyzed_sgf = widgets["save_sgf_checkbox"].active
    generate_karte = widgets["karte_checkbox"].active
    generate_summary = widgets["summary_checkbox"].active

    # Player filter
    karte_player_filter = get_player_filter_fn()

    # Min games
    min_games_text = widgets["min_games_input"].text.strip()
    min_games_per_player = _safe_int(min_games_text, default=3)

    # Variable visits options
    variable_visits = widgets["variable_visits_checkbox"].active
    jitter_text = widgets["jitter_input"].text.strip()
    jitter_pct = _safe_int(jitter_text, default=10)
    deterministic = widgets["deterministic_checkbox"].active
    sound_on_finish = widgets["sound_checkbox"].active


    # Curator generation (Phase 126)
    curator_cb = widgets.get("curator_checkbox")
    generate_curator = curator_cb.active if curator_cb is not None else False

    # Engine selection (Phase 36)
    engine_leela = widgets.get("engine_leela")
    analysis_engine = "leela" if engine_leela and engine_leela.state == "down" else "katago"

    return {
        "input_dir": input_dir,
        "output_dir": output_dir,
        "visits": visits,
        "timeout": timeout,
        "skip_analyzed": skip_analyzed,
        "save_analyzed_sgf": save_analyzed_sgf,
        "generate_karte": generate_karte,
        "generate_summary": generate_summary,
        "generate_curator": generate_curator,
        "analysis_engine": analysis_engine,
        "karte_player_filter": karte_player_filter,
        "min_games_per_player": min_games_per_player,
        "variable_visits": variable_visits,
        "jitter_pct": jitter_pct,
        "deterministic": deterministic,
        "sound_on_finish": sound_on_finish,
    }


def create_log_callback(
    log_text_widget: Any,
    log_scroll_widget: Any,
) -> Callable[[str], None]:
    """スレッドセーフなログコールバックを作成

    Args:
        log_text_widget: ログ表示用TextInputウィジェット
        log_scroll_widget: ログスクロール用ScrollViewウィジェット

    Returns:
        ログコールバック関数
    """

    def log_cb(msg: str) -> None:
        def update_log(dt: float) -> None:
            log_text_widget.text += msg + "\n"
            # Auto-scroll to bottom
            log_scroll_widget.scroll_y = 0

        Clock.schedule_once(update_log, 0)

    return log_cb


def create_progress_callback(
    progress_label_widget: Any,
) -> Callable[[int, int, str], None]:
    """スレッドセーフな進行状況コールバックを作成

    Args:
        progress_label_widget: 進行状況表示用Labelウィジェット

    Returns:
        進行状況コールバック関数
    """

    def progress_cb(current: int, total: int, filename: str) -> None:
        def update_progress(dt: float) -> None:
            progress_label_widget.text = f"[{current}/{total}] {filename}"

        Clock.schedule_once(update_progress, 0)

    return progress_cb


def create_summary_callback(
    is_running: list[bool],
    start_button: Any,
    close_button: Any,
    progress_label: Any,
    log_cb: Callable[[str], None],
) -> Callable[[BatchResult], None]:
    """完了時のサマリ表示コールバックを作成

    Args:
        is_running: 実行中フラグ（リストで参照渡し）
        start_button: 開始ボタンウィジェット
        close_button: 閉じるボタンウィジェット
        progress_label: 進行状況ラベルウィジェット
        log_cb: ログコールバック

    Returns:
        サマリ表示コールバック関数
    """

    def show_summary_callback(result: BatchResult) -> None:
        def show_summary(dt: float) -> None:
            is_running[0] = False
            start_button.text = i18n._("mykatrain:batch:start")
            close_button.disabled = False

            if result.cancelled:
                summary = i18n._("mykatrain:batch:cancelled")
            else:
                # Extended summary with karte/summary counts and error reporting
                karte_total = result.karte_written + result.karte_failed

                # Summary status: "Yes" / "No (skipped)" / "ERROR: <message>"
                if result.summary_written:
                    summary_status = "Yes"
                elif result.summary_error:
                    summary_status = f"ERROR: {result.summary_error}"
                else:
                    summary_status = "No (skipped)"

                summary = i18n._("mykatrain:batch:complete_extended").format(
                    success=result.success_count,
                    failed=result.fail_count,
                    skipped=result.skip_count,
                    karte_ok=result.karte_written,
                    karte_total=karte_total,
                    karte_fail=result.karte_failed,
                    summary=summary_status,
                    sgf=result.analyzed_sgf_written,
                    output_dir=result.output_dir,
                )
            progress_label.text = summary
            log_cb(summary)

        Clock.schedule_once(show_summary, 0)

    return show_summary_callback


def run_batch_in_thread(
    ctx: FeatureContext,
    options: BatchOptions,
    cancel_flag: list[bool],
    progress_cb: Callable[[int, int, str], None],
    log_cb: Callable[[str], None],
    on_complete: Callable[[BatchResult], None],
    save_batch_options_fn: Callable[[BatchOptions], None],
) -> None:
    """バックグラウンドスレッドでバッチ解析を実行

    Args:
        ctx: FeatureContext providing config, engine
        options: バッチオプション辞書
        cancel_flag: キャンセルフラグ（リストで参照渡し）
        progress_cb: 進行状況コールバック
        log_cb: ログコールバック
        on_complete: 完了時コールバック
        save_batch_options_fn: オプション保存関数
    """
    # Parse timeout again with log callback
    timeout = parse_timeout_input(
        str(options["timeout"]) if options["timeout"] is not None else "None",
        default=DEFAULT_TIMEOUT_SECONDS,
        log_cb=log_cb,
    )
    options["timeout"] = timeout

    # Save options for next time
    save_batch_options_fn(
        {
            "input_dir": options["input_dir"],
            "output_dir": options["output_dir"] or "",
            "visits": options["visits"],
            "timeout": options["timeout"],
            "skip_analyzed": options["skip_analyzed"],
            "save_analyzed_sgf": options["save_analyzed_sgf"],
            "generate_karte": options["generate_karte"],
            "generate_summary": options["generate_summary"],
            "generate_curator": options.get("generate_curator", False),
            "karte_player_filter": options["karte_player_filter"],
            "min_games_per_player": options["min_games_per_player"],
            "variable_visits": options["variable_visits"],
            "jitter_pct": options["jitter_pct"],
            "deterministic": options["deterministic"],
            "sound_on_finish": options["sound_on_finish"],
        }
    )

    # Get skill preset for karte/summary generation
    skill_preset = ctx.config("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET

    engine = getattr(ctx, "engine", None)

    result = run_batch(
        katrain=ctx,
        engine=engine,
        input_dir=options["input_dir"],
        output_dir=options["output_dir"],
        visits=options["visits"],
        timeout=options["timeout"],
        skip_analyzed=options["skip_analyzed"],
        progress_cb=progress_cb,
        log_cb=log_cb,
        cancel_flag=cancel_flag,
        save_analyzed_sgf=options["save_analyzed_sgf"],
        generate_karte=options["generate_karte"],
        generate_summary=options["generate_summary"],
        karte_player_filter=options["karte_player_filter"],
        min_games_per_player=options["min_games_per_player"],
        skill_preset=skill_preset,
        variable_visits=options["variable_visits"],
        jitter_pct=options["jitter_pct"],
        deterministic=options["deterministic"],
        lang=ctx.config("general/language") or "jp",
        generate_curator=options.get("generate_curator", False),
    )

    # Play completion sound if enabled
    if options["sound_on_finish"] and not result.cancelled:
        try:
            from katrain.gui.sound import play_sound
            from katrain.gui.theme import Theme

            # Phase 44: Use distinct completion chime instead of stone sounds
            play_sound(Theme.COMPLETION_CHIME_SOUND)
        except Exception:
            logger.debug("Failed to play completion sound", exc_info=True)

    # Call completion callback
    on_complete(result)


# ---------------------------------------------------------------------------
# Pure helper functions (testable without UI)
# ---------------------------------------------------------------------------

# NOTE: needs_leela_karte_warning is now imported from katrain.core.batch (Phase 42-A)

def is_leela_configured(ctx: FeatureContext) -> bool:
    """Leela解析が無効、あるいは実行ファイルが設定されていない場合に警告。

    Args:
        ctx: カレントコンテクスト（get_leela_configメソッドを持つこと）

    Returns:
        True if Leela is enabled or has an exe_path set.
    """
    leela_config = ctx.get_leela_config()
    return bool(leela_config.enabled or leela_config.exe_path)
