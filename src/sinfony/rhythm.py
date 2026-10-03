"""Meter and rhythm generators."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from .curve import Curve, lift
from .rng import Rng

EPS = 1e-6


class MeterGrid:
    """Metric hierarchy: downbeat > mid-bar > beat > subdivision > other."""

    def __init__(self, meter: tuple[int, int] = (4, 4)):
        num, den = meter
        self.meter = (num, den)
        self.beats_per_bar = num * 4 / den
        compound = den == 8 and num % 3 == 0 and num > 3
        self.beat = 1.5 if compound else 4 / den
        self.sub = self.beat / 3 if compound else self.beat / 2
        self._even = (num // 3 if compound else num) % 2 == 0 and num > 2

    @staticmethod
    def _on(x: float, unit: float) -> bool:
        r = x % unit
        return r < EPS or unit - r < EPS

    def strength(self, t: float) -> float:
        pos = float(t) % self.beats_per_bar
        if self._on(pos, self.beats_per_bar):
            return 1.0
        if self._even and self._on(pos, self.beats_per_bar / 2):
            return 0.75
        if self._on(pos, self.beat):
            return 0.5
        if self._on(pos, self.sub):
            return 0.25
        return 0.1


Rhythm = Callable[[float, float, MeterGrid, Rng], list[tuple[float, float]]]


def _fill(onsets: list[float], end: float, cap: float | None) -> list[tuple[float, float]]:
    """Each note lasts until the next onset (or ``end``), optionally capped."""
    out = []
    for j, t in enumerate(onsets):
        nxt = onsets[j + 1] if j + 1 < len(onsets) else end
        d = nxt - t
        out.append((t, min(d, cap) if cap is not None else d))
    return out


class _Every:
    def __init__(self, step: float, dur: float | None):
        if step <= 0:
            raise ValueError("step must be positive")
        self.step, self.dur = step, dur

    def __call__(self, start, end, grid, rng):
        n = int(np.ceil((end - start) / self.step - EPS))
        return [(start + i * self.step, self.dur or self.step) for i in range(n)]


def every(step: float = 1.0, dur: float | None = None) -> Rhythm:
    """A note every ``step`` beats."""
    return _Every(step, dur)


def euclid_pattern(k: int, n: int, rotate: int = 0) -> list[int]:
    """``k`` hits spread as evenly as possible over ``n`` steps.

    Uses the Bresenham form ``(i*k) mod n < k``, which yields Bjorklund's
    Euclidean rhythms up to rotation. E(3, 8) is the Cuban tresillo.
    """
    if n < 1 or not 0 <= k <= n:
        raise ValueError("euclid needs n >= 1 and 0 <= k <= n")
    pat = [1 if (i * k) % n < k else 0 for i in range(n)]
    r = rotate % n
    return pat[r:] + pat[:r]


class _Euclid:
    def __init__(self, k, n, rotate, step, dur):
        if step <= 0:
            raise ValueError("step must be positive")
        self.pattern = euclid_pattern(k, n, rotate)
        self.step, self.dur = step, dur

    def __call__(self, start, end, grid, rng):
        n = len(self.pattern)
        first = int(np.ceil(start / self.step - EPS))
        last = int(np.ceil(end / self.step - EPS))
        onsets = [i * self.step for i in range(first, last) if self.pattern[i % n]]
        if self.dur is None:
            return _fill(onsets, end, None)
        return [(t, min(self.dur, end - t)) for t in onsets]


def euclid(
    k: int, n: int, rotate: int = 0, step: float = 0.5, dur: float | None = None
) -> Rhythm:
    """Euclidean rhythm E(k, n) on a grid of ``step`` beats, phased from beat 0."""
    return _Euclid(k, n, rotate, step, dur)


class _Density:
    def __init__(self, curve: Curve, step: float, max_dur: float | None):
        if step <= 0:
            raise ValueError("step must be positive")
        self.curve, self.step, self.max_dur = curve, step, max_dur

    def __call__(self, start, end, grid, rng):
        n = int(np.ceil((end - start) / self.step - EPS))
        onsets = []
        for i in range(n):
            t = start + i * self.step
            p = float(np.clip(self.curve(t), 0.0, 1.0)) * grid.strength(t)
            if rng.random() < p:  # always draw, so the stream stays aligned
                onsets.append(t)
        return _fill(onsets, end, self.max_dur)


def density(curve, step: float = 0.5, max_dur: float | None = None) -> Rhythm:
    """Onset probability at each grid step = density(t) x beat strength(t)."""
    return _Density(lift(curve), step, max_dur)
