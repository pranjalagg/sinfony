# Playground UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the playground explain itself: a Material-style look, a plain line and "the math" for every control, six teaching examples, a chord strip colored by harmonic function, and Tonal melodies that follow the whole drawing.

**Architecture:**
- **Python:** one engine change in `src/sinfony/motif.py`: each motif copy is placed diatonically where the drawing asks. A generator script writes `web/examples.json`, and a test checks every "Listen for" claim against the engine.
- **Browser:** plain ES modules, no build step, as today. `index.html` and `style.css` carry the new look and all explanation copy. `roll.js` gains the chord strip and legend, a new `examples.js` loads examples and turns each one into a share-link hash, and `app.js` wires them up.

**Tech Stack:** Python ≥ 3.11, numpy, mido (existing); vanilla JS (ES modules), Canvas 2D, Web Audio; Node's `node:test`; Pyodide 314.0.7 (unchanged).

**Spec:** `docs/superpowers/specs/2026-10-21-playground-ui-design.md`. Read it first: the copy tables in its Sections 6–8 are the source of truth for every user-facing string.

## Global Constraints

- **Repo and branch:** work in `/Users/pranjal.aggarwal/Desktop/pers/shan-shui-inf/sinfony` on a new branch **`feat/playground-ui`** created from `main`. Run every command from that directory.
- **Do not stage `notebooks/01_tour.ipynb`.** It has local run output that isn't part of this work.
- **Commits:** `git commit --no-gpg-sign`. Every message ends with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **No external project names** in code, comments, UI copy, or commit messages.
- **No new dependencies.** No npm packages, no bundler, no Material component library. The only new runtime asset is Google Fonts: Roboto 400/500 and Roboto Mono 400, with `display=swap` and a system-font fallback.
- **Share links stay `v=1`.** `share.js` keeps its format, and its existing tests stay green.
- **Ambient output must not change.** `AMBIENT_FP` in `tests/test_presets_overrides.py` stays as is. Only `TONAL_FP` is updated, in Task 1.
- **Spec values (exact):**

  | Constant | Value |
  |---|---|
  | Light tokens | primary `#9c4330`, on-primary `#ffffff`, primary-container `#ffdbd1`, on-primary-container `#3b0a02`, surface `#fff8f6`, surface-container `#fceae5`, on-surface `#231917`, on-surface-variant `#53433f`, outline-variant `#ead6d1` |
  | Radii | cards 12px, Play button 16px; shadow on Play only; no card borders |
  | Copy-placement join weight | 0.25 (Task 1) |
  | Diatonic shift search range | −14 … +14 scale steps (Task 1) |
  | Example order | Rise and fall, Calm to storm, Small steps, Big leaps, Dark and bright, Let chance draw |
  | Phone layout | panel stacks above stage at ≤ 800px; 16px gutter; no horizontal scroll |

- **Commands:**
  - Python tests: `uv run pytest -q`
  - JS tests: `node --test web/tests/*.test.js`
  - Lint: `uv run ruff check --fix .`, which must end clean before each commit.
  - Wheel for the browser: `uv run python scripts/build_web.py`. Its output (`web/wheels/`) is gitignored.
  - Local page: `python3 -m http.server 8000 --directory web`, then open `http://localhost:8000/`.

## Review Focus

