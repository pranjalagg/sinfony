import pytest

from sinfony.theory import MODES, Scale, freq, note_name, pc


def test_freq_equal_temperament():
    assert freq(69) == 440.0
    assert freq(81) == 880.0
    assert freq(60) == pytest.approx(261.6256, rel=1e-6)


def test_pitch_class_wraps():
    assert pc(61) == 1
    assert pc(-1) == 11
    assert note_name(60) == "C4"
    assert note_name(69) == "A4"


def test_stacked_fifths_give_major_and_pentatonic():
    assert Scale.generated(7, 7).steps == MODES["major"]
    assert Scale.generated(7, 5).steps == MODES["pentatonic"]
    assert len(Scale.generated(7, 12)) == 12


def test_degree_handles_octaves_and_negatives():
    c = Scale.major(60)
    assert [c.degree(i) for i in (0, 2, 7, -1, -7)] == [60, 64, 72, 59, 48]


def test_degree_of_inverts_degree():
    for scale in (Scale.major(60), Scale.dorian(62), Scale.pentatonic(57)):
        for i in range(-10, 11):
            assert scale.degree_of(scale.degree(i)) == i


def test_nearest_prefers_lower_on_ties():
    c = Scale.major(60)
    assert c.nearest(61) == 60
    assert c.nearest(66) == 65
    assert c.nearest(64) == 64


def test_contains_and_pcs():
    g = Scale.major(55)
    assert 6 in g.pcs
    assert g.contains(66) and not g.contains(65)


def test_pitches_inclusive():
    assert Scale.pentatonic(60).pitches(60, 72) == [60, 62, 64, 67, 69, 72]


def test_subset_and_transpose():
    d = Scale.dorian(62)
    assert d.subset((0, 1, 2, 4, 5)).steps == (0, 2, 3, 7, 9)
    assert d.transpose(2).root == 64


def test_minor_detection_and_name():
    assert Scale.minor(57).is_minor()
    assert not Scale.major(60).is_minor()
    assert Scale.lydian(60).name == "lydian"


def test_invalid_scales_raise():
    with pytest.raises(ValueError):
        Scale(60, (2, 4))
    with pytest.raises(ValueError):
        Scale.mode("bogus")
