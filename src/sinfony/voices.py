"""Voices: turn chords and curves into notes."""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass, field, replace

import numpy as np

from .curve import Curve
from .events import Events, Note
from .harmony import ChordTrack
from .plan import Plan, Section
from .rhythm import MeterGrid, Rhythm
from .rng import Rng
from .rules import Context, Rule
from .theory import Chord, Scale, close_voicing, pc, voice_lead

EPS = 1e-6
STRONG = 0.5
ROLES = ("melody", "bass", "accomp", "pad", "loop")
PATTERNS = ("block", "sustain", "arpeggio", "alberti")
ORDER = {"arpeggio": (0, 1, 2, 1), "alberti": (0, 2, 1, 2)}


@dataclass
class Voice:
    """One line of music: what it plays (role), where (register), and how."""

    name: str
    role: str
    register: tuple[int, int]
    rhythm: Rhythm | None = None
    contour: Curve | None = None
    rules: list[Rule] = field(default_factory=list)
    pattern: str | dict[str, str] = "block"
    step: float = 0.5
    temperature: float = 0.0
    motif: bool = False
    subset: tuple[int, ...] | None = None
    cell: tuple[int, ...] = (0, 2, 4)
    vel: float = 0.7

    def __post_init__(self):
        lo, hi = self.register
        if lo >= hi:
            raise ValueError(
                f"Voice {self.name!r}: register needs lo < hi, got {self.register}"
            )
        if self.role not in ROLES:
            raise ValueError(f"Voice {self.name!r}: unknown role {self.role!r}; use {ROLES}")
        if self.role == "melody" and (self.rhythm is None or self.contour is None):
            raise ValueError(f"Voice {self.name!r}: melody voices need rhythm and contour")
        if self.role == "loop" and self.rhythm is None:
            raise ValueError(f"Voice {self.name!r}: loop voices need a rhythm")
        if not self.cell:
            raise ValueError(f"Voice {self.name!r}: cell must not be empty")


# --- helpers ------------------------------------------------------------------
def fold(p: int, lo: int, hi: int) -> int:
    """Move ``p`` by octaves into [lo, hi] (clamp if the register is < an octave)."""
    if hi - lo < 12:
        return min(max(p, lo), hi)
    while p < lo:
        p += 12
    while p > hi:
        p -= 12
    return p


def cadence_of(chord: Chord, key: Scale, is_end: bool) -> str:
    if is_end and chord.root == pc(key.root) and chord.quality in ("maj", "min"):
        return "authentic"
    return "none"


def candidates(
    chord: Chord,
    key: Scale,
    strength: float,
    lo: int,
    hi: int,
    subset: tuple[int, ...] | None,
    name: str,
) -> list[int]:
    """Pitches a voice may play here: chord tones on strong beats, else scale tones too."""
    for widen in (0, 12):
        a, b = lo - widen, hi + widen
        tones = chord.pitches(a, b)
        pool = tones if strength >= STRONG else sorted(set(key.pitches(a, b)) | set(tones))
        if subset:
            allowed = key.subset(subset).pcs
            filtered = [p for p in pool if pc(p) in allowed]
            pool = filtered or pool
        if pool:
            if widen:
                warnings.warn(
                    f"Voice {name!r}: no candidate in register {lo}-{hi}; widened by an octave",
                    UserWarning,
                    stacklevel=2,
                )
            return pool
    raise ValueError(f"Voice {name!r}: no candidate pitches near register {lo}-{hi}")


def choose(cands: list[int], scores: np.ndarray, temperature: float, rng: Rng) -> int:
    """Lowest score wins; with temperature > 0, sample from softmax(-score/T)."""
    if temperature <= 0:
        return cands[int(np.argmin(scores))]
    z = np.exp(-(scores - scores.min()) / temperature)
    return int(rng.choice(cands, p=z / z.sum()))


def requantize(
    ev: Events,
    plan: Plan,
    chords: ChordTrack,
    grid: MeterGrid,
    register: tuple[int, int],
    subset: tuple[int, ...] | None = None,
    name: str = "voice",
) -> Events:
    """Fit notes to the actual harmony: nearest allowed pitch, tonic at cadences."""
    lo, hi = register
    out = []
    for n in ev:
        sec = plan.form.section_at(n.onset)
        key = plan.section_key(sec)
        chord = chords.at(n.onset).chord
        p = fold(n.pitch, lo, hi)
        cands = candidates(chord, key, grid.strength(n.onset), lo, hi, subset, name)
        if n.end >= sec.end - EPS and cadence_of(chord, key, True) == "authentic":
            tonics = [c for c in chord.pitches(lo, hi) if pc(c) == pc(key.root)]
            cands = tonics or cands
        out.append(replace(n, pitch=min(cands, key=lambda c: (abs(c - p), c))))
    return Events(out, ev.span)


# --- melody ---------------------------------------------------------------------
def realize_melody(
    voice: Voice,
    plan: Plan,
    chords: ChordTrack,
    grid: MeterGrid,
    rng: Rng,
    sec: Section,
    start: float | None = None,
    end: float | None = None,
) -> Events:
    """Contour gives a target pitch; candidates are scored by distance + rule penalties."""
    start = sec.start if start is None else start
    end = sec.end if end is None else end
    lo, hi = voice.register
    key = plan.section_key(sec)
    notes: list[Note] = []
    prev: list[int] = []
    for onset, dur in voice.rhythm(start, end, grid, rng):
        span = chords.at(onset)
        strength = grid.strength(onset)
        cands = candidates(span.chord, key, strength, lo, hi, voice.subset, voice.name)
        is_end = onset + dur >= sec.end - EPS
        ctx = Context(
            tuple(prev), span.chord, key, strength, onset, is_end,
            cadence_of(span.chord, key, is_end),
        )
        target = lo + float(voice.contour(onset)) * (hi - lo)
        scores = np.array(
            [abs(c - target) + sum(r(ctx, c) for r in voice.rules) for c in cands]
        )
        pitch = choose(cands, scores, voice.temperature, rng)
        notes.append(Note(onset, dur, pitch, voice.vel, voice.name))
        prev.append(pitch)
    return Events(notes, (start, end))


