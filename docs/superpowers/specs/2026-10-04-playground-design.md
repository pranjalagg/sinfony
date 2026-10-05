# sinfony Playground — Design Spec

**Date:** 2026-10-04
**Status:** Approved in brainstorming; pending written-spec review
**Builds on:** `docs/superpowers/specs/2026-10-03-sinfony-design.md` (the engine)

## 1. Purpose

A public web page where anyone can **draw music**. You sketch a melody
contour and a tension curve, and sinfony re-composes the piece to follow
your drawing. You hear the result immediately and can share it as a link.

The goal is **fun first**. Learning features such as "why this note?" are
out of scope for this version.

### Success criteria

- Opening the link with nothing installed gives a playable piece within
  about 15 s on a first visit, and within about 3 s once cached.
- Lifting the pen re-composes the piece, and the new music is heard within
  about 1 s on a laptop.
- Re-composing during playback continues from the same beat instead of
  restarting.
- A share link reproduces exactly the same piece: same notes, same timing.
- Python remains the single source of truth for all composition.

## 2. Decisions taken in brainstorming

| Topic | Decision |
|---|---|
| Core interaction | Draw the music: a contour pad and a tension pad |
| Audience | Public static website (GitHub Pages), shareable links |
| Architecture | Pyodide runs the unchanged Python engine in a Web Worker, plain-JS UI, Web Audio synth |
| Layout | Studio: a sidebar of controls; on the right, the contour pad, the tension pad, and the result piano roll |
| Contour pad | Laid out by section; repeated sections (same material) are linked |
| Tension pad | One continuous curve across the whole piece (not linked) |

## 3. Scope

**In:**
- the contour and tension pads
- sidebar controls
- in-browser composition
- the Web Audio synth and look-ahead player with hot swap
- the result piano roll with a playhead
- share links
- MIDI download
- the loading and error experience
- a responsive layout down to phone width
- a GitHub Pages deploy workflow
- Python and JS tests

**Out:**
- a live formula editor
- endless/streaming mode
- "why this note?" explanations
- WAV export
- accounts and a gallery
- MIDI input

## 4. Architecture

```
┌──────────── browser main thread ────────────┐      ┌──── Web Worker ────┐
│ app.js  sidebar + wiring                     │      │ worker.js          │
│ pads.js contour/tension drawing ──pen up────►│─────►│ Pyodide            │
│ roll.js result roll + playhead               │ msg  │  sinfony.web       │
│ player.js scheduler ◄── piece JSON ──────────│◄─────│   compose(params)  │
│ synth.js Web Audio voices                    │      │   midi(params)     │
│ share.js URL hash <-> params                 │      └────────────────────┘
└──────────────────────────────────────────────┘
```

Python decides everything musical, including timing in seconds. JavaScript
draws, schedules, and synthesizes.

## 5. Engine changes (Python)

### 5.1 New preset overrides

`tonal()` and `ambient()` gain these keyword overrides. When an override is
omitted, the current behavior stays exactly the same.

| Override | Type | Meaning | tonal default | ambient default |
|---|---|---|---|---|
| `contour` | `Curve` | Melody target, values in [0, 1] across the melody register, over beats | phrase arch + pink | sine + pink |
| `tension` | `Curve` | Passed to `Plan(tension=...)`, values in [0, 1] | `default_tension` | `default_tension` |
| `wiggle` | float in [0, 1] | Amplitude of pink noise added on top of the contour (default contour or `contour`), then clipped to [0, 1] | 0.15 | 0.25 |
| `smoothness` | float in [0, 5] | Weight of `step_bias` for the melody | 2.5 | 1.0 |
| `density` | float in [0, 1] | Melody `density(...)` value | 0.85 | 0.35 |

When `contour` is given, the preset's own shape is replaced, and `wiggle`
noise is still added on top. `voices=` continues to take precedence over
all of these.

### 5.2 `Piece.to_json() -> dict`

The result is a JSON-serializable dict. Every `*_s` field is in seconds, taken
from the performed events and integrated with `beats_to_seconds(piece.tempo, …)`.