1. **Clicking an example while music is playing.** Expected: the new piece hot-swaps in and playback continues, without stopping or doubling. Pinned in Task 5, Step 6 (browser check).
2. **Clicking an example of a different style** (Ambient from a Tonal piece). Expected: the example's drawings are applied, with no "Drawing cleared" toast. Pinned in Task 5 (`example contour keys match the style's materials`), plus the Step 6 browser check.
3. **`examples.json` fails to load** (offline, 404, bad JSON). Expected: no chips, no error toast, and the rest of the page works. Pinned in Task 5 (`loadExamples returns [] on failure`).
4. **Dark mode.** Expected: chord pills, legend swatches, and explanation text stay readable. Canvas colors update when the theme changes. Pinned in Task 4 (`readColors exposes function colors`) and the Task 6 dark-mode check.
5. **Phone width with the longer explanation text.** Expected: the panel stacks, an open "the math" wraps inside its card, example chips wrap or scroll, and the page never scrolls sideways. Pinned in Task 6, Step 3 (`scrollWidth <= innerWidth` at 375px).

## File Map

```
src/sinfony/motif.py              modify  _place(); develop_period places copies by the drawing
tests/test_motif.py               modify  copy-placement tests
tests/test_presets_overrides.py   modify  new TONAL_FP values
tests/test_web.py                 modify  late-bar redraw and smoothness-5 tests
scripts/make_examples.py          create  example definitions -> web/examples.json
web/examples.json                 create  generated; committed
tests/test_examples.py            create  the truth checks for every example
web/index.html                    modify  new structure + all explanation copy
web/style.css                     rewrite Material tokens, layout, dark mode
web/tests/page.test.js            create  every control has a plain line and math
web/roll.js                       modify  chord strip pills + legend items
web/tests/roll.test.js            create  chordPills, legendItems, FN_COLOR
web/examples.js                   create  loadExamples, exampleHash
web/tests/examples.test.js        create  hash round-trip, failure, material keys
web/app.js                        modify  readColors tokens, chips, listen banner, legend
README.md                         modify  Playground section mentions examples and explanations
```

---

### Task 1: Tonal motif copies follow the drawing

**Files:**
- Modify: `src/sinfony/motif.py:46-101` (`_join`, `develop_period`)
- Test: `tests/test_motif.py`, `tests/test_web.py`, `tests/test_presets_overrides.py`

**Interfaces:**
- Consumes: `Events.transpose_diatonic(k, scale)`, `Events.shift(dt)`, `Voice.contour` (a `Curve`), `Voice.register`.
- Produces: `_place(part: Events, key: Scale, voice: Voice, prev_last: int | None) -> Events` (private to `motif.py`). `develop_period`'s signature is unchanged.

- [ ] **Step 1: Create the branch**

Run: `git switch -c feat/playground-ui main`
Expected: `Switched to a new branch 'feat/playground-ui'`

- [ ] **Step 2: Write the failing tests**

In `tests/test_motif.py`:
- **Replace** `test_consequent_restates_the_motif`: the notes in beats 16–24 have the same onsets (minus 16) as beats 0–8, and there is one `k` in `range(-14, 15)` with `key.degree(key.degree_of(p) + k)` mapping every motif pitch to the restated pitch.
- **Replace** `test_sequence_is_a_diatonic_transposition`: same check for beats 0–4 vs beats 8–12, with `k` in `range(-14, 15)` (was `(1, -1, 2)`).
- **Add** `test_late_bars_follow_the_drawing`: build `setup()` with a voice whose contour is `Curve(lambda t: np.where(np.asarray(t, dtype=float) < 16, 0.2, 0.85), "low then high")`. Call `develop_period(...)` on section 0. Assert `mean(pitch for onset in [16, 32)) - mean(pitch for onset in [0, 16)) >= 5`.

Let `setup()` take an optional `contour=` argument for this; the default stays as it is today.

In `tests/test_web.py`, add:
- `test_redrawing_late_bars_changes_tonal_melody`: for seeds 0 and 3, the melody pitches from `web.build({"style": "tonal", "seed": s, "contour": {"A": [0.5] * P}})` differ from those with `{"A": [0.5] * 16 + [0.95] * 48}`. This is the opposite of today's behavior.
- `test_drawing_still_leads_at_max_smoothness`: for seeds 0–4, with `{"style": "tonal", "seed": s, "smooth": 5, "contour": {"A": [0.15] * 32 + [0.9] * 32}}`, the first section's mean melody pitch over beats `[16, 32)` is at least 4 above its mean over `[0, 16)`. Take the section span from `piece.plan.form.sections[0]`; tonal 3/4 seeds have a shorter bar.

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_motif.py tests/test_web.py -q`
Expected:
- FAIL: `test_late_bars_follow_the_drawing`, `test_redrawing_late_bars_changes_tonal_melody`, and probably `test_drawing_still_leads_at_max_smoothness`.
- The two replaced tests may pass already. That's fine.

