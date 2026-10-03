"""Harmony: chord progressions generated from functions, lattices, or by hand."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass

import numpy as np

from .plan import Plan, Section
from .rng import Rng
from .theory import Chord, Scale, numeral_function, parse_roman


@dataclass(frozen=True)
class ChordSpan:
    onset: float
    dur: float
    chord: Chord
    function: str = "other"

    @property
    def end(self) -> float:
        return self.onset + self.dur


class ChordTrack(Sequence[ChordSpan]):
    """Chords laid out in time."""

    def __init__(self, spans: Iterable[ChordSpan]):
        self._spans = tuple(sorted(spans, key=lambda s: s.onset))
        if not self._spans:
            raise ValueError("ChordTrack needs at least one span")
        self._onsets = np.array([s.onset for s in self._spans])

    def __len__(self) -> int:
        return len(self._spans)

    def __getitem__(self, i):
        return self._spans[i]

    def __iter__(self) -> Iterator[ChordSpan]:
        return iter(self._spans)

    def __eq__(self, other) -> bool:
        return isinstance(other, ChordTrack) and self._spans == other._spans

    __hash__ = None

    def __repr__(self) -> str:
        return f"ChordTrack({len(self)} chords)"

    def at(self, t: float) -> ChordSpan:
        i = int(np.searchsorted(self._onsets, t + 1e-9, side="right")) - 1
        return self._spans[max(i, 0)]

    def show(self):
        from .render.viz import plot_chords

        return plot_chords(self)


MakeSection = Callable[[Section, Rng], list[ChordSpan]]


def by_section(plan: Plan, rng: Rng, make: MakeSection) -> ChordTrack:
    """Generate chords once per base label and reuse them for repeats."""
    cache: dict[str, list[ChordSpan]] = {}
    spans = []
    for sec in plan.form.sections:
        if sec.base_label not in cache:
            cache[sec.base_label] = make(sec, rng.child(f"section:{sec.base_label}"))
        for s in cache[sec.base_label]:
            spans.append(ChordSpan(s.onset + sec.start, s.dur, s.chord, s.function))
    return ChordTrack(spans)


class Fixed:
    """A hand-written progression of Roman numerals, repeated across the form."""

    def __init__(self, numerals: list[str], per_bar: int = 1):
        if not numerals:
            raise ValueError("Fixed needs at least one numeral")
        if per_bar < 1:
            raise ValueError("per_bar must be >= 1")
        for n in numerals:
            parse_roman(n, Scale.major(60))  # fail early on typos
        self.numerals = list(numerals)
        self.per_bar = per_bar

    def generate(self, plan: Plan, rng: Rng) -> ChordTrack:
        dur = plan.form.beats_per_bar / self.per_bar

        def make(sec: Section, _rng: Rng) -> list[ChordSpan]:
            key = plan.section_key(sec)
            out = []
            for i in range(sec.bars * self.per_bar):
                num = self.numerals[i % len(self.numerals)]
                out.append(
                    ChordSpan(i * dur, dur, parse_roman(num, key), numeral_function(num))
                )
            return out

        return by_section(plan, rng, make)
