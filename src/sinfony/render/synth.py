"""Additive synthesis: every timbre is a sum of decaying sine partials."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..curve import Curve
from ..events import Events
from ..theory import freq

SR = 44100


@dataclass(frozen=True)
class Instrument:
    """Partials are (frequency ratio, amplitude, decay per second).

    ``inharmonicity`` is the string-stiffness constant B: partial n sounds at
    n*f0*sqrt(1 + B*n^2), slightly sharp, as on a real piano.
    """

    partials: tuple[tuple[float, float, float], ...]
    attack: float = 0.005
    release: float = 0.1
    inharmonicity: float = 0.0
    hammer: float = 0.0
    detune_cents: float = 0.0
    gain: float = 1.0


SINE = Instrument(((1.0, 1.0, 0.0),), attack=0.01, release=0.05)
EPIANO = Instrument(
    ((1, 1.0, 1.2), (2, 0.5, 1.8), (3, 0.25, 2.6), (4, 0.14, 3.4), (5, 0.08, 4.2), (6, 0.05, 5.0)),
    attack=0.003,
    release=0.15,
    inharmonicity=0.0004,
    hammer=0.04,
)
PAD = Instrument(
    ((1, 1.0, 0.05), (2, 0.45, 0.08), (3, 0.22, 0.12), (4, 0.12, 0.18)),
    attack=1.2,
    release=2.0,
    detune_cents=6.0,
    gain=0.6,
)
BELL = Instrument(
    ((1, 1.0, 0.7), (2.76, 0.6, 1.1), (5.4, 0.4, 1.7), (8.93, 0.25, 2.4)),
    attack=0.001,
    release=0.6,
    gain=0.7,
)


def render_note(inst: Instrument, pitch: int, vel: float, dur_s: float, sr: int = SR) -> np.ndarray:
    n = max(1, int(round((dur_s + inst.release) * sr)))
    t = np.arange(n) / sr
    f0 = freq(pitch)
    y = np.zeros(n)
    detunes = (0.0,) if inst.detune_cents == 0 else (-inst.detune_cents, inst.detune_cents)
    for ratio, amp, decay in inst.partials:
        f = f0 * ratio * np.sqrt(1.0 + inst.inharmonicity * ratio**2)
        for cents in detunes:
            fc = f * 2.0 ** (cents / 1200)
            if fc < sr / 2:
                y += (amp / len(detunes)) * np.sin(2 * np.pi * fc * t) * np.exp(-decay * t)
    if inst.hammer > 0:
        burst = np.random.default_rng(int(pitch)).standard_normal(n) * np.exp(-t / 0.004)
        y += inst.hammer * np.convolve(burst, np.ones(8) / 8, mode="same")
    env = np.minimum(1.0, t / inst.attack) if inst.attack > 0 else np.ones(n)
    if inst.release > 0:
        env = env * np.clip(1.0 - (t - dur_s) / inst.release, 0.0, 1.0)
    else:
        env = env * (t <= dur_s)
    return (y * env * inst.gain * vel**1.5).astype(np.float32)


def beats_to_seconds(tempo: Curve, beats) -> np.ndarray:
    """Seconds at each beat position: the integral of 60 / tempo(t) dt."""
    b = np.asarray(beats, dtype=float)
    top = float(np.max(b)) if b.size else 0.0
    grid = np.linspace(0.0, max(top, 1e-9), max(2, int(np.ceil(top * 64)) + 1))
    bpm = tempo(grid)
    if np.any(bpm <= 0):
        raise ValueError("tempo must stay positive")
    spb = 60.0 / bpm
    secs = np.concatenate([[0.0], np.cumsum((spb[1:] + spb[:-1]) / 2 * np.diff(grid))])
    return np.interp(b, grid, secs)


@dataclass(frozen=True)
class Reverb:
    """Convolution with exponentially decaying noise (-60 dB after ``seconds``)."""

    seconds: float = 1.5
    mix: float = 0.25
    seed: int = 0

    def impulse(self, sr: int = SR) -> np.ndarray:
        n = max(1, int(self.seconds * sr))
        t = np.arange(n) / sr
        ir = np.random.default_rng(self.seed).standard_normal(n) * np.exp(-6.91 * t / self.seconds)
        return ir / np.sqrt(np.sum(ir**2))

    def apply(self, y: np.ndarray, sr: int = SR) -> np.ndarray:
        ir = self.impulse(sr)
        size = len(y) + len(ir) - 1
        nfft = 1 << (size - 1).bit_length()
        wet = np.fft.irfft(np.fft.rfft(y, nfft) * np.fft.rfft(ir, nfft), nfft)[:size]
        dry = np.concatenate([y, np.zeros(len(ir) - 1)])
        return (1 - self.mix) * dry + self.mix * wet


def render(
    events: Events,
    tempo: Curve,
    instruments: Instrument | dict[str, Instrument] = EPIANO,
    reverb: Reverb | None = None,
    sr: int = SR,
) -> np.ndarray:
    def inst_for(voice: str) -> Instrument:
        if isinstance(instruments, dict):
            return instruments.get(voice, EPIANO)
        return instruments

    end_s = float(beats_to_seconds(tempo, [events.span[1]])[0])
    if len(events) == 0:
        return np.zeros(max(1, int(np.ceil(end_s * sr))), dtype=np.float32)
    ons = beats_to_seconds(tempo, [n.onset for n in events])
    offs = beats_to_seconds(tempo, [n.end for n in events])
    tail = max(inst_for(n.voice).release for n in events)
    total = int(np.ceil((max(end_s, float(offs.max())) + tail) * sr)) + 1
    out = np.zeros(total)
    for n, a, b in zip(events, ons, offs, strict=True):
        buf = render_note(inst_for(n.voice), n.pitch, n.vel, b - a, sr)
        i = int(round(a * sr))
        j = min(total, i + len(buf))
        out[i:j] += buf[: j - i]
    if reverb is not None:
        out = reverb.apply(out, sr)
    if not np.all(np.isfinite(out)):
        raise ValueError("synth produced non-finite audio")
    peak = float(np.max(np.abs(out)))
    if peak > 0:
        out = 0.98 * np.tanh(1.5 * out / peak) / np.tanh(1.5)
    return out.astype(np.float32)