- [ ] **Step 4: Implement `_place` and use it in `develop_period`**

`_place(part, key, voice, prev_last)`. The part is already at its absolute time.
- Empty `part`: return it unchanged.
- `target` = the mean over the part's notes of `lo + contour(onset) · (hi − lo)`, where `(lo, hi) = voice.register`.
- For each `d` in `range(-14, 15)`: take `cand = part.transpose_diatonic(d, key)`. Keep only candidates whose pitches all lie in `[lo, hi]`. If none do, consider all of them.
- Score each candidate as `abs(mean(cand pitches) − target) + 0.25 · abs(cand[0].pitch − prev_last)`. The second term is 0 when `prev_last` is `None`.
- Return the lowest score. Break ties by smaller `abs(d)`, then smaller `d`.

`develop_period`:
- Keep the motif and the variation choice as they are.
- Remove the `options` / `order` / `step` sequence-step logic and its `rng.gen.permutation` draw.
- Build the parts as: the motif at `t = 0`; then `_place(motif.shift(t), …)` for each `t` in `mlen, 2·mlen, …` below `half`; then `_place(motif.shift(half), …)`; then `_place(variation.shift(t), …)` from `half + mlen` until the section ends.
- Each call's `prev_last` is the last pitch of the previous part.
- Update the docstring to say the copies are placed by the drawing.
- Delete `_join` if nothing uses it any more.

- [ ] **Step 5: Run the motif and web tests**

Run: `uv run pytest tests/test_motif.py tests/test_web.py -q`
Expected: PASS.

If `test_drawing_still_leads_at_max_smoothness` fails, **stop and report**. Do not rebalance smoothness: that would change Ambient too, which the spec forbids.

- [ ] **Step 6: Run the full suite and update `TONAL_FP`**

Run: `uv run pytest -q`
Expected: only `test_defaults_unchanged` and `test_explicit_defaults_match_implicit` fail, on the Tonal fingerprints.
- Update `TONAL_FP` to the new values. To print them, use the test file's `fp` logic: `uv run python -c "import hashlib; from sinfony.presets import tonal; print({s: hashlib.sha1(repr([(n.onset, n.dur, n.pitch, n.voice) for n in tonal(s).score]).encode()).hexdigest()[:16] for s in range(4)})"`.
- Change the comment above it to say the values are from after this change.
- Leave `AMBIENT_FP` alone.
- Re-run: everything passes, including `test_tonal_invariants` for 50 seeds (the ≥ 60% stepwise rule).

- [ ] **Step 7: Rebuild the wheel and commit**

