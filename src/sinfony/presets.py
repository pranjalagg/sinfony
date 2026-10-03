"""Presets: complete pieces built only from the public API. Read them as examples."""

from __future__ import annotations

from .curve import arch, pink, sine
from .harmony import Functional, TonnetzWalk
from .perform import Perform
from .piece import Piece
from .plan import Form, Plan
from .render.synth import BELL, EPIANO, PAD, Reverb
from .rhythm import density, euclid
from .rng import Rng
from .rules import avoid_repeat, end_on_tonic, gap_fill, resolve_leading_tone, step_bias
from .theory import Scale
from .voices import Voice

OVERRIDES = (
    "key", "meter", "tempo", "form", "plan", "harmony", "voices", "perform",
    "instruments", "reverb",
)
AMBIENT_MODES = ("dorian", "lydian", "aeolian", "pentatonic")


def _check(overrides: dict) -> None:
    unknown = set(overrides) - set(OVERRIDES)
    if unknown:
        raise TypeError(f"unknown override(s) {sorted(unknown)}; use {OVERRIDES}")


def tonal(seed: int = 0, **overrides) -> Piece:
    """A classical-style piano piece: A A' B A, functional harmony, a developed motif."""
    _check(overrides)
    rng = Rng(seed).child("preset:tonal")
    root = 60 + int(rng.integers(-5, 7))
    minor = rng.random() < 0.35
    triple = rng.random() < 0.3
    tempo_choice = float(rng.uniform(72, 100))

    key = overrides.get("key", Scale.minor(root) if minor else Scale.major(root))
    meter = overrides.get("meter", (3, 4) if triple else (4, 4))
    tempo = overrides.get("tempo", tempo_choice)
    form = overrides.get("form", Form("A A' B A", bars=8, meter=meter))
    plan = overrides.get("plan", Plan(seed, key=key, form=form, tempo=tempo, modulate=True))
    bpb = plan.form.beats_per_bar

    # Melody shape: an arch per 4-bar phrase, plus 1/f wandering.
    contour = (
        0.45 * arch().tile(4 * bpb) + 0.25 + 0.15 * pink(rng.child("contour"), base=1 / 8)
    ).clip(0.0, 1.0)
    voices = overrides.get(
        "voices",
        [
            Voice(
                "melody", "melody", (60, 84),
                rhythm=density(0.85, step=0.5),
                contour=contour,
                rules=[
                    step_bias(2.5), gap_fill(4.0), avoid_repeat(2.0, 2),
                    resolve_leading_tone(3.0), end_on_tonic(20.0),
                ],
                motif=True,
                vel=0.8,
            ),
            Voice("bass", "bass", (36, 60), vel=0.6),
            Voice("accomp", "accomp", (48, 67), pattern={"A": "alberti", "B": "block"}, vel=0.42),
        ],
    )
    return Piece(
        plan,
        overrides.get("harmony", Functional()),
        voices,
        overrides.get("perform", Perform(jitter_ms=6.0)),
        overrides.get("instruments", EPIANO),
        overrides.get("reverb", Reverb(seconds=1.2, mix=0.18)),
    )


def ambient(seed: int = 0, **overrides) -> Piece:
    """A slow modal piece: Tonnetz harmony, a sparse melody, two phasing loops."""
    _check(overrides)
    rng = Rng(seed).child("preset:ambient")
    mode = rng.choice(AMBIENT_MODES)
    root = 57 + int(rng.integers(0, 8))
    tempo_choice = float(rng.uniform(50, 66))

    key = overrides.get("key", Scale.mode(mode, root))
    meter = overrides.get("meter", (4, 4))
    tempo = overrides.get("tempo", tempo_choice)
    form = overrides.get("form", Form("A B A' C A", bars=8, meter=meter))
    plan = overrides.get("plan", Plan(seed, key=key, form=form, tempo=tempo))

    subset = (0, 1, 2, 4, 5) if len(plan.key) == 7 else None  # pentatonic subset of a mode
    contour = (
        0.5 + 0.25 * sine(1 / 32) + 0.25 * pink(rng.child("contour"), base=1 / 16)
    ).clip(0.0, 1.0)
    voices = overrides.get(
        "voices",
        [
            Voice("pad", "pad", (48, 72), vel=0.35),
            Voice(
                "melody", "melody", (62, 86),
                rhythm=density(0.35, step=1.0, max_dur=4.0),
                contour=contour,
                rules=[step_bias(1.0), gap_fill(3.0), avoid_repeat(2.0, 3)],
                temperature=0.8,
                subset=subset,
                vel=0.5,
            ),
            # Loops of 8 and 13 steps line up again only every lcm(8, 13) = 104 steps.
            Voice("loop1", "loop", (67, 91), rhythm=euclid(3, 8, step=0.5, dur=1.0),
                  cell=(0, 2, 4), vel=0.28),
            Voice("loop2", "loop", (55, 79), rhythm=euclid(5, 13, step=0.5, dur=1.0),
                  cell=(4, 3, 1, 0, 2), vel=0.22),
        ],
    )
    return Piece(
        plan,
        overrides.get("harmony", TonnetzWalk(bars_per_chord=(2, 4))),
        voices,
        overrides.get("perform", Perform(jitter_ms=15.0, tempo_arc=0.03, dyn_depth=0.2, ritard=0.3)),
        overrides.get("instruments", {"pad": PAD, "melody": EPIANO, "loop1": BELL, "loop2": BELL}),
        overrides.get("reverb", Reverb(seconds=3.5, mix=0.4)),
    )
