# sinfony Playground Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public static web page where you draw a melody contour and a tension curve, sinfony (running in the browser via Pyodide) re-composes the piece, and you hear it immediately and can share it as a link.

**Architecture:**
- **Python:** the engine gains five preset overrides, `Piece.to_json()`, and a small `sinfony.web` entry point (`compose`, `midi`, `normalize`).
- **Browser:** a Pyodide Web Worker runs that entry point. The page is plain ES modules with no build step:
  - `pads.js` (drawing)
  - `roll.js` (result view)
  - `synth.js` (Web Audio port of the instruments)
  - `player.js` (look-ahead scheduler with hot swap)
  - `engine.js` (worker client)
  - `share.js` (URL hash)
  - `app.js` (wiring)
- **Deploy:** GitHub Pages via an Actions workflow.

**Tech Stack:** Python ≥ 3.11 + numpy + mido (existing); Pyodide 314.0.7 (Python 3.14, numpy 2.4.6) from the jsDelivr CDN; vanilla JavaScript (ES modules), Canvas 2D, Web Audio; Node's built-in test runner (`node:test`); GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-04-playground-design.md` (engine spec: `docs/superpowers/specs/2026-10-03-sinfony-design.md`)

## Global Constraints

- **Repo and branch:** work in `/Users/pranjal.aggarwal/Desktop/pers/shan-shui-inf/sinfony`, on branch **`feat/playground`**, created from `feat/v1`. Run every command from that directory.
- **Commits:** every commit uses `git commit --no-gpg-sign` and ends with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **No external references:** never reference the parent repository or any external project as an inspiration anywhere (code, comments, docs, commit messages).
- **No new dependencies:**
  - No new Python runtime dependencies.
  - Python code must run both on CPython ≥ 3.11 locally and on Pyodide's Python 3.14.
  - No npm dependencies, no bundler, no framework. The page is plain ES modules served as static files.
  - The only third-party runtime asset is Pyodide **314.0.7** from `https://cdn.jsdelivr.net/pyodide/v314.0.7/full/`.
- **Spec constants (exact):**

  | Constant | Value |
  |---|---|
  | `PAD_POINTS` (points per section) | 64 |
  | Share-link point encoding | 6 bits (`round(v·63)`) over the base64url alphabet |
  | Voice cap | 48 |
  | Scheduler tick | 25 ms |
  | Look-ahead | 100 ms |
  | Slider debounce | 300 ms |
  | Responsive breakpoint | 800 px |
- **Presets must not change by default:** `tonal(seed)` and `ambient(seed)` with no new overrides must produce exactly the same scores as before. Fingerprints are pinned in Task 1.
- **Commands:**
  - Python tests: `uv run pytest`
  - JavaScript tests: `node --test web/tests/*.test.js`
  - Lint: `uv run ruff check --fix .` before each commit; it must end clean.

## Review Focus

1. **Drawing before the engine has loaded.** The pads use the style's default section layout until the first piece arrives. Expected: those strokes survive the first composition and are sent with it. Pinned in Task 6 (`mergePads keeps drawn slots and fills the rest from defaults`).
2. **Switching style after drawing,** where the section layouts differ. Expected: drawings are dropped with a toast before composing, and Python never receives mismatched points. Pinned in Task 6 (`sameLayout compares materials in order`) and wired in Task 10.
3. **A share link whose tension length doesn't match the piece** (hand-edited, or from another style). Expected: a readable error toast, and the piece composes without the drawn tension instead of failing. Pinned in Task 3 (`test_bad_params[tension]`) and Task 10 (retry without tension).
4. **Very rapid redraws while a compose is running.** Expected: only the newest result is applied, never an older one arriving late. Pinned in Task 9 (`newest request wins while busy`).
5. **Touch drawing on phones.** Expected: drawing works with a finger and the page doesn't scroll while drawing. Pinned in Task 10 (CSS `touch-action: none`, checked in the browser verification step).

## File Map

```
src/sinfony/plan.py        + PAD_POINTS, pad_positions()                   (Task 1)
src/sinfony/piece.py       + meta=, to_json()                               (Tasks 1, 2)
src/sinfony/presets.py     + contour/tension/wiggle/smoothness/density, meta (Task 1)
src/sinfony/render/synth.py + INSTRUMENTS registry                          (Task 2)
src/sinfony/web.py         normalize / build / compose / midi               (Task 3)
scripts/build_web.py       wheel + manifest into web/wheels/                (Task 4)
web/package.json           {"type": "module"} so Node treats .js as ESM     (Task 5)
web/share.js               URL hash <-> state                               (Task 5)
web/pads.js                pure pad geometry + PadView canvas               (Task 6)
web/canvas.js              fitCanvas (HiDPI canvas sizing)                  (Task 6)
web/synth.js               Web Audio instruments                            (Task 7)
web/player.js              beat<->seconds, window, Player                   (Task 8)
web/engine.js              worker client, newest-request-wins               (Task 9)
web/worker.js              Pyodide + sinfony.web                            (Task 9)
web/index.html, web/style.css, web/roll.js, web/app.js                      (Task 10)
web/tests/*.test.js        node:test suites                                 (Tasks 5-9)
.github/workflows/pages.yml, README.md                                      (Task 11)
```

---

### Task 1: Preset overrides, `meta`, and pad positions

**Files:**
- Modify: `src/sinfony/plan.py` (append), `src/sinfony/piece.py` (constructor), `src/sinfony/presets.py` (replace)
- Test: `tests/test_presets_overrides.py`

**Interfaces:**
- Consumes: the existing `tonal`, `ambient`, `Plan`, `Piece`, `Curve`, `lift`, `pink`, `arch`, `sine`, `step_bias`, `density`, and `pc`.
- Produces:
  - `plan.PAD_POINTS = 64`.
  - `plan.pad_positions(section, n=PAD_POINTS) -> np.ndarray`: the cell centres `start + (k + 0.5)·length/n`.
  - `Piece(..., meta: dict | None = None)`, stored as `piece.meta` (a dict, default `{}`).
  - New override keys for `tonal(seed, **overrides)` and `ambient(seed, **overrides)`: `contour` (Curve or number), `tension` (Curve), `wiggle` (0–1), `smoothness` (0–5), and `density` (0–1). Out-of-range values raise `ValueError`.
  - Preset `piece.meta` holds:
    - `"style"`: `"tonal"` or `"ambient"`
    - `"seed"`
    - `"contour_shape"`: a `Curve`, the contour before wiggle noise
    - `"params"`: `{"style", "seed", "key": "<pc>-<mode>", "tempo", "wiggle", "smooth", "density"}`

- [ ] **Step 0: Create the branch**

```bash
git checkout -b feat/playground
```

- [ ] **Step 1: Write the failing test**

`tests/test_presets_overrides.py`:
```python
import hashlib

import numpy as np
import pytest

from sinfony.curve import Curve, const
from sinfony.plan import PAD_POINTS, Form, pad_positions
from sinfony.presets import ambient, tonal

# Fingerprints of the scores produced before this task (Task 21 of v1).
TONAL_FP = {0: "b1be5de876450e24", 1: "d2d0de4f7602f93b", 2: "e6e5447a4fddfcdd", 3: "6ddef87fbaff3fc5"}
AMBIENT_FP = {0: "573ee1104402dfc2", 1: "28e485bc94d0b8c7", 2: "bc03cf8916025df3", 3: "51ec12ebd73d5e95"}


def fp(piece):
    rows = [(n.onset, n.dur, n.pitch, n.voice) for n in piece.score]
    return hashlib.sha1(repr(rows).encode()).hexdigest()[:16]


def melody(piece):
    return [n.pitch for n in piece.voice("melody")]


def step_ratio(piece):
    m = melody(piece)
    steps = [abs(b - a) <= 2 for a, b in zip(m, m[1:])]
    return sum(steps) / len(steps)


def test_defaults_unchanged():
    for s in range(4):
        assert fp(tonal(s)) == TONAL_FP[s]
        assert fp(ambient(s)) == AMBIENT_FP[s]


def test_explicit_defaults_match_implicit():
    assert fp(tonal(1, wiggle=0.15, smoothness=2.5, density=0.85)) == TONAL_FP[1]
    assert fp(ambient(1, wiggle=0.25, smoothness=1.0, density=0.35)) == AMBIENT_FP[1]


def test_contour_raises_melody():
    high = np.mean(melody(tonal(1, contour=const(0.9))))
    low = np.mean(melody(tonal(1, contour=const(0.1))))
    assert high > low + 6


def test_tension_changes_chords():
    assert tonal(2, tension=const(1.0)).chords != tonal(2, tension=const(0.0)).chords


def test_smoothness_raises_step_ratio():
    rough = np.mean([step_ratio(tonal(s, smoothness=0.0)) for s in range(5)])
    smooth = np.mean([step_ratio(tonal(s, smoothness=5.0)) for s in range(5)])
    assert smooth > rough


def test_density_changes_note_count():
    assert len(melody(tonal(3, density=1.0))) > len(melody(tonal(3, density=0.3)))


def test_wiggle_changes_melody():
    assert melody(tonal(3, wiggle=0.0)) != melody(tonal(3, wiggle=1.0))


@pytest.mark.parametrize("kw", [{"wiggle": 1.5}, {"smoothness": -1}, {"density": 2}])
def test_out_of_range_overrides_raise(kw):
    with pytest.raises(ValueError):
        tonal(0, **kw)


def test_meta():
    p = tonal(4)
    assert p.meta["style"] == "tonal" and p.meta["seed"] == 4
    assert isinstance(p.meta["contour_shape"], Curve)
    params = p.meta["params"]
    assert set(params) == {"style", "seed", "key", "tempo", "wiggle", "smooth", "density"}
    pc_, mode = params["key"].split("-")
    assert int(pc_) == p.plan.key.root % 12 and mode in ("major", "minor")
    assert params["wiggle"] == 0.15 and params["smooth"] == 2.5 and params["density"] == 0.85
    a = ambient(4)
    assert a.meta["style"] == "ambient" and a.meta["params"]["key"].endswith(a.plan.key.name)


def test_pad_positions():
    sec = Form("A", bars=2).sections[0]  # 8 beats
    pts = pad_positions(sec)
    assert len(pts) == PAD_POINTS == 64
    assert pts[0] == pytest.approx(8 / 128) and pts[-1] == pytest.approx(8 - 8 / 128)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_presets_overrides.py -q`
Expected: FAIL with `ImportError: cannot import name 'PAD_POINTS' from 'sinfony.plan'`

- [ ] **Step 3: Implement**

Append to `src/sinfony/plan.py`:
```python
PAD_POINTS = 64


def pad_positions(section: Section, n: int = PAD_POINTS) -> np.ndarray:
    """Beats where a drawing pad samples a section: n evenly spaced cell centres."""
    return section.start + (np.arange(n) + 0.5) * section.length / n
```

In `src/sinfony/piece.py`, add a `meta` parameter to `Piece.__init__`. Change the signature's last line and the body:
```python
        reverb: Reverb | None = _DEFAULT_REVERB,
        meta: dict | None = None,
    ):
```
and, after `self.reverb = reverb`, add:
```python
        self.meta = dict(meta or {})
```