Run: `uv run python scripts/build_web.py`, then `uv run ruff check --fix .`
```bash
git add src/sinfony/motif.py tests/test_motif.py tests/test_web.py tests/test_presets_overrides.py
git commit --no-gpg-sign -m "feat: place Tonal motif copies where the drawing asks

The whole melody drawing now shapes Tonal sections; before, only the
first two bars did. Tonal fingerprints updated; Ambient unchanged.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Example data and truth tests

**Files:**
- Create: `scripts/make_examples.py`, `web/examples.json` (generated), `tests/test_examples.py`

**Interfaces:**
- Consumes: `sinfony.web.build(params) -> Piece`, `sinfony.web.PAD_POINTS` (64).
- Produces:
  - `build() -> list[dict]` in `scripts/make_examples.py`.
  - `web/examples.json`: a list in the spec's order. Each entry is `{"id": str, "name": str, "listen": str, "params": dict}`. `params` holds exactly the keys `web.compose` accepts (`style`, `seed`, and optionally `key`, `tempo`, `wiggle`, `smooth`, `density`, `contour`, `tension`).

- [ ] **Step 1: Write the failing tests**

In `tests/test_examples.py`, load the script the way `tests/test_build_web.py` loads `build_web.py` (`importlib.util.spec_from_file_location`). Helpers: `melody(piece)` returns melody `Note`s, and `in_span(notes, a, b)`.

| Test | Assertion |
|---|---|
| `test_file_matches_script` | `json.loads((ROOT/"web/examples.json").read_text()) == build()` |
| `test_names_in_order` | names `== ["Rise and fall", "Calm to storm", "Small steps", "Big leaps", "Dark and bright", "Let chance draw"]`; ids unique |
| `test_params_are_share_safe` | every point `v` satisfies `round(v*63)/63 == v`; scalars lie inside the share ranges (tempo 40–200, wiggle 0–1, smooth 0–5, density 0–1); `web.compose(params)` succeeds |
| `test_rise_and_fall` | for every section whose material is `"A"`, split it into four equal quarters by onset and take the mean melody pitch of each: `max(q2, q3) >= q1 + 2` and `max(q2, q3) >= q4 + 2`. The first and last A have identical `(onset − start, pitch)` lists |
| `test_calm_to_storm` | the mean velocity of all notes in B is ≥ 1.15 × the mean in the first A. B's count of `function == "D"` chords is greater than for the same params with B's 64 tension points set to `round(0.1·63)/63` |
| `test_steps_vs_leaps` | the Small steps and Big leaps params differ only in `smooth` (5 vs 0). The mean \|interval\| of the melody for Big leaps is ≥ Small steps + 1.5 |
| `test_dark_and_bright` | `params["key"]` ends in `-phrygian`, and every melody pitch class is in that Phrygian scale. With the mode swapped to `lydian`, every pitch class is in that Lydian scale and the two pitch-class sets differ |
| `test_let_chance_draw` | every contour point, for every material, equals `q(0.5) = 32/63`. The melody differs from the same params with `seed + 1`, and from the same params with `wiggle` 0 |

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_examples.py -q`
Expected: FAIL (`scripts/make_examples.py` does not exist).

- [ ] **Step 3: Implement `scripts/make_examples.py`**

- `build()` returns the six entries. `__main__` writes `web/examples.json` with `indent=1` and a trailing newline.
- Round every point with `q(v) = round(min(1, max(0, v)) * 63) / 63`, and every scalar to 3 decimals.
- `listen` strings: copy them verbatim from spec §7's "Listen for" column.

Settings, from spec §7:

| id | params |
|---|---|
| `rise-and-fall` | tonal; contour `{"A": [q(0.1 + 0.8·sin(π·i/63)) for i in 0..63]}`; tension 0.2 everywhere (`64 × sections`); wiggle 0.05; smooth low (start at 0.5) |
| `calm-to-storm` | tonal; tension per section `A: 0.1, A′: 0.1, B: 0.95, A: 0.3` (64 points each, in section order) |
| `small-steps` | tonal; wiggle 1; smooth 5 |
| `big-leaps` | same seed as small-steps; wiggle 1; smooth 0 |
| `dark-and-bright` | ambient; key `"<pc>-phrygian"` |
| `let-chance-draw` | tonal; contour 0.5 on every material of that seed's form; wiggle 0.6; smooth 3 |

Seeds (and any key or tempo) are your call. Pick values where the test passes **and** the music sounds good. If a claim fails for every seed you try, change the example settings, not the test or the engine, and keep the "Listen for" text true. Read each seed's sections from `web.build({"style": ..., "seed": ...}).plan.form` so the contour keys and tension lengths match.

- [ ] **Step 4: Generate the file and run the tests**

