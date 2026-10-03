"""Motifs: a short idea developed into a period by transformation."""

from __future__ import annotations

from dataclasses import replace

from .events import Events, Note
from .harmony import ChordTrack
from .plan import Plan, Section
from .rhythm import MeterGrid
from .rng import Rng
from .theory import Scale
from .voices import EPS, Voice, realize_melody, requantize


def _invert_diatonic(motif: Events, key: Scale) -> Events:
    """Mirror scale degrees around the motif's first note."""
    axis = key.degree_of(motif[0].pitch)
    return motif.map(
        lambda n: replace(n, pitch=key.degree(2 * axis - key.degree_of(n.pitch)))
    )


def _cadences(ev: Events, voice: Voice, plan: Plan, sec: Section) -> Events:
    """Hold one long note on each cadence bar (end of phrase)."""
    bpb = plan.form.beats_per_bar
    n = sec.bars
    bars = [n - 1] + ([n // 2 - 1] if n >= 4 else [])
    notes = list(ev)
    for b in bars:
        t0 = sec.start + b * bpb
        t1 = t0 + bpb
        before = [x for x in notes if x.onset < t0 - EPS]
        if before:
            ref = before[-1].pitch
        elif notes:
            ref = notes[0].pitch
        else:
            ref = sum(voice.register) // 2
        notes = [x for x in notes if not (t0 - EPS <= x.onset < t1 - EPS)]
        notes = [replace(x, dur=t0 - x.onset) if x.end > t0 > x.onset else x for x in notes]
        notes.append(Note(t0, t1 - t0, ref, voice.vel, voice.name))
    return Events(notes, ev.span)


def _join(part: Events, prev: list[Note]) -> Events:
    """Shift a copy by whole octaves so it starts near the previous note."""
    if not prev or not len(part):
        return part
    gap = prev[-1].pitch - part[0].pitch
    return part.transpose(12 * round(gap / 12))


def develop_period(
    voice: Voice, plan: Plan, chords: ChordTrack, grid: MeterGrid, rng: Rng, sec: Section
) -> Events:
    """Motif -> sequence -> half cadence | motif -> variation -> authentic cadence."""
    bpb = plan.form.beats_per_bar
    key = plan.section_key(sec)
    mlen = (2 if sec.bars >= 8 else 1) * bpb
    half = (sec.bars // 2) * bpb if sec.bars >= 2 else sec.length
    motif = realize_melody(voice, plan, chords, grid, rng.child("motif"), sec, sec.start, sec.start + mlen)
    if not len(motif):
        lo, hi = voice.register
        motif = Events(
            [Note(sec.start, mlen, key.nearest((lo + hi) / 2), voice.vel, voice.name)],
            (sec.start, sec.start + mlen),
        )
    # Sequence step: the scale-degree shift whose copy starts closest to where
    # the motif ends, so the line connects (ties broken by a seeded shuffle).
    options = [1, -1, 2, -2]
    order = [options[i] for i in rng.gen.permutation(len(options))]
    step = min(
        order,
        key=lambda k: abs(
            _join(motif.transpose_diatonic(k, key), list(motif))[0].pitch - motif[-1].pitch
        ),
    )
    variation = (
        _invert_diatonic(motif, key) if rng.choice(["invert", "augment"]) == "invert"
        else motif.augment(2)
    )
    parts: list[Events] = []
    t, k = 0.0, 0
    while t < half - EPS:
        copy = motif.transpose_diatonic(k * step, key) if k else motif
        parts.append(_join(copy, list(parts[-1]) if parts else []).shift(t))
        t += mlen
        k += 1
    parts.append(_join(motif, list(parts[-1])).shift(half))  # same motif, nearest octave
    t = half + mlen
    while t < sec.length - EPS:
        parts.append(_join(variation, list(parts[-1])).shift(t))
        t += variation.length
    notes = [
        replace(n, dur=min(n.dur, sec.end - n.onset))
        for p in parts
        for n in p
        if n.onset < sec.end - EPS
    ]
    return _cadences(Events(notes, (sec.start, sec.end)), voice, plan, sec)


def vary(ev: Events, sec: Section, plan: Plan) -> Events:
    """Primed sections (A'): lift the second half up a diatonic third."""
    key = plan.section_key(sec)
    half = sec.start + (sec.bars // 2) * plan.form.beats_per_bar
    return ev.map(
        lambda n: replace(n, pitch=key.degree(key.degree_of(n.pitch) + 2))
        if n.onset >= half - EPS
        else n
    )


def realize_motif_melody(
    voice: Voice, plan: Plan, chords: ChordTrack, grid: MeterGrid, rng: Rng
) -> Events:
    cache: dict[str, Events] = {}
    notes: list[Note] = []
    for sec in plan.form.sections:
        if sec.base_label not in cache:
            period = develop_period(voice, plan, chords, grid, rng.child(f"motif:{sec.base_label}"), sec)
            cache[sec.base_label] = period.shift(-sec.start)
        material = cache[sec.base_label].shift(sec.start)
        if sec.label != sec.base_label:
            material = vary(material, sec, plan)
        notes.extend(material)
    ev = Events(notes, (0.0, plan.total_beats))
    return requantize(ev, plan, chords, grid, voice.register, voice.subset, voice.name)
