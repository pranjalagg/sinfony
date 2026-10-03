import numpy as np
import pytest

from sinfony.curve import const
from sinfony.harmony import Fixed
from sinfony.piece import Piece
from sinfony.plan import Form, Plan
from sinfony.render.synth import SINE
from sinfony.rhythm import every
from sinfony.rules import gap_fill, step_bias
from sinfony.voices import Voice


def small(seed=1, rules=None):
    plan = Plan(seed, form=Form("A B A", bars=2), tempo=120)
    mel = Voice(
        "melody", "melody", (60, 79), rhythm=every(1.0), contour=const(0.5),
        rules=rules or [step_bias(1.5)],
    )
    bass = Voice("bass", "bass", (36, 55))
    return Piece(plan, Fixed(["I", "V"]), [mel, bass], instruments=SINE, reverb=None)


def test_layers_are_cached():
    p = small()
    assert p.chords is p.chords
    assert p.score is p.score


def test_score_has_all_voices_and_span():
    p = small()
    assert {n.voice for n in p.score} == {"melody", "bass"}
    assert p.score.span == (0.0, 24.0)
    assert len(p.events) == len(p.score)
    assert p.tempo(0) > 0


def test_same_seed_same_piece():
    assert small(3).events == small(3).events


def test_layer_isolation():
    a = small(3)
    b = small(3, rules=[step_bias(0.1), gap_fill(9.0)])
    assert a.chords == b.chords
    assert a.voice("bass") == b.voice("bass")


def test_invalid_voices():
    plan = Plan(1)
    v = Voice("bass", "bass", (36, 55))
    with pytest.raises(ValueError):
        Piece(plan, Fixed(["I"]), [v, v])
    with pytest.raises(ValueError):
        Piece(plan, Fixed(["I"]), [])


def test_audio_files_and_duration(tmp_path):
    p = small()
    y = p.audio()
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) <= 1.0
    assert p.save_wav(tmp_path / "a.wav").exists()
    assert p.save_midi(tmp_path / "a.mid").exists()
    assert 10 < p.duration < 15  # 24 beats at ~120 bpm


def test_play_hands_audio_to_player(monkeypatch):
    calls = []
    monkeypatch.setattr("sinfony.render.play.play", lambda audio, sr=44100: calls.append(len(audio)))
    small().play()
    assert calls and calls[0] > 0
