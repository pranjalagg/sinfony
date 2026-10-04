from matplotlib.figure import Figure

from sinfony.curve import arch, const
from sinfony.harmony import Fixed
from sinfony.piece import Piece
from sinfony.plan import Form, Plan
from sinfony.render.synth import SINE
from sinfony.rhythm import every
from sinfony.voices import Voice


def small():
    plan = Plan(1, form=Form("A B", bars=2), tempo=120)
    mel = Voice("melody", "melody", (60, 79), rhythm=every(1.0), contour=arch().over(0, 16))
    bass = Voice("bass", "bass", (36, 55))
    return Piece(plan, Fixed(["I", "V"]), [mel, bass], instruments=SINE, reverb=None)


def test_curve_show():
    fig = arch().show(0, 1)
    assert isinstance(fig, Figure) and fig.axes
    assert isinstance(const(1).show(0, 4), Figure)


def test_chord_track_show():
    assert isinstance(small().chords.show(), Figure)


def test_piano_roll_png_and_svg(tmp_path):
    p = small()
    fig = p.show(save=tmp_path / "roll.png")
    assert isinstance(fig, Figure)
    assert (tmp_path / "roll.png").stat().st_size > 0
    p.show(save=tmp_path / "roll.svg")
    assert (tmp_path / "roll.svg").stat().st_size > 0


def test_figures_display_as_images_in_notebooks():
    from IPython.core.interactiveshell import InteractiveShell

    fmt = InteractiveShell.instance().display_formatter
    p = small()
    for fig in (arch().show(0, 1), p.chords.show(), p.show()):
        data, _ = fmt.format(fig)
        assert "image/png" in data
        assert data["image/png"][:8] == b"\x89PNG\r\n\x1a\n"
