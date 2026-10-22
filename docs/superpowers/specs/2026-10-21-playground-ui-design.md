# sinfony Playground UI — Design Spec

**Date:** 2026-10-21
**Status:** Approved in brainstorming; pending written-spec review
**Builds on:** `docs/superpowers/specs/2026-10-04-playground-design.md` (the playground as built)

## 1. Intent

The playground works, but a newcomer opens it and sees unexplained controls
(Seed, Wiggle, Smoothness, Density, two drawing pads) with no way to predict
what each one does to the sound. This redesign makes the page **explain
itself** and gives it a calmer, Material-style look.

**Audience:** a beginner at music who is good at math. They should be able to
predict what a control will do before touching it, and, if they are curious,
see the formula that makes it happen. This serves sinfony's learning goal:
learn music through math you already know.

## 2. Goals, non-goals, anti-goals

**Goals**
1. A minimalist Material 3 look (Section 4).
2. Every control and pad says, in one plain sentence, what you'll hear when you change it.
3. Every control can reveal "the math": the actual formula sinfony uses, with one sentence linking it to the sound.
4. Six one-click examples, each teaching one idea, each with a "Listen for" line.
5. The result view teaches harmony: chord names colored by their role (home, away, tension).
6. In Tonal, the melody drawing shapes the whole section, not only its first 2 bars (Section 9, the one engine change).

**Non-goals (this version)**
- No other engine changes. Apart from Section 9, controls keep their meaning, ranges, and effect.
- No change to how tension picks chords. Repeated sections keep the chords of their first appearance, as in classical form.
- No humming or audio input (Basic Pitch), no negative harmony, no drums. Recorded for later.
- No guided tour or multi-step tutorial. The page explains itself in place.

**Anti-goals: failure even if it works**
- An explanation that says something the engine doesn't do. Every plain line,
  formula, and "Listen for" claim must be true of the engine as shipped (Section 10).
- Clutter: explanations that make the page busier than today. Text is short,
  muted, and the math is hidden until asked for.
- Share links that stop opening. Links stay `v=1`. Accepted by the user:
  **Tonal links made before Section 9 will play somewhat different melody
  notes**, because the site is new and few links exist. Ambient links play
  unchanged.

## 3. Decisions taken in brainstorming

