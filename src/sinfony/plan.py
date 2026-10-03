"""Form and global plan: sections, key areas, tempo, and the tension curve."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .curve import Curve, const, piecewise, pink
from .rng import Rng
from .theory import Scale

EPS = 1e-9


@dataclass(frozen=True)
class Section:
    index: int
    label: str
    base_label: str
    start: float
    end: float
    bars: int

    @property
    def length(self) -> float:
        return self.end - self.start


class Form:
    """Sections laid end to end, e.g. ``Form("A A' B A", bars=8)``."""

    def __init__(
        self, spec: str, bars: int | list[int] = 8, meter: tuple[int, int] = (4, 4)
    ):
        labels = spec.split()
        if not labels:
            raise ValueError("Form spec is empty")
        num, den = meter
        if num < 1 or den not in (1, 2, 4, 8, 16):
            raise ValueError(f"Unsupported meter {meter}")
        bar_list = [bars] * len(labels) if isinstance(bars, int) else list(bars)
        if len(bar_list) != len(labels):
            raise ValueError("bars list must match the number of sections")
        if any(b < 1 for b in bar_list):
            raise ValueError("each section needs at least 1 bar")
        self.spec = spec
        self.meter = (num, den)
        self.beats_per_bar = num * 4 / den
        sections, t = [], 0.0
        for i, (label, b) in enumerate(zip(labels, bar_list, strict=True)):
            end = t + b * self.beats_per_bar
            sections.append(Section(i, label, label.rstrip("'"), t, end, b))
            t = end
        self.sections = tuple(sections)
        self.total_beats = t

    def material_key(self, section: Section) -> str:
        """Sections share material when their base label and length match.

        A repeat with a different bar count gets its own material, keyed
        ``"A@3"``; the usual case keeps the plain base label.
        """
        first = next(s for s in self.sections if s.base_label == section.base_label)
        if first.bars == section.bars:
            return section.base_label
        return f"{section.base_label}@{section.bars}"

    def section_at(self, t: float) -> Section:
        for s in self.sections:
            if t < s.end - EPS:
                return s
        return self.sections[-1]

    def __repr__(self) -> str:
        return f"Form({self.spec!r}, meter={self.meter}, beats={self.total_beats:g})"


def default_tension(form: Form, rng: Rng) -> Curve:
    """Rise to a peak around 65% of the piece, then resolve; plus faint pink noise."""
    T = form.total_beats
    shape = piecewise([(0, 0.2), (0.65 * T, 1.0), (0.9 * T, 0.45), (T, 0.05)])
    return (shape + 0.05 * pink(rng, base=1 / 8)).clip(0.0, 1.0)


def dominant_key(key: Scale) -> Scale:
    """The key a fifth up, written a fourth down so the register stays put."""
    return Scale(key.root - 5, key.steps)


def relative_key(key: Scale) -> Scale:
    """Major <-> minor sharing the same notes (C major <-> A minor)."""
    if key.is_minor():
        return Scale.major(key.root + 3)
    return Scale.minor(key.root - 3)


class Plan:
    """Everything decided before any note: seed, key areas, form, tempo, tension."""

    def __init__(
        self,
        seed: int | str = 0,
        key: Scale | None = None,
        form: Form | None = None,
        tempo: float | Curve = 90.0,
        tension: Curve | None = None,
        modulate: bool = False,
    ):
        if not isinstance(tempo, Curve) and tempo <= 0:
            raise ValueError("tempo must be positive")
        self.seed = seed
        self.rng = Rng(seed)
        self.key = key or Scale.major(60)
        self.form = form or Form("A A' B A")
        self.tempo = tempo if isinstance(tempo, Curve) else const(tempo)
        _, bpm = self.tempo.sample(0.0, self.form.total_beats, 512)
        if np.any(bpm <= 0):
            raise ValueError("tempo must stay positive over the whole piece")
        self.tension = (
            tension
            if tension is not None
            else default_tension(self.form, self.rng.child("tension"))
        )
        self._keys = self._plan_keys(modulate, self.rng.child("keys"))

    def _plan_keys(self, modulate: bool, rng: Rng) -> dict[str, Scale]:
        keys: dict[str, Scale] = {}
        for s in self.form.sections:
            if s.base_label in keys:
                continue
            key = self.key
            if modulate and s.base_label == "B":
                mean_tension = float(np.mean(self.tension(np.linspace(s.start, s.end, 16))))
                if rng.random() < mean_tension:
                    key = rng.choice([dominant_key(self.key), relative_key(self.key)])
            keys[s.base_label] = key
        return keys

    @property
    def total_beats(self) -> float:
        return self.form.total_beats

    def section_key(self, section) -> Scale:
        return self._keys[section.base_label]

    def key_at(self, t: float) -> Scale:
        return self.section_key(self.form.section_at(t))