Run: `uv run python scripts/make_examples.py && uv run pytest tests/test_examples.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check --fix .
git add scripts/make_examples.py web/examples.json tests/test_examples.py
git commit --no-gpg-sign -m "feat: add six teaching examples with truth tests

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Page structure, explanation copy, and Material theme

**Files:**
- Modify: `web/index.html`
- Rewrite: `web/style.css`
- Create: `web/tests/page.test.js`

**Interfaces:**
- Consumes: nothing new.
- Produces, used by later tasks:
  - **Every existing element id is kept:** `play seed dice style root mode tempo tempo-out wiggle wiggle-out smooth smooth-out density density-out loop share midi reset loading loading-stage loading-bar error error-text retry contour tension roll status toast`.
  - **New ids:** `examples` (chip row, starts `hidden`), `listen` (banner, starts `hidden`) holding `listen-text` and the `listen-close` button, and `legend` (inside the result card).
  - **CSS variables** that `readColors()` reads: `--ink --muted --grid --band --band-alt --accent --playhead --v1…--v5`. Map them onto the new tokens. Also add `--fn-home --fn-away --fn-tension --chord-neutral` for Task 4. Every one of them gets light and dark values.

- [ ] **Step 1: Write the failing test**

`web/tests/page.test.js` reads `web/index.html` as text with `fs` (no DOM). Each control block is `<div class="control" data-control="NAME">…</div>`, and each pad card is `<section class="pad" data-pad="NAME">`.

| Test | Assertion |
|---|---|
| `keeps every existing id` | each id in the list above appears as `id="…"` |
| `every control has a plain line` | for `style key tempo smooth wiggle density seed loop share midi reset`, the block contains `class="hint"` |
| `math controls have a closed disclosure` | for `style key tempo smooth wiggle density seed`, the block contains `<details class="math">` with no `open` attribute, and `<summary>ⓘ the math</summary>` |
| `pads explain themselves` | `data-pad="contour"` contains `Melody shape`, `data-pad="tension"` contains `Tension`, and `data-pad="roll"` contains `What you'll hear` and `id="legend"`. `contour` and `tension` each contain a `class="hint"` and a `<details class="math">` |
| `old titles are gone` | no `Melody contour`, no `>Result<` |
| `new ids exist` | `id="examples"`, `id="listen"`, `id="listen-text"`, `id="listen-close"` |

Extract a block with a small helper: find the `data-control="NAME"` index, then cut at the next `data-control=` or `data-pad=`.

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test web/tests/page.test.js`
Expected: FAIL (`data-control` missing).

- [ ] **Step 3: Rewrite `web/index.html`**

- Follow spec §5's layout:
  - top bar: brand, Play;
  - side panel: groups **Piece** (style, key, tempo), **Tune** (smoothness, wiggle, density), **Chance** (seed + dice), then Loop, Share, MIDI, Reset;
  - stage: `#examples`, `#listen`, then the Melody shape, Tension, and What you'll hear cards.
- Plain lines and math text: copy them **verbatim** from spec §6, into `p.hint` and `details.math > p`.
- Pads: header title, plain line, then the math disclosure, then the canvas.
- The result card's math is the legend: `#legend`, filled by Task 5.
- Link the Google Fonts stylesheet: Roboto 400/500 and Roboto Mono 400, `display=swap`.
- Keep `aria-label`s on the dice, root, and mode. `#listen-close` gets `aria-label="Dismiss"`.

- [ ] **Step 4: Rewrite `web/style.css`**

- Put the tokens on `:root`, using the light values from Global Constraints. Add a dark tonal set under `@media (prefers-color-scheme: dark)` (your values; text must meet WCAG AA).
- Map the legacy variables onto the tokens. For example, `--accent` → primary, and `--ink` → on-surface.
- `body` gets an explicit background: surface.
- Cards and panel groups: surface-container, radius 12px, no border.
- Play: primary, radius 16px, soft shadow.
- Chips: primary-container.
- `.hint`: on-surface-variant, 13px.
- `details.math`: Roboto Mono 12px, wrapping (`overflow-wrap: anywhere`).
- Panel width about 296px. At ≤ 800px: stack the panel, keep a 16px gutter, wrap the example chips, and avoid any horizontal scroll.
- Keep `touch-action: none` on the pad canvases.
- Respect `prefers-reduced-motion` for any transition.

- [ ] **Step 5: Run the tests**

Run: `node --test web/tests/*.test.js`
Expected: PASS (all old and new JS tests).

- [ ] **Step 6: Check in the browser**

- Build the wheel and serve `web/`.
- At 1280px, light theme: the layout matches spec §5, every control shows its plain line, "ⓘ the math" opens and closes with the mouse and with Tab+Enter, and drawing still works.
- Expected: no console errors.

- [ ] **Step 7: Commit**