Replace `src/sinfony/presets.py` with:
```python
"""Presets: complete pieces built only from the public API. Read them as examples."""

from __future__ import annotations

from .curve import Curve, arch, lift, pink, sine
from .harmony import Functional, TonnetzWalk
from .perform import Perform
from .piece import Piece
from .plan import Form, Plan
from .render.synth import BELL, EPIANO, PAD, Reverb
from .rhythm import density, euclid
from .rng import Rng
from .rules import avoid_repeat, end_on_tonic, gap_fill, resolve_leading_tone, step_bias
from .theory import Scale, pc
from .voices import Voice

OVERRIDES = (
    "key", "meter", "tempo", "form", "plan", "harmony", "voices", "perform",
    "instruments", "reverb", "contour", "tension", "wiggle", "smoothness", "density",
)
AMBIENT_MODES = ("dorian", "lydian", "aeolian", "pentatonic")


def _check(overrides: dict) -> None:
    unknown = set(overrides) - set(OVERRIDES)
    if unknown:
        raise TypeError(f"unknown override(s) {sorted(unknown)}; use {OVERRIDES}")


def _ranged(name: str, value, hi: float) -> float:
    v = float(value)
    if not 0.0 <= v <= hi:
        raise ValueError(f"{name} must be between 0 and {hi:g}, got {v:g}")
    return v


def _params(style: str, seed, plan: Plan, wiggle: float, smooth: float, dens: float) -> dict:
    key = plan.key
    if style == "tonal":
        mode = "minor" if key.is_minor() else "major"
    else:
        mode = key.name
    return {
        "style": style,
        "seed": seed,
        "key": f"{pc(key.root)}-{mode}",
        "tempo": round(float(plan.tempo(0.0)), 3),
        "wiggle": wiggle,
        "smooth": smooth,
        "density": dens,
    }


def tonal(seed: int = 0, **overrides) -> Piece:
    """A classical-style piano piece: A A' B A, functional harmony, a developed motif."""
    _check(overrides)
    rng = Rng(seed).child("preset:tonal")
    root = 60 + int(rng.integers(-5, 7))
    minor = rng.random() < 0.35
    triple = rng.random() < 0.3
    tempo_choice = float(rng.uniform(72, 100))

    key = overrides.get("key", Scale.minor(root) if minor else Scale.major(root))
    meter = overrides.get("meter", (3, 4) if triple else (4, 4))
    tempo = overrides.get("tempo", tempo_choice)
    form = overrides.get("form", Form("A A' B A", bars=8, meter=meter))
    plan = overrides.get(
        "plan",
        Plan(seed, key=key, form=form, tempo=tempo, tension=overrides.get("tension"), modulate=True),
    )
    bpb = plan.form.beats_per_bar
    wiggle = _ranged("wiggle", overrides.get("wiggle", 0.15), 1.0)
    smooth = _ranged("smoothness", overrides.get("smoothness", 2.5), 5.0)
    dens = _ranged("density", overrides.get("density", 0.85), 1.0)

    # Melody shape: an arch per 4-bar phrase (or your drawing), plus 1/f wandering.
    shape = overrides.get("contour", 0.45 * arch().tile(4 * bpb) + 0.25)
    contour = (shape + wiggle * pink(rng.child("contour"), base=1 / 8)).clip(0.0, 1.0)
    voices = overrides.get(
        "voices",
        [
            Voice(
                "melody", "melody", (60, 84),
                rhythm=density(dens, step=0.5),
                contour=contour,
                rules=[
                    step_bias(smooth), gap_fill(4.0), avoid_repeat(2.0, 2),
                    resolve_leading_tone(3.0), end_on_tonic(20.0),
                ],
                motif=True,
                vel=0.8,
            ),
            Voice("bass", "bass", (36, 60), vel=0.6),
            Voice("accomp", "accomp", (48, 67), pattern={"A": "alberti", "B": "block"}, vel=0.42),
        ],
    )
    meta = {
        "style": "tonal",
        "seed": seed,
        "contour_shape": lift(shape) if not isinstance(shape, Curve) else shape,
        "params": _params("tonal", seed, plan, wiggle, smooth, dens),
    }
    return Piece(
        plan,
        overrides.get("harmony", Functional()),
        voices,
        overrides.get("perform", Perform(jitter_ms=6.0)),
        overrides.get("instruments", EPIANO),
        overrides.get("reverb", Reverb(seconds=1.2, mix=0.18)),
        meta=meta,
    )


def ambient(seed: int = 0, **overrides) -> Piece:
    """A slow modal piece: Tonnetz harmony, a sparse melody, two phasing loops."""
    _check(overrides)
    rng = Rng(seed).child("preset:ambient")
    mode = rng.choice(AMBIENT_MODES)
    root = 57 + int(rng.integers(0, 8))
    tempo_choice = float(rng.uniform(50, 66))

    key = overrides.get("key", Scale.mode(mode, root))
    meter = overrides.get("meter", (4, 4))
    tempo = overrides.get("tempo", tempo_choice)
    form = overrides.get("form", Form("A B A' C A", bars=8, meter=meter))
    plan = overrides.get(
        "plan", Plan(seed, key=key, form=form, tempo=tempo, tension=overrides.get("tension"))
    )
    wiggle = _ranged("wiggle", overrides.get("wiggle", 0.25), 1.0)
    smooth = _ranged("smoothness", overrides.get("smoothness", 1.0), 5.0)
    dens = _ranged("density", overrides.get("density", 0.35), 1.0)

    subset = (0, 1, 2, 4, 5) if len(plan.key) == 7 else None  # pentatonic subset of a mode
    shape = overrides.get("contour", 0.5 + 0.25 * sine(1 / 32))
    contour = (shape + wiggle * pink(rng.child("contour"), base=1 / 16)).clip(0.0, 1.0)
    voices = overrides.get(
        "voices",
        [
            Voice("pad", "pad", (48, 72), vel=0.35),
            Voice(
                "melody", "melody", (62, 86),
                rhythm=density(dens, step=1.0, max_dur=4.0),
                contour=contour,
                rules=[step_bias(smooth), gap_fill(3.0), avoid_repeat(2.0, 3)],
                temperature=0.8,
                subset=subset,
                vel=0.5,
            ),
            # Loops of 8 and 13 steps line up again only every lcm(8, 13) = 104 steps.
            Voice("loop1", "loop", (67, 91), rhythm=euclid(3, 8, step=0.5, dur=1.0),
                  cell=(0, 2, 4), vel=0.28),
            Voice("loop2", "loop", (55, 79), rhythm=euclid(5, 13, step=0.5, dur=1.0),
                  cell=(4, 3, 1, 0, 2), vel=0.22),
        ],
    )
    meta = {
        "style": "ambient",
        "seed": seed,
        "contour_shape": lift(shape) if not isinstance(shape, Curve) else shape,
        "params": _params("ambient", seed, plan, wiggle, smooth, dens),
    }
    return Piece(
        plan,
        overrides.get("harmony", TonnetzWalk(bars_per_chord=(2, 4))),
        voices,
        overrides.get("perform", Perform(jitter_ms=15.0, tempo_arc=0.03, dyn_depth=0.2, ritard=0.3)),
        overrides.get("instruments", {"pad": PAD, "melody": EPIANO, "loop1": BELL, "loop2": BELL}),
        overrides.get("reverb", Reverb(seconds=3.5, mix=0.4)),
        meta=meta,
    )
```

Notes for the implementer:
- `shape + wiggle * pink(...)` evaluates in the same order as the old `0.45 * arch() ... + 0.25 + 0.15 * pink(...)`. That keeps `test_defaults_unchanged` exact.
- If a fingerprint differs, look first for any change to the order of random draws or to the arithmetic order. The fingerprints were captured from the code on `feat/v1` at commit `42a0d08`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_presets_overrides.py tests/test_presets.py tests/test_piece.py -q`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix .
git add src/sinfony/plan.py src/sinfony/piece.py src/sinfony/presets.py tests/test_presets_overrides.py
git commit --no-gpg-sign -m "feat: let presets take drawn contour, tension, and feel controls" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `Piece.to_json()` and the instrument registry

**Files:**
- Modify: `src/sinfony/render/synth.py` (append), `src/sinfony/piece.py` (imports + method)
- Test: `tests/test_to_json.py`

**Interfaces:**
- Consumes: `Piece.meta` (Task 1), `pad_positions`, `beats_to_seconds`, `Form.material_key`, and `pc`.
- Produces:
  - `synth.INSTRUMENTS = {"sine": SINE, "epiano": EPIANO, "pad": PAD, "bell": BELL}`.
  - `Piece.to_json() -> dict` matching spec §5.2 exactly. Keys: `version`, `style`, `seed`, `key{root,mode,pc}`, `meter`, `beats_per_bar`, `total_beats`, `duration_s`, `beat_s`, `sections[]`, `chords[]`, `notes[]`, `voices[]`, `instruments{}`, `reverb{seconds,mix,seed}`, `pads{contour{material: 64}, tension[64·sections]}`, `params`.
  - Every number is a plain Python `int` or `float`, rounded to 6 decimals.

- [ ] **Step 1: Write the failing test**

`tests/test_to_json.py`:
```python
import json

import numpy as np
import pytest

from sinfony.harmony import Fixed
from sinfony.piece import Piece
from sinfony.plan import PAD_POINTS, Form, Plan
from sinfony.presets import ambient, tonal
from sinfony.render.synth import beats_to_seconds
from sinfony.voices import Voice


def test_serializes_and_has_all_keys():
    j = tonal(1).to_json()
    json.dumps(j)
    assert set(j) == {
        "version", "style", "seed", "key", "meter", "beats_per_bar", "total_beats",
        "duration_s", "beat_s", "sections", "chords", "notes", "voices", "instruments",
        "reverb", "pads", "params",
    }
    assert j["version"] == 1 and j["style"] == "tonal" and j["seed"] == 1


def test_note_seconds_match_tempo_integration():
    p = tonal(2)
    j = p.to_json()
    events = list(p.events)
    expected = beats_to_seconds(p.tempo, [n.onset for n in events])
    got = [n["onset_s"] for n in j["notes"]]
    assert len(got) == len(events)
    assert np.max(np.abs(np.array(got) - expected)) < 1e-3
    assert all(isinstance(n["pitch"], int) for n in j["notes"])


def test_beat_table_and_sections():
    j = ambient(3).to_json()
    beat_s = j["beat_s"]
    assert len(beat_s) == int(j["total_beats"]) + 1
    assert all(b > a for a, b in zip(beat_s, beat_s[1:]))
    assert [s["label"] for s in j["sections"]] == ["A", "B", "A'", "C", "A"]
    assert j["sections"][-1]["end_s"] == pytest.approx(j["duration_s"], abs=1e-3)


def test_pads_shapes():
    j = tonal(4).to_json()
    materials = {s["material"] for s in j["sections"]}
    assert set(j["pads"]["contour"]) == materials
    for pts in j["pads"]["contour"].values():
        assert len(pts) == PAD_POINTS and all(0.0 <= v <= 1.0 for v in pts)
    assert len(j["pads"]["tension"]) == PAD_POINTS * len(j["sections"])


def test_voices_reference_exported_instruments():
    j = ambient(1).to_json()
    for v in j["voices"]:
        assert v["instrument"] in j["instruments"]
    assert {"pad", "epiano", "bell"} <= set(j["instruments"])
    assert j["reverb"]["seconds"] == 3.5


def test_params_echo():
    j = tonal(5).to_json()
    assert j["params"]["style"] == "tonal" and j["params"]["seed"] == 5


def test_custom_piece_exports():
    plan = Plan(1, form=Form("A", bars=2), tempo=100)
    piece = Piece(plan, Fixed(["I", "V"]), [Voice("bass", "bass", (36, 55))], reverb=None)
    j = piece.to_json()
    assert j["style"] == "custom"
    assert j["pads"]["contour"]["A"] == [0.5] * PAD_POINTS
    assert j["reverb"] == {"seconds": 0.0, "mix": 0.0, "seed": 0}
    json.dumps(j)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_to_json.py -q`
Expected: FAIL with `AttributeError: 'Piece' object has no attribute 'to_json'`

- [ ] **Step 3: Implement**

Append to `src/sinfony/render/synth.py`:
```python
INSTRUMENTS: dict[str, Instrument] = {"sine": SINE, "epiano": EPIANO, "pad": PAD, "bell": BELL}
```

In `src/sinfony/piece.py`, replace the import block with:
```python
from __future__ import annotations

from dataclasses import asdict
from functools import cached_property
from pathlib import Path

import numpy as np

from .curve import Curve, const
from .events import Events
from .harmony import ChordTrack
from .perform import Perform
from .plan import Plan, pad_positions
from .render.midi import save_midi
from .render.play import write_wav
from .render.synth import (
    EPIANO,
    INSTRUMENTS,
    Instrument,
    Reverb,
    beats_to_seconds,
    render,
)
from .rhythm import MeterGrid
from .theory import pc
from .voices import Voice, realize
```

Add this helper above `class Piece`:
```python
def _r(x) -> float:
    return round(float(x), 6)