```json
{
  "version": 1,
  "style": "tonal",
  "seed": 42,
  "key": {"root": 60, "mode": "major", "pc": 0},
  "meter": [4, 4],
  "beats_per_bar": 4.0,
  "total_beats": 128.0,
  "duration_s": 89.3,
  "beat_s": [0.0, 0.68, 1.36, "…one entry per integer beat 0..total_beats"],
  "sections": [{"label": "A", "base": "A", "material": "A",
                "start": 0.0, "end": 32.0, "start_s": 0.0, "end_s": 22.1}],
  "chords": [{"onset": 0.0, "dur": 4.0, "label": "I", "pcs": [0, 4, 7],
              "function": "T", "onset_s": 0.0, "dur_s": 2.7}],
  "notes": [{"voice": "melody", "pitch": 64, "vel": 0.71,
             "onset": 0.0, "dur": 0.5, "onset_s": 0.0, "dur_s": 0.34}],
  "voices": [{"name": "melody", "role": "melody", "register": [60, 84],
              "instrument": "epiano"}],
  "instruments": {"epiano": {"partials": [[1, 1.0, 1.2]], "attack": 0.003,
                  "release": 0.15, "inharmonicity": 0.0004, "hammer": 0.04,
                  "detune_cents": 0.0, "gain": 1.0}},
  "reverb": {"seconds": 1.2, "mix": 0.18},
  "pads": {
    "contour": {"A": ["64 floats in [0, 1]"], "B": ["…"]},
    "tension": ["64 floats per section, in section order"]
  },
  "params": {"style": "tonal", "seed": 42, "key": "0-major", "tempo": 88.0,
             "wiggle": 0.15, "smooth": 2.5, "density": 0.85}
}
```

- `pads` holds the curves the piece actually used, sampled exactly in the
  format the page sends back:
  - `pads.contour` is keyed by **material key** (`Form.material_key`). Each
    entry has 64 points spread evenly across that section's span; the
    contour is sampled before `wiggle` noise is added.
  - `pads.tension` is a flat list of 64 points per section, in section
    order.
- `params` echoes the resolved parameters, including the seeded choices, so
  the sidebar can show them.
- Instruments are exported once by name. A voice whose instrument does not
  match a named preset is exported under the name `"custom:<voice>"`.

### 5.3 `src/sinfony/web.py`

This is the only module the browser calls.

- **`compose(params: dict) -> dict`** validates the parameters, builds the
  curves, calls the preset, and returns `to_json()`.
- **`midi(params: dict) -> bytes`** returns the bytes of the same piece's
  MIDI file.
- **`normalize(params: dict) -> dict`** fills defaults and validates. It
  raises `ValueError` with a user-readable message.

Parameter schema (all keys optional except `style`):

| Key | Type / range | Notes |
|---|---|---|
| `style` | `"tonal"` or `"ambient"` | |
| `seed` | int, 0 ≤ seed < 2³¹ | default 0 |
| `key` | `"<pc>-<mode>"`, pc 0–11 | tonal: modes `major` or `minor`; ambient: any `MODES` name. Omitted means the seeded choice |
| `tempo` | 40–200 | omitted means the seeded choice |
| `wiggle` | 0–1 | |
| `smooth` | 0–5 | maps to the `smoothness` override |
| `density` | 0–1 | |
| `contour` | `{material_key: [64 floats in 0..1]}` | unknown keys raise an error; missing keys keep the default for that material |
| `tension` | flat list of 64 × (number of sections) floats in 0..1 | wrong length raises an error |

**Drawn points to curves.** For each section, its 64 points are placed at
evenly spaced beats across `[start, end]` and joined with `piecewise`. For
the contour, every section sharing a material key uses that key's points.
Sections without drawn points use the preset's default contour, sampled the
same way, so the mix is seamless.

**Key root placement:**
- tonal: the MIDI root is `60 + ((pc + 6) % 12) - 6`, so the tonic lies
  between F#3 and F4.
