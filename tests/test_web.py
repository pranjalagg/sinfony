import io
import json

import mido
import numpy as np
import pytest

from sinfony import web
from sinfony.presets import tonal

P = web.PAD_POINTS


def test_undrawn_compose_matches_preset_exactly():
    assert web.compose({"style": "tonal", "seed": 3})["notes"] == tonal(3).to_json()["notes"]


def test_compose_is_deterministic_and_json_safe():
    params = {"style": "ambient", "seed": 1, "contour": {"A": [0.8] * P}, "wiggle": 0.1}
    a = web.compose(params)
    assert a == web.compose(params)
    json.dumps(a)


def test_normalize_defaults():
    p = web.normalize({"style": "ambient"})
    assert p["seed"] == 0 and p["key"] is None and p["tempo"] is None
    assert p["contour"] == {} and p["tension"] is None


@pytest.mark.parametrize(
    "params,msg",
    [
        ({"style": "jazz"}, "style"),
        ({"style": "tonal", "seed": -1}, "seed"),
        ({"style": "tonal", "seed": 1.5}, "whole"),
        ({"style": "tonal", "key": "13-major"}, "key"),
        ({"style": "tonal", "key": "0-dorian"}, "mode"),
        ({"style": "tonal", "tempo": 500}, "tempo"),
        ({"style": "tonal", "wiggle": 2}, "wiggle"),
        ({"style": "tonal", "contour": {"A": [0.5] * 10}}, "64"),
        ({"style": "tonal", "contour": {"A": [2.0] * P}}, "between 0 and 1"),
        ({"style": "tonal", "contour": {"Z": [0.5] * P}}, "unknown section"),
        ({"style": "tonal", "tension": [0.5] * 10}, "tension"),
        ({"style": "tonal", "bogus": 1}, "unknown parameter"),
        ("nope", "object"),
    ],
    ids=[
        "style", "seed", "seed-int", "key", "mode", "tempo", "wiggle",
        "contour-len", "contour-range", "contour-key", "tension", "unknown", "type",
    ],
)
def test_bad_params(params, msg):
    with pytest.raises(ValueError, match=msg):
        web.compose(params)


def test_key_placement():
    t = web.compose({"style": "tonal", "seed": 1, "key": "7-minor"})
    assert t["key"]["pc"] == 7 and t["key"]["root"] == 55
    assert t["params"]["key"] == "7-minor"
    a = web.compose({"style": "ambient", "seed": 1, "key": "2-dorian"})
    assert a["key"]["root"] == 62 and a["key"]["mode"] == "dorian"


def _section_mean(j, label_index):
    s = j["sections"][label_index]
    pitches = [n["pitch"] for n in j["notes"] if n["voice"] == "melody" and s["start"] <= n["onset"] < s["end"]]
    return np.mean(pitches)


def test_linked_contour_drives_every_section_of_that_material():
    base = web.compose({"style": "tonal", "seed": 5})
    high = web.compose({"style": "tonal", "seed": 5, "contour": {"A": [1.0] * P}})
    for i, s in enumerate(base["sections"]):
        if s["material"] == "A":
            assert _section_mean(high, i) > _section_mean(base, i) + 3
        else:
            assert abs(_section_mean(high, i) - _section_mean(base, i)) < 1.5


def test_drawn_tension_changes_chords():
    n = len(web.compose({"style": "tonal", "seed": 2})["sections"])
    calm = web.compose({"style": "tonal", "seed": 2, "tension": [0.0] * (P * n)})
    wild = web.compose({"style": "tonal", "seed": 2, "tension": [1.0] * (P * n)})
    assert [c["label"] for c in calm["chords"]] != [c["label"] for c in wild["chords"]]


def test_midi_bytes():
    params = {"style": "tonal", "seed": 2}
    data = web.midi(params)
    mf = mido.MidiFile(file=io.BytesIO(data))
    ons = [m for t in mf.tracks for m in t if m.type == "note_on" and m.velocity > 0]
    assert len(ons) == len(web.compose(params)["notes"])


def test_seed_range_message_is_readable():
    with pytest.raises(ValueError, match="between 0 and 2147483647"):
        web.compose({"style": "tonal", "seed": 2**31})


def melody_pitches(piece):
    return [n.pitch for n in piece.events if n.voice == "melody"]


@pytest.mark.parametrize("seed", [0, 3])
def test_redrawing_late_bars_changes_tonal_melody(seed):
    flat = web.build({"style": "tonal", "seed": seed, "contour": {"A": [0.5] * P}})
    late = web.build({"style": "tonal", "seed": seed, "contour": {"A": [0.5] * 16 + [0.95] * 48}})
    assert melody_pitches(flat) != melody_pitches(late)


@pytest.mark.parametrize("seed", range(5))
def test_drawing_still_leads_at_max_smoothness(seed):
    piece = web.build({"style": "tonal", "seed": seed, "smooth": 5, "contour": {"A": [0.15] * 32 + [0.9] * 32}})
    sec = piece.plan.form.sections[0]
    mid = (sec.start + sec.end) / 2
    mel = [n for n in piece.events if n.voice == "melody" and sec.start <= n.onset < sec.end]
    first = [n.pitch for n in mel if n.onset < mid]
    second = [n.pitch for n in mel if n.onset >= mid]
    assert sum(second) / len(second) - sum(first) / len(first) >= 4
