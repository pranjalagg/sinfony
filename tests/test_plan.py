import numpy as np
import pytest

from sinfony.curve import const
from sinfony.plan import Form, Plan, dominant_key, relative_key
from sinfony.theory import Scale


def test_form_sections():
    f = Form("A A' B A", bars=8)
    assert [s.start for s in f.sections] == [0, 32, 64, 96]
    assert f.total_beats == 128
    assert f.sections[1].label == "A'" and f.sections[1].base_label == "A"
    assert f.sections[2].bars == 8


def test_form_meters():
    assert Form("A", meter=(3, 4)).beats_per_bar == 3.0
    assert Form("A", meter=(6, 8)).beats_per_bar == 3.0
    assert Form("A B", bars=[2, 4]).total_beats == 24


@pytest.mark.parametrize(
    "args",
    [("",), ("A B", [8]), ("A", 0), ("A", 8, (4, 3))],
)
def test_form_errors(args):
    with pytest.raises(ValueError):
        Form(*args)


def test_section_at_boundaries():
    f = Form("A B", bars=8)
    assert f.section_at(31.9).index == 0
    assert f.section_at(32).index == 1
    assert f.section_at(500).index == 1


def test_default_tension_shape():
    p = Plan(3)
    T = p.total_beats
    t = np.linspace(0, T, 1000)
    y = p.tension(t)
    assert y.min() >= 0 and y.max() <= 1
    assert 0.5 * T < t[np.argmax(y)] < 0.8 * T
    assert y[-1] < 0.3


def test_plan_is_deterministic():
    t = np.linspace(0, 128, 50)
    np.testing.assert_array_equal(Plan(5).tension(t), Plan(5).tension(t))


def test_tempo_and_custom_tension():
    p = Plan(tempo=100, tension=const(0.5))
    assert p.tempo(10) == 100.0 and p.tension(3) == 0.5
    with pytest.raises(ValueError):
        Plan(tempo=0)


def test_no_modulation_by_default():
    p = Plan(1, key=Scale.major(60))
    assert all(p.section_key(s) == p.key for s in p.form.sections)


def test_modulation_targets_and_consistency():
    key = Scale.major(60)
    moved = 0
    for seed in range(30):
        p = Plan(seed, key=key, form=Form("A B A B"), modulate=True)
        b1, b2 = p.form.sections[1], p.form.sections[3]
        assert p.section_key(b1) == p.section_key(b2)
        assert p.section_key(p.form.sections[0]) == key
        if p.section_key(b1) != key:
            moved += 1
            assert p.section_key(b1) in (dominant_key(key), relative_key(key))
    assert moved > 0


def test_related_keys():
    assert dominant_key(Scale.major(60)) == Scale.major(55)
    assert relative_key(Scale.major(60)) == Scale.minor(57)
    assert relative_key(Scale.minor(57)) == Scale.major(60)


def test_tempo_curve_must_stay_positive():
    from sinfony.curve import piecewise

    with pytest.raises(ValueError, match="tempo"):
        Plan(tempo=const(0))
    with pytest.raises(ValueError, match="tempo"):
        Plan(form=Form("A", bars=2), tempo=piecewise([(0, 90), (8, 0)]))
