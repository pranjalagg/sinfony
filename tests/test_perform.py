import pytest

from sinfony.events import Events, Note
from sinfony.perform import Perform
from sinfony.plan import Form, Plan
from sinfony.rhythm import MeterGrid
from sinfony.rng import Rng


def setup():
    plan = Plan(1, form=Form("A A", bars=8), tempo=90)
    score = Events([Note(t * 0.5, 0.5, 60, 0.8) for t in range(128)], (0, 64))
    return plan, score, MeterGrid()


def test_arc_shape():
    plan, _, _ = setup()
    arc = Perform().arc(plan)
    assert arc(0) == pytest.approx(0.0)
    assert arc(8) == pytest.approx(1.0)
    assert arc(16) == pytest.approx(0.0)


def test_tempo_arcs_and_slows_at_end():
    plan, _, _ = setup()
    tempo = Perform().tempo(plan)
    assert tempo(8) > tempo(0.01)
    assert tempo(63.9) < tempo(50) * 0.85


def test_velocities_and_jitter_bounds():
    plan, score, grid = setup()
    p = Perform(jitter_ms=10)
    out, tempo = p.apply(score, plan, grid, Rng(2))
    assert len(out) == len(score)
    assert all(0.05 <= n.vel <= 1.0 for n in out)
    max_shift = 0.010 * max(tempo(t) for t in range(64)) / 60 + 1e-9
    for a, b in zip(sorted(score, key=lambda n: n.onset), sorted(out, key=lambda n: n.onset)):
        assert abs(a.onset - b.onset) <= max_shift
    assert min(n.onset for n in out) >= 0.0


def test_downbeats_louder_than_offbeats_on_average():
    plan, score, grid = setup()
    out, _ = Perform(jitter_ms=0).apply(score, plan, grid, Rng(2))
    down = [n.vel for n in out if n.onset % 4 == 0]
    off = [n.vel for n in out if n.onset % 1 == 0.5]
    assert sum(down) / len(down) > sum(off) / len(off)


def test_no_jitter_keeps_onsets_and_is_deterministic():
    plan, score, grid = setup()
    out, _ = Perform(jitter_ms=0).apply(score, plan, grid, Rng(2))
    assert [n.onset for n in out] == [n.onset for n in score]
    assert Perform().apply(score, plan, grid, Rng(5))[0] == Perform().apply(score, plan, grid, Rng(5))[0]
