# sinfony

Music from mathematics. A piece is written as layered math (curves, noise,
and real music theory), and sinfony turns it into sound, MIDI, and an
annotated piano roll.

```python
import sinfony as sf

piece = sf.tonal(seed=42)   # or sf.ambient(seed=42)
piece.play()                # inline in Jupyter, speakers, or a WAV file
piece.show()                # piano roll with contour, chords, and tension
piece.save_midi("tonal.mid")
```

## How it works

| Layer | Math |
|---|---|
| Plan | form (A A' B A), key areas, tension curve T(t) |
| Harmony | functional Markov chain (T→S→D→T) or a Tonnetz walk (P, L, R) |
| Voices | contour curve + 1/f noise → nearest allowed pitch, shaped by rule penalties |
| Motifs | transpose, invert, augment: group actions on notes |
| Perform | phrase arcs (Todd), ritardando, pink-noise micro-timing |
| Synth | additive partials; piano inharmonicity fₙ = n·f₀·√(1+B·n²) |

Same seed → same piece. Every layer can be inspected (`piece.chords`,
`piece.score`, `piece.plan.tension`).

## Setup

```bash
uv sync
uv run pytest
# open notebooks/01_tour.ipynb in VS Code (uses the ipykernel dev dependency),
# or: uvx --with-editable . jupyter lab notebooks/01_tour.ipynb
```

Optional speaker playback outside notebooks: `uv sync --extra audio`.

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
