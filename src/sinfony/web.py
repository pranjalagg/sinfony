"""The playground's door into sinfony: plain dicts in, plain dicts out."""

from __future__ import annotations

import io
import re

import numpy as np

from .curve import Curve, piecewise
from .piece import Piece
from .plan import PAD_POINTS, Form, pad_positions
from .presets import ambient, tonal
from .render.midi import to_midi
from .theory import MODES, Scale

STYLES = {"tonal": tonal, "ambient": ambient}
TONAL_MODES = ("major", "minor")
KNOWN = {"style", "seed", "key", "tempo", "wiggle", "smooth", "density", "contour", "tension"}
_KEY = re.compile(r"^(\d{1,2})-([a-z]+)$")

__all__ = ["PAD_POINTS", "build", "compose", "midi", "normalize"]


def _number(params: dict, name: str, lo: float, hi: float, integer: bool = False):
    value = params.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    if integer and int(value) != value:
        raise ValueError(f"{name} must be a whole number")
    if not lo <= value <= hi:
        raise ValueError(f"{name} must be between {lo:g} and {hi:g}")
    return int(value) if integer else float(value)


def _points(values, what: str) -> np.ndarray:
    ok = isinstance(values, list) and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) for x in values
    )
    if not ok:
        raise ValueError(f"{what} must be a list of numbers")
    arr = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(arr)) or np.any(arr < 0) or np.any(arr > 1):
        raise ValueError(f"{what} values must be between 0 and 1")
    return arr


def normalize(params: dict) -> dict:
    """Validate browser parameters and fill defaults. Raises ValueError for the user."""
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    unknown = set(params) - KNOWN
    if unknown:
        raise ValueError(f"unknown parameter(s): {sorted(unknown)}")
    style = params.get("style")
    if style not in STYLES:
        raise ValueError(f"style must be one of {sorted(STYLES)}")
    out: dict = {"style": style}
    out["seed"] = _number(params, "seed", 0, 2**31 - 1, integer=True) or 0
    key = params.get("key")
    if key is None:
        out["key"] = None
    else:
        m = _KEY.match(str(key))
        if not m or int(m[1]) > 11:
            raise ValueError("key must look like '0-major' (pitch class 0-11, then a mode)")
        allowed = TONAL_MODES if style == "tonal" else tuple(MODES)
        if m[2] not in allowed:
            raise ValueError(f"mode {m[2]!r} is not available for {style}; use one of {list(allowed)}")
        out["key"] = (int(m[1]), m[2])
    out["tempo"] = _number(params, "tempo", 40, 200)
    out["wiggle"] = _number(params, "wiggle", 0, 1)
    out["smooth"] = _number(params, "smooth", 0, 5)
    out["density"] = _number(params, "density", 0, 1)
    contour = params.get("contour") or {}
    if not isinstance(contour, dict):
        raise ValueError("contour must map section keys to lists of points")
    out["contour"] = {}
    for k, pts in contour.items():
        arr = _points(pts, f"contour[{k}]")
        if len(arr) != PAD_POINTS:
            raise ValueError(f"contour[{k}] needs {PAD_POINTS} points, got {len(arr)}")
        out["contour"][str(k)] = arr
    tension = params.get("tension")
    out["tension"] = None if tension is None else _points(tension, "tension")
    return out


def _scale(style: str, pitch_class: int, mode: str) -> Scale:
    if style == "tonal":
        root = 60 + ((pitch_class + 6) % 12) - 6  # tonic between F#3 and F4
    else:
        root = 57 + ((pitch_class - 9) % 12)  # tonic between A3 and G#4
    return Scale.mode(mode, root)


def _drawn_contour(form: Form, drawn: dict[str, np.ndarray], default: Curve) -> Curve:
    """Drawn points where the user drew (per material), the preset's shape elsewhere."""
    spans = [
        (s.start, s.end, piecewise(zip(pad_positions(s), drawn[form.material_key(s)])))
        for s in form.sections
        if form.material_key(s) in drawn
    ]

    def f(t):
        t = np.asarray(t, dtype=float)
        out = np.broadcast_to(np.asarray(default.f(t), dtype=float), t.shape)
        for a, b, curve in spans:
            out = np.where((t >= a) & (t < b), curve.f(t), out)
        return out

    return Curve(f, "drawn contour")


def build(params: dict) -> Piece:
    p = normalize(params)
    make = STYLES[p["style"]]
    kw: dict = {}
    if p["key"] is not None:
        kw["key"] = _scale(p["style"], *p["key"])
    for name, override in (("tempo", "tempo"), ("wiggle", "wiggle"), ("smooth", "smoothness"), ("density", "density")):
        if p[name] is not None:
            kw[override] = p[name]
    piece = make(p["seed"], **kw)
    if not p["contour"] and p["tension"] is None:
        return piece

    form = piece.plan.form
    if p["tension"] is not None:
        need = PAD_POINTS * len(form.sections)
        if len(p["tension"]) != need:
            raise ValueError(
                f"tension needs {need} points ({PAD_POINTS} per section), got {len(p['tension'])}"
            )
        xs = np.concatenate([pad_positions(s) for s in form.sections])
        kw["tension"] = piecewise(zip(xs, p["tension"]))
    if p["contour"]:
        keys = {form.material_key(s) for s in form.sections}
        unknown = set(p["contour"]) - keys
        if unknown:
            raise ValueError(
                f"contour has unknown section key(s) {sorted(unknown)}; this piece has {sorted(keys)}"
            )
        kw["contour"] = _drawn_contour(form, p["contour"], piece.meta["contour_shape"])
    return make(p["seed"], **kw)


def compose(params: dict) -> dict:
    return build(params).to_json()


def midi(params: dict) -> bytes:
    piece = build(params)
    buf = io.BytesIO()
    to_midi(piece.events, piece.tempo).save(file=buf)
    return buf.getvalue()