```

Add this method to `class Piece`, before `__repr__`:
```python
    def to_json(self) -> dict:
        """Everything a browser needs to draw and play this piece (times also in seconds)."""
        plan, form = self.plan, self.plan.form
        T = plan.total_beats

        def secs(beats) -> list[float]:
            if len(beats) == 0:
                return []
            return [_r(s) for s in beats_to_seconds(self.tempo, beats)]

        events = list(self.events)
        on = secs([n.onset for n in events])
        off = secs([n.end for n in events])
        edges = secs([x for s in form.sections for x in (s.start, s.end)])
        chords = list(self.chords)
        chord_edges = secs([x for c in chords for x in (c.onset, c.end)])

        voice_instrument: dict[str, str] = {}
        instruments: dict[str, dict] = {}
        for v in self.voices:
            inst = (
                self.instruments.get(v.name, EPIANO)
                if isinstance(self.instruments, dict)
                else self.instruments
            )
            name = next((k for k, i in INSTRUMENTS.items() if i == inst), f"custom:{v.name}")
            voice_instrument[v.name] = name
            instruments[name] = asdict(inst)

        shape = self.meta.get("contour_shape")
        if shape is None:
            melodic = next((v for v in self.voices if v.contour is not None), None)
            shape = melodic.contour if melodic is not None else const(0.5)
        contour_pads: dict[str, list[float]] = {}
        for s in form.sections:
            key = form.material_key(s)
            if key not in contour_pads:
                contour_pads[key] = [_r(v) for v in np.clip(shape(pad_positions(s)), 0.0, 1.0)]
        tension_pads = [
            _r(v)
            for s in form.sections
            for v in np.clip(plan.tension(pad_positions(s)), 0.0, 1.0)
        ]
        reverb = (
            {"seconds": _r(self.reverb.seconds), "mix": _r(self.reverb.mix), "seed": int(self.reverb.seed)}
            if self.reverb is not None
            else {"seconds": 0.0, "mix": 0.0, "seed": 0}
        )
        return {
            "version": 1,
            "style": self.meta.get("style", "custom"),
            "seed": self.meta.get("seed", plan.seed),
            "key": {"root": int(plan.key.root), "mode": plan.key.name, "pc": pc(plan.key.root)},
            "meter": [int(x) for x in form.meter],
            "beats_per_bar": _r(form.beats_per_bar),
            "total_beats": _r(T),
            "duration_s": _r(self.duration),
            "beat_s": secs(np.arange(int(np.floor(T)) + 1, dtype=float)),
            "sections": [
                {
                    "label": s.label,
                    "base": s.base_label,
                    "material": form.material_key(s),
                    "start": _r(s.start),
                    "end": _r(s.end),
                    "start_s": edges[2 * i],
                    "end_s": edges[2 * i + 1],
                }
                for i, s in enumerate(form.sections)
            ],
            "chords": [
                {
                    "onset": _r(c.onset),
                    "dur": _r(c.dur),
                    "label": str(c.chord),
                    "pcs": sorted(int(p) for p in c.chord.pcs),
                    "function": c.function,
                    "onset_s": chord_edges[2 * i],
                    "dur_s": _r(chord_edges[2 * i + 1] - chord_edges[2 * i]),
                }
                for i, c in enumerate(chords)
            ],
            "notes": [
                {
                    "voice": n.voice,
                    "pitch": int(n.pitch),
                    "vel": _r(n.vel),
                    "onset": _r(n.onset),
                    "dur": _r(n.dur),
                    "onset_s": on[i],
                    "dur_s": _r(off[i] - on[i]),
                }
                for i, n in enumerate(events)
            ],
            "voices": [
                {
                    "name": v.name,
                    "role": v.role,
                    "register": [int(v.register[0]), int(v.register[1])],
                    "instrument": voice_instrument[v.name],
                }
                for v in self.voices
            ],
            "instruments": instruments,
            "reverb": reverb,
            "pads": {"contour": contour_pads, "tension": tension_pads},
            "params": dict(self.meta.get("params", {})),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_to_json.py tests/test_piece.py -q`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix .
git add src/sinfony/render/synth.py src/sinfony/piece.py tests/test_to_json.py
git commit --no-gpg-sign -m "feat: export pieces as JSON for the browser" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `sinfony.web` — normalize, compose, midi

**Files:**
- Create: `src/sinfony/web.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `tonal`, `ambient`, and `piece.meta["contour_shape"]` (Task 1); `Piece.to_json` (Task 2); `PAD_POINTS`, `pad_positions`, `piecewise`, `to_midi`, `MODES`, and `Scale`.
- Produces:
  - `web.normalize(params) -> dict`. Keys: `style`, `seed` (int), `key` (`(pc, mode)` or `None`), `tempo`, `wiggle`, `smooth`, `density` (each float or `None`), `contour` (`{key: np.ndarray(64)}`), and `tension` (`np.ndarray` or `None`). It raises `ValueError` with a readable message.
  - `web.build(params) -> Piece`.
  - `web.compose(params) -> dict`, which is `build(params).to_json()`.
  - `web.midi(params) -> bytes`, a standard MIDI file.
  - Key root placement:
    - tonal: `60 + ((pc + 6) % 12) - 6`
    - ambient: `57 + ((pc - 9) % 12)`

- [ ] **Step 1: Write the failing test**

`tests/test_web.py`:
```python
import io
import json

import mido
import numpy as np
import pytest

from sinfony import web
from sinfony.presets import tonal

P = web.PAD_POINTS


def test_undrawn_compose_matches_preset_exactly():
    assert web.compose({"style": "tonal", "seed": 3})["notes"] == tonal(3).to_json()["notes"]


def test_compose_is_deterministic_and_json_safe():
    params = {"style": "ambient", "seed": 1, "contour": {"A": [0.8] * P}, "wiggle": 0.1}
    a = web.compose(params)
    assert a == web.compose(params)
    json.dumps(a)


def test_normalize_defaults():
    p = web.normalize({"style": "ambient"})
    assert p["seed"] == 0 and p["key"] is None and p["tempo"] is None
    assert p["contour"] == {} and p["tension"] is None


@pytest.mark.parametrize(
    "params,msg",
    [
        ({"style": "jazz"}, "style"),
        ({"style": "tonal", "seed": -1}, "seed"),
        ({"style": "tonal", "seed": 1.5}, "whole"),
        ({"style": "tonal", "key": "13-major"}, "key"),
        ({"style": "tonal", "key": "0-dorian"}, "mode"),
        ({"style": "tonal", "tempo": 500}, "tempo"),
        ({"style": "tonal", "wiggle": 2}, "wiggle"),
        ({"style": "tonal", "contour": {"A": [0.5] * 10}}, "64"),
        ({"style": "tonal", "contour": {"A": [2.0] * P}}, "between 0 and 1"),
        ({"style": "tonal", "contour": {"Z": [0.5] * P}}, "unknown section"),
        ({"style": "tonal", "tension": [0.5] * 10}, "tension"),
        ({"style": "tonal", "bogus": 1}, "unknown parameter"),
        ("nope", "object"),
    ],
    ids=[
        "style", "seed", "seed-int", "key", "mode", "tempo", "wiggle",
        "contour-len", "contour-range", "contour-key", "tension", "unknown", "type",
    ],
)
def test_bad_params(params, msg):
    with pytest.raises(ValueError, match=msg):
        web.compose(params)


def test_key_placement():
    t = web.compose({"style": "tonal", "seed": 1, "key": "7-minor"})
    assert t["key"]["pc"] == 7 and t["key"]["root"] == 55
    assert t["params"]["key"] == "7-minor"
    a = web.compose({"style": "ambient", "seed": 1, "key": "2-dorian"})
    assert a["key"]["root"] == 62 and a["key"]["mode"] == "dorian"


def _section_mean(j, label_index):
    s = j["sections"][label_index]
    pitches = [n["pitch"] for n in j["notes"] if n["voice"] == "melody" and s["start"] <= n["onset"] < s["end"]]
    return np.mean(pitches)


def test_linked_contour_drives_every_section_of_that_material():
    base = web.compose({"style": "tonal", "seed": 5})
    high = web.compose({"style": "tonal", "seed": 5, "contour": {"A": [1.0] * P}})
    for i, s in enumerate(base["sections"]):
        if s["material"] == "A":
            assert _section_mean(high, i) > _section_mean(base, i) + 3
        else:
            assert abs(_section_mean(high, i) - _section_mean(base, i)) < 1.5


def test_drawn_tension_changes_chords():
    n = len(web.compose({"style": "tonal", "seed": 2})["sections"])
    calm = web.compose({"style": "tonal", "seed": 2, "tension": [0.0] * (P * n)})
    wild = web.compose({"style": "tonal", "seed": 2, "tension": [1.0] * (P * n)})
    assert [c["label"] for c in calm["chords"]] != [c["label"] for c in wild["chords"]]


def test_midi_bytes():
    params = {"style": "tonal", "seed": 2}
    data = web.midi(params)
    mf = mido.MidiFile(file=io.BytesIO(data))
    ons = [m for t in mf.tracks for m in t if m.type == "note_on" and m.velocity > 0]
    assert len(ons) == len(web.compose(params)["notes"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_web.py -q`
Expected: FAIL with `ImportError: cannot import name 'web' from 'sinfony'`

- [ ] **Step 3: Implement**

`src/sinfony/web.py`:
```python
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
```

Notes for the implementer:
- `build` composes a first piece only to learn its form and default contour shape. `Piece` is lazy, so no notes are generated for it.
- The second call uses the same seed, so the plan's random draws (meter, key, form) are identical.
- `test_linked_contour…` allows B to move by less than 1.5 semitones. `requantize` looks at the previous note across section boundaries, so B's first note can change slightly when A changes.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_web.py -q`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix .
git add src/sinfony/web.py tests/test_web.py
git commit --no-gpg-sign -m "feat: add sinfony.web entry point for the playground" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Web build script

**Files:**
- Create: `scripts/build_web.py`
- Modify: `.gitignore` (append `dist/` and `web/wheels/`)
- Test: `tests/test_build_web.py`

**Interfaces:**
- Consumes: the package metadata in `pyproject.toml`.
- Produces: `build(out: Path = <repo>/web/wheels) -> Path`. It builds the wheel with `uv build --wheel`, copies it to `out` (removing older `sinfony-*.whl` files there), writes `out/manifest.json` as `{"sinfony": "<wheel filename>"}`, and returns the wheel path. The worker (Task 9) reads `wheels/manifest.json`.

- [ ] **Step 1: Write the failing test**

`tests/test_build_web.py`:
```python
import importlib.util
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_script():
    spec = importlib.util.spec_from_file_location("build_web", ROOT / "scripts" / "build_web.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_writes_wheel_and_manifest(tmp_path):
    out = tmp_path / "wheels"
    (out).mkdir()
    (out / "sinfony-0.0.1-py3-none-any.whl").write_bytes(b"old")
    wheel = load_script().build(out)
    assert wheel.parent == out and wheel.name.startswith("sinfony-")
    assert json.loads((out / "manifest.json").read_text()) == {"sinfony": wheel.name}
    assert not (out / "sinfony-0.0.1-py3-none-any.whl").exists()
    names = zipfile.ZipFile(wheel).namelist()
    assert "sinfony/web.py" in names
    assert not any(n.startswith("tests/") for n in names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_web.py -q`
Expected: FAIL with `FileNotFoundError` for `scripts/build_web.py`

- [ ] **Step 3: Implement**

`scripts/build_web.py`:
```python
"""Build the playground's Python payload: the sinfony wheel + a manifest in web/wheels/."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(out: Path = ROOT / "web" / "wheels") -> Path:
    dist = ROOT / "dist"
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(dist)], cwd=ROOT, check=True)
    wheels = sorted(dist.glob("sinfony-*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        raise SystemExit("uv build produced no sinfony wheel")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("sinfony-*.whl"):
        old.unlink()
    wheel = Path(shutil.copy2(wheels[-1], out))
    (out / "manifest.json").write_text(json.dumps({"sinfony": wheel.name}))
    return wheel


if __name__ == "__main__":
    print(f"built {build()}")
```

Append to `.gitignore`:
```
dist/
web/wheels/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_web.py -q`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix .
git add scripts/build_web.py tests/test_build_web.py .gitignore
git commit --no-gpg-sign -m "build: add web build script for the sinfony wheel" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Share links (`share.js`)

**Files:**
- Create: `web/package.json`, `web/share.js`
- Test: `web/tests/share.test.js`

**Interfaces:**
- Consumes: nothing.
- Produces (ES module `web/share.js`):
  - `POINTS = 64`.
  - `quantize(v) -> number`: rounds to one of the 64 storable levels, `round(clamp01(v)·63)/63`.
  - `encodePoints(number[]) -> string` and `decodePoints(text, expected?) -> number[]`. `decodePoints` throws on a bad character or the wrong length.
  - `encodeHash(state) -> "#v=1&..."`.
  - `decodeHash(hash) -> {state, ignored: string[]}`.
  - `state` has the shape `{style, seed, key|null, tempo|null, wiggle|null, smooth|null, density|null, contour: {materialKey: number[64]}, tension: number[]|null}`.

- [ ] **Step 1: Write the failing test**

`web/package.json`:
```json
{
  "name": "sinfony-playground",
  "private": true,
  "type": "module"
}
```

`web/tests/share.test.js`:
```js
import assert from "node:assert/strict";
import test from "node:test";

import { POINTS, decodeHash, decodePoints, encodeHash, encodePoints, quantize } from "../share.js";

const ramp = Array.from({ length: POINTS }, (_, i) => i / (POINTS - 1));

test("points round-trip within quantization", () => {
  const back = decodePoints(encodePoints(ramp));
  back.forEach((v, i) => assert.ok(Math.abs(v - ramp[i]) <= 0.5 / 63 + 1e-12));
  assert.deepEqual(decodePoints(encodePoints(back)), back);
});

test("quantize is idempotent and clamps", () => {
  assert.equal(quantize(quantize(0.37)), quantize(0.37));
  assert.equal(quantize(2), 1);
  assert.equal(quantize(-1), 0);
});

test("decodePoints rejects bad input", () => {
  assert.throws(() => decodePoints("@@@"));
  assert.throws(() => decodePoints("AAA", POINTS));
});

test("hash round-trips a full state", () => {
  const state = {
    style: "ambient", seed: 42, key: "2-dorian", tempo: 60, wiggle: 0.3, smooth: 1.5, density: 0.4,
    contour: { A: ramp.map(quantize), "A@3": ramp.map((v) => quantize(1 - v)) },
    tension: [...ramp, ...ramp].map(quantize),
  };
  const { state: back, ignored } = decodeHash(encodeHash(state));
  assert.deepEqual(ignored, []);
  assert.deepEqual(back, state);
});

test("hash omits unset fields", () => {
  const h = encodeHash({
    style: "tonal", seed: 1, key: null, tempo: null, wiggle: null, smooth: null, density: null,
    contour: {}, tension: null,
  });
  assert.equal(h, "#v=1&style=tonal&seed=1");
});

test("malformed fields fall back to defaults and are reported", () => {
  const { state, ignored } = decodeHash("#v=1&style=jazz&seed=-4&key=13-major&tempo=999&c=A.@@@&t=xyz");
  assert.equal(state.style, "tonal");
  assert.equal(state.seed, 0);
  assert.equal(state.key, null);
  assert.equal(state.tempo, null);
  assert.deepEqual(state.contour, {});
  assert.equal(state.tension, null);
  assert.deepEqual([...ignored].sort(), ["c", "key", "seed", "style", "t", "tempo"]);
});

test("empty hash gives defaults", () => {
  const { state, ignored } = decodeHash("");
  assert.equal(state.style, "tonal");
  assert.equal(state.seed, 0);
  assert.deepEqual(ignored, []);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test web/tests/*.test.js`
Expected: FAIL with `Cannot find module '.../web/share.js'`

- [ ] **Step 3: Implement**

`web/share.js`:
```js
// Share links: the whole drawing and settings live in the URL hash.

export const POINTS = 64;
const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
const STYLES = ["tonal", "ambient"];
const RANGES = { tempo: [40, 200], wiggle: [0, 1], smooth: [0, 5], density: [0, 1] };

const clamp01 = (v) => Math.min(1, Math.max(0, v));
const fmt = (x) => String(Math.round(x * 1000) / 1000);

/** Round a value to one of the 64 levels a link can store. */
export function quantize(v) {
  return Math.round(clamp01(v) * 63) / 63;
}

export function encodePoints(points) {
  return points.map((v) => ALPHABET[Math.round(clamp01(v) * 63)]).join("");
}

export function decodePoints(text, expected) {
  if (expected !== undefined && text.length !== expected) {
    throw new Error(`expected ${expected} points, got ${text.length}`);
  }
  return [...text].map((ch) => {
    const i = ALPHABET.indexOf(ch);
    if (i < 0) throw new Error(`bad point character ${JSON.stringify(ch)}`);
    return i / 63;
  });
}

export function encodeHash(state) {
  const parts = ["v=1", `style=${state.style}`, `seed=${state.seed}`];
  if (state.key) parts.push(`key=${state.key}`);
  for (const name of Object.keys(RANGES)) {
    if (state[name] !== null && state[name] !== undefined) parts.push(`${name}=${fmt(state[name])}`);
  }
  const contour = Object.entries(state.contour || {});
  if (contour.length) {
    parts.push("c=" + contour.map(([k, pts]) => `${encodeURIComponent(k)}.${encodePoints(pts)}`).join("~"));
  }
  if (state.tension) parts.push(`t=${encodePoints(state.tension)}`);
  return "#" + parts.join("&");
}

export function decodeHash(hash) {
  const state = {
    style: "tonal", seed: 0, key: null, tempo: null, wiggle: null, smooth: null, density: null,
    contour: {}, tension: null,
  };
  const ignored = [];
  const q = new URLSearchParams(String(hash || "").replace(/^#/, ""));

  if (q.has("style")) {
    const s = q.get("style");
    if (STYLES.includes(s)) state.style = s;
    else ignored.push("style");
  }
  if (q.has("seed")) {
    const raw = q.get("seed");
    const n = Number(raw);
    if (raw !== "" && Number.isInteger(n) && n >= 0 && n < 2 ** 31) state.seed = n;
    else ignored.push("seed");
  }
  if (q.has("key")) {
    const m = /^(\d{1,2})-([a-z]+)$/.exec(q.get("key"));
    if (m && Number(m[1]) <= 11) state.key = q.get("key");
    else ignored.push("key");
  }
  for (const [name, [lo, hi]] of Object.entries(RANGES)) {
    if (!q.has(name)) continue;
    const raw = q.get(name);
    const n = Number(raw);
    if (raw !== "" && Number.isFinite(n) && n >= lo && n <= hi) state[name] = n;
    else ignored.push(name);
  }
  if (q.has("c")) {
    try {
      for (const entry of q.get("c").split("~")) {
        const dot = entry.indexOf(".");
        if (dot < 1) throw new Error("missing section key");
        state.contour[decodeURIComponent(entry.slice(0, dot))] = decodePoints(entry.slice(dot + 1), POINTS);
      }
    } catch {
      state.contour = {};
      ignored.push("c");
    }
  }
  if (q.has("t")) {
    try {
      const pts = decodePoints(q.get("t"));
      if (!pts.length || pts.length % POINTS) throw new Error("tension length");
      state.tension = pts;
    } catch {
      ignored.push("t");
    }
  }
  return { state, ignored };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test web/tests/*.test.js`
Expected: `# pass 7`, `# fail 0`

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/share.js web/tests/share.test.js
git commit --no-gpg-sign -m "feat(web): encode drawings and settings in share links" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Drawing pads (`pads.js`, `canvas.js`)

**Files:**
- Create: `web/canvas.js`, `web/pads.js`
- Test: `web/tests/pads.test.js`

**Interfaces:**
- Consumes: nothing (DOM is used only inside `PadView` methods).
- Produces:
  - `canvas.js`: `fitCanvas(canvas) -> CanvasRenderingContext2D`. It sizes the backing store to the canvas's CSS size × devicePixelRatio and sets the transform, so callers draw in CSS pixels.
  - `pads.js` pure functions:
    - `POINTS = 64`
    - `layoutSections(sections) -> [{label, material, u0, u1}]`. Widths are proportional to beats when `start`/`end` are present, else equal. `material` defaults to the label with trailing `'` removed.
    - `pointU(sec, k) -> number`
    - `cleanStroke(samples) -> [{u, y}]`: sorted by u, y clamped to [0, 1].
    - `strokeAt(stroke, u) -> number | null`
    - `smoothRange(points, lo, hi) -> number[]`: keeps indices `lo` and `hi`.
    - `applyStroke(values, sections, stroke, linked) -> {values, touched: Set<string>}`. The slot key is the material when linked, else `String(index)`.
    - `mergePads(defaults, values, drawn) -> values`: drawn slots keep the user's points; other slots take the defaults.
    - `sameLayout(a, b) -> boolean`: same number of sections and the same materials in the same order.
  - `pads.js` class `PadView(canvas, {linked, colors, onCommit})`:
    - `setModel(sections, values, drawnSlots)`
    - `draw(playheadU = null)`
    - `onCommit({values, touched})` is called on pen-up.

- [ ] **Step 1: Write the failing test**

`web/tests/pads.test.js`:
```js
import assert from "node:assert/strict";
import test from "node:test";

import {
  POINTS, applyStroke, cleanStroke, layoutSections, mergePads, pointU, sameLayout, smoothRange, strokeAt,
} from "../pads.js";

const flat = (v) => Array(POINTS).fill(v);
const tonalSections = [{ label: "A" }, { label: "A'" }, { label: "B" }, { label: "A" }];

test("layoutSections: equal widths without beats, proportional with beats", () => {
  const eq = layoutSections(tonalSections);
  assert.deepEqual(eq.map((s) => s.material), ["A", "A", "B", "A"]);
  assert.equal(eq[1].u0, 0.25);
  assert.equal(eq[3].u1, 1);
  const prop = layoutSections([
    { label: "A", material: "A", start: 0, end: 8 },
    { label: "A'", material: "A@3", start: 8, end: 32 },
  ]);
  assert.equal(prop[0].u1, 0.25);
  assert.equal(prop[1].material, "A@3");
});

test("pointU spans each section by cell centres", () => {
  const [sec] = layoutSections([{ label: "A" }]);
  assert.equal(pointU(sec, 0), 0.5 / POINTS);
  assert.equal(pointU(sec, POINTS - 1), 1 - 0.5 / POINTS);
});

test("cleanStroke sorts and clamps", () => {
  const s = cleanStroke([{ u: 0.5, y: 2 }, { u: 0.1, y: -1 }]);
  assert.deepEqual(s, [{ u: 0.1, y: 0 }, { u: 0.5, y: 1 }]);
});

test("strokeAt interpolates inside and is null outside", () => {
  const s = [{ u: 0.2, y: 0 }, { u: 0.4, y: 1 }];
  assert.equal(strokeAt(s, 0.3), 0.5);
  assert.equal(strokeAt(s, 0.1), null);
  assert.equal(strokeAt(s, 0.5), null);
});

test("smoothRange keeps the endpoints and averages inside", () => {
  const out = smoothRange([0, 0, 3, 0, 0], 0, 4);
  assert.deepEqual(out, [0, 1, 1, 1, 0]);
});

test("linked stroke writes one material shared by every section of it", () => {
  const sections = layoutSections(tonalSections);
  const values = { A: flat(0.5), B: flat(0.5) };
  const stroke = [{ u: 0, y: 1 }, { u: 0.25, y: 1 }];
  const { values: next, touched } = applyStroke(values, sections, stroke, true);
  assert.deepEqual([...touched], ["A"]);
  assert.ok(next.A.every((v) => v === 1));
  assert.equal(next.B, values.B);
  assert.ok(values.A.every((v) => v === 0.5), "input is not mutated");
});

test("unlinked stroke writes only the sections it crosses", () => {
  const sections = layoutSections(tonalSections);
  const values = Object.fromEntries(sections.map((_, i) => [String(i), flat(0.2)]));
  const stroke = [{ u: 0.2, y: 0.9 }, { u: 0.3, y: 0.9 }];
  const { values: next, touched } = applyStroke(values, sections, stroke, false);
  assert.deepEqual([...touched].sort(), ["0", "1"]);
  assert.equal(next["3"], values["3"]);
});

test("mergePads keeps drawn slots and fills the rest from defaults", () => {
  const defaults = { A: flat(0.3), B: flat(0.4) };
  const drawn = new Set(["A"]);
  const merged = mergePads(defaults, { A: flat(0.9), B: flat(0.5) }, drawn);
  assert.deepEqual(merged, { A: flat(0.9), B: flat(0.4) });
  assert.deepEqual(mergePads(defaults, {}, new Set(["A"])), defaults);
});

test("sameLayout compares materials in order", () => {
  const a = [{ material: "A" }, { material: "B" }];
  assert.ok(sameLayout(a, [{ material: "A" }, { material: "B" }]));
  assert.ok(!sameLayout(a, [{ material: "A" }, { material: "B" }, { material: "C" }]));
  assert.ok(!sameLayout(a, [{ material: "B" }, { material: "A" }]));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test web/tests/*.test.js`
Expected: FAIL with `Cannot find module '.../web/pads.js'`

- [ ] **Step 3: Implement**

`web/canvas.js`:
```js
// Size a canvas's backing store for sharp drawing on HiDPI screens.

export function fitCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const w = Math.max(1, Math.round(canvas.clientWidth * dpr));
  const h = Math.max(1, Math.round(canvas.clientHeight * dpr));
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return ctx;
}
```

`web/pads.js`:
```js
// Drawing pads: pure geometry (tested in Node) plus a small canvas view.

import { fitCanvas } from "./canvas.js";

export const POINTS = 64;

/** Place sections across [0, 1]: by beats when known, else equal widths. */
export function layoutSections(sections) {
  const spans = sections.map((s) => (s.end !== undefined ? s.end - s.start : 1));
  const total = spans.reduce((a, b) => a + b, 0);
  let u = 0;
  return sections.map((s, i) => {
    const u0 = u;
    u += spans[i] / total;
    return {
      label: s.label,
      material: s.material ?? s.label.replace(/'+$/, ""),
      u0,
      u1: i === sections.length - 1 ? 1 : u,
    };
  });
}

/** Horizontal position (0..1) of point k of a section: evenly spaced cell centres. */
export function pointU(sec, k) {
  return sec.u0 + ((k + 0.5) / POINTS) * (sec.u1 - sec.u0);
}

/** Pointer samples -> stroke sorted by u, y clamped (later samples win at equal u). */
export function cleanStroke(samples) {
  const byU = new Map();
  for (const p of samples) byU.set(Math.round(p.u * 1e4), { u: p.u, y: Math.min(1, Math.max(0, p.y)) });
  return [...byU.values()].sort((a, b) => a.u - b.u);
}

/** Height of the stroke at u (linear between samples), or null outside it. */
export function strokeAt(stroke, u) {
  if (!stroke.length || u < stroke[0].u || u > stroke[stroke.length - 1].u) return null;
  let i = 1;
  while (i < stroke.length && stroke[i].u < u) i++;
  if (i >= stroke.length) return stroke[stroke.length - 1].y;
  const a = stroke[i - 1];
  const b = stroke[i];
  if (b.u === a.u) return b.y;
  return a.y + ((u - a.u) / (b.u - a.u)) * (b.y - a.y);
}

/** 3-point moving average over lo..hi, keeping lo and hi unchanged. */
export function smoothRange(points, lo, hi) {
  const out = points.slice();
  for (let k = lo + 1; k < hi; k++) out[k] = (points[k - 1] + points[k] + points[k + 1]) / 3;
  return out;
}

const slotOf = (sec, i, linked) => (linked ? sec.material : String(i));

/** Apply a stroke; returns new arrays for touched slots and the set of touched slot keys. */
export function applyStroke(values, sections, stroke, linked) {
  const next = { ...values };
  const touched = new Set();
  sections.forEach((sec, i) => {
    const slot = slotOf(sec, i, linked);
    const pts = (next[slot] ?? Array(POINTS).fill(0.5)).slice();
    let lo = Infinity;
    let hi = -Infinity;
    for (let k = 0; k < POINTS; k++) {
      const y = strokeAt(stroke, pointU(sec, k));
      if (y !== null) {
        pts[k] = y;
        lo = Math.min(lo, k);
        hi = Math.max(hi, k);
      }
    }
    if (hi >= lo) {
      next[slot] = smoothRange(pts, lo, hi);
      touched.add(slot);
    }
  });
  return { values: next, touched };
}

/** Drawn slots keep the user's points; everything else comes from the defaults. */
export function mergePads(defaults, values, drawn) {
  const out = {};
  for (const [slot, pts] of Object.entries(defaults)) {
    out[slot] = drawn.has(slot) && values[slot] ? values[slot] : pts;
  }
  return out;
}

/** True when both section lists have the same materials in the same order. */
export function sameLayout(a, b) {
  return a.length === b.length && a.every((s, i) => s.material === b[i].material);
}

export class PadView {
  constructor(canvas, { linked, colors, onCommit }) {
    this.canvas = canvas;
    this.linked = linked;
    this.colors = colors;
    this.onCommit = onCommit;
    this.sections = [];
    this.values = {};
    this.drawn = new Set();
    this.samples = null;
    this.preview = null;
    canvas.addEventListener("pointerdown", (e) => this._down(e));
    canvas.addEventListener("pointermove", (e) => this._move(e));
    canvas.addEventListener("pointerup", (e) => this._up(e));
    canvas.addEventListener("pointercancel", () => this._cancel());
    new ResizeObserver(() => this.draw()).observe(canvas);
  }

  setModel(sections, values, drawnSlots) {
    this.sections = layoutSections(sections);
    this.values = values;
    this.drawn = new Set(drawnSlots);
    this.draw();
  }

  _uv(e) {
    const r = this.canvas.getBoundingClientRect();
    return { u: (e.clientX - r.left) / r.width, y: 1 - (e.clientY - r.top) / r.height };
  }

  _down(e) {
    if (!this.sections.length) return;
    try {
      this.canvas.setPointerCapture(e.pointerId);
    } catch {
      /* synthetic or already-released pointers can't be captured; drawing still works */
    }
    this.samples = [this._uv(e)];
  }

  _move(e) {
    if (!this.samples) return;
    this.samples.push(this._uv(e));
    this.preview = applyStroke(this.values, this.sections, cleanStroke(this.samples), this.linked).values;
    this.draw();
  }

  _up(e) {
    if (!this.samples) return;
    this.samples.push(this._uv(e));
    const { values, touched } = applyStroke(this.values, this.sections, cleanStroke(this.samples), this.linked);
    this.samples = null;
    this.preview = null;
    if (!touched.size) return this.draw();
    this.values = values;
    touched.forEach((slot) => this.drawn.add(slot));
    this.draw();
    this.onCommit({ values, touched });
  }

  _cancel() {
    this.samples = null;
    this.preview = null;
    this.draw();
  }

  draw(playheadU = null) {
    const ctx = fitCanvas(this.canvas);
    const W = this.canvas.clientWidth;
    const H = this.canvas.clientHeight;
    const c = this.colors();
    ctx.clearRect(0, 0, W, H);
    const values = this.preview ?? this.values;
    const counts = {};
    for (const s of this.sections) counts[s.material] = (counts[s.material] || 0) + 1;

    this.sections.forEach((sec, i) => {
      const x0 = sec.u0 * W;
      const x1 = sec.u1 * W;
      ctx.fillStyle = i % 2 ? c.band : c.bandAlt;
      ctx.fillRect(x0, 0, x1 - x0, H);
      if (this.linked && counts[sec.material] > 1) {
        ctx.globalAlpha = 0.07; // linked sections share an accent tint
        ctx.fillStyle = c.accent;
        ctx.fillRect(x0, 0, x1 - x0, H);
        ctx.globalAlpha = 1;
      }
      ctx.fillStyle = c.muted;
      ctx.font = "600 12px system-ui, sans-serif";
      const linkedMark = this.linked && counts[sec.material] > 1 ? " ⛓" : "";
      ctx.fillText(sec.label + linkedMark, x0 + 8, 16);
      if (i) {
        ctx.strokeStyle = c.grid;
        ctx.beginPath();
        ctx.moveTo(x0, 0);
        ctx.lineTo(x0, H);
        ctx.stroke();
      }
    });

    this.sections.forEach((sec, i) => {
      const slot = slotOf(sec, i, this.linked);
      const pts = values[slot];
      if (!pts) return;
      const drawn = this.drawn.has(slot) || (this.preview && this.preview[slot] !== this.values[slot]);
      ctx.strokeStyle = drawn ? c.accent : c.muted;
      ctx.lineWidth = drawn ? 2.5 : 1.5;
      ctx.setLineDash(drawn ? [] : [5, 4]);
      ctx.beginPath();
      pts.forEach((v, k) => {
        const x = pointU(sec, k) * W;
        const y = (1 - v) * (H - 24) + 20;
        if (k) ctx.lineTo(x, y);
        else ctx.moveTo(x, y);
      });
      ctx.stroke();
    });
    ctx.setLineDash([]);

    if (playheadU !== null) {
      ctx.strokeStyle = c.playhead;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(playheadU * W, 0);
      ctx.lineTo(playheadU * W, H);
      ctx.stroke();
    }
  }
}
```

Notes for the implementer:
- `pads.js` imports `canvas.js`, which touches `window` only inside `fitCanvas`, so importing it in Node is safe.
- `ResizeObserver` is created only in the `PadView` constructor, which Node tests never call.
- In `test_smoothRange`, `[0, 0, 3, 0, 0]` averages to `[0, 1, 1, 1, 0]`: index 1 is (0 + 0 + 3)/3, index 2 is (0 + 3 + 0)/3, index 3 is (3 + 0 + 0)/3.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test web/tests/*.test.js`
Expected: `# fail 0` (16 tests across share and pads)

- [ ] **Step 5: Commit**

```bash
git add web/canvas.js web/pads.js web/tests/pads.test.js
git commit --no-gpg-sign -m "feat(web): add drawing pads with linked repeat sections" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Browser synth (`synth.js`)

**Files:**
- Create: `web/synth.js`
- Test: `web/tests/synth.test.js`

**Interfaces:**
- Consumes: instrument dicts in the `to_json()` format (`{partials: [[ratio, amp, decay]...], attack, release, inharmonicity, hammer, detune_cents, gain}`), from Task 2.
- Produces:
  - Pure functions:
    - `MAX_VOICES = 48`
    - `midiToHz(pitch)`
    - `partialList(inst, pitch, sampleRate = 44100) -> [{freq, amp, decay}]`
    - `noteLevel(inst, vel)`
    - `impulseData(sampleRate, seconds, seed = 1) -> Float32Array`: unit energy, decaying to −60 dB at the end
    - `voiceToSteal(voices, when, max = MAX_VOICES) -> voice | null`: the oldest voice sounding at `when`, if the cap is reached
  - Class `Synth(ctx)`:
    - `setReverb({seconds, mix})`
    - `noteOn(inst, pitch, vel, when, dur) -> handle {start, end, stop(at)}`
    - `cancelAfter(t)`: stops notes starting after `t`
    - `stopAll(at)`

- [ ] **Step 1: Write the failing test**

`web/tests/synth.test.js`:
```js
import assert from "node:assert/strict";
import test from "node:test";

import { MAX_VOICES, impulseData, midiToHz, noteLevel, partialList, voiceToSteal } from "../synth.js";

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test("midiToHz is equal temperament", () => {
  close(midiToHz(69), 440);
  close(midiToHz(81), 880);
  close(midiToHz(60), 261.6255653005986, 1e-9);
});

test("partials apply inharmonicity", () => {
  const inst = { partials: [[1, 1, 0], [6, 0.5, 1]], inharmonicity: 0.001, detune_cents: 0 };
  const [p1, p6] = partialList(inst, 57);
  close(p1.freq, 220 * Math.sqrt(1.001));
  close(p6.freq, 220 * 6 * Math.sqrt(1 + 0.001 * 36));
  assert.equal(p6.amp, 0.5);
  assert.equal(p6.decay, 1);
});

test("detune doubles oscillators at half amplitude", () => {
  const inst = { partials: [[1, 1, 0]], inharmonicity: 0, detune_cents: 6 };
  const ps = partialList(inst, 69);
  assert.equal(ps.length, 2);
  assert.ok(ps[0].freq < 440 && ps[1].freq > 440);
  assert.equal(ps[0].amp, 0.5);
});

test("partials above Nyquist are dropped", () => {
  const inst = { partials: [[1, 1, 0], [100, 1, 0]], inharmonicity: 0, detune_cents: 0 };
  assert.equal(partialList(inst, 100, 44100).length, 1);
});

test("noteLevel follows gain * vel^1.5", () => {
  close(noteLevel({ gain: 0.6 }, 0.5), 0.6 * 0.5 ** 1.5);
  close(noteLevel({}, 1), 1);
});

test("impulse is deterministic, unit energy, and decays", () => {
  const a = impulseData(1000, 2);
  const b = impulseData(1000, 2);
  assert.equal(a.length, 2000);
  assert.deepEqual(a, b);
  close(a.reduce((s, v) => s + v * v, 0), 1, 1e-6);
  const head = a.slice(0, 200).reduce((s, v) => s + v * v, 0);
  const tail = a.slice(1800).reduce((s, v) => s + v * v, 0);
  assert.ok(tail < head / 1000);
});

test("voiceToSteal picks the oldest sounding voice only at the cap", () => {
  const voices = Array.from({ length: MAX_VOICES }, (_, i) => ({ start: i, end: 1000 }));
  assert.equal(voiceToSteal(voices, 100).start, 0);
  assert.equal(voiceToSteal(voices.slice(1), 100), null);
  assert.equal(voiceToSteal([{ start: 0, end: 5 }], 10, 1), null);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test web/tests/*.test.js`
Expected: FAIL with `Cannot find module '.../web/synth.js'`

- [ ] **Step 3: Implement**

`web/synth.js`:
```js
// Web Audio port of sinfony's additive instruments: each note is a few decaying sines.

export const MAX_VOICES = 48;

export function midiToHz(pitch) {
  return 440 * 2 ** ((pitch - 69) / 12);
}

/** One entry per oscillator. Stiff strings sound sharp: f_n = n f0 sqrt(1 + B n^2). */
export function partialList(inst, pitch, sampleRate = 44100) {
  const f0 = midiToHz(pitch);
  const B = inst.inharmonicity || 0;
  const detunes = inst.detune_cents ? [-inst.detune_cents, inst.detune_cents] : [0];
  const out = [];
  for (const [ratio, amp, decay] of inst.partials) {
    const f = f0 * ratio * Math.sqrt(1 + B * ratio * ratio);
    for (const cents of detunes) {
      const freq = f * 2 ** (cents / 1200);
      if (freq < sampleRate / 2) out.push({ freq, amp: amp / detunes.length, decay });
    }
  }
  return out;
}

export function noteLevel(inst, vel) {
  return (inst.gain ?? 1) * vel ** 1.5;
}

/** Exponentially decaying noise (-60 dB at the end), normalized to unit energy. */
export function impulseData(sampleRate, seconds, seed = 1) {
  const n = Math.max(1, Math.floor(seconds * sampleRate));
  const data = new Float32Array(n);
  let s = seed >>> 0 || 1;
  let energy = 0;
  for (let i = 0; i < n; i++) {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0; // linear congruential generator
    data[i] = (s / 2 ** 31 - 1) * Math.exp((-6.91 * i) / n);
    energy += data[i] * data[i];
  }
  const norm = 1 / Math.sqrt(energy || 1);
  for (let i = 0; i < n; i++) data[i] *= norm;
  return data;
}

/** At the voice cap, the oldest voice still sounding at `when`; otherwise null. */
export function voiceToSteal(voices, when, max = MAX_VOICES) {
  const sounding = voices.filter((v) => v.start <= when && v.end > when);
  if (sounding.length < max) return null;
  return sounding.reduce((a, b) => (b.start < a.start ? b : a));
}

export class Synth {
  constructor(ctx) {
    this.ctx = ctx;
    this.input = ctx.createGain();
    this.dry = ctx.createGain();
    this.wet = ctx.createGain();
    this.convolver = ctx.createConvolver();
    this.convolver.normalize = false;
    this.limiter = ctx.createDynamicsCompressor();
    this.limiter.threshold.value = -6;
    this.limiter.knee.value = 0;
    this.limiter.ratio.value = 20;
    this.limiter.attack.value = 0.003;
    this.limiter.release.value = 0.1;
    this.master = ctx.createGain();
    this.master.gain.value = 0.5;
    this.input.connect(this.dry).connect(this.limiter);
    this.input.connect(this.convolver).connect(this.wet).connect(this.limiter);
    this.limiter.connect(this.master).connect(ctx.destination);
    this.noise = this._noiseBuffer();
    this.voices = [];
    this.setReverb({ seconds: 1.5, mix: 0.25 });
  }

  _noiseBuffer() {
    const data = impulseData(this.ctx.sampleRate, 0.1, 7).map((v, i, a) => v / Math.exp((-6.91 * i) / a.length));
    const buf = this.ctx.createBuffer(1, data.length, this.ctx.sampleRate);
    buf.getChannelData(0).set(data);
    return buf;
  }

  setReverb({ seconds, mix }) {
    const on = seconds > 0;
    if (on) {
      const data = impulseData(this.ctx.sampleRate, seconds);
      const buf = this.ctx.createBuffer(1, data.length, this.ctx.sampleRate);
      buf.getChannelData(0).set(data);
      this.convolver.buffer = buf;
    }
    this.wet.gain.value = on ? mix : 0;
    this.dry.gain.value = on ? 1 - mix : 1;
  }

  noteOn(inst, pitch, vel, when, dur) {
    const ctx = this.ctx;
    this.voices = this.voices.filter((v) => !v.stopped && v.end > ctx.currentTime);
    voiceToSteal(this.voices, when)?.stop(when);

    const level = noteLevel(inst, vel);
    const end = when + dur;
    const out = ctx.createGain();
    out.gain.setValueAtTime(level, when);
    out.gain.setValueAtTime(level, end);
    out.gain.linearRampToValueAtTime(0, end + inst.release);
    out.connect(this.input);

    const sources = [];
    const attack = Math.max(inst.attack, 0.001);
    for (const p of partialList(inst, pitch, ctx.sampleRate)) {
      const osc = ctx.createOscillator();
      osc.frequency.value = p.freq;
      const g = ctx.createGain();
      g.gain.setValueAtTime(0, when);
      g.gain.linearRampToValueAtTime(p.amp, when + attack);
      if (p.decay > 0) g.gain.setTargetAtTime(0, when + attack, 1 / p.decay);
      osc.connect(g).connect(out);
      osc.start(when);
      osc.stop(end + inst.release + 0.05);
      sources.push(osc);
    }
    if (inst.hammer > 0) {
      const src = ctx.createBufferSource();
      src.buffer = this.noise;
      const lp = ctx.createBiquadFilter();
      lp.type = "lowpass";
      lp.frequency.value = 3000;
      const g = ctx.createGain();
      g.gain.setValueAtTime(inst.hammer, when);
      g.gain.setTargetAtTime(0, when, 0.004);
      src.connect(lp).connect(g).connect(out);
      src.start(when);
      src.stop(when + 0.1);
      sources.push(src);
    }
    const handle = { start: when, end: end + inst.release, out, sources, stopped: false };
    handle.stop = (at) => this._stop(handle, at);
    this.voices.push(handle);
    return handle;
  }

  _stop(h, at) {
    if (h.stopped) return;
    h.stopped = true;
    const t = Math.max(at, this.ctx.currentTime);
    if (h.start >= t) {
      for (const s of h.sources) {
        try { s.stop(); } catch { /* already stopped */ }
      }
      h.out.disconnect();
      return;
    }
    h.out.gain.cancelScheduledValues(t);
    h.out.gain.setValueAtTime(h.out.gain.value, t);
    h.out.gain.linearRampToValueAtTime(0, t + 0.05);
    for (const s of h.sources) {
      try { s.stop(t + 0.06); } catch { /* already stopped */ }
    }
  }

  cancelAfter(t) {
    for (const v of this.voices) if (v.start > t) v.stop(t);
  }

  stopAll(at) {
    for (const v of this.voices) v.stop(at);
    this.voices = [];
  }
}
```

Note for the implementer: `_noiseBuffer` reuses `impulseData`'s deterministic generator and then removes its decay, which gives flat white noise. The hammer's own envelope supplies the 4 ms decay.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test web/tests/*.test.js`
Expected: `# fail 0`

- [ ] **Step 5: Commit**

```bash
git add web/synth.js web/tests/synth.test.js
git commit --no-gpg-sign -m "feat(web): port additive instruments to Web Audio" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Player (`player.js`)

**Files:**
- Create: `web/player.js`
- Test: `web/tests/player.test.js`

**Interfaces:**
- Consumes:
  - From the piece JSON (Task 2): `beat_s`, `notes[]` (sorted by `onset_s`), `duration_s`, `voices[]`, `instruments{}`, `reverb`.
  - From the `Synth` API (Task 7): `noteOn`, `cancelAfter`, `stopAll`, `setReverb`.
- Produces:
  - Constants `TICK_MS = 25` and `LOOKAHEAD_S = 0.1`.
  - Pure functions:
    - `secondsAtBeat(beatS, beat)` and `beatAtSeconds(beatS, s)`: linear, extrapolating past both ends
    - `swapPosition(oldPiece, newPiece, seconds)`
    - `firstNoteAt(notes, t)` and `notesInWindow(notes, t0, t1)`: the window is [t0, t1)
  - Class `Player(ctx, synth, {onEnd})`:
    - methods `load(piece)`, `play()`, `stop()`, `tick()`
    - getters `position` (seconds) and `playing`
    - property `loop`

- [ ] **Step 1: Write the failing test**

`web/tests/player.test.js`:
```js
import assert from "node:assert/strict";
import test from "node:test";

import { Player, beatAtSeconds, notesInWindow, secondsAtBeat, swapPosition } from "../player.js";

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);
const halfSecondBeats = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4];

