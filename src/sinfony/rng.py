"""Seeded randomness with independent per-layer streams."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

import numpy as np


def _key(seed: int | str) -> int:
    digest = hashlib.sha256(str(seed).encode()).digest()
    return int.from_bytes(digest[:8], "little")


class Rng:
    """A seeded random stream.

    ``child(name)`` derives a new stream from this stream's seed and the name
    only. Drawing numbers in one layer therefore never changes another layer.
    """

    def __init__(self, seed: int | str = 0):
        self.seed = seed
        self.key = _key(seed)
        self.gen = np.random.default_rng(self.key)

    def child(self, name: str) -> Rng:
        return Rng(f"{self.key}/{name}")

    def random(self, size=None):
        return self.gen.random(size)

    def uniform(self, lo: float, hi: float, size=None):
        return self.gen.uniform(lo, hi, size)

    def integers(self, lo: int, hi: int, size=None):
        return self.gen.integers(lo, hi, size)

    def choice(self, items: Sequence[Any], p=None) -> Any:
        if len(items) == 0:
            raise ValueError("Cannot choose from an empty sequence")
        return items[int(self.gen.choice(len(items), p=p))]

    def __repr__(self) -> str:
        return f"Rng({self.seed!r})"
