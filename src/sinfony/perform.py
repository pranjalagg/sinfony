"""Performance: the human touch as curves (phrase arcs, ritardando, jitter)."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .curve import Curve, pink
from .events import Events
from .plan import Plan
from .rhythm import MeterGrid
from .rng import Rng


@dataclass
class Perform:
    """Todd's phrase-arc model plus a final ritardando and pink-noise timing."""

    jitter_ms: float = 8.0
    phrase_bars: int = 4
    tempo_arc: float = 0.06
    ritard: float = 0.25
    ritard_bars: int = 2
    dyn_depth: float = 0.3

    def arc(self, plan: Plan) -> Curve:
        """0 at phrase edges, 1 mid-phrase: 1 - 4(u - 1/2)^2."""
        L = self.phrase_bars * plan.form.beats_per_bar
        return Curve(lambda t: 1.0 - 4.0 * (np.mod(t, L) / L - 0.5) ** 2, "phrase_arc")

    def tempo(self, plan: Plan) -> Curve:
        """Push forward mid-phrase, and slow down over the final bars."""
        T = plan.total_beats
        R = min(self.ritard_bars * plan.form.beats_per_bar, T)
        rit = Curve(
            lambda t: 1.0 - self.ritard * np.clip((t - (T - R)) / R, 0.0, 1.0) ** 2,
            "ritard",
        )
        return plan.tempo * (1.0 + self.tempo_arc * (self.arc(plan) - 0.5)) * rit

    def apply(
        self, score: Events, plan: Plan, grid: MeterGrid, rng: Rng
    ) -> tuple[Events, Curve]:
        tempo = self.tempo(plan)
        arc = self.arc(plan)
        jitter: dict[str, Curve] = {}
        out = []
        for n in score:
            if n.voice not in jitter:
                jitter[n.voice] = pink(rng.child(n.voice), base=1 / 4)
            accent = 0.85 + 0.15 * grid.strength(n.onset)
            dyn = (1 - self.dyn_depth) + self.dyn_depth * float(arc(n.onset))
            tens = 0.7 + 0.3 * float(plan.tension(n.onset))
            vel = float(np.clip(n.vel * accent * dyn * tens, 0.05, 1.0))
            seconds = self.jitter_ms / 1000.0 * float(jitter[n.voice](n.onset))
            onset = max(score.span[0], n.onset + seconds * float(tempo(n.onset)) / 60.0)
            out.append(replace(n, onset=onset, vel=vel))
        return Events(out, score.span), tempo
