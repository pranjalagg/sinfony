"""Presets: complete pieces built only from the public API. Read them as examples."""

from __future__ import annotations

from .curve import Curve, arch, lift, pink, sine
from .harmony import Functional, TonnetzWalk
from .perform import Perform
from .piece import Piece
from .plan import Form, Plan
from .render.synth import BELL, EPIANO, PAD, Reverb
from .rhythm import density, euclid
from .rng import Rng
from .rules import avoid_repeat, end_on_tonic, gap_fill, resolve_leading_tone, step_bias
from .theory import Scale, pc
from .voices import Voice

OVERRIDES = (
    "key", "meter", "tempo", "form", "plan", "harmony", "voices", "perform",
    "instruments", "reverb", "contour", "tension", "wiggle", "smoothness", "density",
)
AMBIENT_MODES = ("dorian", "lydian", "aeolian", "pentatonic")


def _check(overrides: dict) -> None:
    unknown = set(overrides) - set(OVERRIDES)
    if unknown:
        raise TypeError(f"unknown override(s) {sorted(unknown)}; use {OVERRIDES}")


def _ranged(name: str, value, hi: float) -> float:
    v = float(value)
    if not 0.0 <= v <= hi:
        raise ValueError(f"{name} must be between 0 and {hi:g}, got {v:g}")
    return v


def _params(style: str, seed, plan: Plan, wiggle: float, smooth: float, dens: float) -> dict:
    key = plan.key
    if style == "tonal":
        mode = "minor" if key.is_minor() else "major"
    else:
        mode = key.name
    return {
        "style": style,
        "seed": seed,
        "key": f"{pc(key.root)}-{mode}",
        "tempo": round(float(plan.tempo(0.0)), 3),
        "wiggle": wiggle,
        "smooth": smooth,
        "density": dens,
    }


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
    plan = overrides.get(
        "plan",
        Plan(seed, key=key, form=form, tempo=tempo, tension=overrides.get("tension"), modulate=True),
    )
    bpb = plan.form.beats_per_bar
    wiggle = _ranged("wiggle", overrides.get("wiggle", 0.15), 1.0)
    smooth = _ranged("smoothness", overrides.get("smoothness", 2.5), 5.0)
    dens = _ranged("density", overrides.get("density", 0.85), 1.0)

    # Melody shape: an arch per 4-bar phrase (or your drawing), plus 1/f wandering.
    shape = overrides.get("contour", 0.45 * arch().tile(4 * bpb) + 0.25)
    contour = (shape + wiggle * pink(rng.child("contour"), base=1 / 8)).clip(0.0, 1.0)
    voices = overrides.get(
        "voices",
        [
            Voice(
                "melody", "melody", (60, 84),
                rhythm=density(dens, step=0.5),
                contour=contour,
                rules=[
                    step_bias(smooth), gap_fill(4.0), avoid_repeat(2.0, 2),
                    resolve_leading_tone(3.0), end_on_tonic(20.0),
                ],
                motif=True,
                vel=0.8,
            ),
            Voice("bass", "bass", (36, 60), vel=0.6),
            Voice("accomp", "accomp", (48, 67), pattern={"A": "alberti", "B": "block"}, vel=0.42),
        ],
    )
    meta = {
        "style": "tonal",
        "seed": seed,
        "contour_shape": lift(shape) if not isinstance(shape, Curve) else shape,
        "params": _params("tonal", seed, plan, wiggle, smooth, dens),
    }
    return Piece(
        plan,
        overrides.get("harmony", Functional()),
        voices,
        overrides.get("perform", Perform(jitter_ms=6.0)),
        overrides.get("instruments", EPIANO),
        overrides.get("reverb", Reverb(seconds=1.2, mix=0.18)),
        meta=meta,
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
    plan = overrides.get(
        "plan", Plan(seed, key=key, form=form, tempo=tempo, tension=overrides.get("tension"))
    )
    wiggle = _ranged("wiggle", overrides.get("wiggle", 0.25), 1.0)
    smooth = _ranged("smoothness", overrides.get("smoothness", 1.0), 5.0)
    dens = _ranged("density", overrides.get("density", 0.35), 1.0)

    subset = (0, 1, 2, 4, 5) if len(plan.key) == 7 else None  # pentatonic subset of a mode
    shape = overrides.get("contour", 0.5 + 0.25 * sine(1 / 32))
    contour = (shape + wiggle * pink(rng.child("contour"), base=1 / 16)).clip(0.0, 1.0)
    voices = overrides.get(
        "voices",
        [
            Voice("pad", "pad", (48, 72), vel=0.35),
            Voice(
                "melody", "melody", (62, 86),
                rhythm=density(dens, step=1.0, max_dur=4.0),
                contour=contour,
                rules=[step_bias(smooth), gap_fill(3.0), avoid_repeat(2.0, 3)],
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
    meta = {
        "style": "ambient",
        "seed": seed,
        "contour_shape": lift(shape) if not isinstance(shape, Curve) else shape,
        "params": _params("ambient", seed, plan, wiggle, smooth, dens),
    }
    return Piece(
        plan,
        overrides.get("harmony", TonnetzWalk(bars_per_chord=(2, 4))),
        voices,
        overrides.get("perform", Perform(jitter_ms=15.0, tempo_arc=0.03, dyn_depth=0.2, ritard=0.3)),
        overrides.get("instruments", {"pad": PAD, "melody": EPIANO, "loop1": BELL, "loop2": BELL}),
        overrides.get("reverb", Reverb(seconds=3.5, mix=0.4)),
        meta=meta,
    )
