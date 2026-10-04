"""Pictures of the math: curves, chords, and an annotated piano roll."""

from __future__ import annotations

import io

import numpy as np
from matplotlib.collections import PolyCollection
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure

PALETTE = ("#2E6F9E", "#C8553D", "#588B3A", "#8E5BA8", "#D49A2A", "#3A9E95", "#A8475E")
FUNCTION_COLORS = {"T": "#2E6F9E", "S": "#588B3A", "D": "#C8553D", "other": "#888888"}
BLACK_KEYS = {1, 3, 6, 8, 10}


class SinfonyFigure(Figure):
    """A Figure that draws itself as an image in notebooks.

    Built without pyplot (so nothing pops up twice); ``_repr_png_`` is what
    Jupyter calls to display it.
    """

    def _repr_png_(self) -> bytes:
        buf = io.BytesIO()
        self.savefig(buf, format="png", bbox_inches="tight", dpi=110)
        return buf.getvalue()


def _color(i: int) -> str:
    return PALETTE[i % len(PALETTE)]


def plot_curve(curve, t0: float = 0.0, t1: float = 1.0, n: int = 512) -> Figure:
    fig = SinfonyFigure(figsize=(7, 2.5), constrained_layout=True)
    ax = fig.add_subplot()
    t, y = curve.sample(t0, t1, n)
    ax.plot(t, y, color=PALETTE[0])
    ax.set_title(curve.name, fontsize=9)
    ax.set_xlabel("t (beats)")
    ax.grid(alpha=0.3)
    return fig


def plot_chords(track) -> Figure:
    fig = SinfonyFigure(figsize=(10, 1.6), constrained_layout=True)
    ax = fig.add_subplot()
    for s in track:
        ax.barh(0, s.dur, left=s.onset, color=FUNCTION_COLORS.get(s.function, "#888888"),
                alpha=0.3, edgecolor="white")
        ax.text(s.onset + s.dur / 2, 0, str(s.chord), ha="center", va="center", fontsize=7)
    ax.set_yticks([])
    ax.set_xlabel("beats")
    return fig


def piano_roll(piece, save=None) -> Figure:
    events, plan = piece.events, piece.plan
    T = plan.total_beats
    pitches = [n.pitch for n in events] or [60]
    lo, hi = min(pitches) - 2, max(pitches) + 3

    fig = SinfonyFigure(figsize=(14, 7), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, width_ratios=[0.6, 14], height_ratios=[6, 1])
    ax = fig.add_subplot(gs[0, 1])
    kb = fig.add_subplot(gs[0, 0], sharey=ax)
    ten = fig.add_subplot(gs[1, 1], sharex=ax)
    fig.add_subplot(gs[1, 0]).axis("off")

    for s in plan.form.sections:
        if s.index % 2:
            ax.axvspan(s.start, s.end, color="#000000", alpha=0.04, lw=0)
        ax.text(s.start + 0.3, hi + 1.2, s.label, fontsize=10, weight="bold", va="bottom")

    for i, v in enumerate(piece.voices):
        notes = [n for n in events if n.voice == v.name]
        if notes:
            verts = [
                [(n.onset, n.pitch - 0.4), (n.end, n.pitch - 0.4),
                 (n.end, n.pitch + 0.4), (n.onset, n.pitch + 0.4)]
                for n in notes
            ]
            colors = [to_rgba(_color(i), 0.25 + 0.75 * n.vel) for n in notes]
            ax.add_collection(PolyCollection(verts, facecolors=colors, edgecolors="none", label=v.name))

    t = np.linspace(0, T, 800)
    for i, v in enumerate(piece.voices):
        if v.contour is not None:
            a, b = v.register
            ax.plot(t, a + v.contour(t) * (b - a), color=_color(i), lw=1, ls="--", alpha=0.8,
                    label=f"{v.name} contour")

    for s in piece.chords:
        pcs = ",".join(str(p) for p in sorted(s.chord.pcs))
        ax.text(s.onset + 0.1, hi + 0.9, f"{s.chord}\n{{{pcs}}}", fontsize=6, va="top", color="#444444")

    ax.set_xlim(0, T)
    ax.set_ylim(lo, hi + 3)
    ax.tick_params(labelleft=False)
    ax.legend(loc="lower right", fontsize=7)

    scale_pcs = plan.key.pcs
    for p in range(lo, hi + 3):
        kb.barh(p, 1, height=1, color="#222222" if p % 12 in BLACK_KEYS else "#FFFFFF",
                edgecolor="#999999", lw=0.3)
        if p % 12 in scale_pcs:
            kb.barh(p, 0.35, left=0.65, height=0.6, color=PALETTE[1])
    kb.set_xlim(0, 1)
    kb.set_xticks([])
    kb.set_ylabel("MIDI pitch")

    tt = plan.tension(t)
    ten.fill_between(t, 0, tt, color=PALETTE[1], alpha=0.25)
    ten.plot(t, tt, color=PALETTE[1], lw=1)
    ten.set_ylim(0, 1.05)
    ten.set_ylabel("T(t)")
    ten.set_xlabel("beats")

    if save is not None:
        fig.savefig(save, bbox_inches="tight", dpi=120)
    return fig
