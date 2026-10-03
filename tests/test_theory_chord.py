import pytest

from sinfony.theory import (
    Chord,
    L,
    P,
    R,
    Scale,
    numeral_function,
    parse_roman,
    seventh,
    triad,
)

C = Scale.major(60)
A_MIN = Scale.minor(57)


def test_triads_from_scale_degrees():
    assert triad(C, 0).pcs == {0, 4, 7} and triad(C, 0).label == "I"
    assert triad(C, 1).pcs == {2, 5, 9} and triad(C, 1).label == "ii"
    assert triad(C, 6).label == "vii°"
    assert seventh(C, 4).quality == "dom7" and seventh(C, 4).label == "V7"


def test_parse_roman_major_key():
    assert parse_roman("V", C).pcs == {7, 11, 2}
    assert parse_roman("vi", C).pcs == {9, 0, 4}
    assert parse_roman("V7", C).pcs == {7, 11, 2, 5}
    assert parse_roman("V/V", C).pcs == {2, 6, 9}
    assert parse_roman("bVII", C).pcs == {10, 2, 5}
    assert parse_roman("vii°", C).quality == "dim"


def test_parse_roman_minor_key_uses_harmonic_dominant():
    assert parse_roman("V", A_MIN).pcs == {4, 8, 11}
    assert parse_roman("iv", A_MIN).pcs == {2, 5, 9}
    assert parse_roman("VI", A_MIN).pcs == {5, 9, 0}


@pytest.mark.parametrize("bad", ["X", "IIII", "", "V9", "Imaj9"])
def test_unknown_numeral_raises(bad):
    with pytest.raises(ValueError, match="Roman numeral"):
        parse_roman(bad, C)


def test_numeral_function():
    assert [numeral_function(n) for n in ("I", "vi", "IV", "ii", "V7", "vii°")] == [
        "T",
        "T",
        "S",
        "S",
        "D",
        "D",
    ]
    assert numeral_function("V/V") == "S"
    assert numeral_function("bVII") == "other"


def test_plr_examples():
    c_major = Chord.build(0, "maj")
    assert P(c_major) == Chord.build(0, "min")
    assert L(c_major) == Chord.build(4, "min")
    assert R(c_major) == Chord.build(9, "min")


def test_plr_are_involutions_on_all_24_triads():
    for root in range(12):
        for quality in ("maj", "min"):
            chord = Chord.build(root, quality)
            for move in (P, L, R):
                assert move(move(chord)) == chord


def test_plr_reject_other_chords():
    with pytest.raises(ValueError):
        P(Chord.build(0, "dim"))


def test_chord_pitches_and_label_free_equality():
    c_major = Chord.build(0, "maj")
    assert c_major.pitches(60, 72) == [60, 64, 67, 72]
    assert Chord(0, frozenset({0, 4, 7}), "I") == Chord(0, frozenset({0, 4, 7}), "C")
    with pytest.raises(ValueError):
        Chord(1, frozenset({0, 4, 7}))
