"""Harmony: chord progressions generated from functions, lattices, or by hand."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass

import numpy as np

from .curve import Curve
from .plan import Plan, Section
from .rng import Rng
from .theory import Chord, L, P, R, Scale, numeral_function, parse_roman


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
        key = plan.form.material_key(sec)
        if key not in cache:
            cache[key] = make(sec, rng.child(f"section:{key}"))
        for s in cache[key]:
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


# --- functional harmony -----------------------------------------------------
FUNCTIONS = {
    "major": {
        "T": [("I", 0.7), ("vi", 0.3)],
        "S": [("IV", 0.6), ("ii", 0.4)],
        "D": [("V", 0.8), ("vii°", 0.2)],
    },
    "minor": {
        "T": [("i", 0.7), ("VI", 0.3)],
        "S": [("iv", 0.6), ("ii°", 0.4)],
        "D": [("V", 0.8), ("vii°", 0.2)],
    },
}
# Probability of the next harmonic function given the current one.
TRANSITIONS = {
    "T": {"T": 0.2, "S": 0.5, "D": 0.3},
    "S": {"T": 0.1, "S": 0.2, "D": 0.7},
    "D": {"T": 0.8, "S": 0.05, "D": 0.15},
}

Slot = tuple[float, float, tuple[str, str] | None]


class Functional:
    """Tonic -> pre-dominant -> dominant -> tonic as a Markov chain, with cadences.

    Higher tension makes dominant chords (and secondary dominants V/V) more
    likely. Each section opens on the tonic, has a half cadence (V) in the
    middle, and closes with an authentic cadence (V -> I).
    """

    def __init__(self, rhythm: Curve | None = None):
        self.rhythm = rhythm

    def generate(self, plan: Plan, rng: Rng) -> ChordTrack:
        bpb = plan.form.beats_per_bar

        def make(sec: Section, srng: Rng) -> list[ChordSpan]:
            key = plan.section_key(sec)
            table = FUNCTIONS["minor" if key.is_minor() else "major"]
            tonic, pre, dom = table["T"][0][0], table["S"][0][0], "V"
            out: list[ChordSpan] = []
            prev_fn, prev_num = "T", None
            for onset, dur, forced in self._slots(sec, bpb, tonic, pre, dom):
                tension = float(plan.tension(sec.start + onset))
                if forced is not None:
                    num, fn = forced
                elif prev_num == "V/V":
                    num, fn = "V", "D"
                else:
                    fn = self._next_function(prev_fn, tension, srng)
                    num = self._pick(table[fn], prev_num, srng)
                    if fn == "S" and tension > 0.5 and srng.random() < tension - 0.5:
                        num = "V/V"
                out.append(ChordSpan(onset, dur, parse_roman(num, key), fn))
                prev_fn, prev_num = fn, num
            return out

        return self._prime(by_section(plan, rng, make), plan)

    def _slots(self, sec: Section, bpb: float, tonic: str, pre: str, dom: str):
        n = sec.bars
        cad_end = n - 1
        cad_half = n // 2 - 1 if n >= 4 else None
        T, S, D = (tonic, "T"), (pre, "S"), (dom, "D")
        slots: list[Slot] = []
        for b in range(n):
            t0 = b * bpb
            if b == cad_end:
                halves = [T]
            elif b == cad_half:
                halves = [D]
            elif b + 1 == cad_end:
                halves = [S, D]
            elif cad_half is not None and b + 1 == cad_half:
                halves = [None, S]
            elif self.rhythm is not None and float(self.rhythm(sec.start + t0)) >= 1.5:
                halves = [None, None]
            else:
                halves = [None]
            if b == 0 and b != cad_end:
                halves[0] = T
            dur = bpb / len(halves)
            slots += [(t0 + i * dur, dur, h) for i, h in enumerate(halves)]
        return slots

    @staticmethod
    def _next_function(prev: str, tension: float, rng: Rng) -> str:
        w = dict(TRANSITIONS[prev])
        w["D"] *= 1.0 + tension
        w["T"] *= 1.5 - tension
        names = list(w)
        p = np.array([w[k] for k in names])
        return rng.choice(names, p=p / p.sum())

    @staticmethod
    def _pick(options, prev: str | None, rng: Rng) -> str:
        opts = [(n, w) for n, w in options if n != prev] or list(options)
        names = [n for n, _ in opts]
        p = np.array([w for _, w in opts])
        return rng.choice(names, p=p / p.sum())

    @staticmethod
    def _prime(track: ChordTrack, plan: Plan) -> ChordTrack:
        """Primed sections (A') that are not last end deceptively on vi."""
        spans = list(track)
        last = len(plan.form.sections) - 1
        for sec in plan.form.sections:
            if sec.label == sec.base_label or sec.index == last:
                continue
            key = plan.section_key(sec)
            deceptive = "VI" if key.is_minor() else "vi"
            for i, s in enumerate(spans):
                if abs(s.end - sec.end) < 1e-9:
                    spans[i] = ChordSpan(s.onset, s.dur, parse_roman(deceptive, key), "T")
        return ChordTrack(spans)


# --- Tonnetz walk -------------------------------------------------------------
def home_chord(key: Scale) -> Chord:
    """Tonic triad: major if the key has a major third above the tonic, else minor."""
    quality = "maj" if key.contains(key.root + 4) else "min"
    return Chord.build(key.root, quality)


class TonnetzWalk:
    """A random walk on the Tonnetz: each move is P, L, or R.

    These moves keep two common tones and shift one note by a step, so the
    harmony drifts smoothly. Moves that stay inside the key are preferred.
    """

    def __init__(self, rate: Curve | None = None, bars_per_chord: tuple[int, int] = (2, 4)):
        lo, hi = bars_per_chord
        if lo < 1 or hi < lo:
            raise ValueError("bars_per_chord needs 1 <= lo <= hi")
        self.rate = rate
        self.bars_per_chord = (lo, hi)

    def generate(self, plan: Plan, rng: Rng) -> ChordTrack:
        bpb = plan.form.beats_per_bar
        lo, hi = self.bars_per_chord

        def make(sec: Section, srng: Rng) -> list[ChordSpan]:
            key = plan.section_key(sec)
            chord = home_chord(key)
            t, out = 0.0, []
            while t < sec.length - 1e-9:
                bars = int(srng.integers(lo, hi + 1))
                dur = min(bars * bpb, sec.length - t)
                if out:
                    at = sec.start + t
                    p = (
                        float(self.rate(at))
                        if self.rate is not None
                        else 0.3 + 0.6 * float(plan.tension(at))
                    )
                    if srng.random() < p:
                        chord = self._move(chord, key, srng)
                out.append(ChordSpan(t, dur, chord, "other"))
                t += dur
            if plan.form.material_key(sec) == final_key:  # the piece ends at home
                end = out[-1]
                out[-1] = ChordSpan(end.onset, end.dur, home_chord(key), end.function)
            return out

        final_key = plan.form.material_key(plan.form.sections[-1])
        return by_section(plan, rng, make)

    @staticmethod
    def _move(chord: Chord, key: Scale, rng: Rng) -> Chord:
        moves = [P(chord), L(chord), R(chord)]
        fits = [len(c.pcs & key.pcs) for c in moves]
        best = max(fits)
        return rng.choice([c for c, f in zip(moves, fits, strict=True) if f == best])
