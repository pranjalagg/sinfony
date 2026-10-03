import pytest

from sinfony.rhythm import MeterGrid, density, euclid, euclid_pattern, every
from sinfony.rng import Rng


def test_strength_4_4():
    g = MeterGrid((4, 4))
    assert [g.strength(t) for t in (0, 1, 2, 3, 4)] == [1.0, 0.5, 0.75, 0.5, 1.0]
    assert g.strength(0.5) == 0.25 and g.strength(0.25) == 0.1


def test_strength_3_4():
    g = MeterGrid((3, 4))
    assert [g.strength(t) for t in (0, 1, 2, 3)] == [1.0, 0.5, 0.5, 1.0]


def test_strength_6_8():
    g = MeterGrid((6, 8))
    assert g.beats_per_bar == 3.0 and g.beat == 1.5
    assert [g.strength(t) for t in (0, 1.5, 0.5, 1.0, 3.0)] == [1.0, 0.75, 0.25, 0.25, 1.0]


def test_strength_5_4():
    g = MeterGrid((5, 4))
    assert g.strength(2) == 0.5 and g.strength(5) == 1.0


def test_euclid_patterns():
    assert euclid_pattern(3, 8) == [1, 0, 0, 1, 0, 0, 1, 0]
    p = euclid_pattern(5, 8)
    bjorklund = [1, 0, 1, 1, 0, 1, 1, 0]
    assert sum(p) == 5
    assert any(p[r:] + p[:r] == bjorklund for r in range(8))
    assert euclid_pattern(3, 8, rotate=1) == [0, 0, 1, 0, 0, 1, 0, 1]
    with pytest.raises(ValueError):
        euclid_pattern(9, 8)


def test_euclid_rhythm_keeps_absolute_phase():
    g, r = MeterGrid(), Rng(0)
    full = euclid(3, 8, step=0.5)(0, 8, g, r)
    assert [o for o, _ in full] == [0, 1.5, 3, 4, 5.5, 7]
    assert [d for _, d in full][:2] == [1.5, 1.5]
    late = euclid(3, 8, step=0.5)(2, 8, g, r)
    assert [o for o, _ in late] == [3, 4, 5.5, 7]
    fixed = euclid(3, 8, step=0.5, dur=0.25)(0, 4, g, r)
    assert all(d == 0.25 for _, d in fixed)


def test_every():
    assert every(1.0)(0, 3, MeterGrid(), Rng(0)) == [(0, 1.0), (1, 1.0), (2, 1.0)]


def test_density():
    g = MeterGrid()
    assert density(0.0)(0, 8, g, Rng(1)) == []
    hits = density(1.0)(0, 8, g, Rng(1))
    onsets = [o for o, _ in hits]
    assert 0 in onsets and 4 in onsets  # downbeats always hit at density 1
    assert hits[-1][0] + hits[-1][1] == 8
    assert density(0.6)(0, 16, g, Rng(9)) == density(0.6)(0, 16, g, Rng(9))
    capped = density(1.0, step=1.0, max_dur=0.5)(0, 4, g, Rng(1))
    assert all(d <= 0.5 for _, d in capped)
