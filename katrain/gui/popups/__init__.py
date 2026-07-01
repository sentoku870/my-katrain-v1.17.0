"""GUI popups package.

Phase 140 P2-1: Extracted from katrain/gui/popups.py (1168 lines) into a
focused package of 5 submodules:

- _base.py: Common base classes, input widgets, helpers
- quick_config.py: QuickConfigGui + 5 derived popups
- config_popup.py: BaseConfigPopup + ConfigPopup (engine/model config)
- sgf_popups.py: LoadSGFPopup, SaveSGFPopup, ReAnalyzeGamePopup
- misc_popups.py: TsumegoFramePopup, GameReportPopup

This __init__.py re-exports all public names for backward compatibility with
existing `from katrain.gui.popups import ...` imports.
"""
from __future__ import annotations

from katrain.gui.popups._base import (
    DescriptionLabel,
    I18NPopup,
    InputParseError,
    LabelledCheckBox,
    LabelledFloatInput,
    LabelledIntInput,
    LabelledPathInput,
    LabelledSelectionSlider,
    LabelledSpinner,
    LabelledTextInput,
    _get_app_gui,  # noqa: F401 - re-exported for backward compatibility
    wrap_anchor,
)
from katrain.gui.popups.config_popup import BaseConfigPopup, ConfigPopup
from katrain.gui.popups.misc_popups import GameReportPopup, TsumegoFramePopup
from katrain.gui.popups.quick_config import (
    ConfigAIPopup,
    ConfigTeacherPopup,
    ConfigTimerPopup,
    EngineRecoveryPopup,
    NewGamePopup,
    QuickConfigGui,
)
from katrain.gui.popups.sgf_popups import (
    LoadSGFPopup,
    ReAnalyzeGamePopup,
    SaveSGFPopup,
)

__all__ = [
    # Base
    "BaseConfigPopup",
    "ConfigAIPopup",
    "ConfigPopup",
    "ConfigTeacherPopup",
    "ConfigTimerPopup",
    "DescriptionLabel",
    "EngineRecoveryPopup",
    "GameReportPopup",
    "I18NPopup",
    "InputParseError",
    "LabelledCheckBox",
    "LabelledFloatInput",
    "LabelledIntInput",
    "LabelledPathInput",
    "LabelledSelectionSlider",
    "LabelledSpinner",
    "LabelledTextInput",
    "LoadSGFPopup",
    "NewGamePopup",
    "QuickConfigGui",
    "ReAnalyzeGamePopup",
    "SaveSGFPopup",
    "TsumegoFramePopup",
    "wrap_anchor",
]