test("beat <-> seconds interpolation and inverse", () => {
  close(secondsAtBeat(halfSecondBeats, 3), 1.5);
  close(secondsAtBeat(halfSecondBeats, 2.5), 1.25);
  close(beatAtSeconds(halfSecondBeats, 1.25), 2.5);
  close(beatAtSeconds(halfSecondBeats, 5), 10); // extrapolates past the end
  close(secondsAtBeat(halfSecondBeats, -1), -0.5);
});

test("notesInWindow is half-open", () => {
  const notes = [0, 0.1, 0.2, 0.3].map((onset_s) => ({ onset_s }));
  assert.deepEqual(notesInWindow(notes, 0.1, 0.3).map((n) => n.onset_s), [0.1, 0.2]);
});

test("swapPosition keeps the beat when the tempo changes", () => {
  const old = { beat_s: halfSecondBeats };
  const quick = { beat_s: halfSecondBeats.map((s) => s / 2) };
  close(swapPosition(old, quick, 2), 1); // beat 4 in both pieces
});

function fakeWorld() {
  const ctx = { currentTime: 10 };
  const calls = [];
  const synth = {
    noteOn: (inst, pitch, vel, when, dur) => calls.push({ pitch, when, dur }),
    cancelAfter: (t) => calls.push({ cancelAfter: t }),
    stopAll: () => calls.push({ stopAll: true }),
    setReverb: () => {},
  };
  return { ctx, synth, calls };
}

