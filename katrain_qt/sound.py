"""
Sound Manager for KaTrain Qt.

Provides sound effects for:
- Stone placement (random from stone1-5.wav)
- Capture sound
- Analysis completion (optional)

Uses Qt Multimedia for cross-platform audio playback.
"""

import random
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect


# =============================================================================
# Constants
# =============================================================================

# Sound file directory (relative to katrain package)
SOUNDS_DIR = Path(__file__).parent.parent / "katrain" / "sounds"

# Sound file names
STONE_SOUNDS = ["stone1.wav", "stone2.wav", "stone3.wav", "stone4.wav", "stone5.wav"]
CAPTURE_SOUND = "capturing.wav"
COUNTDOWN_SOUND = "countdownbeep.wav"
BOING_SOUND = "boing.wav"


# =============================================================================
# SoundManager
# =============================================================================

class SoundManager:
    """
    Manages sound effect playback for KaTrain Qt.

    Features:
    - Stone placement sounds (randomly selected)
    - Capture sound
    - Enable/disable toggle
    - Volume control
    """

    def __init__(self, enabled: bool = True, volume: float = 0.5):
        """
        Initialize sound manager.

        Args:
            enabled: Whether sounds are enabled
            volume: Volume level (0.0 - 1.0)
        """
        self._enabled = enabled
        self._volume = max(0.0, min(1.0, volume))

        # Pre-load sound effects
        self._stone_sounds: list[QSoundEffect] = []
        self._capture_sound: Optional[QSoundEffect] = None
        self._countdown_sound: Optional[QSoundEffect] = None
        self._boing_sound: Optional[QSoundEffect] = None

        self._load_sounds()

    def _load_sounds(self):
        """Load all sound effects."""
        # Stone sounds
        for filename in STONE_SOUNDS:
            sound_path = SOUNDS_DIR / filename
            if sound_path.exists():
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(sound_path)))
                effect.setVolume(self._volume)
                self._stone_sounds.append(effect)

        # Capture sound
        capture_path = SOUNDS_DIR / CAPTURE_SOUND
        if capture_path.exists():
            self._capture_sound = QSoundEffect()
            self._capture_sound.setSource(QUrl.fromLocalFile(str(capture_path)))
            self._capture_sound.setVolume(self._volume)

        # Countdown sound
        countdown_path = SOUNDS_DIR / COUNTDOWN_SOUND
        if countdown_path.exists():
            self._countdown_sound = QSoundEffect()
            self._countdown_sound.setSource(QUrl.fromLocalFile(str(countdown_path)))
            self._countdown_sound.setVolume(self._volume)

        # Boing sound (for errors/warnings)
        boing_path = SOUNDS_DIR / BOING_SOUND
        if boing_path.exists():
            self._boing_sound = QSoundEffect()
            self._boing_sound.setSource(QUrl.fromLocalFile(str(boing_path)))
            self._boing_sound.setVolume(self._volume)

    @property
    def enabled(self) -> bool:
        """Whether sounds are enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """Enable or disable sounds."""
        self._enabled = value

    @property
    def volume(self) -> float:
        """Current volume level (0.0 - 1.0)."""
        return self._volume

    @volume.setter
    def volume(self, value: float):
        """Set volume level."""
        self._volume = max(0.0, min(1.0, value))
        # Update all sound effects
        for effect in self._stone_sounds:
            effect.setVolume(self._volume)
        if self._capture_sound:
            self._capture_sound.setVolume(self._volume)
        if self._countdown_sound:
            self._countdown_sound.setVolume(self._volume)
        if self._boing_sound:
            self._boing_sound.setVolume(self._volume)

    def play_stone(self):
        """Play a random stone placement sound."""
        if not self._enabled or not self._stone_sounds:
            return
        sound = random.choice(self._stone_sounds)
        sound.play()

    def play_capture(self):
        """Play capture sound."""
        if not self._enabled or not self._capture_sound:
            return
        self._capture_sound.play()

    def play_countdown(self):
        """Play countdown beep sound."""
        if not self._enabled or not self._countdown_sound:
            return
        self._countdown_sound.play()

    def play_boing(self):
        """Play boing sound (for errors/invalid moves)."""
        if not self._enabled or not self._boing_sound:
            return
        self._boing_sound.play()


# =============================================================================
# Module-level singleton
# =============================================================================

_sound_manager: Optional[SoundManager] = None


def get_sound_manager() -> SoundManager:
    """Get the global sound manager instance."""
    global _sound_manager
    if _sound_manager is None:
        _sound_manager = SoundManager()
    return _sound_manager


def init_sound_manager(enabled: bool = True, volume: float = 0.5) -> SoundManager:
    """Initialize and return the global sound manager."""
    global _sound_manager
    _sound_manager = SoundManager(enabled=enabled, volume=volume)
    return _sound_manager
