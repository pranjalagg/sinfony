"""MIDI export: one track per voice plus a tempo map."""

from __future__ import annotations

import math
from pathlib import Path

import mido

from ..curve import Curve
from ..events import Events

_CHANNELS = [c for c in range(16) if c != 9]  # channel 9 is drums in General MIDI


def to_midi(events: Events, tempo: Curve, ppq: int = 480) -> mido.MidiFile:
    mf = mido.MidiFile(type=1, ticks_per_beat=ppq)
    conductor = mido.MidiTrack()
    mf.tracks.append(conductor)
    for b in range(int(math.ceil(events.span[1])) + 1):
        conductor.append(
            mido.MetaMessage(
                "set_tempo", tempo=mido.bpm2tempo(float(tempo(b))), time=0 if b == 0 else ppq
            )
        )
    for i, (voice, ev) in enumerate(sorted(events.by_voice().items())):
        track = mido.MidiTrack()
        mf.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=voice, time=0))
        ch = _CHANNELS[i % len(_CHANNELS)]
        msgs = []
        for n in ev:
            on = int(round(n.onset * ppq))
            off = max(on + 1, int(round(n.end * ppq)))
            pitch = min(127, max(0, n.pitch))
            vel = min(127, max(1, round(1 + 126 * n.vel)))
            msgs.append((on, 1, mido.Message("note_on", note=pitch, velocity=vel, channel=ch)))
            msgs.append((off, 0, mido.Message("note_off", note=pitch, velocity=0, channel=ch)))
        msgs.sort(key=lambda m: (m[0], m[1]))
        now = 0
        for tick, _, msg in msgs:
            track.append(msg.copy(time=tick - now))
            now = tick
    return mf


def save_midi(events: Events, tempo: Curve, path) -> Path:
    path = Path(path)
    to_midi(events, tempo).save(str(path))
    return path
