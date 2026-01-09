"""
Unified Settings Management for KaTrain Qt.

Provides a single source of truth for all settings:
- KataGo paths (exe, config, model)
- Analysis parameters (max_visits, max_candidates, rules, komi)
- UI preferences (window geometry, dock layout)

Settings are persisted to JSON and can be overridden by environment variables.

Usage:
    from katrain_qt.settings import Settings

    settings = Settings()
    settings.katago_exe = "/path/to/katago"
    settings.save()

    # Environment variables override:
    # KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, QByteArray


# =============================================================================
# Constants
# =============================================================================

SETTINGS_FILENAME = "katrain_qt_settings.json"
QSETTINGS_ORG = "KaTrain"
QSETTINGS_APP = "KaTrain-Qt"

# Default values
DEFAULT_MAX_VISITS = 1000
DEFAULT_MAX_CANDIDATES = 5
DEFAULT_KOMI = 6.5
DEFAULT_RULES = "japanese"


# =============================================================================
# Settings Data Class
# =============================================================================

@dataclass
class AppSettings:
    """Application settings with defaults."""

    # KataGo paths
    katago_exe: str = ""
    config_path: str = ""
    model_path: str = ""

    # Analysis parameters
    max_visits: int = DEFAULT_MAX_VISITS
    max_candidates: int = DEFAULT_MAX_CANDIDATES
    komi: float = DEFAULT_KOMI
    rules: str = DEFAULT_RULES

    # File dialogs
    last_sgf_dir: str = ""

    # Dev/Experimental features (default: OFF)
    dev_show_loss: bool = False
    dev_hover_pv: bool = False

    # Language (en = English, ja = Japanese)
    language: str = "en"

    # Sound settings
    sound_enabled: bool = True
    sound_volume: float = 0.5  # 0.0 - 1.0

    # Theme (light, dark)
    theme: str = "light"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        """Create from dictionary, ignoring unknown keys."""
        known_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)


# =============================================================================
# Settings Manager
# =============================================================================

class Settings:
    """
    Unified settings manager for KaTrain Qt.

    Handles:
    - JSON file persistence for app settings
    - QSettings for window geometry and dock layout
    - Environment variable overrides
    """

    def __init__(self, settings_dir: Optional[Path] = None):
        """
        Initialize settings manager.

        Args:
            settings_dir: Directory for settings file.
                         Defaults to katrain_qt package directory.
        """
        if settings_dir is None:
            settings_dir = Path(__file__).parent

        self._settings_dir = settings_dir
        self._settings_path = settings_dir / SETTINGS_FILENAME

        # Qt settings for geometry (uses system registry/plist/ini)
        self._qsettings = QSettings(QSETTINGS_ORG, QSETTINGS_APP)

        # Load settings
        self._settings = self._load()

    # -------------------------------------------------------------------------
    # File Path
    # -------------------------------------------------------------------------

    @property
    def settings_path(self) -> Path:
        """Path to the settings JSON file."""
        return self._settings_path

    @property
    def settings_dir(self) -> Path:
        """Directory containing settings file."""
        return self._settings_dir

    # -------------------------------------------------------------------------
    # KataGo Paths (with environment variable override)
    # -------------------------------------------------------------------------

    @property
    def katago_exe(self) -> str:
        """KataGo executable path. KATAGO_EXE env var overrides."""
        return os.environ.get("KATAGO_EXE", self._settings.katago_exe)

    @katago_exe.setter
    def katago_exe(self, value: str):
        self._settings.katago_exe = value

    @property
    def config_path(self) -> str:
        """KataGo config path. KATAGO_CONFIG env var overrides."""
        return os.environ.get("KATAGO_CONFIG", self._settings.config_path)

    @config_path.setter
    def config_path(self, value: str):
        self._settings.config_path = value

    @property
    def model_path(self) -> str:
        """KataGo model path. KATAGO_MODEL env var overrides."""
        return os.environ.get("KATAGO_MODEL", self._settings.model_path)

    @model_path.setter
    def model_path(self, value: str):
        self._settings.model_path = value

    # -------------------------------------------------------------------------
    # Analysis Parameters
    # -------------------------------------------------------------------------

    @property
    def max_visits(self) -> int:
        """Maximum visits per analysis query."""
        return self._settings.max_visits

    @max_visits.setter
    def max_visits(self, value: int):
        self._settings.max_visits = max(1, min(value, 100000))

    @property
    def max_candidates(self) -> int:
        """Maximum candidate moves to display."""
        return self._settings.max_candidates

    @max_candidates.setter
    def max_candidates(self, value: int):
        self._settings.max_candidates = max(1, min(value, 20))

    @property
    def komi(self) -> float:
        """Default komi for new games."""
        return self._settings.komi

    @komi.setter
    def komi(self, value: float):
        self._settings.komi = value

    @property
    def rules(self) -> str:
        """Game rules (japanese, chinese, etc.)."""
        return self._settings.rules

    @rules.setter
    def rules(self, value: str):
        self._settings.rules = value

    # -------------------------------------------------------------------------
    # File Dialogs
    # -------------------------------------------------------------------------

    @property
    def last_sgf_dir(self) -> str:
        """Last directory used for SGF file dialogs."""
        return self._settings.last_sgf_dir

    @last_sgf_dir.setter
    def last_sgf_dir(self, value: str):
        self._settings.last_sgf_dir = value

    # -------------------------------------------------------------------------
    # Dev/Experimental Features
    # -------------------------------------------------------------------------

    @property
    def dev_show_loss(self) -> bool:
        """Show Loss column in Candidates panel (experimental)."""
        return self._settings.dev_show_loss

    @dev_show_loss.setter
    def dev_show_loss(self, value: bool):
        self._settings.dev_show_loss = value

    @property
    def dev_hover_pv(self) -> bool:
        """Show PV preview on candidate hover (experimental)."""
        return self._settings.dev_hover_pv

    @dev_hover_pv.setter
    def dev_hover_pv(self, value: bool):
        self._settings.dev_hover_pv = value

    @property
    def language(self) -> str:
        """UI language code (en, ja)."""
        return self._settings.language

    @language.setter
    def language(self, value: str):
        self._settings.language = value

    # -------------------------------------------------------------------------
    # Sound Settings
    # -------------------------------------------------------------------------

    @property
    def sound_enabled(self) -> bool:
        """Whether sound effects are enabled."""
        return self._settings.sound_enabled

    @sound_enabled.setter
    def sound_enabled(self, value: bool):
        self._settings.sound_enabled = value

    @property
    def sound_volume(self) -> float:
        """Sound volume (0.0 - 1.0)."""
        return self._settings.sound_volume

    @sound_volume.setter
    def sound_volume(self, value: float):
        self._settings.sound_volume = max(0.0, min(1.0, value))

    # -------------------------------------------------------------------------
    # Theme Settings
    # -------------------------------------------------------------------------

    @property
    def theme(self) -> str:
        """UI theme (light, dark)."""
        return self._settings.theme

    @theme.setter
    def theme(self, value: str):
        if value in ("light", "dark"):
            self._settings.theme = value

    # -------------------------------------------------------------------------
    # Effective Values (with env override indicators)
    # -------------------------------------------------------------------------

    def is_katago_exe_from_env(self) -> bool:
        """Check if katago_exe is set via environment variable."""
        return bool(os.environ.get("KATAGO_EXE"))

    def is_config_path_from_env(self) -> bool:
        """Check if config_path is set via environment variable."""
        return bool(os.environ.get("KATAGO_CONFIG"))

    def is_model_path_from_env(self) -> bool:
        """Check if model_path is set via environment variable."""
        return bool(os.environ.get("KATAGO_MODEL"))

    # -------------------------------------------------------------------------
    # Window Geometry (QSettings)
    # -------------------------------------------------------------------------

    def save_window_geometry(self, geometry: QByteArray):
        """Save window geometry."""
        self._qsettings.setValue("window/geometry", geometry)

    def load_window_geometry(self) -> Optional[QByteArray]:
        """Load window geometry, returns None if not set."""
        value = self._qsettings.value("window/geometry")
        if isinstance(value, QByteArray):
            return value
        return None

    def save_window_state(self, state: QByteArray):
        """Save window state (dock positions, etc.)."""
        self._qsettings.setValue("window/state", state)

    def load_window_state(self) -> Optional[QByteArray]:
        """Load window state, returns None if not set."""
        value = self._qsettings.value("window/state")
        if isinstance(value, QByteArray):
            return value
        return None

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _load(self) -> AppSettings:
        """Load settings from JSON file."""
        if self._settings_path.exists():
            try:
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return AppSettings.from_dict(data)
            except (json.JSONDecodeError, IOError):
                pass
        return AppSettings()

    def save(self):
        """Save settings to JSON file."""
        try:
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(self._settings.to_dict(), f, indent=2)
        except IOError:
            pass

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self._settings = AppSettings()
        self.save()
        # Clear QSettings
        self._qsettings.clear()

    def sync(self):
        """Force sync QSettings to storage."""
        self._qsettings.sync()


# =============================================================================
# Module-level singleton
# =============================================================================

_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
