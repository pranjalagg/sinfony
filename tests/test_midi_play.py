import sys
import wave

import mido
import numpy as np

from sinfony.curve import const
from sinfony.events import Events, Note
from sinfony.render import play as play_mod
from sinfony.render.midi import save_midi, to_midi
from sinfony.render.play import write_wav


def ev():
    return Events(
        [Note(0, 1, 60, 1.0, "a"), Note(1, 1, 62, 0.0, "a"), Note(0, 2, 40, 0.5, "b")]
    )


def test_midi_round_trip(tmp_path):
    path = save_midi(ev(), const(100), tmp_path / "x.mid")
    mf = mido.MidiFile(str(path))
    ons = [m for t in mf.tracks for m in t if m.type == "note_on" and m.velocity > 0]
    assert len(ons) == 3
    names = [m.name for t in mf.tracks for m in t if m.type == "track_name"]
    assert names == ["a", "b"]


def test_velocity_mapping_and_tempo():
    mf = to_midi(ev(), const(100))
    vels = sorted(m.velocity for t in mf.tracks for m in t if m.type == "note_on")
    assert vels == [1, 64, 127]
    tempos = [m for m in mf.tracks[0] if m.type == "set_tempo"]
    assert tempos[0].tempo == mido.bpm2tempo(100)
    assert len(tempos) == 3  # beats 0, 1, 2


def test_write_wav_round_trip(tmp_path):
    audio = np.linspace(-1, 1, 1000, dtype=np.float32)
    path = write_wav(tmp_path / "x.wav", audio)
    with wave.open(str(path)) as w:
        assert (w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()) == (
            1000,
            44100,
            1,
            2,
        )


def test_not_in_notebook_under_pytest():
    assert play_mod.in_notebook() is False


def test_play_falls_back_to_wav(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(play_mod, "in_notebook", lambda: False)
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    monkeypatch.setattr(play_mod.tempfile, "gettempdir", lambda: str(tmp_path))
    play_mod.play(np.zeros(100, dtype=np.float32))
    assert "wrote" in capsys.readouterr().out
    assert (tmp_path / "sinfony-play.wav").exists()
