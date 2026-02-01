"""Engine comparison popup for viewing KataGo/Leela analysis side-by-side.

Phase 39: エンジン比較ビュー

This module provides a popup to compare KataGo and Leela Zero analysis results
in a tabbed interface with:
- Move-by-move comparison table (手別比較)
- Statistics summary (統計サマリー)
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.togglebutton import ToggleButton

from katrain.core.analysis.engine_compare import (
    ComparisonWarning,
    EngineComparisonResult,
    EngineStats,
    MoveComparison,
    build_comparison_from_game,
)
from katrain.core.constants import OUTPUT_ERROR, OUTPUT_INFO
from katrain.core.lang import i18n
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


# =============================================================================
# Constants
# =============================================================================

# Divergent filter threshold (|diff| >= this value shown when filter active)
DIVERGENT_FILTER_THRESHOLD = 1.0

# Row height for table rows
ROW_HEIGHT = dp(28)

# Header height
HEADER_HEIGHT = dp(32)

# Highlight color for large differences
HIGHLIGHT_COLOR = [1.0, 0.9, 0.6, 0.3]  # Light yellow

# Column widths for the table
COL_WIDTHS = {
    "move": dp(50),
    "player": dp(50),
    "coord": dp(60),
    "katago": dp(80),
    "leela": dp(80),
    "diff": dp(80),
}


# =============================================================================
# Public API
# =============================================================================


def show_engine_compare_popup(ctx: "FeatureContext") -> None:
    """Show engine comparison popup.

    Args:
        ctx: FeatureContext providing game, log, config access.
    """
    Clock.schedule_once(lambda dt: _show_engine_compare_popup_impl(ctx), 0)


# =============================================================================
# Implementation
# =============================================================================


def _show_engine_compare_popup_impl(ctx: "FeatureContext") -> None:
    """Implementation of engine comparison popup display."""
    # Check if game is loaded
    game = getattr(ctx, "game", None)
    if game is None:
        ctx.log(i18n._("engine-compare:no-game"), OUTPUT_ERROR)
        return

    # Build comparison result
    try:
        result = build_comparison_from_game(game)
    except (ValueError, AttributeError) as e:
        # Comparison build failure: invalid game state or missing analysis data
        logging.info(f"Engine comparison build failed: {e}")
        ctx.log(f"{i18n._('engine-compare:build-error')}: {e}", OUTPUT_ERROR)
        return
    except Exception as e:
        # Boundary fallback: unexpected error building comparison
        logging.warning(f"Unexpected error in engine comparison: {e}", exc_info=True)
        ctx.log(f"{i18n._('engine-compare:build-error')}: {e}", OUTPUT_ERROR)
        return

    # Check if any analysis exists
    has_katago = result.katago_stats.analyzed_moves > 0
    has_leela = result.leela_stats.analyzed_moves > 0
    if not has_katago and not has_leela:
        ctx.log(i18n._("engine-compare:no-analysis"), OUTPUT_ERROR)
        return

    # Build popup content
    _build_and_show_popup(ctx, result)


def _build_and_show_popup(ctx: "FeatureContext", result: EngineComparisonResult) -> None:
    """Build and show the popup."""
    content = BoxLayout(orientation="vertical", spacing=dp(5), padding=dp(5))

    # Warning banner (if any relevant warnings)
    warning_text = _format_warnings(result)
    if warning_text:
        warning_label = Label(
            text=warning_text,
            font_name=Theme.DEFAULT_FONT,
            size_hint=(1, None),
            height=dp(40),
            halign="center",
            valign="middle",
            color=[1.0, 0.8, 0.2, 1.0],  # Yellow warning color
        )
        warning_label.bind(size=warning_label.setter("text_size"))
        content.add_widget(warning_label)

    # Tabbed panel
    tabbed = TabbedPanel(do_default_tab=False)

    # Tab 1: Move comparison
    moves_tab = TabbedPanelItem(text=i18n._("engine-compare:tab-moves"))
    moves_content, filter_state = _build_moves_tab(ctx, result)
    moves_tab.add_widget(moves_content)
    tabbed.add_widget(moves_tab)

    # Tab 2: Statistics summary
    stats_tab = TabbedPanelItem(text=i18n._("engine-compare:tab-stats"))
    stats_content = _build_stats_tab(result)
    stats_tab.add_widget(stats_content)
    tabbed.add_widget(stats_tab)

    tabbed.default_tab = moves_tab
    content.add_widget(tabbed)

    # Close button
    close_btn = Button(
        text=i18n._("engine-compare:close"),
        font_name=Theme.DEFAULT_FONT,
        size_hint=(1, None),
        height=dp(40),
    )
    content.add_widget(close_btn)

    # Create popup
    popup = Popup(
        title=i18n._("engine-compare:title"),
        content=content,
        size_hint=(0.85, 0.85),
    )

    close_btn.bind(on_release=popup.dismiss)
    popup.open()


def _format_warnings(result: EngineComparisonResult) -> str:
    """Format warnings into display text."""
    parts = []

    for warning in result.warnings:
        if warning == ComparisonWarning.KATAGO_ONLY:
            parts.append(i18n._("engine-compare:katago-only"))
        elif warning == ComparisonWarning.LEELA_ONLY:
            parts.append(i18n._("engine-compare:leela-only"))
        elif warning == ComparisonWarning.PARTIAL_OVERLAP:
            # Calculate overlap percentage
            if result.total_moves > 0:
                both_count = sum(1 for m in result.move_comparisons if m.has_both)
                pct = int(100 * both_count / result.total_moves)
                parts.append(i18n._("engine-compare:partial-overlap").format(pct=pct))
        elif warning == ComparisonWarning.SEMANTICS_DIFFER:
            parts.append(i18n._("engine-compare:semantics-differ"))

    return " | ".join(parts)


# =============================================================================
# Moves Tab
# =============================================================================


def _build_moves_tab(
    ctx: "FeatureContext",
    result: EngineComparisonResult,
) -> Tuple[BoxLayout, Dict[str, Any]]:
    """Build the moves comparison tab.

    Returns:
        (content_widget, filter_state_dict)
    """
    layout = BoxLayout(orientation="vertical", spacing=dp(5))

    # Filter controls
    filter_row = BoxLayout(
        orientation="horizontal",
        size_hint=(1, None),
        height=dp(40),
        spacing=dp(10),
        padding=[dp(5), 0],
    )

    filter_label = Label(
        text=i18n._("engine-compare:filter-label"),
        font_name=Theme.DEFAULT_FONT,
        size_hint=(None, 1),
        width=dp(80),
        halign="right",
        valign="middle",
    )
    filter_label.bind(size=filter_label.setter("text_size"))
    filter_row.add_widget(filter_label)

    # Filter state
    filter_state = {"divergent_only": True, "scroll": None, "table_container": None}

    # Toggle button for divergent filter
    filter_btn = ToggleButton(
        text=i18n._("engine-compare:filter-divergent"),
        font_name=Theme.DEFAULT_FONT,
        size_hint=(None, 1),
        width=dp(120),
        state="down",  # Default: filter ON
        group="engine_compare_filter",
    )
    filter_row.add_widget(filter_btn)

    # Show all button
    all_btn = ToggleButton(
        text=i18n._("engine-compare:filter-all"),
        font_name=Theme.DEFAULT_FONT,
        size_hint=(None, 1),
        width=dp(120),
        group="engine_compare_filter",
    )
    filter_row.add_widget(all_btn)

    # Spacer
    filter_row.add_widget(Label(size_hint=(1, 1)))

    layout.add_widget(filter_row)

    # Table container with scroll
    scroll = ScrollView(size_hint=(1, 1))
    table_container = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        spacing=0,
    )
    table_container.bind(minimum_height=table_container.setter("height"))

    filter_state["scroll"] = scroll
    filter_state["table_container"] = table_container

    # Build initial table (filtered by default)
    _rebuild_moves_table(ctx, result, table_container, filter_state)

    scroll.add_widget(table_container)
    layout.add_widget(scroll)

    # Bind filter buttons
    def on_filter_change(instance: Any, value: str) -> None:
        if value == "down":
            filter_state["divergent_only"] = instance == filter_btn
            _rebuild_moves_table(ctx, result, table_container, filter_state)

    filter_btn.bind(state=on_filter_change)
    all_btn.bind(state=on_filter_change)

    return layout, filter_state


def _rebuild_moves_table(
    ctx: "FeatureContext",
    result: EngineComparisonResult,
    container: BoxLayout,
    filter_state: Dict[str, Any],
) -> None:
    """Rebuild the moves table based on filter state."""
    container.clear_widgets()

    # Filter moves
    if filter_state["divergent_only"]:
        moves = [m for m in result.move_comparisons if m.abs_diff >= DIVERGENT_FILTER_THRESHOLD]
    else:
        moves = result.move_comparisons

    # Header row
    header = _build_header_row()
    container.add_widget(header)

    # Data rows
    for move in moves:
        row = _build_move_row(ctx, move, result)
        container.add_widget(row)

    # No data message
    if not moves:
        no_data = Label(
            text=i18n._("engine-compare:no-divergent"),
            font_name=Theme.DEFAULT_FONT,
            size_hint_y=None,
            height=ROW_HEIGHT * 2,
            halign="center",
            valign="middle",
        )
        no_data.bind(size=no_data.setter("text_size"))
        container.add_widget(no_data)


def _build_header_row() -> BoxLayout:
    """Build the table header row."""
    header = BoxLayout(
        orientation="horizontal",
        size_hint=(1, None),
        height=HEADER_HEIGHT,
    )

    headers = [
        (i18n._("engine-compare:col-move"), COL_WIDTHS["move"]),
        (i18n._("engine-compare:col-player"), COL_WIDTHS["player"]),
        (i18n._("engine-compare:col-coord"), COL_WIDTHS["coord"]),
        (i18n._("engine-compare:col-katago"), COL_WIDTHS["katago"]),
        (i18n._("engine-compare:col-leela"), COL_WIDTHS["leela"]),
        (i18n._("engine-compare:col-diff"), COL_WIDTHS["diff"]),
    ]

    for text, width in headers:
        lbl = Label(
            text=f"[b]{text}[/b]",
            markup=True,
            font_name=Theme.DEFAULT_FONT,
            size_hint=(None, 1),
            width=width,
            halign="center",
            valign="middle",
            color=Theme.TEXT_COLOR,
        )
        lbl.bind(size=lbl.setter("text_size"))
        header.add_widget(lbl)

    # Spacer for remaining width
    header.add_widget(Label(size_hint=(1, 1)))

    return header


def _build_move_row(
    ctx: "FeatureContext",
    move: MoveComparison,
    result: EngineComparisonResult,
) -> BoxLayout:
    """Build a single move row."""
    # Determine if this row should be highlighted
    highlight = move.abs_diff >= 2.0

    row = BoxLayout(
        orientation="horizontal",
        size_hint=(1, None),
        height=ROW_HEIGHT,
    )

    # Add highlight background if needed
    if highlight:
        from kivy.graphics import Color, Rectangle

        with row.canvas.before:
            Color(*HIGHLIGHT_COLOR)
            rect = Rectangle(pos=row.pos, size=row.size)
            row.bind(pos=lambda inst, val: setattr(rect, "pos", val))
            row.bind(size=lambda inst, val: setattr(rect, "size", val))

    # Move number
    _add_cell(row, str(move.move_number), COL_WIDTHS["move"])

    # Player
    _add_cell(row, move.player, COL_WIDTHS["player"])

    # Coordinate
    _add_cell(row, move.gtp, COL_WIDTHS["coord"])

    # KataGo loss
    katago_text = f"{move.katago_loss:.1f}" if move.katago_loss is not None else "-"
    _add_cell(row, katago_text, COL_WIDTHS["katago"])

    # Leela loss
    leela_text = f"{move.leela_loss:.1f}" if move.leela_loss is not None else "-"
    _add_cell(row, leela_text, COL_WIDTHS["leela"])

    # Difference
    if move.loss_diff is not None:
        sign = "+" if move.loss_diff > 0 else ""
        diff_text = f"{sign}{move.loss_diff:.1f}"
    else:
        diff_text = "-"
    _add_cell(row, diff_text, COL_WIDTHS["diff"])

    # Spacer
    row.add_widget(Label(size_hint=(1, 1)))

    # Make row clickable to jump to move
    row.bind(on_touch_down=lambda inst, touch: _on_row_click(ctx, move, inst, touch))

    return row


def _add_cell(row: BoxLayout, text: str, width: float) -> None:
    """Add a cell to the row."""
    cell = Label(
        text=text,
        font_name=Theme.DEFAULT_FONT,
        size_hint=(None, 1),
        width=width,
        halign="center",
        valign="middle",
        color=Theme.TEXT_COLOR,
    )
    cell.bind(size=cell.setter("text_size"))
    row.add_widget(cell)


def _on_row_click(
    ctx: "FeatureContext",
    move: MoveComparison,
    instance: Any,
    touch: Any,
) -> bool:
    """Handle row click to jump to move."""
    if not instance.collide_point(*touch.pos):
        return False

    # Jump to the move
    game = getattr(ctx, "game", None)
    if game is not None:
        # Navigate to the move number
        target_depth = move.move_number
        current_depth = game.current_node.depth

        if target_depth > current_depth:
            game.redo(target_depth - current_depth)
        elif target_depth < current_depth:
            game.undo(current_depth - target_depth)

        # Update UI
        if hasattr(ctx, "update_state"):
            ctx.update_state(redraw_board=True)

        ctx.log(
            i18n._("engine-compare:jumped-to").format(move=move.move_number),
            OUTPUT_INFO,
        )

    return True


# =============================================================================
# Statistics Tab
# =============================================================================


def _build_stats_tab(result: EngineComparisonResult) -> BoxLayout:
    """Build the statistics summary tab."""
    layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))

    scroll = ScrollView(size_hint=(1, 1))
    content = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        spacing=dp(10),
        padding=dp(5),
    )
    content.bind(minimum_height=content.setter("height"))

    # Engine comparison stats
    stats_grid = _build_stats_comparison_grid(result)
    content.add_widget(stats_grid)

    # Divergence analysis section
    divergence_section = _build_divergence_section(result)
    content.add_widget(divergence_section)

    scroll.add_widget(content)
    layout.add_widget(scroll)

    return layout


def _build_stats_comparison_grid(result: EngineComparisonResult) -> GridLayout:
    """Build the side-by-side engine stats grid."""
    grid = GridLayout(
        cols=3,
        size_hint=(1, None),
        spacing=dp(5),
        padding=dp(5),
    )
    grid.bind(minimum_height=grid.setter("height"))

    def add_row(label: str, katago_val: str, leela_val: str) -> None:
        """Add a row to the grid."""
        for text in [label, katago_val, leela_val]:
            cell = Label(
                text=text,
                font_name=Theme.DEFAULT_FONT,
                size_hint_y=None,
                height=dp(30),
                halign="center",
                valign="middle",
                color=Theme.TEXT_COLOR,
            )
            cell.bind(size=cell.setter("text_size"))
            grid.add_widget(cell)

    # Header
    add_row(
        "",
        f"[b]KataGo[/b]",
        f"[b]Leela[/b]",
    )
    # Enable markup for header cells
    for child in grid.children[:3]:
        child.markup = True

    # Stats rows
    ks = result.katago_stats
    ls = result.leela_stats

    add_row(
        i18n._("engine-compare:analyzed-moves"),
        str(ks.analyzed_moves),
        str(ls.analyzed_moves),
    )
    add_row(
        i18n._("engine-compare:total-loss"),
        f"{ks.total_loss:.1f}",
        f"{ls.total_loss:.1f}",
    )
    add_row(
        i18n._("engine-compare:avg-loss"),
        f"{ks.avg_loss:.2f}",
        f"{ls.avg_loss:.2f}",
    )
    add_row(
        i18n._("engine-compare:blunder-count"),
        str(ks.blunder_count),
        str(ls.blunder_count),
    )
    add_row(
        i18n._("engine-compare:mistake-count"),
        str(ks.mistake_count),
        str(ls.mistake_count),
    )
    add_row(
        i18n._("engine-compare:inaccuracy-count"),
        str(ks.inaccuracy_count),
        str(ls.inaccuracy_count),
    )

    return grid


def _build_divergence_section(result: EngineComparisonResult) -> BoxLayout:
    """Build the divergence analysis section."""
    section = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        spacing=dp(5),
    )
    section.bind(minimum_height=section.setter("height"))

    # Section header
    header = Label(
        text=f"[b]{i18n._('engine-compare:divergence-analysis')}[/b]",
        markup=True,
        font_name=Theme.DEFAULT_FONT,
        size_hint_y=None,
        height=dp(35),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
    )
    header.bind(size=header.setter("text_size"))
    section.add_widget(header)

    # Correlation
    corr_text = (
        f"{result.correlation:.3f}" if result.correlation is not None else i18n._("engine-compare:insufficient-data")
    )
    corr_label = Label(
        text=f"{i18n._('engine-compare:correlation')}: {corr_text}",
        font_name=Theme.DEFAULT_FONT,
        size_hint_y=None,
        height=dp(28),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
    )
    corr_label.bind(size=corr_label.setter("text_size"))
    section.add_widget(corr_label)

    # Trend
    if result.mean_diff is not None:
        if result.mean_diff > 0.5:
            trend = i18n._("engine-compare:trend-katago-strict")
        elif result.mean_diff < -0.5:
            trend = i18n._("engine-compare:trend-leela-strict")
        else:
            trend = i18n._("engine-compare:trend-similar")
    else:
        trend = i18n._("engine-compare:insufficient-data")

    trend_label = Label(
        text=f"{i18n._('engine-compare:trend')}: {trend}",
        font_name=Theme.DEFAULT_FONT,
        size_hint_y=None,
        height=dp(28),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
    )
    trend_label.bind(size=trend_label.setter("text_size"))
    section.add_widget(trend_label)

    # Divergent top 5
    if result.divergent_moves:
        top_header = Label(
            text=f"{i18n._('engine-compare:divergent-top').format(n=len(result.divergent_moves))}:",
            font_name=Theme.DEFAULT_FONT,
            size_hint_y=None,
            height=dp(28),
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
        )
        top_header.bind(size=top_header.setter("text_size"))
        section.add_widget(top_header)

        for move in result.divergent_moves:
            sign = "+" if (move.loss_diff or 0) > 0 else ""
            diff_str = f"{sign}{move.loss_diff:.1f}" if move.loss_diff is not None else "-"
            text = f"  #{move.move_number} {move.player} {move.gtp}: {diff_str}"
            item = Label(
                text=text,
                font_name=Theme.DEFAULT_FONT,
                size_hint_y=None,
                height=dp(24),
                halign="left",
                valign="middle",
                color=Theme.TEXT_COLOR,
            )
            item.bind(size=item.setter("text_size"))
            section.add_widget(item)

    return section
