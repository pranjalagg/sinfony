import pytest

from sinfony.events import Events, Note
from sinfony.theory import Scale


def ev():
    return Events([Note(1, 0.5, 64), Note(0, 1, 60), Note(1.5, 0.5, 67)])


def test_sorted_and_span():
    e = ev()
    assert [n.onset for n in e] == [0, 1, 1.5]
    assert e.span == (0.0, 2.0)
    assert e.length == 2.0
    assert e.pitches == [60, 64, 67]


def test_empty_events():
    e = Events()
    assert len(e) == 0 and e.span == (0.0, 0.0)


def test_transpose_group_law():
    e = ev()
    assert e.transpose(3).transpose(4) == e.transpose(7)
    assert e.transpose(0) == e


def test_invert_twice_is_identity():
    e = ev()
    assert e.invert(62).pitches == [64, 60, 57]
    assert e.invert(62).invert(62) == e


def test_retrograde_twice_is_identity():
    e = ev()
    r = e.retrograde()
    assert r[0].pitch == 67 and r[0].onset == 0.0
    assert r.retrograde() == e


def test_augment_inverse():
    e = ev()
    assert e.augment(2).span == (0.0, 4.0)
    assert e.augment(2).augment(0.5) == e
    with pytest.raises(ValueError):
        e.augment(0)


def test_shift_moves_span():
    assert ev().shift(4).span == (4.0, 6.0)


def test_concatenate_and_overlay():
    e = ev()
    cat = e + e
    assert len(cat) == 6 and cat.span == (0.0, 4.0)
    assert cat[3].onset == 2.0
    lay = e | e
    assert len(lay) == 6 and lay.span == (0.0, 2.0)
    assert (Events() | e).span == e.span


def test_transpose_diatonic_stays_in_key():
    e = ev().transpose_diatonic(1, Scale.major(60))
    assert e.pitches == [62, 65, 69]


def test_by_voice_and_filter_map():
    e = Events([Note(0, 1, 60, voice="a"), Note(0, 1, 40, voice="b")])
    groups = e.by_voice()
    assert set(groups) == {"a", "b"}
    assert groups["b"].span == e.span
    assert e.filter(lambda n: n.pitch > 50).pitches == [60]
    assert e.map(lambda n: Note(n.onset, n.dur, n.pitch + 1, n.vel, n.voice)).pitches == [
        41,
        61,
    ]
