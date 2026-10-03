import pytest

from sinfony.curve import const, sine
from sinfony.events import Events, Note
from sinfony.harmony import Fixed
from sinfony.plan import Form, Plan
from sinfony.rhythm import MeterGrid, euclid, every
from sinfony.rng import Rng
from sinfony.rules import step_bias
from sinfony.theory import Chord, Scale, close_voicing, parse_roman, pc
from sinfony.voices import STRONG, Voice, candidates, fold, realize, requantize


def setup(form=None, numerals=("I", "IV", "V", "I")):
    plan = Plan(1, form=form or Form("A B A", bars=4))
    chords = Fixed(list(numerals)).generate(plan, plan.rng.child("harmony"))
    return plan, chords, MeterGrid(plan.form.meter)


def melody(**kw):
    args = dict(
        name="melody",
        role="melody",
        register=(60, 84),
        rhythm=every(1.0),
        contour=const(0.5),
        rules=[step_bias(1.5)],
    )
    args.update(kw)
    return Voice(**args)


def test_voice_validation():
    with pytest.raises(ValueError):
        Voice("x", "melody", (60, 60), rhythm=every(), contour=const(0))
    with pytest.raises(ValueError):
        Voice("x", "drums", (60, 72))
    with pytest.raises(ValueError):
        Voice("x", "melody", (60, 72))
    with pytest.raises(ValueError):
        Voice("x", "loop", (60, 72))


def test_candidates_strong_and_weak():
    c, key = Chord.build(0, "maj"), Scale.major(60)
    assert candidates(c, key, 1.0, 60, 72, None, "m") == [60, 64, 67, 72]
    assert 62 in candidates(c, key, 0.25, 60, 72, None, "m")
    weak = candidates(c, key, 0.25, 60, 72, (0, 1, 2, 4, 5), "m")
    assert {pc(p) for p in weak} == {0, 2, 4, 7, 9}


def test_narrow_register_widens_with_warning():
    with pytest.warns(UserWarning, match="widened"):
        cands = candidates(Chord.build(0, "maj"), Scale.major(60), 1.0, 61, 62, None, "m")
    assert cands and all(pc(p) in {0, 4, 7} for p in cands)


def test_fold():
    assert fold(50, 60, 72) == 62
    assert fold(80, 60, 72) == 68
    assert fold(63, 60, 62) == 62


def test_melody_follows_contour():
    plan, chords, grid = setup()
    low = realize(melody(contour=const(0.0)), plan, chords, grid, Rng(1))
    high = realize(melody(contour=const(1.0)), plan, chords, grid, Rng(1))
    assert max(low.pitches) <= 67
    assert min(high.pitches) >= 76


def test_strong_beats_are_chord_tones_and_in_key():
    plan, chords, grid = setup()
    v = melody(rhythm=every(0.5), contour=(0.5 + 0.4 * sine(1 / 8)).clip(0, 1))
    ev = realize(v, plan, chords, grid, Rng(2))
    for n in ev:
        chord = chords.at(n.onset).chord
        assert plan.key.contains(n.pitch) or chord.contains(n.pitch)
        if grid.strength(n.onset) >= STRONG:
            assert chord.contains(n.pitch)


def test_requantize_snaps_and_ends_on_tonic():
    plan, chords, grid = setup()
    ev = Events([Note(0, 1, 62), Note(15, 1, 65)], (0, 16))
    out = requantize(ev, plan, chords, grid, (60, 84))
    assert out.pitches == [60, 60]


def test_repeated_sections_match():
    plan, chords, grid = setup()
    ev = realize(melody(rhythm=every(0.5)), plan, chords, grid, Rng(3))
    first = [(n.onset, n.pitch) for n in ev if n.onset < 16]
    last = [(n.onset - 32, n.pitch) for n in ev if n.onset >= 32]
    assert first == last


def test_bass_roots_at_cadences_and_register():
    plan, chords, grid = setup()
    ev = realize(Voice("bass", "bass", (36, 60)), plan, chords, grid, Rng(4))
    assert len(ev) == len(chords)
    assert all(36 <= p <= 60 for p in ev.pitches)
    ends = {s.end for s in plan.form.sections}
    for span, n in zip(chords, ev, strict=True):
        if span.end in ends:
            assert pc(n.pitch) == span.chord.root


def test_alberti_order():
    plan, chords, grid = setup()
    ev = realize(Voice("acc", "accomp", (48, 67), pattern="alberti"), plan, chords, grid, Rng(5))
    v = close_voicing(parse_roman("I", plan.key), 3, 48, 67)
    assert ev.pitches[:4] == [v[0], v[2], v[1], v[2]]
    assert [n.onset for n in ev][:4] == [0, 0.5, 1.0, 1.5]


def test_block_strikes_on_strong_beats():
    plan, chords, grid = setup()
    ev = realize(Voice("acc", "accomp", (48, 67), pattern="block"), plan, chords, grid, Rng(5))
    first_bar = [n for n in ev if n.onset < 4]
    assert sorted({n.onset for n in first_bar}) == [0, 2]
    assert len(first_bar) == 6


def test_pattern_per_section_and_unknown():
    plan, chords, grid = setup()
    v = Voice("acc", "accomp", (48, 67), pattern={"A": "alberti", "B": "block"})
    ev = realize(v, plan, chords, grid, Rng(5))
    assert len([n for n in ev if n.onset < 1]) == 2  # alberti eighths in A
    assert len([n for n in ev if 16 <= n.onset < 17]) == 3  # block chord in B
    with pytest.raises(ValueError):
        realize(Voice("acc", "accomp", (48, 67), pattern="waltz"), plan, chords, grid, Rng(5))


def test_pad_sustains_and_voice_leads_smoothly():
    plan, chords, grid = setup()
    ev = realize(Voice("pad", "pad", (48, 72)), plan, chords, grid, Rng(6))
    assert len(ev) == 4 * len(chords)
    groups = [sorted(n.pitch for n in ev if n.onset == s.onset) for s in chords]
    for a, b in zip(groups, groups[1:]):
        assert max(abs(x - y) for x, y in zip(a, b, strict=True)) <= 7
    assert all(n.dur == chords.at(n.onset).dur for n in ev)


def test_loop_follows_pattern_and_scale():
    plan, chords, grid = setup()
    v = Voice("loop", "loop", (60, 84), rhythm=euclid(3, 8, step=0.5), cell=(0, 2, 4))
    ev = realize(v, plan, chords, grid, Rng(7))
    assert [n.onset for n in ev][:3] == [0, 1.5, 3]
    assert ev.pitches[:3] == [60, 64, 67]
    assert all(plan.key.contains(p) and 60 <= p <= 84 for p in ev.pitches)