| Topic | Decision | By |
|---|---|---|
| Look | **A · Tonal**: warm tinted surfaces from the current terracotta, Material 3, no borders | user |
| Layout | **A · One side panel** for all controls, grouped under headings; drawings large on the right | user |
| Explanations | One plain line always visible; "ⓘ the math" reveals the formula | proposed, user agreed |
| Examples | The six in Section 7 | proposed, user agreed |
| Chord view | Chord names under the notes, colored by function (idea from musicpy's chord analysis) | proposed, user agreed |
| Tonal drawing reach | Change the engine so motif copies follow the drawing (Section 9) | proposed, user agreed |
| Tension and chords | Keep the engine. Tension is explained as mainly loudness, plus a few more tense chords in Tonal | proposed, user agreed |

Mockups from brainstorming: `.superpowers/brainstorm/46602-1792622871/content/visual-style.html`
and `layout.html` (local only; not committed; add `.superpowers/` to `.gitignore`).

### Facts found while checking this design (engine as of commit 8750311)

- **Tonal drawing reach:** Tonal builds a 2-bar motif from the drawing, then fills bars 3–8 with copies (sequence, restatement, variation) in `develop_period` (`src/sinfony/motif.py`). Redrawing pad points 16–63 of a section gives bit-identical notes (checked on seeds 0 and 3). Ambient is not affected.
- **Smoothness vs wiggle:** with wiggle 0 and a smooth drawing, smoothness barely changes the melody. Mean melodic interval on tonal seed 0: 1.8 (smoothness 0) vs 2.0 semitones (smoothness 5). With wiggle 1: 6.4 vs 1.7.
- **Smoothness vs the drawing:** above about 1, smoothness can stop the tune from following a steep drawing, because each semitone beyond a whole step costs more than it gains.
- **Tension:** mean velocity rises about 25–40% from low to high tension. Chord effect is weak: chords are generated once per section letter and reused on its repeats (`by_section`, `harmony.py`). High tension on the B section adds about one dominant chord in ten on average (seeds 0–5: 3.2 → 4.3), and not for every seed.
- **Note choice:** Tonal picks the lowest-scoring note. Ambient samples with temperature 0.8: p(c) ∝ exp(−score/0.8). Both styles then fit notes to the chords in a final pass (`requantize`, fixed smoothness weight 0.5).

## 4. Look

Material 3 with a custom tonal palette built from the existing accent `#c8553d`.
Values used in the approved mockup (light):

| Role | Light | Use |
|---|---|---|
| primary | `#9c4330` | Play button, slider fill and thumb, drawn curves, links |
| on-primary | `#ffffff` | text on primary |
| primary-container | `#ffdbd1` | example chips |
| on-primary-container | `#3b0a02` | chip text |
| surface | `#fff8f6` | page background |
| surface-container | `#fceae5` | panel groups, pad cards |
| on-surface | `#231917` | main text |
| on-surface-variant | `#53433f` | plain-line explanations |
| outline-variant | `#ead6d1` | slider track, dividers if needed |

- **Dark mode:** a matching dark tonal set, derived from the same seed color.
  Must keep the existing `prefers-color-scheme` behavior, and the canvas
  colors (`readColors()` in `web/app.js`) must come from the same tokens.
- **No borders** on cards: color separates surfaces. Corner radius 12px for
  cards and 16px for the Play button. A soft shadow on Play only.
- **Type:** Roboto (Google Fonts) with a system-font fallback; Roboto Mono for formulas. (Builder's call: drop the web font if it hurts first load.)
- **Voice colors** in the piano roll may be re-tuned to sit with the palette, but stay distinguishable in both themes.
- Material *style* only: **no** Material component library. Plain HTML/CSS/JS, as today.

## 5. Layout

```
┌───────────────────────────────────────────────────────────────┐
│ sinfony                                              [▶ Play] │
├────────────────────┬──────────────────────────────────────────┤
│ PIECE              │ Try an example: (chip)(chip)(chip)…      │
│  Style             │ ┌ Listen for: … ─────────────────── × ┐  │
│  Key   [root][mode]│ ┌ Melody shape ───────────────────────┐  │
│  Tempo ───●──      │ │ plain line                          │  │
│ TUNE               │ │ (drawing pad)                       │  │
│  Smoothness ──●─   │ └─────────────────────────────────────┘  │
│  Wiggle ●────      │ ┌ Tension ────────────────────────────┐  │
│  Density ───●─     │ └─────────────────────────────────────┘  │
│ CHANCE             │ ┌ What you'll hear ───────────────────┐  │
│  Seed [ 42 ] 🎲    │ │ chord strip + piano roll + legend   │  │
│ ────────────────── │ └─────────────────────────────────────┘  │
│ ☐ Loop             │                                          │
│ Share · MIDI ·     │                                          │
│ Reset drawing      │                                          │
└────────────────────┴──────────────────────────────────────────┘
```

- **Top bar:** brand on the left, Play/Stop on the right (Material filled button with an icon).
- **Side panel**, in groups on surface-container cards: **Piece** (style, key, tempo), **Tune** (smoothness, wiggle, density), **Chance** (seed, dice). Loop, Share, MIDI, and Reset sit at the bottom of the panel.
- **Stage:** example chips, then the "Listen for" banner (only after an example is chosen), then the Melody shape, Tension, and What you'll hear cards.
- The loading and error banners keep their behavior and adopt the new look.
- **Phone width:** the panel stacks above the stage (as today). Example chips scroll sideways or wrap. No horizontal page scroll.
- Panel width is the builder's call (today 250px; the explanations may need about 280–300px).

## 6. Controls: plain lines and the math

Each control shows its **plain line** at all times, in on-surface-variant
under the control. **"ⓘ the math"** is a disclosure (a `<details>` element or
an accessible equivalent): it opens the formula plus one linking sentence,
and it starts closed. Keep the exact wording close to the text below; the
facts must stay true (Section 10). Where the engine change in Section 9
alters a formula, the text must describe the shipped engine.

| Control | Plain line (always visible) | The math (revealed) |
|---|---|---|
| **Style** | Tonal: classical piano; chords pull toward a home chord, and the piece ends there. Ambient: slow and drifting; chords glide to close neighbors while two bell loops repeat. | Tonal: chords follow a Markov chain over functions, Tonic → Subdominant → Dominant → Tonic. The melody is a 2-bar motif, repeated and moved to follow your drawing. Ambient: chords walk the Tonnetz with P, L, R moves (each changes one note by one or two semitones). The loops have 8 and 13 steps, so they line up again only every lcm(8, 13) = 104 steps. |
| **Key** (root, mode) | Which notes the music may use. The first menu picks the home note; the second picks the mood (major sounds bright, minor darker). | A scale is a set of pitch classes in ℤ₁₂. Major = 7 stacked fifths: 7k mod 12, for k = −1…5, gives {0, 2, 4, 5, 7, 9, 11}. A mode uses the same notes as another scale with a different home note. |
| **Tempo** | How fast, in beats per minute. | One beat lasts 60 / bpm seconds. The performance pushes a little faster in the middle of each 4-bar phrase, using the arc 1 − 4(u − ½)², and slows down over the final bars. |
| **Smoothness** | Higher: the tune moves to nearby notes. Lower: it's free to leap. You hear it most when Wiggle or your drawing jumps around. | Each candidate note c gets a score \|c − target\| + w · max(0, \|c − previous\| − 2), with w = smoothness. A whole step (2 semitones) is free; every semitone beyond it costs w. Tonal picks the lowest score; Ambient picks at random, with p(c) ∝ exp(−score / 0.8), so low scores are much likelier. |
| **Wiggle** | How far the tune wanders from your drawing. 0 stays close to it; 1 wanders a lot. | shape(t) = drawing(t) + wiggle · pink(t), clipped to [0, 1]. Pink (1/f) noise has big slow drifts and small fast jitters, like real melodies (Voss & Clarke, 1975). |
| **Density** | How many notes the tune plays. Low: a few long notes. High: busy. | At every grid step (½ beat in Tonal, 1 beat in Ambient) a note starts with probability density × beat strength. Strong beats get notes first. |
| **Seed + 🎲** | The piece is fixed until you change this number. The same seed gives the same piece on every computer. A new seed also picks a new key and tempo. | All randomness comes from a generator started from this number. Each layer (plan, harmony, melody…) gets its own stream, so changing one control doesn't reshuffle the others. |
| **Loop** | Start again from the top when the piece ends. | none |
| **Share** | Copy a link that plays exactly this piece. | none |
| **MIDI** | Download the notes. Open the file in MuseScore or GarageBand to see the sheet music. | none |
| **Reset drawing** | Clear your drawings and go back to the style's own shapes. | none |

**Pads** (plain line in the card header, math disclosure in the card):

| Pad | Plain line | The math |
|---|---|---|
| **Melody shape** | Draw where the tune goes high or low. Sections with the same letter (A, A′) repeat, so drawing one draws them all. | target pitch = low + shape(t) · (high − low), inside the melody's range. Notes are then picked by the score under Smoothness. In Tonal, the first 2 bars become a motif, and each later copy of it is moved up or down to sit where you drew (Section 9). |
| **Tension** | Low: calm and softer. High: louder and more intense; in Tonal, a few more chords that want to resolve. | Loudness × (0.7 + 0.3 · tension). Tonal: when a new chord is chosen, the chance of a Dominant × (1 + tension), of a Tonic × (1.5 − tension). Repeated sections reuse their first chords, so tension changes chords mostly in sections heard once (like B). Ambient: the chance of a chord change = 0.3 + 0.6 · tension. |
| **What you'll hear** | The notes as they'll play, with the chords above them. | Legend (Section 8). |

**Rename:** "Melody contour" becomes **Melody shape** and "Result" becomes
**What you'll hear**. Control ids, parameter names, and share-link fields do
not change.

## 7. Examples

A row of chips. Clicking one loads its full settings and drawings (exactly
like opening a share link), then shows a dismissible **Listen for** banner
above the pads. Changing anything afterwards keeps the banner until it is
dismissed or another example is chosen. (Builder's call: dim it instead.)

| Chip | Settings | Listen for |
|---|---|---|
| **Rise and fall** | Tonal. Melody shape: one arch (rise, then fall) drawn across the A material. Tension flat and low (≈0.2). Wiggle 0.05. Smoothness low enough that the tune follows the arch (builder's call, verified by test). | The tune climbs and falls with your arch, and every A section comes back with the same shape. |
| **Calm to storm** | Tonal. Default melody shape. Tension low through the A sections and high through B, then easing back for the final A. | B gets much louder and more intense. Watch the chord strip: more Tension-colored chords in B. |
| **Small steps** | Tonal. Wiggle 1, smoothness 5. | Lots of wandering, but the tune still moves note to note, like a scale. Compare with Big leaps. |
| **Big leaps** | Tonal. Wiggle 1, smoothness 0. Same seed as Small steps. | Same wandering, but now the tune jumps. Only smoothness changed. |
| **Dark and bright** | Ambient, Phrygian mode. | A dark, tense mood. Switch the mode to Lydian: same drawing, bright and floating, because only the allowed notes changed. |
| **Let chance draw** | Tonal. Melody shape drawn flat (0.5) on every material. Wiggle 0.6, smoothness 3. | You drew nothing, so pink noise writes the melody. Roll 🎲 to hear other takes. |

- Seeds, keys, and tempos for each example are the builder's call: choose ones that sound good and make the claim obvious. For Calm to storm, pick a seed where B's dominant count clearly rises at high tension (the effect varies by seed; see Section 3 facts).
- **One source of truth:** define the examples as data (for example, `web/examples.json` holding chip name, "Listen for" text, and the share-link parameters), so a Python test can check each claim (Section 10).

## 8. Chord strip (from musicpy's analysis idea)

The roll already prints chord labels (`web/roll.js`), and the engine already
exports each chord's `label` and `function` (`Piece.to_json`). Make them
teach:

- A chord strip above the notes: one pill per chord span, label inside (I, IV, V7…).
- **Tonal:** color by function, with a small legend: **Home** (T: I, iii, vi), **Away** (S: ii, IV, and secondary dominants such as V/V), **Tension** (D: V, V7, vii°). This follows `numeral_function` in `theory.py`. Builder's call: the colors, from the palette.
- **Ambient:** the functions are `"other"`, so show chord names (Cm, A♭…) in a neutral color, and a one-line legend: "Each chord moves to a close neighbor on the Tonnetz (P, L, or R)."
- Keep the existing overlap-skipping so labels stay readable on narrow screens.
- The section letters (A, A′, B) stay on the bands.

## 9. Engine change: Tonal motif copies follow the drawing

**Problem:** in `develop_period` only the first 2 bars of each section read
the drawing. The later copies are placed by a fixed sequence step and by
"nearest octave" joins, so bars 3–8 ignore what the user drew.

**Change:** keep the motif-and-copies structure, because it makes the tune
memorable, but choose where each copy sits from the drawing:

- For each copy (sequence copies, the restatement at the half, and the variation copies), compute the drawing's target over that copy's time window: target = low + mean(shape over the window) · (high − low), using the same shaped contour the motif used (drawing + wiggle · pink).
- Transpose the copy **diatonically** (within the section's key) so its mean pitch is as close as possible to that target. Keep the copy's internal intervals and rhythm.
- A gentle tie-break keeps the line connected at copy boundaries, for example preferring the candidate whose first note is closest to the previous copy's last note when two transpositions fit the target about equally well.
- The variation (inversion or augmentation), the A′ lift, the cadences, and the final `requantize` pass stay as they are.
- With the default Tonal shape (an arch every 4 bars), the result should still sound like a sequence. Listen to a few seeds before and after and confirm it still sounds musical.

**Smoothness balance:** after this change, check the claim "the tune follows the drawing" across the whole smoothness range (0–5). If high smoothness still flattens a steep drawing so much that the claim is false, the builder may rebalance (for example, by scaling the step-bias weight) as long as the slider's plain line and formula are updated to match the shipped code. Keep the slider range 0–5 and the share-link field unchanged.

**Tests (Python):**
- Redrawing pad points 16–63 of a Tonal section **does** change the melody in bars 3–8.
- A drawing that is high in bars 5–8 and low in bars 1–4 gives a higher mean melody pitch in bars 5–8 than in bars 1–4 (several seeds).
- Same seed and params still give identical output (determinism).
- Existing engine tests keep passing; update any that pinned the old placement, and say so in the commit.
- Rebuild the wheel used by the web app.

## 10. Constraints

- **Truth check:** every claim in Sections 6 and 7 must hold for the engine as shipped. Add a Python test that loads the example data and checks the measurable claims on the engine output. At least:
  - Big leaps has a clearly larger mean melodic interval than Small steps.
  - Calm to storm: mean velocity in B is higher than in the first A, and B has more dominant chords than the same seed with low tension in B.
  - Rise and fall: the melody's mean pitch rises over the first half of the arch and falls over the second, and the A sections share their contour.
  - Let chance draw: two different seeds give different melodies.
  If a claim fails, change the example settings or the wording, not the engine (Section 9 is the only engine change).
- Share links stay `v=1`. Examples use the same parameters a share link carries.
- No new runtime dependencies beyond a web font. Plain JS modules, as today.
- Existing JS (`web/tests`) and Python tests keep passing.
- Accessibility: every control keeps a visible label; "the math" opens from the keyboard; text contrast meets WCAG AA in both themes.
- Works at phone width with a 16px gutter and no horizontal scroll.
- GitHub Pages deploy unchanged.

## 11. Left to the builder

- Exact dark palette values, spacing, panel width, and icon glyphs.
- How "the math" renders: plain text with Unicode is fine; no math typesetting library.
- Seeds, keys, and tempos for the examples, and exact "Listen for" wording within the facts above.
- Whether the plain lines live in HTML or in a JS table that also feeds the examples.
- The exact tie-break and any smoothness rebalance in Section 9, within its constraints.
- Animations: optional and subtle; respect `prefers-reduced-motion`.

## 12. Later (out of this version)

- Hum or play a motif as input (Basic Pitch via `basic-pitch-ts`), which needs beat quantization and key detection first.
- Negative harmony as a new transformation: pc ↦ (2·tonic + 7 − pc) mod 12.
- Tension that also re-chooses chords on repeated sections.
- Chord detection/analysis of imported MIDI, and a drums voice with pattern strings (musicpy ideas).
