from sinfony.rules import (
    Context,
    avoid_repeat,
    end_on_tonic,
    gap_fill,
    range_limit,
    resolve_leading_tone,
    step_bias,
)
from sinfony.theory import Chord, Scale

C_MAJ = Scale.major(60)


def ctx(prev=(), section_end=False, cadence="none"):
    return Context(tuple(prev), Chord.build(0, "maj"), C_MAJ, 1.0, 0.0, section_end, cadence)


def test_step_bias():
    r = step_bias(1.5)
    assert r(ctx(), 72) == 0.0
    assert r(ctx([60]), 62) == 0.0
    assert r(ctx([60]), 67) == 1.5 * 5
    assert r.__name__ == "step_bias(1.5)"


def test_gap_fill_penalizes_continuing_after_leap():
    r = gap_fill(4.0)
    assert r(ctx([60, 67]), 69) == 4.0  # leap up, keeps going up
    assert r(ctx([60, 67]), 65) == 0.0  # steps back down
    assert r(ctx([60, 62]), 64) == 0.0  # no leap before
    assert r(ctx([67]), 69) == 0.0


def test_range_limit():
    r = range_limit(60, 72)
    assert r(ctx(), 59) == 100.0 and r(ctx(), 60) == 0.0


def test_avoid_repeat():
    r = avoid_repeat(2.0, 2)
    assert r(ctx([64, 64]), 64) == 2.0
    assert r(ctx([62, 64]), 64) == 0.0


def test_resolve_leading_tone():
    r = resolve_leading_tone(3.0)
    assert r(ctx([71]), 72) == 0.0
    assert r(ctx([71]), 67) == 3.0
    assert r(ctx([69]), 67) == 0.0


def test_end_on_tonic():
    r = end_on_tonic(20.0)
    assert r(ctx(section_end=True, cadence="authentic"), 64) == 20.0
    assert r(ctx(section_end=True, cadence="authentic"), 72) == 0.0
    assert r(ctx(section_end=False, cadence="authentic"), 64) == 0.0
