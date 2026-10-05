import hashlib

import numpy as np
import pytest

from sinfony.curve import Curve, const
from sinfony.plan import PAD_POINTS, Form, pad_positions
from sinfony.presets import ambient, tonal

# Fingerprints of the scores produced before this task (Task 21 of v1).
TONAL_FP = {0: "b1be5de876450e24", 1: "d2d0de4f7602f93b", 2: "e6e5447a4fddfcdd", 3: "6ddef87fbaff3fc5"}
AMBIENT_FP = {0: "573ee1104402dfc2", 1: "28e485bc94d0b8c7", 2: "bc03cf8916025df3", 3: "51ec12ebd73d5e95"}


def fp(piece):
    rows = [(n.onset, n.dur, n.pitch, n.voice) for n in piece.score]
    return hashlib.sha1(repr(rows).encode()).hexdigest()[:16]


def melody(piece):
    return [n.pitch for n in piece.voice("melody")]


def step_ratio(piece):
    m = melody(piece)
    steps = [abs(b - a) <= 2 for a, b in zip(m, m[1:])]
    return sum(steps) / len(steps)


def test_defaults_unchanged():
    for s in range(4):
        assert fp(tonal(s)) == TONAL_FP[s]
        assert fp(ambient(s)) == AMBIENT_FP[s]


def test_explicit_defaults_match_implicit():
    assert fp(tonal(1, wiggle=0.15, smoothness=2.5, density=0.85)) == TONAL_FP[1]
    assert fp(ambient(1, wiggle=0.25, smoothness=1.0, density=0.35)) == AMBIENT_FP[1]


def test_contour_raises_melody():
    high = np.mean(melody(tonal(1, contour=const(0.9))))
    low = np.mean(melody(tonal(1, contour=const(0.1))))
    assert high > low + 6


def test_tension_changes_chords():
    assert tonal(2, tension=const(1.0)).chords != tonal(2, tension=const(0.0)).chords


def test_smoothness_raises_step_ratio():
    rough = np.mean([step_ratio(tonal(s, smoothness=0.0)) for s in range(5)])
    smooth = np.mean([step_ratio(tonal(s, smoothness=5.0)) for s in range(5)])
    assert smooth > rough


def test_density_changes_note_count():
    assert len(melody(tonal(3, density=1.0))) > len(melody(tonal(3, density=0.3)))


def test_wiggle_changes_melody():
    assert melody(tonal(3, wiggle=0.0)) != melody(tonal(3, wiggle=1.0))


@pytest.mark.parametrize("kw", [{"wiggle": 1.5}, {"smoothness": -1}, {"density": 2}])
def test_out_of_range_overrides_raise(kw):
    with pytest.raises(ValueError):
        tonal(0, **kw)


def test_meta():
    p = tonal(4)
    assert p.meta["style"] == "tonal" and p.meta["seed"] == 4
    assert isinstance(p.meta["contour_shape"], Curve)
    params = p.meta["params"]
    assert set(params) == {"style", "seed", "key", "tempo", "wiggle", "smooth", "density"}
    pc_, mode = params["key"].split("-")
    assert int(pc_) == p.plan.key.root % 12 and mode in ("major", "minor")
    assert params["wiggle"] == 0.15 and params["smooth"] == 2.5 and params["density"] == 0.85
    a = ambient(4)
    assert a.meta["style"] == "ambient" and a.meta["params"]["key"].endswith(a.plan.key.name)


def test_pad_positions():
    sec = Form("A", bars=2).sections[0]  # 8 beats
    pts = pad_positions(sec)
    assert len(pts) == PAD_POINTS == 64
    assert pts[0] == pytest.approx(8 / 128) and pts[-1] == pytest.approx(8 - 8 / 128)