- ambient: the MIDI root is `57 + ((pc - 9) % 12)`, so the tonic lies
  between A3 and G#4.

## 6. Share links

```
https://<user>.github.io/sinfony/#v=1&style=tonal&seed=42&key=0-major&tempo=88
    &wiggle=0.15&smooth=2.5&density=0.85&c=A.<64ch>~B.<64ch>&t=<64ch × sections>
```

- **Point encoding:**
  - Each value v in [0, 1] becomes `round(v·63)`, written as one character
    of the base64url alphabet
    (`A–Z a–z 0–9 - _`).
  - Decoding maps each character back to `index / 63`.
- **`c`:** material key, `.`, then 64 characters, with entries joined by
  `~`. Only keys the user actually drew are included.
- **`t`:** present only if the user drew tension; it covers all sections in
  order.
- **Parameters:** `v` is the link-format version. Unknown parameters are
  ignored, and invalid ones fall back to defaults with a toast.
- **Hash, not query string:** the link data never reaches a server, and
  static hosting works.
- **Determinism:** the engine is deterministic, so a link reproduces the
  piece exactly. Quantizing to 64 levels is part of the format: the page
  applies the same quantization to the curves it sends at compose time, so
  the live piece and the shared piece are identical.

## 7. Page

### 7.1 Layout (Studio)

```
┌ sidebar ┐┌──────────────────────────────────────────────┐
│ ▶ / ■    ││ contour pad  [A │ A' │ B │ A]  (A↔A linked)   │
│ 🎲 seed  ││                                               │
│ style    │├──────────────────────────────────────────────┤
│ key      ││ tension pad  (one continuous curve)           │
│ tempo    │├──────────────────────────────────────────────┤
│ wiggle   ││ result piano roll + playhead (read-only)      │
│ smooth   ││                                               │
│ density  │└──────────────────────────────────────────────┘
│ 🔗 share │
│ ⬇ MIDI   │
│ ↺ reset  │
│ ⟳ loop   │
└──────────┘
```

Below 800 px of width, the sidebar becomes a top bar of controls and the
pads take the full width.

### 7.2 Pads (`pads.js`)

- **Canvas and axes:** each pad is a `<canvas>` using pointer events, so
  mouse, touch, and pen all work. x is beats across the whole piece and y
  is 0–1, with 1 at the top.
- **Starting state:** each pad opens showing `pads.*` from the last
  composition, which is the preset default on first load.
- **Drawing:**
  - While drawing, the stroke replaces the curve under it, linearly
    interpolated between pointer samples.
  - On pen-up, the edited span gets a light 3-point moving-average
    smoothing, and the sections it touched are re-sampled to 64 points.
- **Linking (contour only):** a stroke inside a section is mirrored live
  into every other section with the same material key. Linked sections show
  a small chain icon and a matching tint.
