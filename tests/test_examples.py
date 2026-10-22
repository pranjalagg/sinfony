import importlib.util
import json
from pathlib import Path

import pytest

from sinfony import web

ROOT = Path(__file__).resolve().parent.parent
P = web.PAD_POINTS
PHRYGIAN = (0, 1, 3, 5, 7, 8, 10)
LYDIAN = (0, 2, 4, 6, 7, 9, 11)


def load_script():
    spec = importlib.util.spec_from_file_location("make_examples", ROOT / "scripts" / "make_examples.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def examples():
    return {e["id"]: e for e in load_script().build()}


def melody(piece):
    return [n for n in piece.events if n.voice == "melody"]


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


def mean_interval(piece):
    pitches = [n.pitch for n in melody(piece)]
    return mean(abs(b - a) for a, b in zip(pitches, pitches[1:]))


def test_file_matches_script():
    assert json.loads((ROOT / "web" / "examples.json").read_text()) == load_script().build()


def test_names_in_order():
    built = load_script().build()
    assert [e["name"] for e in built] == [
        "Rise and fall", "Calm to storm", "Small steps", "Big leaps", "Dark and bright", "Let chance draw",
    ]
    assert len({e["id"] for e in built}) == 6


def test_params_are_share_safe():
    ranges = {"tempo": (40, 200), "wiggle": (0, 1), "smooth": (0, 5), "density": (0, 1)}
    for e in load_script().build():
        params = e["params"]
        for name, (lo, hi) in ranges.items():
            if name in params:
                assert lo <= params[name] <= hi, (e["id"], name)
        points = [v for pts in params.get("contour", {}).values() for v in pts] + list(params.get("tension") or [])
        assert all(round(v * 63) / 63 == v for v in points), e["id"]
        assert web.compose(params)["notes"], e["id"]


def test_rise_and_fall(examples):
    piece = web.build(examples["rise-and-fall"]["params"])
    seen = []
    for sec in piece.plan.form.sections:
        if sec.label != "A":
            continue
        notes = [n for n in melody(piece) if sec.start <= n.onset < sec.end]
        q = [mean(n.pitch for n in notes if sec.start + i * sec.length / 4 <= n.onset < sec.start + (i + 1) * sec.length / 4) for i in range(4)]
        assert max(q[1], q[2]) >= q[0] + 2 and max(q[1], q[2]) >= q[3] + 2, q
        seen.append([n.pitch for n in notes])  # onsets carry per-note performance jitter
    assert len(seen) == 2 and seen[0] == seen[1]


def test_calm_to_storm(examples):
    params = examples["calm-to-storm"]["params"]
    piece = web.build(params)
    secs = piece.plan.form.sections
    b = next(s for s in secs if s.label == "B")
    first_a = secs[0]
    vel = lambda s: mean(n.vel for n in piece.events if s.start <= n.onset < s.end)  # noqa: E731
    assert vel(b) >= 1.15 * vel(first_a)

    calm = list(params["tension"])
    i = secs.index(b)
    calm[i * P : (i + 1) * P] = [round(0.1 * 63) / 63] * P
    calm_piece = web.build({**params, "tension": calm})
    count = lambda p: sum(1 for c in p.chords if c.function == "D" and b.start <= c.onset < b.end)  # noqa: E731
    assert count(piece) > count(calm_piece)


def test_steps_vs_leaps(examples):
    steps, leaps = examples["small-steps"]["params"], examples["big-leaps"]["params"]
    assert {k: v for k, v in steps.items() if k != "smooth"} == {k: v for k, v in leaps.items() if k != "smooth"}
    assert (steps["smooth"], leaps["smooth"]) == (5, 0)
    assert mean_interval(web.build(leaps)) >= mean_interval(web.build(steps)) + 1.5


def test_dark_and_bright(examples):
    params = examples["dark-and-bright"]["params"]
    root, mode = params["key"].split("-")
    assert params["style"] == "ambient" and mode == "phrygian"

    def pitch_classes(p):
        return {n.pitch % 12 for n in melody(web.build(p))}

    dark = pitch_classes(params)
    bright = pitch_classes({**params, "key": f"{root}-lydian"})
    assert dark <= {(int(root) + s) % 12 for s in PHRYGIAN}
    assert bright <= {(int(root) + s) % 12 for s in LYDIAN}
    assert dark != bright


def test_let_chance_draw(examples):
    params = examples["let-chance-draw"]["params"]
    flat = round(0.5 * 63) / 63
    assert params["contour"] and all(v == flat for pts in params["contour"].values() for v in pts)
    pitches = lambda p: [n.pitch for n in melody(web.build(p))]  # noqa: E731
    assert pitches(params) != pitches({**params, "seed": params["seed"] + 1})
    assert pitches(params) != pitches({**params, "wiggle": 0})
