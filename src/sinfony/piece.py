"""Piece: runs Plan -> Harmony -> Voices -> Perform -> Render, caching each layer."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

import numpy as np

from .curve import Curve
from .events import Events
from .harmony import ChordTrack
from .perform import Perform
from .plan import Plan
from .render.midi import save_midi
from .render.play import write_wav
from .render.synth import EPIANO, Instrument, Reverb, beats_to_seconds, render
from .rhythm import MeterGrid
from .voices import Voice, realize

_DEFAULT_REVERB = Reverb()


class Piece:
    def __init__(
        self,
        plan: Plan,
        harmony,
        voices: list[Voice],
        perform: Perform | None = None,
        instruments: Instrument | dict[str, Instrument] = EPIANO,
        reverb: Reverb | None = _DEFAULT_REVERB,
    ):
        names = [v.name for v in voices]
        if not names:
            raise ValueError("a piece needs at least one voice")
        if len(set(names)) != len(names):
            raise ValueError(f"voice names must be unique, got {names}")
        self.plan = plan
        self.harmony = harmony
        self.voices = list(voices)
        self.perform = perform if perform is not None else Perform()
        self.instruments = instruments
        self.reverb = reverb
        self.grid = MeterGrid(plan.form.meter)

    @cached_property
    def chords(self) -> ChordTrack:
        return self.harmony.generate(self.plan, self.plan.rng.child("harmony"))

    @cached_property
    def score(self) -> Events:
        out = Events(span=(0.0, self.plan.total_beats))
        for v in self.voices:
            rng = self.plan.rng.child(f"voice:{v.name}")
            out = out | realize(v, self.plan, self.chords, self.grid, rng)
        return out

    @cached_property
    def _performed(self) -> tuple[Events, Curve]:
        return self.perform.apply(
            self.score, self.plan, self.grid, self.plan.rng.child("perform")
        )

    @property
    def events(self) -> Events:
        return self._performed[0]

    @property
    def tempo(self) -> Curve:
        return self._performed[1]

    @property
    def duration(self) -> float:
        return float(beats_to_seconds(self.tempo, [self.plan.total_beats])[0])

    def voice(self, name: str) -> Events:
        return self.score.filter(lambda n: n.voice == name)

    @cached_property
    def _audio(self) -> np.ndarray:
        return render(self.events, self.tempo, self.instruments, self.reverb)

    def audio(self) -> np.ndarray:
        return self._audio

    def play(self) -> None:
        from .render import play as _play

        _play.play(self.audio())

    def show(self, save=None):
        from .render.viz import piano_roll

        return piano_roll(self, save=save)

    def save_wav(self, path) -> Path:
        return write_wav(path, self.audio())

    def save_midi(self, path) -> Path:
        return save_midi(self.events, self.tempo, path)

    def __repr__(self) -> str:
        return (
            f"Piece({self.plan.form.spec!r}, key={self.plan.key.name} "
            f"{self.plan.key.root}, voices={[v.name for v in self.voices]})"
        )
