"""Playback: inline in notebooks, through speakers, or to a WAV file."""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path

import numpy as np

from .synth import SR


def in_notebook() -> bool:
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    ip = get_ipython()
    return ip is not None and "IPKernelApp" in getattr(ip, "config", {})


def write_wav(path, audio: np.ndarray, sr: int = SR) -> Path:
    path = Path(path)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def play(audio: np.ndarray, sr: int = SR) -> None:
    if in_notebook():
        from IPython.display import Audio, display

        display(Audio(audio, rate=sr))
        return
    try:
        import sounddevice as sd
    except (ImportError, OSError):
        sd = None
    if sd is not None:
        sd.play(audio, sr)
        sd.wait()
        return
    path = write_wav(Path(tempfile.gettempdir()) / "sinfony-play.wav", audio, sr)
    print(f"sounddevice not available; wrote {path}")
