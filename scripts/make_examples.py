"""Write web/examples.json: the playground's one-click examples.

Every "listen" line is checked against the engine in tests/test_examples.py.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from sinfony import web

ROOT = Path(__file__).resolve().parent.parent
P = web.PAD_POINTS
SEEDS = {"rise": 0, "storm": 5, "steps": 3, "dark": 4, "chance": 7}
DARK_ROOT = 2


def q(v: float) -> float:
    """Round to one of the 64 levels a share link can store."""
    return round(min(1.0, max(0.0, v)) * 63) / 63


def sections(style: str, seed: int):
    return web.build({"style": style, "seed": seed}).plan.form.sections


def build() -> list[dict]:
    seed = SEEDS["rise"]
    arch = [q(0.1 + 0.8 * math.sin(math.pi * i / (P - 1))) for i in range(P)]
    rise = {
        "style": "tonal", "seed": seed, "contour": {"A": arch},
        "tension": [q(0.2)] * (P * len(sections("tonal", seed))),
        "wiggle": 0.05, "smooth": 0.5,
    }

    seed = SEEDS["storm"]
    levels = {"A": 0.1, "A'": 0.1, "B": 0.95}
    storm = {
        "style": "tonal", "seed": seed,
        "tension": [
            q(levels.get(s.label, 0.3) if i < len(sections("tonal", seed)) - 1 else 0.3)
            for i, s in enumerate(sections("tonal", seed))
            for _ in range(P)
        ],
    }

    seed = SEEDS["steps"]
    steps = {"style": "tonal", "seed": seed, "wiggle": 1, "smooth": 5}
    leaps = {**steps, "smooth": 0}

    dark = {"style": "ambient", "seed": SEEDS["dark"], "key": f"{DARK_ROOT}-phrygian"}

    seed = SEEDS["chance"]
    flat = {s.base_label: [q(0.5)] * P for s in sections("tonal", seed)}
    chance = {"style": "tonal", "seed": seed, "contour": flat, "wiggle": 0.6, "smooth": 3}

    return [
        {"id": "rise-and-fall", "name": "Rise and fall",
         "listen": "The tune climbs and falls with your arch, and every A section comes back with the same shape.",
         "params": rise},
        {"id": "calm-to-storm", "name": "Calm to storm",
         "listen": "B gets much louder and more intense. Watch the chord strip: more Tension-colored chords in B.",
         "params": storm},
        {"id": "small-steps", "name": "Small steps",
         "listen": "Lots of wandering, but the tune still moves note to note, like a scale. Compare with Big leaps.",
         "params": steps},
        {"id": "big-leaps", "name": "Big leaps",
         "listen": "Same wandering, but now the tune jumps. Only smoothness changed.",
         "params": leaps},
        {"id": "dark-and-bright", "name": "Dark and bright",
         "listen": "A dark, tense mood. Switch the mode to Lydian: same drawing, bright and floating, because only the allowed notes changed.",
         "params": dark},
        {"id": "let-chance-draw", "name": "Let chance draw",
         "listen": "You drew nothing, so pink noise writes the melody. Roll the dice to hear other takes.",
         "params": chance},
    ]


if __name__ == "__main__":
    path = ROOT / "web" / "examples.json"
    path.write_text(json.dumps(build(), indent=1) + "\n")
    print(f"wrote {path}")