```bash
git add web/index.html web/style.css web/tests/page.test.js
git commit --no-gpg-sign -m "feat(web): Material look and in-place explanations for every control

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Chord strip colored by function

**Files:**
- Modify: `web/roll.js`, `web/app.js` (`readColors` only)
- Create: `web/tests/roll.test.js`

**Interfaces:**
- Consumes: the chords in `piece.chords` (`{onset, dur, label, function}`), and the CSS variables from Task 3.
- Produces:
  - `export const FN_COLOR = { T: "fnHome", S: "fnAway", D: "fnTension", other: "chordNeutral" }`.
  - `export const MIN_LABEL_PX = 22`.
  - `export function chordPills(chords, x) -> Array<{x0: number, x1: number, label: string, colorKey: string, showLabel: boolean}>`. `x` maps beats to pixels.
  - `export function legendItems(style: "tonal" | "ambient") -> Array<{colorKey: string, text: string}>`.
  - `readColors()` also returns `fnHome`, `fnAway`, `fnTension`, `chordNeutral`.

- [ ] **Step 1: Write the failing tests**

In `web/tests/roll.test.js`:
- `chordPills spans each chord`: given chords at beats 0–4 (`T`) and 4–8 (`D`) and `x = b => b * 10`, the result is `[{x0: 0, x1: 40, …colorKey: "fnHome"}, {x0: 40, x1: 80, …colorKey: "fnTension"}]`.
- `chordPills hides labels that do not fit`: a chord 1 beat wide at `x = b => b * 10` (10px < 22) has `showLabel === false`; a chord 4 beats wide has `true`.
- `unknown function falls back to neutral`: a chord with `function: "other"` gets `"chordNeutral"`.
- `legendItems tonal`: three items with keys `fnHome, fnAway, fnTension`. Their texts contain `Home (I, iii, vi)`, `Away (ii, IV, V/V)` and `Tension (V, V7, vii°)`.
- `legendItems ambient`: one item, `chordNeutral`, with the text `Each chord moves to a close neighbor on the Tonnetz (P, L, or R).`

- [ ] **Step 2: Run them to verify they fail**

Run: `node --test web/tests/roll.test.js`
Expected: FAIL (no export named `chordPills`).

- [ ] **Step 3: Implement**

- Add the exports to `roll.js`.
- In `drawRoll`, replace the text-only chord labels with a pill strip: top band 26px; pills 18px tall, radius 9px, 1px gap; label centred when `showLabel`. The fill is the `colorKey` color at about 35% alpha in light theme and 45% in dark, with on-surface text.
- The notes area starts below the strip.
- Section letters stay on the bands.
- In `app.js`, extend `readColors()` with the four new keys from `--fn-home`, `--fn-away`, `--fn-tension`, `--chord-neutral`. The existing theme listener then refreshes them.

- [ ] **Step 4: Run the tests**

Run: `node --test web/tests/*.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/roll.js web/app.js web/tests/roll.test.js
git commit --no-gpg-sign -m "feat(web): chord strip colored by harmonic function

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Example chips, Listen-for banner, and legend wiring

**Files:**
- Create: `web/examples.js`, `web/tests/examples.test.js`
- Modify: `web/app.js`

**Interfaces:**
- Consumes: `encodeHash`/`decodeHash` (`share.js`), `web/examples.json` (Task 2), `legendItems` (Task 4), and the ids `examples listen listen-text listen-close legend` (Task 3).
- Produces:
  - `export async function loadExamples(fetchFn = fetch, url = "examples.json") -> Promise<Array<{id, name, listen, params}>>`. It returns `[]` on any failure: a rejected fetch, a non-OK response, bad JSON, or something that isn't an array of objects with string `id/name/listen` and an object `params`.
  - `export function exampleHash(example) -> string`: `encodeHash` of `{style, seed, key, tempo, wiggle, smooth, density, contour, tension}` from `params`, with missing fields as `null` (`contour` defaults to `{}`).

- [ ] **Step 1: Write the failing tests**

In `web/tests/examples.test.js`, read the real `web/examples.json` with `fs`.
- `exampleHash round-trips every example`: `decodeHash(exampleHash(ex))` gives `ignored.length === 0`. Its state's `style`, `seed`, `key`, `wiggle`, `smooth`, `density`, `contour` and `tension` deep-equal `params`, with missing fields expected as `null` or `{}`.
- `example contour keys match the style's materials`: the keys are a subset of `{A, B}` for tonal and `{A, B, C}` for ambient. The tension length, when present, is `64 × 4` for tonal and `64 × 5` for ambient.
- `loadExamples returns [] on failure`: with a fetch stub that rejects → `[]`; with one returning `{ok: false}` → `[]`; with one whose `json()` resolves to `{}` → `[]`.
- `loadExamples returns the list`: with a fetch stub returning the real file's parsed JSON → the same array.

- [ ] **Step 2: Run them to verify they fail**

Run: `node --test web/tests/examples.test.js`
Expected: FAIL (cannot find `../examples.js`).

- [ ] **Step 3: Implement `web/examples.js`**

- [ ] **Step 4: Wire it into `app.js`**

- **On startup:** `loadExamples()`. If the list is non-empty, render one `button.chip` per example (with `aria-pressed`) into `#examples`, behind a "Try an example:" label, and unhide it.
- **On a chip click:**
  - Compute `h = exampleHash(ex)`. If `location.hash === h`, run the hashchange path directly (`loadFromHash(); refreshPads(); requestCompose();`); otherwise set `location.hash = h`.
  - Then set `#listen-text` to `ex.listen`, unhide `#listen`, and mark this chip `aria-pressed="true"` (all others `false`).
- **`#listen-close`:** hides the banner and clears the pressed state. The banner otherwise stays visible while the user edits.
- **In `applyPiece`:** fill `#legend` from `legendItems(piece.style)`, with a swatch `span` per item colored by its token and the item's text. Use `textContent`, not `innerHTML`.

- [ ] **Step 5: Run the tests**

Run: `node --test web/tests/*.test.js`
Expected: PASS.

- [ ] **Step 6: Check in the browser**

- Click each of the six chips. Each loads its drawing and settings, shows its Listen-for line, and the legend matches the style.
- Click **Dark and bright** while a Tonal piece is playing. Playback continues into the new piece, and there's no "Drawing cleared" toast.
- Click the same chip twice: the piece is reapplied.
- Temporarily rename `examples.json` and reload: there are no chips and no error toast, and drawing and Play work. Then restore the file.

- [ ] **Step 7: Commit**

```bash
git add web/examples.js web/tests/examples.test.js web/app.js
git commit --no-gpg-sign -m "feat(web): one-click examples with listen-for hints and chord legend

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Whole-page verification and README

**Files:**
- Modify: `README.md` (Playground section)

- [ ] **Step 1: Run all suites**

Run: `uv run pytest -q && node --test web/tests/*.test.js && uv run ruff check .`
Expected: all pass; ruff clean.

- [ ] **Step 2: Check desktop, light and dark**

- Serve `web/` at 1280×800. Check the look against spec §4, then emulate dark mode.
- Pills, legend swatches, hints, and math text are readable in both themes.
- Toggling the OS theme while the page is open recolors the canvases.
- Play/Stop, Loop, Share (link copied), and MIDI download all work, and an old-style link (`#v=1&style=tonal&seed=3`) opens.

- [ ] **Step 3: Check phone width**

- At 375×812, run `document.scrollingElement.scrollWidth <= innerWidth` in the console. Expected: `true`, with every "the math" open and the Calm to storm banner shown.
- Drawing with touch emulation doesn't scroll the page.

- [ ] **Step 4: Update the README**

In `README.md`'s Playground section, add two sentences: every control explains itself (with the math one tap away), and six examples each demonstrate one idea.

- [ ] **Step 5: Leave listening files for the user**

Run: `uv run python -c "import sinfony; [sinfony.tonal(s).save_wav('listen-tonal-%d.wav' % s) for s in range(3)]"`. This writes them to the repo root, where `*.wav` is gitignored.
Report the paths so the user can hear the new Tonal sequences.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit --no-gpg-sign -m "docs: describe the playground's explanations and examples

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
