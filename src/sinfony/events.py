"""Discrete notes and the musical group actions on them."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .theory import Scale


@dataclass(frozen=True)
class Note:
    onset: float
    dur: float
    pitch: int
    vel: float = 0.7
    voice: str = "melody"

    @property
    def end(self) -> float:
        return self.onset + self.dur


def _sort_key(n: Note):
    return (n.onset, n.pitch, n.voice)


class Events(Sequence[Note]):
    """An immutable, time-sorted collection of notes with a time span."""

    def __init__(
        self, notes: Iterable[Note] = (), span: tuple[float, float] | None = None
    ):
        self._notes = tuple(sorted(notes, key=_sort_key))
        if span is None:
            if self._notes:
                span = (
                    min(n.onset for n in self._notes),
                    max(n.end for n in self._notes),
                )
            else:
                span = (0.0, 0.0)
        self.span = (float(span[0]), float(span[1]))

    # --- sequence protocol ----------------------------------------------
    def __len__(self) -> int:
        return len(self._notes)

    def __getitem__(self, i):
        return self._notes[i]

    def __iter__(self) -> Iterator[Note]:
        return iter(self._notes)

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Events)
            and self._notes == other._notes
            and self.span == other.span
        )

    __hash__ = None  # mutable-looking value semantics; not hashable

    def __repr__(self) -> str:
        return f"Events({len(self)} notes, span={self.span})"

    @property
    def length(self) -> float:
        return self.span[1] - self.span[0]

    @property
    def pitches(self) -> list[int]:
        return [n.pitch for n in self]

    # --- generic --------------------------------------------------------
    def map(self, fn: Callable[[Note], Note]) -> Events:
        return Events((fn(n) for n in self), self.span)

    def filter(self, pred: Callable[[Note], bool]) -> Events:
        return Events((n for n in self if pred(n)), self.span)

    # --- group actions --------------------------------------------------
    def transpose(self, k: int) -> Events:
        """Add ``k`` semitones to every pitch."""
        return self.map(lambda n: replace(n, pitch=n.pitch + int(k)))

    def transpose_diatonic(self, k: int, scale: Scale) -> Events:
        """Move every pitch ``k`` steps along ``scale`` (stays in key)."""
        return self.map(
            lambda n: replace(n, pitch=scale.degree(scale.degree_of(n.pitch) + k))
        )

    def invert(self, axis: float) -> Events:
        """Mirror pitches around ``axis``: p -> 2*axis - p."""
        twice = int(round(2 * axis))
        return self.map(lambda n: replace(n, pitch=twice - n.pitch))

    def retrograde(self) -> Events:
        """Play backwards in time within the span."""
        s, e = self.span
        return self.map(lambda n: replace(n, onset=s + e - n.end))

    def augment(self, k: float) -> Events:
        """Scale time by ``k`` around the span start (k=2 is twice as slow)."""
        if k <= 0:
            raise ValueError("augment factor must be positive")
        s, e = self.span
        notes = (replace(n, onset=s + (n.onset - s) * k, dur=n.dur * k) for n in self)
        return Events(notes, (s, s + (e - s) * k))

    def shift(self, dt: float) -> Events:
        s, e = self.span
        return Events((replace(n, onset=n.onset + dt) for n in self), (s + dt, e + dt))

    def __add__(self, other: Events) -> Events:
        """Concatenate: ``other`` starts where ``self`` ends."""
        moved = other.shift(self.span[1] - other.span[0])
        return Events(self._notes + moved._notes, (self.span[0], moved.span[1]))

    def __or__(self, other: Events) -> Events:
        """Overlay both sets of notes."""
        spans = [e.span for e in (self, other) if len(e) or e.span != (0.0, 0.0)]
        span = (
            (min(s for s, _ in spans), max(e for _, e in spans))
            if spans
            else (0.0, 0.0)
        )
        return Events(self._notes + other._notes, span)

    def by_voice(self) -> dict[str, Events]:
        groups: dict[str, list[Note]] = {}
        for n in self:
            groups.setdefault(n.voice, []).append(n)
        return {v: Events(ns, self.span) for v, ns in groups.items()}
