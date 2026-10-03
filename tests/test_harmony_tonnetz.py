import pytest

from sinfony.curve import const
from sinfony.harmony import TonnetzWalk, home_chord
from sinfony.plan import Form, Plan
from sinfony.theory import L, P, R, Scale


def make(seed=0, key=None, rate=None):
    plan = Plan(seed, key=key or Scale.major(60), form=Form("A B A' C A", bars=8))
    return plan, TonnetzWalk(rate).generate(plan, plan.rng.child("harmony"))


def test_home_chord():
    assert home_chord(Scale.major(60)).quality == "maj"
    assert home_chord(Scale.dorian(62)).quality == "min"
    assert home_chord(Scale.pentatonic(60)).quality == "maj"


@pytest.mark.parametrize("seed", range(10))
def test_walk_moves_by_plr_within_sections(seed):
    plan, track = make(seed)
    for sec in plan.form.sections:
        spans = [s for s in track if sec.start <= s.onset < sec.end]
        assert spans[0].chord == home_chord(plan.section_key(sec))
        for a, b in zip(spans, spans[1:]):
            if b is track[-1]:
                continue  # the final span is forced home, not walked to
            if a.chord != b.chord:
                assert b.chord in (P(a.chord), L(a.chord), R(a.chord))


def test_spans_tile_and_durations():
    plan, track = make(3)
    bpb = plan.form.beats_per_bar
    for a, b in zip(track, list(track)[1:]):
        assert b.onset == pytest.approx(a.end)
    for s in track:
        assert s.dur <= 4 * bpb + 1e-9


def test_mostly_in_key():
    fits = total = 0
    for seed in range(20):
        plan, track = make(seed)
        for s in track:
            total += 1
            fits += s.chord.pcs <= plan.key.pcs
    assert fits / total >= 0.8


def test_ends_home_and_rate_zero_stays_home():
    plan, track = make(5)
    assert track[-1].chord == home_chord(plan.key)
    _, still = make(5, rate=const(0.0))
    assert all(s.chord == home_chord(plan.key) for s in still)


def test_invalid_bars_per_chord():
    with pytest.raises(ValueError):
        TonnetzWalk(bars_per_chord=(3, 2))
