import numpy as np

from sinfony.curve import brown, pink, white
from sinfony.rng import Rng


def spectral_slope(curve, lo, hi, dt=1 / 32, n=2**17, segments=32):
    """Slope of log(power) vs log(frequency), averaged over segments."""
    x = curve(np.arange(n) * dt)
    x = x - x.mean()
    seg = x.reshape(segments, -1) * np.hanning(n // segments)
    power = (np.abs(np.fft.rfft(seg, axis=1)) ** 2).mean(axis=0)
    f = np.fft.rfftfreq(n // segments, dt)
    m = (f >= lo) & (f <= hi)
    return np.polyfit(np.log(f[m]), np.log(power[m]), 1)[0]


def test_pink_is_one_over_f():
    c = pink(Rng(0).child("t"), octaves=10, base=1 / 64)
    assert abs(spectral_slope(c, 1 / 16, 1.0) + 1.0) < 0.3


def test_brown_is_steeper_than_pink():
    c = brown(Rng(0).child("t"), octaves=10, base=1 / 64)
    assert abs(spectral_slope(c, 1 / 16, 1.0) + 2.0) < 0.4


def test_white_is_flat():
    c = white(Rng(0).child("t"), rate=4.0)
    assert abs(spectral_slope(c, 1 / 16, 1.0)) < 0.3


def test_noise_is_deterministic_per_rng():
    t = np.linspace(0, 50, 500)
    np.testing.assert_array_equal(pink(Rng(3))(t), pink(Rng(3))(t))
    assert not np.array_equal(pink(Rng(3))(t), pink(Rng(4))(t))


def test_noise_range_and_spread():
    t = np.linspace(0, 2000, 20000)
    for make in (pink, brown, white):
        y = make(Rng(1))(t)
        assert y.min() >= -1.0 and y.max() <= 1.0
        assert 0.2 < y.std() < 0.8


def test_noise_handles_negative_time_and_scalars():
    c = pink(Rng(2))
    assert -1.0 <= c(-3.7) <= 1.0
    assert isinstance(c(1.5), float)
