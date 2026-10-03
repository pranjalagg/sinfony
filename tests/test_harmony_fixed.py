import pytest

from sinfony.harmony import ChordSpan, ChordTrack, Fixed
from sinfony.plan import Form, Plan
from sinfony.theory import Chord, parse_roman


def test_fixed_cycles_numerals():
    plan = Plan(1, form=Form("A B", bars=4))
    track = Fixed(["I", "vi", "IV", "V"]).generate(plan, plan.rng.child("harmony"))
    assert len(track) == 8
    assert [s.chord.label for s in track][:4] == ["I", "vi", "IV", "V"]
    assert track.at(4.5).chord == parse_roman("vi", plan.key)
    assert [s.function for s in track][:4] == ["T", "T", "S", "D"]


def test_fixed_per_bar():
    plan = Plan(1, form=Form("A", bars=2))
    track = Fixed(["I", "V"], per_bar=2).generate(plan, plan.rng)
    assert [s.dur for s in track] == [2.0, 2.0, 2.0, 2.0]


def test_repeats_reuse_material():
    plan = Plan(1, form=Form("A B A", bars=2))
    track = Fixed(["I", "IV", "V"]).generate(plan, plan.rng)
    first = [(s.onset, s.chord) for s in track if s.onset < 8]
    last = [(s.onset - 16, s.chord) for s in track if s.onset >= 16]
    assert first == last


def test_fixed_validates_numerals():
    with pytest.raises(ValueError, match="Roman numeral"):
        Fixed(["I", "Q"])
    with pytest.raises(ValueError):
        Fixed([])


def test_chord_track_at_and_errors():
    c = Chord.build(0, "maj")
    track = ChordTrack([ChordSpan(4, 4, c), ChordSpan(0, 4, c, "T")])
    assert track[0].onset == 0
    assert track.at(3.999).onset == 0
    assert track.at(4).onset == 4
    assert track.at(-1).onset == 0
    with pytest.raises(ValueError):
        ChordTrack([])