- **Section bands:** each section is drawn as a band labelled with its
  `label` (A, A', B, A).
- **When to compose:** pen-up triggers composition. Changing a sidebar
  control also triggers it, debounced by 300 ms for sliders.
- **What gets sent:** the page sends `contour` points only for material keys
  the user has drawn, and `tension` only once the user has drawn on the
  tension pad. Everything else uses the preset's exact default curves, so an
  undrawn piece and its share link match the plain preset exactly.

### 7.3 Result roll (`roll.js`)

- Notes are drawn as bars colored by voice.
- A vertical line marks the playhead.
- Sounding notes are highlighted.
- Chord labels sit along the top.
- The roll is read-only.

### 7.4 Sidebar (`app.js`)

**Controls:**
- play/stop
- seed: the number plus a 🎲 button for a random seed
- style toggle
- key: a root dropdown and a mode dropdown (the modes offered depend on the
  style)
- sliders for tempo, wiggle, smooth, and density
- share: copies the link and shows a "Link copied" toast
- MIDI download
- reset drawing: clears drawn curves back to the preset default
- loop toggle

**Rules:**
- Changing style or seed keeps the drawn curves only if the form's material
  keys and section count still match. Otherwise the drawing resets to
  defaults, with a toast explaining why.
- The slider ranges match the §5.3 schema.

## 8. Audio

### 8.1 Synth (`synth.js`)

A Web Audio port of `sinfony.render.synth.Instrument`:

- **Partials:** each note creates one `OscillatorNode` (sine) per partial.
  The frequency is `f0·ratio·√(1 + B·ratio²)`. With `detune_cents`, each
  partial gets two oscillators at ±detune, each at half amplitude.
- **Envelope:**
  - Each partial's `GainNode` ramps linearly from 0 to `amp` over `attack`,
    then decays exponentially with time constant `1/decay`. A decay of 0
    means the partial holds.
  - At note end, a linear release to 0 over `release`.
  - Overall level is `gain · vel^1.5`, the same curve as Python.
- **Hammer:** when `hammer > 0`, a short noise buffer (white noise, decaying
  with τ = 4 ms) goes through a low-pass filter at 3 kHz.
- **Reverb:** a `ConvolverNode` with an impulse response built from
  exponentially decaying noise, reaching −60 dB after `reverb.seconds`. The
  wet/dry split is `mix`.
- **Master:** gain, then `DynamicsCompressorNode` (limiter settings), then
  the destination.
- **Voice cap:** at most 48 notes sound at once. When a new note would
  exceed the cap, the oldest sounding note is released early.
- `f0 = 440·2^((pitch − 69)/12)`. This is a pure function, tested.

### 8.2 Player (`player.js`)

- **Look-ahead scheduling:** a 25 ms `setInterval` schedules every note
  whose `onset_s` falls in `[now, now + 100 ms)` on the AudioContext clock.
- **Position:** the current position is kept in seconds and converted
  to and from beats through the piece's `beat_s` table, using linear
  interpolation.
- **Hot swap:** when a new piece arrives during playback:
  1. Convert the current position to a beat using the old `beat_s`.
  2. Convert that beat back to seconds using the new `beat_s`.
  3. Stop all scheduled notes that have not started yet, and let sounding
     notes finish their release.
  4. Continue scheduling from the new position.
- **Loop:** at `duration_s`, jump to 0 if loop is on; otherwise stop.
- **Audio unlock:** the AudioContext is created or resumed on the first user
  gesture.

## 9. Worker and loading (`worker.js`)

- **Version pinning:** the worker loads a pinned Pyodide version from the
  official CDN. The version is the newest stable release at implementation
  time, recorded in `worker.js` and the README.
- **Startup sequence:**
  1. `loadPackage("numpy")`
  2. `micropip.install("mido")`
  3. `micropip.install(<site>/wheels/<sinfony wheel>, deps=False)`; the
     wheel name comes from `wheels/manifest.json`, and matplotlib is never
     installed.
  4. Import `sinfony.web`.
- **Messages:**

  | Direction | Message |
  |---|---|
  | page → worker | `{id, op: "compose" \| "midi", params}` |
  | worker → page | `{id, ok: true, result}` or `{id, ok: false, error}` |
  | worker → page | progress events `{progress: 0..1, stage}` during loading |

  For `midi`, `result` is the file bytes.
- **Newest request wins:** the page sends at most one compose at a time. If
  the user draws again while one is running, the newest request is queued
  and older queued ones are dropped.
- **Loading screen:** shows a "Warming up the orchestra…" progress bar. The
  pads already accept drawing while the engine loads; the first composition
  runs as soon as it is ready.

## 10. Error handling

| Situation | Behavior |
|---|---|
| Pyodide or wheel fails to load | Panel: "Couldn't load the engine" + reason + Retry |
| `compose` raises `ValueError` | Toast with the message; the previous piece keeps playing |
| Any other worker exception | Toast "Something went wrong composing" + details logged to console; previous piece kept |
| No Web Audio or Worker support | Static message: "Your browser can't run the playground" |
| Invalid share link parameters | Defaults used for the invalid fields; toast lists what was ignored |

## 11. Build and deploy

- **`scripts/build_web.py`:**
  - runs `uv build --wheel`
  - copies the wheel to `web/wheels/`
  - writes `web/wheels/manifest.json` (`{"sinfony": "<wheel filename>"}`)
  - The built wheels are git-ignored.
- **Local preview:**
  `uv run python scripts/build_web.py && uv run python -m http.server -d web 8000`
- **`.github/workflows/pages.yml`** runs on every push to `main`:
  1. Set up uv and Node.
  2. `uv run pytest`
  3. `node --test web/tests/`
  4. `build_web.py`
  5. Upload `web/` and deploy to GitHub Pages.

  The README notes the one-time step: enable Pages with source "GitHub
  Actions".

## 12. Files

```
src/sinfony/web.py                 compose / midi / normalize
src/sinfony/piece.py               + to_json()
src/sinfony/presets.py             + contour, tension, wiggle, smoothness, density
web/index.html, web/style.css
web/app.js  web/pads.js  web/roll.js  web/synth.js  web/player.js
web/share.js  web/worker.js
web/tests/*.test.js                node --test, no dependencies
scripts/build_web.py
.github/workflows/pages.yml
tests/test_web.py, tests/test_presets.py (+ overrides), tests/test_piece.py (+ to_json)
```

The page uses plain ES modules: no framework, no npm, no bundler. The pure
logic in `share.js`, `player.js` (scheduling math), `pads.js` (resampling
and linking), and `synth.js` (frequency math) is written as exported
functions that do not touch the DOM, so Node can test them.

## 13. Testing

**Python (pytest):**
- **Overrides change the music:**
  - Raising `contour` raises the melody's average pitch.
  - Drawn tension changes the chords of the first occurrence of each
    material.
  - `smoothness` raises the step ratio.
  - `density` changes the note count.
- **Defaults are unchanged:** without the new overrides, `tonal(seed)` and
  `ambient(seed)` produce scores identical to before.
- **`to_json`:**
  - The result serializes with `json.dumps`.
  - Each note's `onset_s` equals `beats_to_seconds(tempo, onset)` within
    1 ms.
  - `beat_s` is strictly increasing.
  - `pads` has the shapes described in §5.2.
  - Composing twice with the same drawn points gives identical results.
    (Feeding back the default `pads` gives a close but not identical piece,
    because they sample a smooth curve. That is why the page sends only the
    sections the user drew; see §7.2.)
- **`web.normalize` and `compose`:**
  - Every schema violation raises a `ValueError` with a readable message.
  - `compose` is deterministic.
  - Linked contour: one material key's points drive every section that
    shares it.
- **`midi`:** returns bytes that `mido` parses, with the same note count.

**JavaScript (`node --test web/tests/`):**
- **share:**
  - Encoding then decoding round-trips within quantization.
  - Malformed hashes produce defaults plus a list of ignored fields.
- **pads:**
  - Resampling a stroke to 64 points.
  - Linked sections receive identical points.
  - Smoothing keeps the endpoints.
- **player:**
  - Notes are selected for the `[t, t + window)` window.
  - The beat↔seconds interpolation is correct.
  - Hot swap maps beat b to the new piece's seconds for b.
- **synth:**
  - `f0`, plus the inharmonic partial frequency.
  - The envelope parameters computed from an instrument definition.

**End-to-end (manual, using the Playwright browser tool during
development):**
- load the built page
- wait for "ready"
- draw a stroke on the contour pad
- the roll changes
- play, and confirm the playhead advances
- copy the share link, open it in a new tab, and confirm the same notes
  (compare `to_json` note lists exposed on `window.__sinfony` for testing)
- confirm the console has no errors

## 14. Deliverables

1. The engine changes, with tests.
2. The `web/` page, implementing everything in §7–§10.
3. The build script and the Pages workflow.
4. A README section: how to play, how to run it locally, and how to deploy.
5. A manual end-to-end check (§13) passed in a real browser.
