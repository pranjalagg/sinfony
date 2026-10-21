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


# Cost of a leap into a copy, per semitone, against 1 per semitone of missing the drawing.
JOIN_WEIGHT = 0.5


def _place(part: Events, key: Scale, voice: Voice, prev_last: int | None) -> Events:
    """Move a copy along the scale to where the drawing asks, staying joined to the line."""
    if not len(part):
        return part
    lo, hi = voice.register
    target = sum(lo + float(voice.contour(n.onset)) * (hi - lo) for n in part) / len(part)
    options = [(d, part.transpose_diatonic(d, key)) for d in range(-14, 15)]
    inside = [(d, c) for d, c in options if all(lo <= n.pitch <= hi for n in c)]

    def cost(item):
        d, cand = item
        mean = sum(n.pitch for n in cand) / len(cand)
        join = JOIN_WEIGHT * abs(cand[0].pitch - prev_last) if prev_last is not None else 0.0
        return (abs(mean - target) + join, abs(d), d)

    return min(inside or options, key=cost)[1]


def develop_period(
    voice: Voice, plan: Plan, chords: ChordTrack, grid: MeterGrid, rng: Rng, sec: Section
) -> Events:
    """Motif -> sequence -> half cadence | motif -> variation -> authentic cadence.

    Every copy of the motif is placed diatonically where the drawing asks.
    """
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
    variation = (
        _invert_diatonic(motif, key) if rng.choice(["invert", "augment"]) == "invert"
        else motif.augment(2)
    )
    def inside(ev: Events) -> Events:  # a copy may run past the section; only its notes inside count
        return ev.filter(lambda n: n.onset < sec.end - EPS)

    parts: list[Events] = [motif]
    t = mlen
    while t < half - EPS:
        parts.append(_place(inside(motif.shift(t)), key, voice, parts[-1][-1].pitch))
        t += mlen
    parts.append(_place(inside(motif.shift(half)), key, voice, parts[-1][-1].pitch))  # same motif again
    t = half + mlen
    while t < sec.length - EPS:
        parts.append(_place(inside(variation.shift(t)), key, voice, parts[-1][-1].pitch))
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
        key = plan.form.material_key(sec)
        if key not in cache:
            period = develop_period(voice, plan, chords, grid, rng.child(f"motif:{key}"), sec)
            cache[key] = period.shift(-sec.start)
        material = cache[key].shift(sec.start)
        if sec.label != sec.base_label:
            material = vary(material, sec, plan)
        notes.extend(material)
    ev = Events(notes, (0.0, plan.total_beats))
    return requantize(ev, plan, chords, grid, voice.register, voice.subset, voice.name)
