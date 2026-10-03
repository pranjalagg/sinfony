import numpy as np
import pytest

from sinfony.curve import const, piecewise
from sinfony.events import Events, Note
from sinfony.render.synth import (
    BELL,
    EPIANO,
    PAD,
    SINE,
    SR,
    Instrument,
    Reverb,
    beats_to_seconds,
    render,
    render_note,
)


def peak_hz(y):
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    return np.fft.rfftfreq(len(y), 1 / SR)[np.argmax(spec)]


def test_beats_to_seconds_constant():
    np.testing.assert_allclose(beats_to_seconds(const(120), [0, 1, 4]), [0, 0.5, 2.0])


def test_beats_to_seconds_linear_tempo():
    tempo = piecewise([(0, 60), (8, 120)])
    assert beats_to_seconds(tempo, [8])[0] == pytest.approx(8 * np.log(2), rel=1e-3)


def test_nonpositive_tempo_raises():
    with pytest.raises(ValueError, match="tempo"):
        beats_to_seconds(const(0), [4])
    with pytest.raises(ValueError, match="tempo"):
        beats_to_seconds(piecewise([(0, 60), (4, -10)]), [4])


def test_sine_note_has_the_right_pitch_and_length():
    y = render_note(SINE, 69, 1.0, 1.0)
    assert len(y) == round((1.0 + SINE.release) * SR)
    assert y.dtype == np.float32
    assert peak_hz(y) == pytest.approx(440, abs=2)


def test_inharmonicity_sharpens_upper_partials():
    stiff = Instrument(((6, 1.0, 0.0),), inharmonicity=0.001)
    assert peak_hz(render_note(stiff, 57, 1.0, 1.0)) > 6 * 220 + 10


def test_presets_render_finite():
    for inst in (SINE, EPIANO, PAD, BELL):
        assert np.all(np.isfinite(render_note(inst, 60, 0.8, 0.5)))


def test_render_bounds_and_duration():
    ev = Events([Note(0, 4, 60), Note(1, 1, 64, 0.5)])
    y = render(ev, const(120), SINE)
    assert y.dtype == np.float32
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) <= 1.0
    assert abs(len(y) / SR - SINE.release - 2.0) / 2.0 < 0.01


def test_instruments_per_voice_and_fallback():
    ev = Events([Note(0, 1, 60, voice="a"), Note(0, 1, 48, voice="zzz")])
    y = render(ev, const(100), {"a": BELL})
    assert np.all(np.isfinite(y))


def test_reverb_extends_and_mixes():
    y = np.zeros(1000)
    y[0] = 1.0
    r = Reverb(seconds=0.1, mix=0.5)
    out = r.apply(y)
    assert len(out) == 1000 + int(0.1 * SR) - 1
    assert np.sum(out[2000:] ** 2) > 0


def test_empty_events_are_silent():
    y = render(Events(span=(0, 2)), const(120))
    assert len(y) > 0 and np.all(y == 0)
