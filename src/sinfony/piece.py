"""Piece: runs Plan -> Harmony -> Voices -> Perform -> Render, caching each layer."""

from __future__ import annotations

from dataclasses import asdict
from functools import cached_property
from pathlib import Path

import numpy as np

from .curve import Curve, const
from .events import Events
from .harmony import ChordTrack
from .perform import Perform
from .plan import Plan, pad_positions
from .render.midi import save_midi
from .render.play import write_wav
from .render.synth import (
    EPIANO,
    INSTRUMENTS,
    Instrument,
    Reverb,
    beats_to_seconds,
    render,
)
from .rhythm import MeterGrid
from .theory import pc
from .voices import Voice, realize


def _r(x) -> float:
    return round(float(x), 6)


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
        meta: dict | None = None,
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
        self.meta = dict(meta or {})
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

    def to_json(self) -> dict:
        """Everything a browser needs to draw and play this piece (times also in seconds)."""
        plan, form = self.plan, self.plan.form
        T = plan.total_beats

        def secs(beats) -> list[float]:
            if len(beats) == 0:
                return []
            return [_r(s) for s in beats_to_seconds(self.tempo, beats)]

        events = list(self.events)
        on = secs([n.onset for n in events])
        off = secs([n.end for n in events])
        edges = secs([x for s in form.sections for x in (s.start, s.end)])
        chords = list(self.chords)
        chord_edges = secs([x for c in chords for x in (c.onset, c.end)])

        voice_instrument: dict[str, str] = {}
        instruments: dict[str, dict] = {}
        for v in self.voices:
            inst = (
                self.instruments.get(v.name, EPIANO)
                if isinstance(self.instruments, dict)
                else self.instruments
            )
            name = next((k for k, i in INSTRUMENTS.items() if i == inst), f"custom:{v.name}")
            voice_instrument[v.name] = name
            instruments[name] = asdict(inst)

        shape = self.meta.get("contour_shape")
        if shape is None:
            melodic = next((v for v in self.voices if v.contour is not None), None)
            shape = melodic.contour if melodic is not None else const(0.5)
        contour_pads: dict[str, list[float]] = {}
        for s in form.sections:
            key = form.material_key(s)
            if key not in contour_pads:
                contour_pads[key] = [_r(v) for v in np.clip(shape(pad_positions(s)), 0.0, 1.0)]
        tension_pads = [
            _r(v)
            for s in form.sections
            for v in np.clip(plan.tension(pad_positions(s)), 0.0, 1.0)
        ]
        reverb = (
            {"seconds": _r(self.reverb.seconds), "mix": _r(self.reverb.mix), "seed": int(self.reverb.seed)}
            if self.reverb is not None
            else {"seconds": 0.0, "mix": 0.0, "seed": 0}
        )
        return {
            "version": 1,
            "style": self.meta.get("style", "custom"),
            "seed": self.meta.get("seed", plan.seed),
            "key": {"root": int(plan.key.root), "mode": plan.key.name, "pc": pc(plan.key.root)},
            "meter": [int(x) for x in form.meter],
            "beats_per_bar": _r(form.beats_per_bar),
            "total_beats": _r(T),
            "duration_s": _r(self.duration),
            "beat_s": secs(np.arange(int(np.floor(T)) + 1, dtype=float)),
            "sections": [
                {
                    "label": s.label,
                    "base": s.base_label,
                    "material": form.material_key(s),
                    "start": _r(s.start),
                    "end": _r(s.end),
                    "start_s": edges[2 * i],
                    "end_s": edges[2 * i + 1],
                }
                for i, s in enumerate(form.sections)
            ],
            "chords": [
                {
                    "onset": _r(c.onset),
                    "dur": _r(c.dur),
                    "label": str(c.chord),
                    "pcs": sorted(int(p) for p in c.chord.pcs),
                    "function": c.function,
                    "onset_s": chord_edges[2 * i],
                    "dur_s": _r(chord_edges[2 * i + 1] - chord_edges[2 * i]),
                }
                for i, c in enumerate(chords)
            ],
            "notes": [
                {
                    "voice": n.voice,
                    "pitch": int(n.pitch),
                    "vel": _r(n.vel),
                    "onset": _r(n.onset),
                    "dur": _r(n.dur),
                    "onset_s": on[i],
                    "dur_s": _r(off[i] - on[i]),
                }
                for i, n in enumerate(events)
            ],
            "voices": [
                {
                    "name": v.name,
                    "role": v.role,
                    "register": [int(v.register[0]), int(v.register[1])],
                    "instrument": voice_instrument[v.name],
                }
                for v in self.voices
            ],
            "instruments": instruments,
            "reverb": reverb,
            "pads": {"contour": contour_pads, "tension": tension_pads},
            "params": dict(self.meta.get("params", {})),
        }

    def __repr__(self) -> str:
        return (
            f"Piece({self.plan.form.spec!r}, key={self.plan.key.name} "
            f"{self.plan.key.root}, voices={[v.name for v in self.voices]})"
        )
