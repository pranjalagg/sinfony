import pytest

from sinfony.presets import ambient, tonal
from sinfony.theory import Scale, pc
from sinfony.voices import STRONG


def melody(piece):
    return [n for n in piece.score if n.voice == "melody"]


def assert_common(piece):
    plan, chords, grid = piece.plan, piece.chords, piece.grid
    for n in melody(piece):
        key = plan.key_at(n.onset)
        chord = chords.at(n.onset).chord
        assert key.contains(n.pitch) or chord.contains(n.pitch), n
        if grid.strength(n.onset) >= STRONG:
            assert chord.contains(n.pitch), n
    for v in piece.voices:
        lo, hi = v.register
        assert all(lo <= n.pitch <= hi for n in piece.score if n.voice == v.name), v.name
    secs = plan.form.sections
    for a in secs:
        for b in secs:
            if a.index < b.index and a.label == b.label:
                pa = [(n.onset - a.start, n.pitch) for n in melody(piece) if a.start <= n.onset < a.end]
                pb = [(n.onset - b.start, n.pitch) for n in melody(piece) if b.start <= n.onset < b.end]
                assert pa == pb, (a.label, a.index, b.index)


def assert_tonal(piece):
    assert_common(piece)
    mel = melody(piece)
    key = piece.plan.section_key(piece.plan.form.sections[-1])
    final = piece.chords[-1].chord
    assert final.root == pc(key.root) and final.quality in ("maj", "min")
    assert pc(mel[-1].pitch) == pc(key.root)
    steps = [abs(b.pitch - a.pitch) <= 2 for a, b in zip(mel, mel[1:])]
    assert sum(steps) / len(steps) >= 0.6


@pytest.mark.parametrize("seed", range(50))
def test_tonal_invariants(seed):
    assert_tonal(tonal(seed))


@pytest.mark.parametrize("seed", range(50))
def test_ambient_invariants(seed):
    assert_common(ambient(seed))


def test_tonal_in_six_eight():
    p = tonal(4, meter=(6, 8))
    assert p.plan.form.beats_per_bar == 3.0
    assert_tonal(p)


def test_overrides():
    p = tonal(3, key=Scale.minor(57), meter=(3, 4), tempo=80)
    assert p.plan.key == Scale.minor(57)
    assert p.plan.form.beats_per_bar == 3.0
    assert p.plan.tempo(0) == 80
    assert_tonal(p)


def test_unknown_override():
    with pytest.raises(TypeError, match="temp"):
        tonal(1, temp=90)
    with pytest.raises(TypeError):
        ambient(1, colour="blue")


def test_deterministic():
    assert tonal(5).score == tonal(5).score
    assert ambient(5).score == ambient(5).score


def test_durations():
    assert 60 <= tonal(0).duration <= 150
    assert 120 <= ambient(0).duration <= 240


def test_ambient_loops_phase():
    p = ambient(2)
    steps = int(p.plan.total_beats / 0.5)
    n1 = sum(1 for n in p.score if n.voice == "loop1")
    n2 = sum(1 for n in p.score if n.voice == "loop2")
    assert abs(n1 - steps * 3 / 8) <= 3
    assert abs(n2 - steps * 5 / 13) <= 3
