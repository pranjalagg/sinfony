import pytest

from sinfony.curve import const
from sinfony.harmony import Functional
from sinfony.plan import Form, Plan
from sinfony.theory import Scale, parse_roman


def make(seed=0, form=None, key=None, tension=None, rhythm=None):
    plan = Plan(
        seed,
        key=key or Scale.major(60),
        form=form or Form("A A' B A", bars=8),
        tension=tension,
    )
    return plan, Functional(rhythm).generate(plan, plan.rng.child("harmony"))


def test_spans_tile_the_piece():
    plan, track = make()
    assert track[0].onset == 0
    for a, b in zip(track, list(track)[1:]):
        assert b.onset == pytest.approx(a.end)
    assert track[-1].end == pytest.approx(plan.total_beats)


@pytest.mark.parametrize("seed", range(10))
def test_cadences(seed):
    plan, track = make(seed)
    bpb = plan.form.beats_per_bar
    last = len(plan.form.sections) - 1
    for sec in plan.form.sections:
        key = plan.section_key(sec)
        tonic = parse_roman("I", key)
        assert track.at(sec.start).chord == tonic
        assert track.at(sec.start + 3 * bpb).chord == parse_roman("V", key)
        assert track.at(sec.end - bpb - 0.01).chord == parse_roman("V", key)
        final = track.at(sec.end - 0.01).chord
        if sec.label != sec.base_label and sec.index != last:
            assert final == parse_roman("vi", key)
        else:
            assert final == tonic


def test_repeated_sections_match():
    plan, track = make(4)
    a0, a3 = plan.form.sections[0], plan.form.sections[3]
    first = [(s.onset - a0.start, s.chord) for s in track if a0.start <= s.onset < a0.end]
    last = [(s.onset - a3.start, s.chord) for s in track if a3.start <= s.onset < a3.end]
    assert first == last


def test_minor_key_dominant_has_leading_tone():
    plan, track = make(2, key=Scale.minor(57))
    assert track.at(plan.form.sections[0].end - 5).chord.pcs == {4, 8, 11}


def test_deterministic_and_seed_sensitive():
    assert make(7)[1] == make(7)[1]
    assert any(make(s)[1] != make(0)[1] for s in range(1, 6))


def test_tension_pushes_toward_dominant():
    def dominant_count(level):
        total = 0
        for seed in range(20):
            _, track = make(seed, tension=const(level))
            total += sum(s.function == "D" for s in track)
        return total

    assert dominant_count(1.0) > dominant_count(0.0)


def test_short_sections():
    plan, track = make(1, form=Form("A B C", bars=[1, 2, 3]))
    secs = plan.form.sections
    assert track.at(secs[0].start).chord == parse_roman("I", plan.key)
    assert track.at(secs[1].end - 0.01).chord == parse_roman("I", plan.key)
    assert track.at(secs[2].end - 0.01).chord == parse_roman("I", plan.key)
    assert track[-1].end == pytest.approx(plan.total_beats)


def test_rhythm_curve_adds_chords():
    _, plain = make(3)
    _, busy = make(3, rhythm=const(2.0))
    assert len(busy) > len(plain)
