from sinfony.curve import sine
from sinfony.harmony import Functional
from sinfony.motif import develop_period
from sinfony.plan import Form, Plan
from sinfony.rhythm import MeterGrid, density
from sinfony.rng import Rng
from sinfony.rules import step_bias
from sinfony.theory import pc
from sinfony.voices import Voice, realize


def setup(form=None, rhythm=None):
    plan = Plan(2, form=form or Form("A A' B A", bars=8))
    chords = Functional().generate(plan, plan.rng.child("harmony"))
    voice = Voice(
        "melody",
        "melody",
        (60, 84),
        rhythm=rhythm or density(0.85),
        contour=(0.5 + 0.3 * sine(1 / 16)).clip(0, 1),
        rules=[step_bias(1.5)],
        motif=True,
    )
    return plan, chords, MeterGrid(plan.form.meter), voice


def test_consequent_restates_the_motif():
    plan, chords, grid, voice = setup()
    ev = develop_period(voice, plan, chords, grid, Rng(1), plan.form.sections[0])
    a = [(n.onset, n.pitch) for n in ev if n.onset < 8]
    b = [(n.onset - 16, n.pitch) for n in ev if 16 <= n.onset < 24]
    assert a and a == b


def test_sequence_is_a_diatonic_transposition():
    plan, chords, grid, voice = setup()
    ev = develop_period(voice, plan, chords, grid, Rng(1), plan.form.sections[0])
    key = plan.key
    motif = [n for n in ev if n.onset < 4]
    seq = [n for n in ev if 8 <= n.onset < 12]
    matches = [
        k
        for k in (1, -1, 2)
        if [key.degree(key.degree_of(n.pitch) + k) for n in motif] == [n.pitch for n in seq]
    ]
    assert matches


def test_cadence_bars_hold_one_long_note():
    plan, chords, grid, voice = setup()
    ev = develop_period(voice, plan, chords, grid, Rng(1), plan.form.sections[0])
    for bar in (3, 7):
        t0 = bar * 4
        inside = [n for n in ev if t0 <= n.onset < t0 + 4]
        assert len(inside) == 1 and inside[0].onset == t0 and inside[0].dur == 4


def test_motif_melody_invariants():
    plan, chords, grid, voice = setup()
    ev = realize(voice, plan, chords, grid, Rng(3))
    s = plan.form.sections
    sec_notes = [[(n.onset - x.start, n.pitch) for n in ev if x.start <= n.onset < x.end] for x in s]
    assert sec_notes[0] == sec_notes[3]
    assert [x for x in sec_notes[1] if x[0] < 16] == [x for x in sec_notes[0] if x[0] < 16]
    assert sec_notes[1] != sec_notes[0]
    for n in ev:
        if grid.strength(n.onset) >= 0.5:
            assert chords.at(n.onset).chord.contains(n.pitch)
    assert pc(ev[-1].pitch) == pc(plan.key.root)


def test_one_bar_section():
    plan, chords, grid, voice = setup(form=Form("A", bars=1))
    ev = realize(voice, plan, chords, grid, Rng(4))
    assert len(ev) >= 1
    assert pc(ev[-1].pitch) == pc(plan.key.root)


def test_empty_rhythm_falls_back_to_a_note():
    plan, chords, grid, voice = setup(rhythm=density(0.0))
    ev = develop_period(voice, plan, chords, grid, Rng(1), plan.form.sections[0])
    assert len(ev) >= 2  # at least the two cadence notes
