#!/usr/bin/env python3
"""Generate a completion chime WAV file using only Python standard library.

This script generates a pleasant short chime sound for batch completion notifications.
The generated WAV file is MIT-compatible and safe for distribution.

Usage:
    python tools/generate_chime.py

Output:
    katrain/sounds/complete_chime.wav
"""

import math
import struct
import wave
from pathlib import Path


def generate_chime(
    filename: str,
    duration: float = 0.4,
    sample_rate: int = 44100,
) -> None:
    """Generate a pleasant completion chime (A major chord with decay).

    Args:
        filename: Output WAV file path
        duration: Duration in seconds
        sample_rate: Sample rate in Hz
    """
    # A major chord: A5 (880 Hz), C#6 (1108.7 Hz), E6 (1318.5 Hz)
    frequencies = [880.0, 1108.73, 1318.51]
    n_samples = int(sample_rate * duration)

    samples = []
    for i in range(n_samples):
        t = i / sample_rate

        # Envelope: quick attack (0.02s), smooth exponential decay
        attack_time = 0.02
        if t < attack_time:
            envelope = t / attack_time
        else:
            envelope = math.exp(-5 * (t - attack_time))

        # Mix frequencies with slight detuning for warmth
        sample = 0.0
        for j, freq in enumerate(frequencies):
            # Add very slight detuning for richness
            detune = 1.0 + (j - 1) * 0.001
            sample += math.sin(2 * math.pi * freq * detune * t)

        # Normalize and apply envelope
        sample = sample / len(frequencies) * envelope * 0.6

        # Convert to 16-bit integer
        sample_int = int(sample * 32767)
        # Clamp to valid range
        sample_int = max(-32768, min(32767, sample_int))
        samples.append(sample_int)

    # Write WAV file
    with wave.open(filename, "w") as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def main() -> None:
    """Generate the chime and save to katrain/sounds/."""
    # Determine output path relative to script location
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    output_path = repo_root / "katrain" / "sounds" / "complete_chime.wav"

    # Ensure sounds directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generate_chime(str(output_path))
    print(f"Generated: {output_path}")
    print(f"File size: {output_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