const piece = (beatSeconds, onsets) => ({
  beat_s: Array.from({ length: 9 }, (_, i) => i * beatSeconds),
  duration_s: 8 * beatSeconds,
  notes: onsets.map((b, i) => ({ voice: "melody", pitch: 60 + i, vel: 0.8, onset_s: b * beatSeconds, dur_s: 0.1 })),
  voices: [{ name: "melody", instrument: "epiano" }],
  instruments: { epiano: { partials: [[1, 1, 1]], attack: 0.01, release: 0.1, gain: 1 } },
  reverb: { seconds: 1, mix: 0.2 },
});

test("player schedules the look-ahead window on the audio clock", () => {
  const { ctx, synth, calls } = fakeWorld();
  const p = new Player(ctx, synth);
  p.load(piece(0.5, [0, 0.1, 1]));
  p.play();
  const first = calls.filter((c) => c.pitch !== undefined);
  assert.deepEqual(first.map((c) => c.pitch), [60, 61]); // onsets 0 s and 0.05 s are within 0.1 s
  close(first[0].when, p.origin);
  p.stop();
});

test("hot swap continues from the same beat", () => {
  const { ctx, synth, calls } = fakeWorld();
  const p = new Player(ctx, synth);
  p.load(piece(0.5, [0, 4, 6]));
  p.play();
  ctx.currentTime += 2.05; // play() starts 0.05 s ahead, so this is 2 s in = beat 4 at 0.5 s per beat
  p.load(piece(0.25, [0, 4, 6])); // twice as fast: beat 4 is at 1 s
  close(p.position, 1, 1e-6);
  assert.ok(calls.some((c) => c.cancelAfter !== undefined));
  p.tick();
  const scheduled = calls.filter((c) => c.pitch !== undefined).map((c) => c.pitch);
  assert.ok(scheduled.includes(61), "note at beat 4 plays in the new piece");
  p.stop();
});

