import itertools

import pytest

from sinfony.theory import Chord, close_voicing, pc, roughness, voice_lead

C = Chord.build(0, "maj")
F = Chord.build(5, "maj")
G = Chord.build(7, "maj")


def test_voice_lead_known_cases():
    assert voice_lead([60, 64, 67], F, 48, 84) == [60, 65, 69]
    assert voice_lead([60, 64, 67], G, 48, 84) == [59, 62, 67]


def test_voice_lead_is_minimal_among_full_coverage():
    start = [60, 64, 67]
    result = voice_lead(start, F, 48, 84)
    cost = sum(abs(a - b) for a, b in zip(sorted(start), result, strict=True))
    pool = F.pitches(48, 84)
    for combo in itertools.combinations(pool, 3):
        if {pc(p) for p in combo} == F.pcs:
            alt = sum(abs(a - b) for a, b in zip(sorted(start), combo, strict=True))
            assert cost <= alt


def test_voice_lead_stays_in_register_and_covers():
    result = voice_lead([50, 55, 59], C, 48, 67)
    assert all(48 <= p <= 67 for p in result)
    assert {pc(p) for p in result} == C.pcs


def test_close_voicing_covers_chord_near_center():
    v = close_voicing(C, 3, 48, 72)
    assert {pc(p) for p in v} == C.pcs
    assert v == sorted(v)
    assert abs(sum(v) / 3 - 60) <= 6


def test_close_voicing_four_voices():
    v = close_voicing(C, 4, 48, 72)
    assert len(v) == 4 and {pc(p) for p in v} == C.pcs


def test_register_errors():
    with pytest.raises(ValueError):
        close_voicing(C, 3, 60, 60)
    with pytest.raises(ValueError):
        close_voicing(C, 3, 60, 62)
    with pytest.raises(ValueError):
        voice_lead([60], C, 61, 62)


def test_roughness_orders_consonance():
    assert roughness([60, 67]) < roughness([60, 61])
    assert roughness([60, 72]) < roughness([60, 66])
    assert roughness([60, 64, 67]) < roughness([60, 61, 62])
    assert roughness([60]) >= 0.0
