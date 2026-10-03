"""sinfony: music from mathematics."""

from .curve import (
    Curve,
    arch,
    brown,
    const,
    lift,
    piecewise,
    pink,
    ramp,
    sine,
    step,
    white,
)
from .events import Events, Note
from .harmony import ChordSpan, ChordTrack, Fixed, Functional, TonnetzWalk, home_chord
from .perform import Perform
from .piece import Piece
from .plan import Form, Plan, Section
from .presets import ambient, tonal
from .render.synth import BELL, EPIANO, PAD, SINE, Instrument, Reverb
from .rhythm import MeterGrid, density, euclid, every
from .rng import Rng
from .rules import (
    avoid_repeat,
    end_on_tonic,
    gap_fill,
    range_limit,
    resolve_leading_tone,
    step_bias,
)
from .theory import (
    Chord,
    L,
    P,
    R,
    Scale,
    close_voicing,
    freq,
    note_name,
    parse_roman,
    pc,
    roughness,
    seventh,
    triad,
    voice_lead,
)
from .voices import Voice

__version__ = "0.1.0"

__all__ = [
    "BELL", "EPIANO", "PAD", "SINE", "Chord", "ChordSpan", "ChordTrack", "Curve",
    "Events", "Fixed", "Form", "Functional", "Instrument", "L", "MeterGrid", "Note",
    "P", "Perform", "Piece", "Plan", "R", "Reverb", "Rng", "Scale", "Section",
    "TonnetzWalk", "Voice", "ambient", "arch", "avoid_repeat", "brown",
    "close_voicing", "const", "density", "end_on_tonic", "euclid", "every", "freq",
    "gap_fill", "home_chord", "lift", "note_name", "parse_roman", "pc", "piecewise",
    "pink", "ramp", "range_limit", "resolve_leading_tone", "roughness", "seventh",
    "sine", "step", "step_bias", "tonal", "triad", "voice_lead", "white",
]