test("player stops at the end unless looping", () => {
  const { ctx, synth } = fakeWorld();
  let ended = 0;
  const p = new Player(ctx, synth, { onEnd: () => ended++ });
  p.load(piece(0.5, [0]));
  p.play();
  ctx.currentTime += 5;
  p.tick();
  assert.equal(p.playing, false);
  assert.equal(ended, 1);
  p.loop = true;
  p.play();
  ctx.currentTime += 5;
  p.tick();
  assert.equal(p.playing, true);
  close(p.position, 0, 0.06);
  p.stop();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test web/tests/*.test.js`
Expected: FAIL with `Cannot find module '.../web/player.js'`

- [ ] **Step 3: Implement**

`web/player.js`:
```js
// Look-ahead scheduling: Python decided every time in seconds; the player just plays it.

export const TICK_MS = 25;
export const LOOKAHEAD_S = 0.1;
const LEAD_S = 0.05; // small head start so the first notes are never late
const TAIL_S = 0.5; // let the last notes ring before stopping

/** Seconds at a (fractional) beat, interpolating the beat_s table. */
export function secondsAtBeat(beatS, beat) {
  const n = beatS.length;
  if (n < 2) return 0;
  if (beat <= 0) return beat * (beatS[1] - beatS[0]);
  const i = Math.min(Math.floor(beat), n - 2);
  return beatS[i] + (beat - i) * (beatS[i + 1] - beatS[i]);
}

/** Inverse of secondsAtBeat. */
export function beatAtSeconds(beatS, s) {
  const n = beatS.length;
  if (n < 2) return 0;
  if (s <= 0) return s / (beatS[1] - beatS[0]);
  if (s >= beatS[n - 1]) return n - 2 + (s - beatS[n - 2]) / (beatS[n - 1] - beatS[n - 2]);
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (beatS[mid] <= s) lo = mid;
    else hi = mid;
  }
  return lo + (s - beatS[lo]) / (beatS[hi] - beatS[lo]);
}

/** Where to continue in a new piece: the same beat, at the new piece's tempo. */
export function swapPosition(oldPiece, newPiece, seconds) {
  return secondsAtBeat(newPiece.beat_s, beatAtSeconds(oldPiece.beat_s, seconds));
}

/** Index of the first note starting at or after t (notes sorted by onset_s). */
export function firstNoteAt(notes, t) {
  let lo = 0;
  let hi = notes.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (notes[mid].onset_s < t) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export function notesInWindow(notes, t0, t1) {
  const out = [];
  for (let i = firstNoteAt(notes, t0); i < notes.length && notes[i].onset_s < t1; i++) out.push(notes[i]);
  return out;
}

export class Player {
  constructor(ctx, synth, { onEnd } = {}) {
    this.ctx = ctx;
    this.synth = synth;
    this.onEnd = onEnd;
    this.piece = null;
    this.loop = false;
    this._playing = false;
    this.offset = 0; // position while stopped
    this.origin = 0; // audio-clock time of piece time 0 while playing
    this.cursor = 0; // piece time scheduled up to
    this.timer = null;
    this.voiceInstrument = {};
  }

  get playing() {
    return this._playing;
  }

  get position() {
    return this._playing ? this.ctx.currentTime - this.origin : this.offset;
  }

  load(piece) {
    const old = this.piece;
    this.piece = piece;
    this.voiceInstrument = Object.fromEntries(piece.voices.map((v) => [v.name, v.instrument]));
    this.synth.setReverb(piece.reverb);
    if (!old) return;
    if (this._playing) {
      const pos = swapPosition(old, piece, this.position);
      this.synth.cancelAfter(this.ctx.currentTime);
      this.origin = this.ctx.currentTime - pos;
      this.cursor = pos;
    } else {
      this.offset = swapPosition(old, piece, this.offset);
    }
  }

  play() {
    if (!this.piece || this._playing) return;
    const start = this.offset >= this.piece.duration_s ? 0 : this.offset;
    this._playing = true;
    this._startAt(start);
    this.timer = setInterval(() => this.tick(), TICK_MS);
    this.tick();
  }

  stop() {
    if (!this._playing) return;
    this.offset = this.position;
    this._playing = false;
    clearInterval(this.timer);
    this.timer = null;
    this.synth.stopAll(this.ctx.currentTime);
  }

  _startAt(pos) {
    this.origin = this.ctx.currentTime + LEAD_S - pos;
    this.cursor = pos;
  }

  tick() {
    if (!this._playing || !this.piece) return;
    const now = this.ctx.currentTime - this.origin;
    if (now >= this.piece.duration_s + TAIL_S) {
      if (this.loop) {
        this._startAt(0);
      } else {
        this.stop();
        this.offset = 0;
        this.onEnd?.();
        return;
      }
    }
    const until = Math.max(this.ctx.currentTime - this.origin, 0) + LOOKAHEAD_S;
    for (const n of notesInWindow(this.piece.notes, this.cursor, until)) {
      const inst = this.piece.instruments[this.voiceInstrument[n.voice]];
      this.synth.noteOn(inst, n.pitch, n.vel, this.origin + n.onset_s, n.dur_s);
    }
    this.cursor = Math.max(this.cursor, until);
  }
}
```

Notes for the implementer:
- In `player schedules the look-ahead window…`, `play()` puts piece time 0 at `currentTime + 0.05`. The first tick therefore covers piece time [0, 0.1) (`until = max(-0.05, 0) + 0.1`), which includes the notes at 0 s and 0.05 s but not the one at 0.5 s.
- In the hot-swap test, after `load()` the position is the new piece's beat 4 (1 s). The next `tick()` schedules from 1 s, which is where the note at beat 4 sits.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test web/tests/*.test.js`
Expected: `# fail 0`

- [ ] **Step 5: Commit**

```bash
git add web/player.js web/tests/player.test.js
git commit --no-gpg-sign -m "feat(web): add look-ahead player with hot swap" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Engine client and Pyodide worker (`engine.js`, `worker.js`)

**Files:**
- Create: `web/engine.js`, `web/worker.js`
- Test: `web/tests/engine.test.js`

**Interfaces:**
- Consumes:
  - From `sinfony.web` (Task 3): `compose` and `midi`.
  - `wheels/manifest.json` (Task 4).
- Produces:
  - `Engine(worker, {onProgress})` with two methods:
    - `compose(params) -> Promise<piece | null>`: resolves `null` when a newer request replaced this one while it waited.
    - `midi(params) -> Promise<string>`: base64 MIDI bytes.
  - Rejections are `Error` objects with `.kind` set to `"value"`, `"internal"`, or `"load"`.
  - Worker message protocol:

    | Direction | Message |
    |---|---|
    | page → worker | `{id, op: "compose" \| "midi", params}` |
    | worker → page | `{id, ok: true, result}` or `{id, ok: false, kind, error}` |
    | worker → page | progress events `{progress: 0..1, stage}` |

- [ ] **Step 1: Write the failing test**

`web/tests/engine.test.js`:
```js
import assert from "node:assert/strict";
import test from "node:test";

import { Engine } from "../engine.js";

class FakeWorker {
  constructor() {
    this.sent = [];
    this.onmessage = null;
  }
  postMessage(msg) {
    this.sent.push(msg);
  }
  reply(msg) {
    this.onmessage({ data: msg });
  }
}

test("compose resolves with the worker's result", async () => {
  const w = new FakeWorker();
  const engine = new Engine(w);
  const promise = engine.compose({ style: "tonal" });
  assert.equal(w.sent[0].op, "compose");
  w.reply({ id: w.sent[0].id, ok: true, result: { notes: [] } });
  assert.deepEqual(await promise, { notes: [] });
});

test("newest request wins while busy", async () => {
  const w = new FakeWorker();
  const engine = new Engine(w);
  const first = engine.compose({ seed: 1 });
  const second = engine.compose({ seed: 2 });
  const third = engine.compose({ seed: 3 });
  assert.equal(w.sent.length, 1, "only one compose in flight");
  assert.equal(await second, null, "replaced request resolves null");
  w.reply({ id: w.sent[0].id, ok: true, result: "one" });
  assert.equal(await first, "one");
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(w.sent.length, 2);
  assert.deepEqual(w.sent[1].params, { seed: 3 });
  w.reply({ id: w.sent[1].id, ok: true, result: "three" });
  assert.equal(await third, "three");
});

test("errors reject with kind", async () => {
  const w = new FakeWorker();
  const engine = new Engine(w);
  const promise = engine.compose({});
  w.reply({ id: w.sent[0].id, ok: false, kind: "value", error: "tempo must be between 40 and 200" });
  await assert.rejects(promise, (err) => err.kind === "value" && /tempo/.test(err.message));
});

test("progress messages go to onProgress", () => {
  const w = new FakeWorker();
  const seen = [];
  new Engine(w, { onProgress: (p) => seen.push(p) });
  w.reply({ progress: 0.5, stage: "Loading numpy" });
  assert.deepEqual(seen, [{ progress: 0.5, stage: "Loading numpy" }]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test web/tests/*.test.js`
Expected: FAIL with `Cannot find module '.../web/engine.js'`

- [ ] **Step 3: Implement**

`web/engine.js`:
```js
// Talks to the Pyodide worker. One compose runs at a time; while it runs, only the
// newest waiting request is kept (older waiting requests resolve to null).

export class Engine {
  constructor(worker, { onProgress } = {}) {
    this.worker = worker;
    this.onProgress = onProgress;
    this.nextId = 1;
    this.calls = new Map();
    this.busy = false;
    this.pending = null;
    worker.onmessage = (event) => this._receive(event.data);
  }

  _receive(msg) {
    if (msg.progress !== undefined) {
      this.onProgress?.(msg);
      return;
    }
    const call = this.calls.get(msg.id);
    if (!call) return;
    this.calls.delete(msg.id);
    if (msg.ok) call.resolve(msg.result);
    else call.reject(Object.assign(new Error(msg.error), { kind: msg.kind }));
  }

  _send(op, params) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.calls.set(id, { resolve, reject });
      this.worker.postMessage({ id, op, params });
    });
  }

  compose(params) {
    if (this.busy) {
      this.pending?.resolve(null);
      return new Promise((resolve, reject) => {
        this.pending = { params, resolve, reject };
      });
    }
    this.busy = true;
    return this._send("compose", params).finally(() => {
      this.busy = false;
      const next = this.pending;
      this.pending = null;
      if (next) this.compose(next.params).then(next.resolve, next.reject);
    });
  }

  midi(params) {
    return this._send("midi", params);
  }
}
```

`web/worker.js`:
```js
/* Pyodide worker: runs sinfony.web in the browser (classic worker, uses importScripts). */

const PYODIDE_VERSION = "314.0.7";
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

const progress = (value, stage) => self.postMessage({ progress: value, stage });

const PY_BRIDGE = `
import base64, json
import sinfony.web as web

def _call(op, params_json):
    try:
        params = json.loads(params_json)
        if op == "compose":
            result = web.compose(params)
        elif op == "midi":
            result = base64.b64encode(web.midi(params)).decode("ascii")
        else:
            raise ValueError(f"unknown operation {op!r}")
        return json.dumps({"ok": True, "result": result})
    except ValueError as e:
        return json.dumps({"ok": False, "kind": "value", "error": str(e)})
    except Exception as e:
        return json.dumps({"ok": False, "kind": "internal", "error": f"{type(e).__name__}: {e}"})
`;

const ready = (async () => {
  progress(0.05, "Loading Python");
  importScripts(`${PYODIDE_URL}pyodide.js`);
  const py = await loadPyodide({ indexURL: PYODIDE_URL });
  progress(0.45, "Loading numpy");
  await py.loadPackage(["numpy", "micropip"]);
  progress(0.7, "Installing sinfony");
  const manifest = await (await fetch("wheels/manifest.json")).json();
  const micropip = py.pyimport("micropip");
  await micropip.install("mido");
  const wheelUrl = new URL(`wheels/${manifest.sinfony}`, self.location.href).href;
  await micropip.install.callKwargs(wheelUrl, { deps: false });
  progress(0.9, "Warming up");
  py.runPython(PY_BRIDGE);
  progress(1, "Ready");
  return py.globals.get("_call");
})();

self.onmessage = async (event) => {
  const { id, op, params } = event.data;
  try {
    const call = await ready;
    const reply = JSON.parse(call(op, JSON.stringify(params)));
    self.postMessage({ id, ...reply });
  } catch (err) {
    self.postMessage({ id, ok: false, kind: "load", error: String((err && err.message) || err) });
  }
};
```

Note for the implementer: `worker.js` runs only in browsers (it uses `importScripts` and fetches Pyodide). It is exercised in Task 10's browser verification, not by Node tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test web/tests/*.test.js`
Expected: `# fail 0`

- [ ] **Step 5: Commit**

```bash
git add web/engine.js web/worker.js web/tests/engine.test.js
git commit --no-gpg-sign -m "feat(web): add Pyodide worker and newest-request-wins client" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: The page — layout, result roll, and wiring (`index.html`, `style.css`, `roll.js`, `app.js`)

**Files:**
- Create: `web/index.html`, `web/style.css`, `web/roll.js`, `web/app.js`
- Verify: in a real browser, using the Playwright MCP tools (`mcp__plugin_playwright_playwright__*`)

**Interfaces:**
- Consumes:
  - Task 5: `decodeHash`, `encodeHash`, `quantize`
  - Task 6: `POINTS`, `PadView`, `mergePads`, `sameLayout`, `fitCanvas`
  - Task 7: `Synth`
  - Task 8: `Player`, `beatAtSeconds`
  - Task 9: `Engine`, `worker.js`
  - Task 4: `scripts/build_web.py`
  - Task 2: the piece JSON fields
- Produces:
  - The playable page.
  - A test hook, `window.__sinfony = { piece (getter), state, compose() }`, used by the verification step.
  - `roll.js`: `drawRoll(canvas, piece, positionS | null, colors)`.

- [ ] **Step 1: Write `web/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>sinfony · draw music</title>
  <meta name="description" content="Draw a melody and a tension curve; sinfony composes music from the mathematics.">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <h1 class="brand">sinfony</h1>
      <button id="play" class="primary" disabled>▶ Play</button>
      <label>Seed
        <span class="row"><input id="seed" type="number" min="0" step="1" value="0"><button id="dice" title="Random seed" aria-label="Random seed">🎲</button></span>
      </label>
      <label>Style
        <select id="style"><option value="tonal">Tonal</option><option value="ambient">Ambient</option></select>
      </label>
      <label>Key
        <span class="row"><select id="root" aria-label="Key root"></select><select id="mode" aria-label="Mode"></select></span>
      </label>
      <label>Tempo <output id="tempo-out"></output><input id="tempo" type="range" min="40" max="200" step="1"></label>
      <label>Wiggle <output id="wiggle-out"></output><input id="wiggle" type="range" min="0" max="1" step="0.01"></label>
      <label>Smoothness <output id="smooth-out"></output><input id="smooth" type="range" min="0" max="5" step="0.1"></label>
      <label>Density <output id="density-out"></output><input id="density" type="range" min="0" max="1" step="0.01"></label>
      <label class="check"><input id="loop" type="checkbox"> Loop</label>
      <div class="actions">
        <button id="share">🔗 Share</button>
        <button id="midi">⬇ MIDI</button>
        <button id="reset">↺ Reset drawing</button>
      </div>
    </aside>
    <main class="stage">
      <div class="notices">
        <div id="loading" class="banner">
          <span id="loading-stage">Warming up the orchestra…</span>
          <progress id="loading-bar" max="1" value="0"></progress>
          <small>First visit downloads about 10 MB, cached after that. You can draw already.</small>
        </div>
        <div id="error" class="banner error" hidden>
          <span><strong>Couldn't load the engine.</strong> <span id="error-text"></span></span>
          <button id="retry" class="primary">Retry</button>
        </div>
      </div>
      <section class="pad">
        <header>Melody contour <small>draw the shape of the tune · ⛓ sections repeat, so they are drawn together</small></header>
        <canvas id="contour"></canvas>
      </section>
      <section class="pad short">
        <header>Tension <small>low = calm · high = intense</small></header>
        <canvas id="tension"></canvas>
      </section>
      <section class="pad">
        <header>Result <small id="status"></small></header>
        <canvas id="roll"></canvas>
      </section>
    </main>
  </div>
  <div id="toast" role="status" aria-live="polite"></div>
  <script type="module" src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `web/style.css`**

```css
:root {
  color-scheme: light dark;
  --bg: #f6f3ec;
  --panel: #fffdf8;
  --ink: #1d2126;
  --muted: #6b6f76;
  --grid: #e2dccf;
  --band: #f1ece1;
  --band-alt: #faf7f0;
  --accent: #c8553d;
  --playhead: #2e6f9e;
  --v1: #2e6f9e;
  --v2: #c8553d;
  --v3: #588b3a;
  --v4: #8e5ba8;
  --v5: #d49a2a;
  --radius: 10px;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15171a;
    --panel: #1d2024;
    --ink: #ece9e2;
    --muted: #9a9ea6;
    --grid: #2c3036;
    --band: #1b1e22;
    --band-alt: #202328;
    --accent: #e07a5f;
    --playhead: #6fa8dc;
    --v1: #6fa8dc;
    --v2: #e07a5f;
    --v3: #8fbf6a;
    --v4: #b48ad1;
    --v5: #e6b450;
  }
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  min-height: 100%;
  background: var(--bg);
  color: var(--ink);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
}

.app { display: grid; grid-template-columns: 250px minmax(0, 1fr); min-height: 100vh; }

.sidebar {
  background: var(--panel);
  border-right: 1px solid var(--grid);
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.brand { font-size: 22px; margin: 0 0 4px; letter-spacing: 0.02em; }

label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--muted); }
label output { color: var(--ink); font-variant-numeric: tabular-nums; }
.check { flex-direction: row; align-items: center; gap: 8px; }

.row { display: flex; gap: 6px; }
.row > * { flex: 1; min-width: 0; }

input, select, button {
  font: inherit;
  color: var(--ink);
  background: var(--bg);
  border: 1px solid var(--grid);
  border-radius: 8px;
  padding: 8px 10px;
}
input[type="range"] { padding: 0; accent-color: var(--accent); }
input[type="checkbox"] { accent-color: var(--accent); }
button { cursor: pointer; }
button:hover:not(:disabled) { border-color: var(--muted); }
button:disabled { opacity: 0.5; cursor: default; }
button.primary { background: var(--accent); color: #fff; border-color: transparent; font-weight: 600; padding: 10px 12px; }

.actions { display: grid; gap: 8px; margin-top: auto; }

.stage {
  padding: 16px;
  display: grid;
  grid-template-rows: auto minmax(160px, 2fr) minmax(110px, 1fr) minmax(160px, 2fr);
  gap: 12px;
  min-width: 0;
  height: 100vh;
}

.notices:empty { display: none; }

.banner {
  background: var(--panel);
  border: 1px solid var(--grid);
  border-radius: var(--radius);
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.banner[hidden] { display: none; }
.banner progress { flex: 1; min-width: 120px; accent-color: var(--accent); }
.banner small { color: var(--muted); }
.banner.error { border-color: var(--accent); }

.pad {
  background: var(--panel);
  border: 1px solid var(--grid);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.pad header { padding: 10px 14px; font-weight: 600; font-size: 14px; display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.pad header small { color: var(--muted); font-weight: 400; }
.pad canvas { flex: 1; width: 100%; min-height: 0; display: block; touch-action: none; cursor: crosshair; }
#roll { cursor: default; }

#toast {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translate(-50%, 20px);
  background: var(--ink);
  color: var(--bg);
  padding: 10px 16px;
  border-radius: 999px;
  opacity: 0;
  transition: opacity 0.2s, transform 0.2s;
  pointer-events: none;
  max-width: calc(100vw - 32px);
}
#toast.show { opacity: 1; transform: translate(-50%, 0); }

.unsupported { padding: 32px 16px; text-align: center; }

@media (max-width: 800px) {
  .app { grid-template-columns: 1fr; }
  .sidebar {
    border-right: 0;
    border-bottom: 1px solid var(--grid);
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .brand, #play, .actions, .check { grid-column: 1 / -1; }
  .actions { grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 0; }
  .stage { height: auto; grid-template-rows: auto 240px 140px 240px; }
}
```

- [ ] **Step 3: Write `web/roll.js`**

```js
// Result piano roll: notes coloured by voice, chord labels, sections, playhead.

import { fitCanvas } from "./canvas.js";
import { beatAtSeconds } from "./player.js";

export function drawRoll(canvas, piece, positionS, colors) {
  const ctx = fitCanvas(canvas);
  const W = canvas.clientWidth;
  const H = canvas.clientHeight;
  const c = colors();
  ctx.clearRect(0, 0, W, H);
  if (!piece || !piece.notes.length) return;

  const T = piece.total_beats;
  let lo = Infinity;
  let hi = -Infinity;
  for (const n of piece.notes) {
    lo = Math.min(lo, n.pitch);
    hi = Math.max(hi, n.pitch);
  }
  lo -= 1;
  hi += 1;
  const top = 22;
  const rowH = (H - top) / (hi - lo + 1);
  const x = (beat) => (beat / T) * W;
  const y = (pitch) => top + (hi - pitch) * rowH;

  piece.sections.forEach((s, i) => {
    ctx.fillStyle = i % 2 ? c.band : c.bandAlt;
    ctx.fillRect(x(s.start), 0, x(s.end) - x(s.start), H);
  });

  ctx.font = "10px system-ui, sans-serif";
  ctx.fillStyle = c.muted;
  let lastLabel = -Infinity;
  for (const ch of piece.chords) {
    const cx = x(ch.onset) + 3;
    if (cx - lastLabel < 34) continue; // skip labels that would overlap
    ctx.fillText(ch.label, cx, 14);
    lastLabel = cx;
  }

  const voiceColor = Object.fromEntries(piece.voices.map((v, i) => [v.name, c.voices[i % c.voices.length]]));
  for (const n of piece.notes) {
    const sounding = positionS !== null && n.onset_s <= positionS && positionS < n.onset_s + n.dur_s;
    const nx = x(n.onset);
    const nw = Math.max(1.5, x(n.onset + n.dur) - nx);
    const nh = Math.max(1.5, rowH * 0.8);
    ctx.globalAlpha = sounding ? 1 : 0.35 + 0.55 * n.vel;
    ctx.fillStyle = voiceColor[n.voice];
    ctx.fillRect(nx, y(n.pitch), nw, nh);
    if (sounding) {
      ctx.strokeStyle = c.ink;
      ctx.lineWidth = 1;
      ctx.strokeRect(nx, y(n.pitch), nw, nh);
    }
  }
  ctx.globalAlpha = 1;

  if (positionS !== null) {
    const px = x(beatAtSeconds(piece.beat_s, positionS));
    ctx.strokeStyle = c.playhead;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(px, 0);
    ctx.lineTo(px, H);
    ctx.stroke();
  }
}
```

- [ ] **Step 4: Write `web/app.js`**

```js
// sinfony playground: wiring between controls, pads, the Python engine, and audio.

import { Engine } from "./engine.js";
import { POINTS, PadView, mergePads, sameLayout } from "./pads.js";
import { Player, beatAtSeconds } from "./player.js";
import { drawRoll } from "./roll.js";
import { decodeHash, encodeHash, quantize } from "./share.js";
import { Synth } from "./synth.js";

const $ = (id) => document.getElementById(id);
const STYLE_SECTIONS = { tonal: ["A", "A'", "B", "A"], ambient: ["A", "B", "A'", "C", "A"] };
const MODES = {
  tonal: ["major", "minor"],
  ambient: ["dorian", "lydian", "aeolian", "pentatonic", "mixolydian", "phrygian", "major", "minor"],
};
const NOTE_NAMES = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];
const SLIDERS = ["tempo", "wiggle", "smooth", "density"];
const FORMAT = {
  tempo: (v) => `${Math.round(v)} bpm`,
  wiggle: (v) => v.toFixed(2),
  smooth: (v) => v.toFixed(1),
  density: (v) => v.toFixed(2),
};
const flat = (v) => Array(POINTS).fill(v);
const withMaterial = (s) => ({ ...s, material: s.material ?? s.label.replace(/'+$/, "") });

if (!window.AudioContext || !window.Worker) {
  document.body.innerHTML =
    '<p class="unsupported">Your browser can\'t run the playground: it needs Web Audio and Web Workers.</p>';
  throw new Error("unsupported browser");
}

const state = {
  params: { style: "tonal", seed: 0, key: null, tempo: null, wiggle: null, smooth: null, density: null },
  contour: {}, // material key -> 64 quantized points (drawn slots only)
  drawnContour: new Set(),
  tension: null, // flat quantized list, 64 per section, once the user draws tension
  sections: STYLE_SECTIONS.tonal.map((label) => withMaterial({ label })),
  piece: null,
};

// ---------- helpers
let toastTimer = null;
function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3500);
}

function readColors() {
  const css = getComputedStyle(document.documentElement);
  const v = (name) => css.getPropertyValue(name).trim();
  return {
    ink: v("--ink"), muted: v("--muted"), grid: v("--grid"), band: v("--band"), bandAlt: v("--band-alt"),
    accent: v("--accent"), playhead: v("--playhead"),
    voices: [v("--v1"), v("--v2"), v("--v3"), v("--v4"), v("--v5")],
  };
}
let colors = readColors();
const getColors = () => colors;
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  colors = readColors();
  redraw();
});

// ---------- pads
const contourPad = new PadView($("contour"), {
  linked: true,
  colors: getColors,
  onCommit: ({ values, touched }) => {
    for (const slot of touched) {
      state.contour[slot] = values[slot].map(quantize);
      state.drawnContour.add(slot);
    }
    requestCompose();
  },
});
const tensionPad = new PadView($("tension"), {
  linked: false,
  colors: getColors,
  onCommit: ({ values }) => {
    state.tension = state.sections.flatMap((_, i) => (values[String(i)] ?? flat(0.5)).map(quantize));
    requestCompose();
  },
});

function pieceMatchesSections() {
  return state.piece !== null && sameLayout(state.piece.sections, state.sections);
}

function refreshPads() {
  const contourDefaults = pieceMatchesSections()
    ? state.piece.pads.contour
    : Object.fromEntries(state.sections.map((s) => [s.material, flat(0.5)]));
  contourPad.setModel(state.sections, mergePads(contourDefaults, state.contour, state.drawnContour), state.drawnContour);
  const source = state.tension ?? (pieceMatchesSections() ? state.piece.pads.tension : null);
  const tension = Object.fromEntries(
    state.sections.map((_, i) => [String(i), source ? source.slice(i * POINTS, (i + 1) * POINTS) : flat(0.5)]),
  );
  tensionPad.setModel(state.sections, tension, state.tension ? state.sections.map((_, i) => String(i)) : []);
}

function clearDrawings(reason) {
  const had = state.drawnContour.size > 0 || state.tension !== null;
  state.contour = {};
  state.drawnContour = new Set();
  state.tension = null;
  if (had && reason) toast(reason);
}

// ---------- controls
function fillSelect(select, items) {
  select.replaceChildren(...items.map(([value, text]) => new Option(text, value)));
}
fillSelect($("root"), NOTE_NAMES.map((n, i) => [String(i), n]));
function fillModes(style) {
  fillSelect($("mode"), MODES[style].map((m) => [m, m[0].toUpperCase() + m.slice(1)]));
}
fillModes("tonal");

function syncControls(params) {
  $("seed").value = params.seed;
  $("style").value = params.style;
  fillModes(params.style);
  const [pc, mode] = params.key.split("-");
  $("root").value = pc;
  $("mode").value = mode;
  for (const name of SLIDERS) {
    $(name).value = params[name];
    $(`${name}-out`).textContent = FORMAT[name](Number(params[name]));
  }
}

function setSeed(seed) {
  state.params.seed = seed;
  state.params.key = null;
  state.params.tempo = null;
  requestCompose();
}

$("style").addEventListener("change", (e) => {
  const style = e.target.value;
  state.params = { style, seed: state.params.seed, key: null, tempo: null, wiggle: null, smooth: null, density: null };
  const next = STYLE_SECTIONS[style].map((label) => withMaterial({ label }));
  if (!sameLayout(next, state.sections)) clearDrawings("Drawing cleared: this style has different sections");
  state.sections = next;
  fillModes(style);
  refreshPads();
  requestCompose();
});
$("seed").addEventListener("change", (e) => setSeed(Math.max(0, Math.floor(Number(e.target.value) || 0))));
$("dice").addEventListener("click", () => {
  const seed = Math.floor(Math.random() * 100000);
  $("seed").value = seed;
  setSeed(seed);
});
for (const id of ["root", "mode"]) {
  $(id).addEventListener("change", () => {
    state.params.key = `${$("root").value}-${$("mode").value}`;
    requestCompose();
  });
}
for (const name of SLIDERS) {
  $(name).addEventListener("input", (e) => {
    const v = Number(e.target.value);
    state.params[name] = v;
    $(`${name}-out`).textContent = FORMAT[name](v);
    requestCompose(300);
  });
}
$("loop").addEventListener("change", (e) => {
  if (player) player.loop = e.target.checked;
});
$("reset").addEventListener("click", () => {
  clearDrawings();
  refreshPads();
  requestCompose();
});
$("share").addEventListener("click", async () => {
  updateHash();
  try {
    await navigator.clipboard.writeText(location.href);
    toast("Link copied");
  } catch {
    toast("Copy the link from the address bar");
  }
});
$("midi").addEventListener("click", async () => {
  try {
    const b64 = await engine.midi(composeParams());
    const bytes = Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "audio/midi" }));
    const link = Object.assign(document.createElement("a"), {
      href: url,
      download: `sinfony-${state.params.style}-${state.params.seed}.mid`,
    });
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (err) {
    toast(err.message);
  }
});

// ---------- audio (created on the first user gesture, as browsers require)
let audio = null;
let player = null;
function ensureAudio() {
  if (!audio) {
    audio = new AudioContext();
    player = new Player(audio, new Synth(audio), { onEnd: setPlayingUI });
    player.loop = $("loop").checked;
    if (state.piece) player.load(state.piece);
  }
  if (audio.state === "suspended") audio.resume();
}
function setPlayingUI() {
  $("play").textContent = player?.playing ? "■ Stop" : "▶ Play";
  redraw();
}
$("play").addEventListener("click", () => {
  ensureAudio();
  if (player.playing) player.stop();
  else player.play();
  setPlayingUI();
});

// ---------- engine
let engine = null;
function startEngine() {
  $("loading").hidden = false;
  $("error").hidden = true;
  const worker = new Worker("worker.js");
  worker.onerror = (e) => showError(e.message || "the engine worker failed to start");
  engine = new Engine(worker, {
    onProgress: ({ progress, stage }) => {
      $("loading-bar").value = progress;
      $("loading-stage").textContent = progress >= 1 ? "Ready" : `${stage}…`;
      if (progress >= 1) $("loading").hidden = true;
    },
  });
}
function showError(message) {
  $("loading").hidden = true;
  $("error-text").textContent = message;
  $("error").hidden = false;
}
$("retry").addEventListener("click", () => {
  engine.worker.terminate();
  startEngine();
  requestCompose();
});

function composeParams() {
  const p = { style: state.params.style, seed: state.params.seed };
  for (const name of ["key", ...SLIDERS]) if (state.params[name] !== null) p[name] = state.params[name];
  if (state.drawnContour.size) {
    p.contour = Object.fromEntries([...state.drawnContour].map((k) => [k, state.contour[k]]));
  }
  if (state.tension) p.tension = state.tension;
  return p;
}

let debounce = null;
function requestCompose(delay = 0) {
  clearTimeout(debounce);
  debounce = setTimeout(runCompose, delay);
}

async function runCompose() {
  $("status").textContent = "composing…";
  try {
    const piece = await engine.compose(composeParams());
    if (piece) applyPiece(piece);
  } catch (err) {
    if (err.kind === "load") return showError(err.message);
    if (err.kind === "value" && /tension/.test(err.message) && state.tension) {
      state.tension = null;
      toast(`Tension drawing ignored: ${err.message}`);
      refreshPads();
      return runCompose();
    }
    if (err.kind === "value" && /contour/.test(err.message) && state.drawnContour.size) {
      clearDrawings(`Contour drawing ignored: ${err.message}`);
      refreshPads();
      return runCompose();
    }
    if (err.kind === "value" && /key|mode/.test(err.message) && state.params.key) {
      state.params.key = null;
      toast(`Key ignored: ${err.message}`);
      return runCompose();
    }
    toast(err.kind === "value" ? err.message : "Something went wrong composing");
    console.error(err);
    $("status").textContent = "";
  }
}

function applyPiece(piece) {
  if (!sameLayout(piece.sections, state.sections)) clearDrawings("Drawing cleared: the piece has different sections");
  state.sections = piece.sections.map(withMaterial);
  state.piece = piece;
  refreshPads();
  syncControls(piece.params);
  updateHash();
  if (player) player.load(piece);
  $("play").disabled = false;
  const [pc, mode] = piece.params.key.split("-");
  $("status").textContent =
    `${NOTE_NAMES[Number(pc)]} ${mode} · ${Math.round(piece.params.tempo)} bpm · ${Math.round(piece.duration_s)} s`;
  redraw();
}

// ---------- share links
function updateHash() {
  const p = composeParams();
  const hash = encodeHash({
    style: p.style, seed: p.seed, key: p.key ?? null, tempo: p.tempo ?? null, wiggle: p.wiggle ?? null,
    smooth: p.smooth ?? null, density: p.density ?? null, contour: p.contour ?? {}, tension: p.tension ?? null,
  });
  history.replaceState(null, "", hash);
}

function loadFromHash() {
  const { state: s, ignored } = decodeHash(location.hash);
  state.params = { style: s.style, seed: s.seed, key: s.key, tempo: s.tempo, wiggle: s.wiggle, smooth: s.smooth, density: s.density };
  state.contour = s.contour;
  state.drawnContour = new Set(Object.keys(s.contour));
  state.tension = s.tension;
  state.sections = STYLE_SECTIONS[s.style].map((label) => withMaterial({ label }));
  $("style").value = s.style;
  $("seed").value = s.seed;
  fillModes(s.style);
  if (ignored.length) toast(`Ignored invalid link fields: ${ignored.join(", ")}`);
}
window.addEventListener("hashchange", () => {
  loadFromHash();
  refreshPads();
  requestCompose();
});

// ---------- drawing loop
function redraw() {
  const pos = player && player.playing ? player.position : null;
  drawRoll($("roll"), state.piece, pos, getColors);
  const u = pos !== null && state.piece
    ? Math.min(1, Math.max(0, beatAtSeconds(state.piece.beat_s, pos) / state.piece.total_beats))
    : null;
  contourPad.draw(u);
  tensionPad.draw(u);
}
function frame() {
  if (player && player.playing) redraw();
  requestAnimationFrame(frame);
}
new ResizeObserver(() => redraw()).observe($("roll"));

window.__sinfony = {
  get piece() {
    return state.piece;
  },
  state,
  compose: runCompose,
};

loadFromHash();
refreshPads();
startEngine();
requestCompose();
requestAnimationFrame(frame);
```

- [ ] **Step 5: Build and serve the page locally**

Run the build:
```bash
uv run python scripts/build_web.py
```
Expected: `built .../web/wheels/sinfony-0.1.0-py3-none-any.whl`

Then serve the page (run this in the background):
```bash
uv run python -m http.server -d web 8765
```

- [ ] **Step 6: Verify in a real browser (Playwright MCP tools)**

Load the tools with `ToolSearch` (`select:mcp__plugin_playwright_playwright__browser_navigate,mcp__plugin_playwright_playwright__browser_evaluate,mcp__plugin_playwright_playwright__browser_take_screenshot,mcp__plugin_playwright_playwright__browser_console_messages,mcp__plugin_playwright_playwright__browser_click,mcp__plugin_playwright_playwright__browser_resize`). Then run each check below and compare it with its expected result.

1. **Load:** navigate to `http://localhost:8765/`. Evaluate:
   ```js
   async () => {
     for (let i = 0; i < 600 && !window.__sinfony.piece; i++) await new Promise((r) => setTimeout(r, 100));
     const p = window.__sinfony.piece;
     return p && { style: p.style, notes: p.notes.length, sections: p.sections.map((s) => s.label) };
   }
   ```
   Expected: `{style: "tonal", notes: > 100, sections: ["A","A'","B","A"]}` within 60 s.

2. **Draw:** evaluate:
   ```js
   async () => {
     const c = document.getElementById("contour");
     const r = c.getBoundingClientRect();
     const before = JSON.stringify(window.__sinfony.piece.notes);
     const t0 = performance.now();
     const fire = (type, u, y) =>
       c.dispatchEvent(new PointerEvent(type, { bubbles: true, pointerId: 1, clientX: r.left + u * r.width, clientY: r.top + (1 - y) * r.height }));
     fire("pointerdown", 0.01, 0.95);
     for (let u = 0.02; u < 0.24; u += 0.01) fire("pointermove", u, 0.95);
     fire("pointerup", 0.24, 0.95);
     for (let i = 0; i < 100 && JSON.stringify(window.__sinfony.piece.notes) === before; i++) await new Promise((r) => setTimeout(r, 100));
     return {
       changed: JSON.stringify(window.__sinfony.piece.notes) !== before,
       ms: Math.round(performance.now() - t0),
       drawn: [...window.__sinfony.state.drawnContour],
       hash: location.hash.includes("c=A."),
     };
   }
   ```
   Expected: `{changed: true, ms: < 3000, drawn: ["A"], hash: true}`. The spec targets about 1 s on a laptop; record the measured `ms` in the ledger.

3. **Play:** click `#play`, then evaluate:
   ```js
   async () => {
     const t0 = performance.now();
     await new Promise((r) => setTimeout(r, 1500));
     return { label: document.getElementById("play").textContent, waited: Math.round(performance.now() - t0) };
   }
   ```
   Expected: the label is `■ Stop`. Then take a screenshot: the playhead line is visible on the roll and on both pads. Click `#play` again to stop.

4. **Share link reproduces the piece:** evaluate:
   ```js
   () => {
     sessionStorage.setItem("notes", JSON.stringify(window.__sinfony.piece.notes));
     location.reload(); // the URL hash already holds the drawing (updateHash)
     return location.href;
   }
   ```
   After the reload, run the load check from step 1 again, then evaluate:
   ```js
   () => ({
     same: JSON.stringify(window.__sinfony.piece.notes) === sessionStorage.getItem("notes"),
     drawn: [...window.__sinfony.state.drawnContour],
   })
   ```
   Expected: `{same: true, drawn: ["A"]}`. Record the reload's load time from step 1 in the ledger; the spec target is about 3 s when cached.

5. **Style switch drops the drawing:** evaluate:
   ```js
   async () => {
     const sel = document.getElementById("style");
     sel.value = "ambient";
     sel.dispatchEvent(new Event("change"));
     for (let i = 0; i < 300 && window.__sinfony.piece.style !== "ambient"; i++) await new Promise((r) => setTimeout(r, 100));
     return { style: window.__sinfony.piece.style, drawn: [...window.__sinfony.state.drawnContour], toast: document.getElementById("toast").textContent };
   }
   ```
   Expected: `{style: "ambient", drawn: [], toast: "Drawing cleared: this style has different sections"}`.

6. **Touch and phone layout:** resize to 390×844 and take a screenshot. Expected: the controls are stacked above full-width pads with no horizontal scroll. Then evaluate `getComputedStyle(document.getElementById("contour")).touchAction`; expected `"none"`.

7. **Console:** read the console messages. Expected: no errors. Warnings about AudioContext autoplay before the first click are acceptable.

If any check fails, debug with superpowers:systematic-debugging, fix the cause, and repeat the failing check and every check after it.

- [ ] **Step 7: Run all tests and commit**

```bash
uv run pytest -q
node --test web/tests/*.test.js
uv run ruff check --fix .
git add web/index.html web/style.css web/roll.js web/app.js
git commit --no-gpg-sign -m "feat(web): add the drawing playground page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Deploy workflow and README

**Files:**
- Create: `.github/workflows/pages.yml`
- Modify: `README.md` (append a "Playground" section)
- Test: `tests/test_workflow.py`

**Interfaces:**
- Consumes: `scripts/build_web.py` (Task 4), `web/` (Tasks 5–10), and the test commands.
- Produces: a GitHub Pages deployment on every push to `main`, and user-facing docs.

- [ ] **Step 1: Write the failing test**

`tests/test_workflow.py`:
```python
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pages_workflow_runs_tests_builds_and_deploys():
    text = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    for needle in (
        "branches: [main]",
        "uv run pytest",
        "node --test web/tests/*.test.js",
        "uv run python scripts/build_web.py",
        "actions/upload-pages-artifact",
        "path: web",
        "actions/deploy-pages",
        "pages: write",
        "id-token: write",
    ):
        assert needle in text, needle


def test_readme_documents_the_playground():
    text = (ROOT / "README.md").read_text()
    for needle in ("## Playground", "scripts/build_web.py", "http.server", "GitHub Actions"):
        assert needle in text, needle
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workflow.py -q`
Expected: FAIL with `FileNotFoundError` for `.github/workflows/pages.yml`

- [ ] **Step 3: Implement**

`.github/workflows/pages.yml`:
```yaml
name: Deploy playground

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - run: uv sync
      - run: uv run pytest -q
      - run: node --test web/tests/*.test.js
      - run: uv run python scripts/build_web.py
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

Append to `README.md`:
````markdown

## Playground

Draw music in the browser. Sketch the **melody contour** and the **tension**
curve, and sinfony re-composes the piece when you lift the pen. Repeated
sections (the A's) are linked, so drawing one draws them all. **Share**
copies a link that reproduces the exact piece; **MIDI** downloads it.

The page runs the same Python engine inside the browser with
[Pyodide](https://pyodide.org) (pinned to 314.0.7 in `web/worker.js`), so
there is no server. The first visit downloads about 10 MB, which is
cached after that.

Run it locally:

```bash
uv run python scripts/build_web.py          # builds web/wheels/
uv run python -m http.server -d web 8000    # then open http://localhost:8000
```

Tests: `uv run pytest` (engine) and `node --test web/tests/*.test.js`
(page logic, no dependencies).

Deploy: the workflow in `.github/workflows/pages.yml` tests, builds, and
publishes `web/` to GitHub Pages on every push to `main`. One-time setup:
in the repository settings, set **Pages → Source** to **GitHub Actions**.
````

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workflow.py -q`
Expected: 2 passed

- [ ] **Step 5: Run everything and commit**

```bash
uv run pytest -q
node --test web/tests/*.test.js
uv run ruff check --fix .
git add .github/workflows/pages.yml README.md tests/test_workflow.py
git commit --no-gpg-sign -m "ci: deploy the playground to GitHub Pages" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
