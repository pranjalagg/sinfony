"""Continuous curves over time (in beats) that compose like math."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import numpy as np

ArrayFn = Callable[[np.ndarray], np.ndarray]


class Curve:
    """A vectorized function of time ``t`` (in beats).

    Curves combine with numbers and other curves, so
    ``0.6 * arch() + 0.3 * pink(rng)`` is itself a curve.
    """

    def __init__(self, f: ArrayFn, name: str = "curve"):
        self.f = f
        self.name = name

    def __call__(self, t):
        arr = np.asarray(t, dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):  # reported below
            out = np.broadcast_to(np.asarray(self.f(arr), dtype=float), arr.shape)
        if not np.all(np.isfinite(out)):
            raise ValueError(f"Curve '{self.name}' produced NaN or inf")
        if arr.ndim == 0:
            return float(out)
        return np.array(out)

    def __repr__(self) -> str:
        return f"Curve({self.name})"

    # --- arithmetic -----------------------------------------------------
    def _combine(self, other, op, sym: str, reverse: bool = False) -> Curve:
        o = lift(other)
        a, b = (o, self) if reverse else (self, o)
        return Curve(lambda t: op(a.f(t), b.f(t)), f"({a.name} {sym} {b.name})")

    def __add__(self, other):
        return self._combine(other, np.add, "+")

    def __radd__(self, other):
        return self._combine(other, np.add, "+", reverse=True)

    def __sub__(self, other):
        return self._combine(other, np.subtract, "-")

    def __rsub__(self, other):
        return self._combine(other, np.subtract, "-", reverse=True)

    def __mul__(self, other):
        return self._combine(other, np.multiply, "*")

    def __rmul__(self, other):
        return self._combine(other, np.multiply, "*", reverse=True)

    def __truediv__(self, other):
        return self._combine(other, np.divide, "/")

    def __rtruediv__(self, other):
        return self._combine(other, np.divide, "/", reverse=True)

    def __pow__(self, other):
        return self._combine(other, np.power, "**")

    def __rpow__(self, other):
        return self._combine(other, np.power, "**", reverse=True)

    def __neg__(self):
        return Curve(lambda t: -self.f(t), f"-{self.name}")

    def __abs__(self):
        return Curve(lambda t: np.abs(self.f(t)), f"|{self.name}|")

    # --- transforms -----------------------------------------------------
    def shift(self, dt: float) -> Curve:
        """Move the curve later in time by ``dt`` beats."""
        return Curve(lambda t: self.f(t - dt), f"{self.name}.shift({dt:g})")

    def stretch(self, k: float) -> Curve:
        """Slow the curve down by factor ``k`` (k > 1 makes it longer)."""
        if k <= 0:
            raise ValueError("stretch factor must be positive")
        return Curve(lambda t: self.f(t / k), f"{self.name}.stretch({k:g})")

    def clip(self, lo: float, hi: float) -> Curve:
        return Curve(lambda t: np.clip(self.f(t), lo, hi), f"{self.name}.clip")

    def remap(self, a: float, b: float, c: float, d: float) -> Curve:
        """Linear map of values from [a, b] to [c, d]."""
        if a == b:
            raise ValueError("remap needs a != b")
        return Curve(
            lambda t: c + (d - c) * (self.f(t) - a) / (b - a), f"{self.name}.remap"
        )

    def over(self, t0: float, t1: float) -> Curve:
        """Play a shape defined on [0, 1] across beats [t0, t1]; hold it outside."""
        if t1 <= t0:
            raise ValueError("over needs t1 > t0")
        return Curve(
            lambda t: self.f(np.clip((t - t0) / (t1 - t0), 0.0, 1.0)),
            f"{self.name}.over({t0:g},{t1:g})",
        )

    def tile(self, period: float) -> Curve:
        """Repeat a shape defined on [0, 1] every ``period`` beats."""
        if period <= 0:
            raise ValueError("tile period must be positive")
        return Curve(
            lambda t: self.f(np.mod(t, period) / period),
            f"{self.name}.tile({period:g})",
        )

    # --- inspection -----------------------------------------------------
    def sample(self, t0: float, t1: float, n: int = 256):
        t = np.linspace(t0, t1, n)
        return t, self(t)

    def show(self, t0: float = 0.0, t1: float = 1.0, n: int = 512):
        from .render.viz import plot_curve

        return plot_curve(self, t0, t1, n)


def lift(x) -> Curve:
    """Turn a number into a constant curve; pass curves through."""
    if isinstance(x, Curve):
        return x
    if isinstance(x, (int, float, np.integer, np.floating)):
        return const(float(x))
    raise TypeError(f"Cannot use {type(x).__name__} as a Curve")


# --- shapes -------------------------------------------------------------
def const(v: float) -> Curve:
    v = float(v)
    return Curve(lambda t: np.full(np.shape(t), v), f"{v:g}")


def sine(freq: float = 1.0, phase: float = 0.0) -> Curve:
    return Curve(lambda t: np.sin(2 * np.pi * (freq * t + phase)), f"sine({freq:g})")


def arch() -> Curve:
    """sin(pi*u) on [0, 1]: rises from 0 to 1 and falls back."""
    return Curve(lambda t: np.sin(np.pi * np.clip(t, 0.0, 1.0)), "arch")


def ramp() -> Curve:
    return Curve(lambda t: np.clip(t, 0.0, 1.0), "ramp")


def step(edges: Iterable[float], values: Iterable[float]) -> Curve:
    e = np.asarray(list(edges), dtype=float)
    v = np.asarray(list(values), dtype=float)
    if len(v) != len(e) + 1:
        raise ValueError("step needs len(values) == len(edges) + 1")
    if np.any(np.diff(e) <= 0):
        raise ValueError("step edges must be increasing")
    return Curve(lambda t: v[np.searchsorted(e, t, side="right")], "step")


def piecewise(points: Iterable[tuple[float, float]]) -> Curve:
    pts = sorted((float(x), float(y)) for x, y in points)
    if len(pts) < 2:
        raise ValueError("piecewise needs at least 2 points")
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    if np.any(np.diff(xs) <= 0):
        raise ValueError("piecewise x values must be distinct")
    return Curve(lambda t: np.interp(t, xs, ys), "piecewise")
