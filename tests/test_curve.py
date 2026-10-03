import numpy as np
import pytest

from sinfony.curve import arch, const, lift, piecewise, ramp, sine, step


def test_scalar_and_array_evaluation():
    assert ramp()(0.25) == 0.25
    assert isinstance(ramp()(0.25), float)
    np.testing.assert_allclose(ramp()(np.array([0.0, 0.5, 2.0])), [0.0, 0.5, 1.0])


def test_const_broadcasts():
    np.testing.assert_allclose(const(3)(np.zeros(4)), [3, 3, 3, 3])


def test_arithmetic():
    assert (2 * ramp() + 1)(0.5) == 2.0
    assert (ramp() - ramp())(0.3) == 0.0
    assert (1 - ramp())(0.25) == 0.75
    assert (ramp() / 2)(1.0) == 0.5
    assert (ramp() ** 2)(0.5) == 0.25
    assert (-ramp())(0.5) == -0.5
    assert abs(sine(1.0))(0.75) == pytest.approx(1.0)
    assert (ramp() * ramp())(0.5) == 0.25


def test_shift_moves_later():
    assert arch().shift(1)(1.5) == pytest.approx(arch()(0.5))


def test_stretch_slows_down():
    assert ramp().stretch(4)(2.0) == 0.5


def test_clip_and_remap():
    assert (3 * ramp()).clip(0, 1)(0.9) == 1.0
    assert ramp().remap(0, 1, 60, 72)(0.5) == 66.0


def test_over_binds_shape_to_beats_and_holds_outside():
    c = arch().over(0, 32)
    assert c(16) == pytest.approx(1.0)
    assert c(40) == pytest.approx(0.0, abs=1e-12)
    assert c(-5) == pytest.approx(0.0)


def test_tile_repeats():
    assert ramp().tile(4)(5.0) == 0.25


def test_step_and_piecewise():
    s = step([1, 2], [0, 5, 9])
    assert (s(0.5), s(1.5), s(3)) == (0.0, 5.0, 9.0)
    assert piecewise([(0, 0), (10, 1)])(5) == 0.5


def test_sample_returns_n_points():
    t, y = ramp().sample(0, 1, 11)
    assert len(t) == len(y) == 11


def test_lift():
    assert lift(2.5)(0) == 2.5
    c = ramp()
    assert lift(c) is c
    with pytest.raises(TypeError):
        lift("x")


def test_nan_raises():
    with pytest.raises(ValueError, match="NaN"):
        (const(-1) ** 0.5)(0)


@pytest.mark.parametrize(
    "make",
    [
        lambda: ramp().stretch(0),
        lambda: ramp().remap(1, 1, 0, 1),
        lambda: ramp().over(2, 1),
        lambda: ramp().tile(0),
        lambda: step([1], [0]),
        lambda: step([2, 1], [0, 1, 2]),
        lambda: piecewise([(0, 1)]),
    ],
)
def test_invalid_arguments_raise(make):
    with pytest.raises(ValueError):
        make()
