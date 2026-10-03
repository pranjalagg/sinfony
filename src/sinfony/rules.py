"""Melody rules: small penalty functions that shape note choices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .theory import Chord, Scale, pc


@dataclass(frozen=True)
class Context:
    """What a rule can see when judging a candidate pitch."""

    prev: tuple[int, ...]
    chord: Chord
    scale: Scale
    strength: float
    t: float
    section_end: bool
    cadence: str  # "authentic" or "none"


Rule = Callable[[Context, int], float]


def _named(rule: Rule, name: str) -> Rule:
    rule.__name__ = name
    return rule


def step_bias(w: float = 1.5) -> Rule:
    """Penalize leaps: w per semitone beyond a whole step."""

    def rule(ctx: Context, c: int) -> float:
        return w * max(0, abs(c - ctx.prev[-1]) - 2) if ctx.prev else 0.0

    return _named(rule, f"step_bias({w:g})")


def gap_fill(w: float = 4.0) -> Rule:
    """After a leap (> 4 semitones), penalize moving further the same way."""

    def rule(ctx: Context, c: int) -> float:
        if len(ctx.prev) < 2:
            return 0.0
        leap = ctx.prev[-1] - ctx.prev[-2]
        move = c - ctx.prev[-1]
        return w if abs(leap) > 4 and move * leap > 0 else 0.0

    return _named(rule, f"gap_fill({w:g})")


def range_limit(lo: int, hi: int, w: float = 100.0) -> Rule:
    def rule(ctx: Context, c: int) -> float:
        return w if c < lo or c > hi else 0.0

    return _named(rule, f"range_limit({lo},{hi})")


def avoid_repeat(w: float = 2.0, n: int = 2) -> Rule:
    """Penalize playing the same pitch more than ``n`` times in a row."""

    def rule(ctx: Context, c: int) -> float:
        recent = ctx.prev[-n:]
        return w if len(recent) == n and all(p == c for p in recent) else 0.0

    return _named(rule, f"avoid_repeat({w:g},{n})")


def resolve_leading_tone(w: float = 3.0) -> Rule:
    """The note a semitone below the tonic should rise to the tonic."""

    def rule(ctx: Context, c: int) -> float:
        if not ctx.prev:
            return 0.0
        last = ctx.prev[-1]
        if pc(last) == pc(ctx.scale.root - 1) and c != last + 1:
            return w
        return 0.0

    return _named(rule, f"resolve_leading_tone({w:g})")


def end_on_tonic(w: float = 20.0) -> Rule:
    """At an authentic cadence, the last note of the section should be the tonic."""

    def rule(ctx: Context, c: int) -> float:
        if ctx.section_end and ctx.cadence == "authentic" and pc(c) != pc(ctx.scale.root):
            return w
        return 0.0

    return _named(rule, f"end_on_tonic({w:g})")
