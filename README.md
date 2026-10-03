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
