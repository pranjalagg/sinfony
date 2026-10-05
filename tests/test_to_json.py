import json

import numpy as np
import pytest

from sinfony.harmony import Fixed
from sinfony.piece import Piece
from sinfony.plan import PAD_POINTS, Form, Plan
from sinfony.presets import ambient, tonal
from sinfony.render.synth import beats_to_seconds
from sinfony.voices import Voice


def test_serializes_and_has_all_keys():
    j = tonal(1).to_json()
    json.dumps(j)
    assert set(j) == {
        "version", "style", "seed", "key", "meter", "beats_per_bar", "total_beats",
        "duration_s", "beat_s", "sections", "chords", "notes", "voices", "instruments",
        "reverb", "pads", "params",
    }
    assert j["version"] == 1 and j["style"] == "tonal" and j["seed"] == 1


def test_note_seconds_match_tempo_integration():
    p = tonal(2)
    j = p.to_json()
    events = list(p.events)
    expected = beats_to_seconds(p.tempo, [n.onset for n in events])
    got = [n["onset_s"] for n in j["notes"]]
    assert len(got) == len(events)
    assert np.max(np.abs(np.array(got) - expected)) < 1e-3
    assert all(isinstance(n["pitch"], int) for n in j["notes"])


def test_beat_table_and_sections():
    j = ambient(3).to_json()
    beat_s = j["beat_s"]
    assert len(beat_s) == int(j["total_beats"]) + 1
    assert all(b > a for a, b in zip(beat_s, beat_s[1:]))
    assert [s["label"] for s in j["sections"]] == ["A", "B", "A'", "C", "A"]
    assert j["sections"][-1]["end_s"] == pytest.approx(j["duration_s"], abs=1e-3)


def test_pads_shapes():
    j = tonal(4).to_json()
    materials = {s["material"] for s in j["sections"]}
    assert set(j["pads"]["contour"]) == materials
    for pts in j["pads"]["contour"].values():
        assert len(pts) == PAD_POINTS and all(0.0 <= v <= 1.0 for v in pts)
    assert len(j["pads"]["tension"]) == PAD_POINTS * len(j["sections"])


def test_voices_reference_exported_instruments():
    j = ambient(1).to_json()
    for v in j["voices"]:
        assert v["instrument"] in j["instruments"]
    assert {"pad", "epiano", "bell"} <= set(j["instruments"])
    assert j["reverb"]["seconds"] == 3.5


def test_params_echo():
    j = tonal(5).to_json()
    assert j["params"]["style"] == "tonal" and j["params"]["seed"] == 5


def test_custom_piece_exports():
    plan = Plan(1, form=Form("A", bars=2), tempo=100)
    piece = Piece(plan, Fixed(["I", "V"]), [Voice("bass", "bass", (36, 55))], reverb=None)
    j = piece.to_json()
    assert j["style"] == "custom"
    assert j["pads"]["contour"]["A"] == [0.5] * PAD_POINTS
    assert j["reverb"] == {"seconds": 0.0, "mix": 0.0, "seed": 0}
    json.dumps(j)