MakeNotes = Callable[[Voice, Plan, ChordTrack, MeterGrid, Rng, Section], Events]


def per_section(
    voice: Voice,
    plan: Plan,
    chords: ChordTrack,
    grid: MeterGrid,
    rng: Rng,
    make: MakeNotes,
) -> Events:
    """Generate once per base label, copy into repeats, then fit to the chords."""
    cache: dict[str, Events] = {}
    notes: list[Note] = []
    for sec in plan.form.sections:
        if sec.base_label not in cache:
            fresh = make(voice, plan, chords, grid, rng.child(f"section:{sec.base_label}"), sec)
            cache[sec.base_label] = fresh.shift(-sec.start)
        notes.extend(cache[sec.base_label].shift(sec.start))
    ev = Events(notes, (0.0, plan.total_beats))
    return requantize(ev, plan, chords, grid, voice.register, voice.subset, voice.name)


# --- bass, chords, loops ----------------------------------------------------------
def realize_bass(voice, plan, chords, grid, rng) -> Events:
    """Chord roots, with inversions when they shorten the bass line (never at cadences)."""
    lo, hi = voice.register
    ends = {round(s.end, 6) for s in plan.form.sections}
    notes, prev = [], None
    for span in chords:
        tones = span.chord.pitches(lo, hi) or span.chord.pitches(lo - 12, hi + 12)
        ref = prev if prev is not None else (lo + hi) / 2 - 4
        cadence = round(span.end, 6) in ends
        options = [
            (abs(p - ref) + (0 if pc(p) == span.chord.root else 3), p)
            for p in tones
            if pc(p) == span.chord.root or not cadence
        ] or [(abs(p - ref), p) for p in tones]
        pitch = min(options)[1]
        hits = voice.rhythm(span.onset, span.end, grid, rng) if voice.rhythm else [
            (span.onset, span.dur)
        ]
        notes += [Note(o, d, pitch, voice.vel, voice.name) for o, d in hits]
        prev = pitch
    return Events(notes, (0.0, plan.total_beats))


def _pattern_for(voice: Voice, base_label: str) -> str:
    if voice.role == "pad":
        return "sustain"
    kind = (
        voice.pattern.get(base_label, "block")
        if isinstance(voice.pattern, dict)
        else voice.pattern
    )
    if kind not in PATTERNS:
        raise ValueError(f"Voice {voice.name!r}: unknown pattern {kind!r}; use {PATTERNS}")
    return kind


def realize_chords(voice, plan, chords, grid, rng) -> Events:
    """Voice-led chords laid out as sustain, block, arpeggio, or Alberti bass."""
    lo, hi = voice.register
    n_voices = 4 if voice.role == "pad" else 3
    voicing, notes = None, []
    for span in chords:
        voicing = (
            close_voicing(span.chord, n_voices, lo, hi)
            if voicing is None
            else voice_lead(voicing, span.chord, lo, hi)
        )
        kind = _pattern_for(voice, plan.form.section_at(span.onset).base_label)
        if kind in ("sustain", "block"):
            strikes, t = [], span.onset
            while t < span.end - EPS:
                if kind == "sustain" and t > span.onset:
                    break
                if t == span.onset or grid.strength(t) >= 0.75:
                    strikes.append(t)
                t += grid.beat
            for j, t in enumerate(strikes):
                stop = strikes[j + 1] if j + 1 < len(strikes) else span.end
                notes += [Note(t, stop - t, p, voice.vel, voice.name) for p in voicing]
        else:
            order, t, i = ORDER[kind], span.onset, 0
            while t < span.end - EPS:
                p = voicing[order[i % len(order)] % len(voicing)]
                notes.append(Note(t, min(voice.step, span.end - t), p, voice.vel, voice.name))
                t += voice.step
                i += 1
    return Events(notes, (0.0, plan.total_beats))


def realize_loop(voice, plan, chords, grid, rng) -> Events:
    """A short cell of scale degrees replayed on a rhythm across the whole piece."""
    lo, hi = voice.register
    notes = []
    for i, (onset, dur) in enumerate(voice.rhythm(0.0, plan.total_beats, grid, rng)):
        key = plan.key_at(onset)
        p = fold(key.degree(voice.cell[i % len(voice.cell)]), lo, hi)
        notes.append(Note(onset, dur, p, voice.vel, voice.name))
    return Events(notes, (0.0, plan.total_beats))


def realize(voice: Voice, plan: Plan, chords: ChordTrack, grid: MeterGrid, rng: Rng) -> Events:
    if voice.role == "melody":
        if voice.motif:
            from .motif import realize_motif_melody

            return realize_motif_melody(voice, plan, chords, grid, rng)
        return per_section(voice, plan, chords, grid, rng, realize_melody)
    if voice.role == "bass":
        return realize_bass(voice, plan, chords, grid, rng)
    if voice.role in ("accomp", "pad"):
        return realize_chords(voice, plan, chords, grid, rng)
    return realize_loop(voice, plan, chords, grid, rng)
