"""Music theory as mathematics: pitch, scales, chords, voice leading, consonance."""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np

NOTE_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")


def freq(n: float) -> float:
    """Equal temperament: each semitone multiplies frequency by 2^(1/12)."""
    return 440.0 * 2.0 ** ((n - 69) / 12)


def pc(n: int) -> int:
    """Pitch class: the pitch modulo the octave (12 semitones)."""
    return int(n) % 12


def note_name(n: int) -> str:
    return f"{NOTE_NAMES[pc(n)]}{int(n) // 12 - 1}"


MODES: dict[str, tuple[int, ...]] = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "ionian": (0, 2, 4, 5, 7, 9, 11),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
    "pentatonic": (0, 2, 4, 7, 9),
}


@dataclass(frozen=True)
class Scale:
    """A tonic (MIDI pitch) plus the semitone steps above it.

    The major scale is ``Scale(60, (0, 2, 4, 5, 7, 9, 11))``: C major.
    """

    root: int
    steps: tuple[int, ...]

    def __post_init__(self):
        steps = tuple(sorted({int(s) % 12 for s in self.steps}))
        if not steps or steps[0] != 0:
            raise ValueError("Scale steps must include 0 (the tonic)")
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "root", int(self.root))

    # --- constructors ---------------------------------------------------
    @classmethod
    def generated(cls, gen: int = 7, n: int = 7, root: int = 60) -> Scale:
        """Stack ``n`` copies of the interval ``gen`` (mod 12). gen=7 stacks fifths.

        For n >= 7 the stack starts one step below the tonic so the result is
        the major scale (F C G D A E B); for smaller n it starts on the tonic
        (C G D A E = major pentatonic).
        """
        if n < 1:
            raise ValueError("n must be >= 1")
        start = -1 if n >= 7 else 0
        return cls(root, tuple((gen * (k + start)) % 12 for k in range(n)))

    @classmethod
    def mode(cls, name: str, root: int = 60) -> Scale:
        if name not in MODES:
            raise ValueError(f"Unknown mode {name!r}; choose from {sorted(MODES)}")
        return cls(root, MODES[name])

    @classmethod
    def major(cls, root: int = 60) -> Scale:
        return cls.mode("major", root)

    @classmethod
    def minor(cls, root: int = 57) -> Scale:
        return cls.mode("minor", root)

    @classmethod
    def dorian(cls, root: int = 62) -> Scale:
        return cls.mode("dorian", root)

    @classmethod
    def phrygian(cls, root: int = 64) -> Scale:
        return cls.mode("phrygian", root)

    @classmethod
    def lydian(cls, root: int = 65) -> Scale:
        return cls.mode("lydian", root)

    @classmethod
    def mixolydian(cls, root: int = 67) -> Scale:
        return cls.mode("mixolydian", root)

    @classmethod
    def aeolian(cls, root: int = 57) -> Scale:
        return cls.mode("aeolian", root)

    @classmethod
    def locrian(cls, root: int = 59) -> Scale:
        return cls.mode("locrian", root)

    @classmethod
    def pentatonic(cls, root: int = 60) -> Scale:
        return cls.mode("pentatonic", root)

    # --- properties -----------------------------------------------------
    @property
    def pcs(self) -> frozenset[int]:
        return frozenset((self.root + s) % 12 for s in self.steps)

    @property
    def name(self) -> str:
        for name, steps in MODES.items():
            if steps == self.steps:
                return name
        return "custom"

    def is_minor(self) -> bool:
        return self.steps == MODES["aeolian"]

    def __len__(self) -> int:
        return len(self.steps)

    # --- pitch arithmetic -----------------------------------------------
    def degree(self, i: int) -> int:
        """MIDI pitch of scale degree ``i`` (0 = tonic, 7 = tonic an octave up)."""
        octave, idx = divmod(int(i), len(self.steps))
        return self.root + 12 * octave + self.steps[idx]

    def contains(self, pitch: int) -> bool:
        return (int(pitch) - self.root) % 12 in self.steps

    def nearest(self, pitch: float) -> int:
        p = int(round(pitch))
        cands = [q for q in range(p - 6, p + 7) if self.contains(q)]
        return min(cands, key=lambda q: (abs(q - pitch), q))

    def degree_of(self, pitch: int) -> int:
        q = self.nearest(pitch)
        octave, rel = divmod(q - self.root, 12)
        return octave * len(self.steps) + self.steps.index(rel)

    def pitches(self, lo: int, hi: int) -> list[int]:
        return [p for p in range(lo, hi + 1) if self.contains(p)]

    def transpose(self, k: int) -> Scale:
        return Scale(self.root + k, self.steps)

    def subset(self, degrees: Iterable[int]) -> Scale:
        return Scale(self.root, tuple(self.steps[d % len(self.steps)] for d in degrees))


# --- chords -------------------------------------------------------------
QUALITIES: dict[str, tuple[int, ...]] = {
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "dom7": (0, 4, 7, 10),
    "min7": (0, 3, 7, 10),
    "hdim7": (0, 3, 6, 10),
    "maj7": (0, 4, 7, 11),
}
_SYMBOL = {
    "maj": "",
    "min": "m",
    "dim": "dim",
    "aug": "+",
    "dom7": "7",
    "min7": "m7",
    "hdim7": "m7b5",
    "maj7": "maj7",
}
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")


@dataclass(frozen=True)
class Chord:
    """A set of pitch classes in Z12 with a root. C major = {0, 4, 7}."""

    root: int
    pcs: frozenset[int]
    label: str = field(default="", compare=False)

    def __post_init__(self):
        object.__setattr__(self, "root", pc(self.root))
        object.__setattr__(self, "pcs", frozenset(pc(p) for p in self.pcs))
        if self.root not in self.pcs:
            raise ValueError("Chord root must be one of its pitch classes")

    @classmethod
    def build(cls, root: int, quality: str, label: str = "") -> Chord:
        if quality not in QUALITIES:
            raise ValueError(f"Unknown chord quality {quality!r}")
        r = pc(root)
        pcs = frozenset((r + i) % 12 for i in QUALITIES[quality])
        return cls(r, pcs, label or f"{NOTE_NAMES[r]}{_SYMBOL[quality]}")

    @property
    def intervals(self) -> tuple[int, ...]:
        return tuple(sorted((p - self.root) % 12 for p in self.pcs))

    @property
    def quality(self) -> str | None:
        for name, iv in QUALITIES.items():
            if iv == self.intervals:
                return name
        return None

    def contains(self, pitch: int) -> bool:
        return pc(pitch) in self.pcs

    def pitches(self, lo: int, hi: int) -> list[int]:
        return [p for p in range(lo, hi + 1) if pc(p) in self.pcs]

    def __str__(self) -> str:
        return self.label or f"{NOTE_NAMES[self.root]}{sorted(self.pcs)}"


def _roman_label(degree: int, quality: str | None, size: int) -> str:
    base = ROMAN[degree % 7] if size == 7 else str(degree % size + 1)
    if quality in ("min", "dim", "min7", "hdim7"):
        base = base.lower()
    suffix = {"dim": "°", "aug": "+", "hdim7": "ø7", "dom7": "7", "min7": "7", "maj7": "maj7"}
    return base + suffix.get(quality or "", "")


def _stacked(scale: Scale, degree: int, count: int) -> Chord:
    ps = [scale.degree(degree + 2 * k) for k in range(count)]
    chord = Chord(pc(ps[0]), frozenset(pc(p) for p in ps))
    return Chord(chord.root, chord.pcs, _roman_label(degree, chord.quality, len(scale)))


def triad(scale: Scale, degree: int) -> Chord:
    """Stack two thirds on a scale degree (0-based: 0 is I)."""
    return _stacked(scale, degree, 3)


def seventh(scale: Scale, degree: int) -> Chord:
    """Stack three thirds on a scale degree (0-based: 4 is V7)."""
    return _stacked(scale, degree, 4)


_ROMAN_RE = re.compile(
    r"^(?P<acc>[b#]?)"
    r"(?P<num>VII|VI|IV|V|III|II|I|vii|vi|iv|v|iii|ii|i)"
    r"(?P<qual>°|o|\+)?(?P<sev>7)?$"
)


def parse_roman(numeral: str, scale: Scale) -> Chord:
    """Chord for a Roman numeral in ``scale``. Case sets quality: V major, v minor."""
    text = numeral.strip()
    if "/" in text:
        head, _, tail = text.partition("/")
        target = parse_roman(tail, scale)
        chord = parse_roman(head, Scale.major(60 + target.root))
        return Chord(chord.root, chord.pcs, text)
    m = _ROMAN_RE.match(text)
    if not m:
        raise ValueError(f"Unknown Roman numeral: {numeral!r}")
    if len(scale) != 7:
        raise ValueError("Roman numerals need a 7-note scale")
    num = m["num"]
    root = pc(scale.degree(ROMAN.index(num.upper()))) + {"b": -1, "#": 1, "": 0}[
        m["acc"]
    ]
    seventh_ = m["sev"] is not None
    if m["qual"] in ("°", "o"):
        quality = "hdim7" if seventh_ else "dim"
    elif m["qual"] == "+":
        quality = "aug"
    elif num.isupper():
        quality = "dom7" if seventh_ else "maj"
    else:
        quality = "min7" if seventh_ else "min"
    return Chord.build(root, quality, text)


def numeral_function(numeral: str) -> str:
    """Harmonic function: T (tonic), S (pre-dominant), D (dominant), or other."""
    if "/" in numeral:
        return "S"  # secondary dominants prepare the dominant
    if numeral[:1] in ("b", "#"):
        return "other"
    head = numeral.rstrip("7°o+").upper()
    return {"I": "T", "VI": "T", "III": "T", "IV": "S", "II": "S", "V": "D", "VII": "D"}.get(
        head, "other"
    )


# --- neo-Riemannian transformations ---------------------------------------
def _major_or_minor(chord: Chord) -> tuple[int, str]:
    if chord.quality not in ("maj", "min"):
        raise ValueError(f"P/L/R need a major or minor triad, got {chord}")
    return chord.root, chord.quality


def P(chord: Chord) -> Chord:
    """Parallel: C major <-> C minor (move the third by a semitone)."""
    r, q = _major_or_minor(chord)
    return Chord.build(r, "min" if q == "maj" else "maj")


def R(chord: Chord) -> Chord:
    """Relative: C major <-> A minor (move the fifth up a tone)."""
    r, q = _major_or_minor(chord)
    return Chord.build(r + 9, "min") if q == "maj" else Chord.build(r + 3, "maj")


def L(chord: Chord) -> Chord:
    """Leading-tone exchange: C major <-> E minor (move the root down a semitone)."""
    r, q = _major_or_minor(chord)
    return Chord.build(r + 4, "min") if q == "maj" else Chord.build(r + 8, "maj")


# --- voice leading --------------------------------------------------------
def close_voicing(
    chord: Chord, n: int, lo: int, hi: int, center: float | None = None
) -> list[int]:
    """``n`` adjacent chord tones in [lo, hi] whose average sits nearest ``center``."""
    if lo >= hi:
        raise ValueError(f"register needs lo < hi, got {lo}-{hi}")
    pool = chord.pitches(lo, hi)
    need = min(n, len(chord.pcs))
    center = (lo + hi) / 2 if center is None else center
    best: tuple[float, list[int]] | None = None
    for i in range(len(pool) - n + 1):
        window = pool[i : i + n]
        if len({pc(p) for p in window}) < need:
            continue
        key = abs(sum(window) / n - center)
        if best is None or key < best[0]:
            best = (key, window)
    if best is None:
        raise ValueError(f"register {lo}-{hi} too narrow for {n} voices of {chord}")
    return list(best[1])


def voice_lead(voicing: list[int], target: Chord, lo: int, hi: int) -> list[int]:
    """Move each voice to a tone of ``target`` with the least total motion.

    Brute force over the 4 nearest target tones per voice. Ranking: cover as
    many of the chord's pitch classes as possible, then minimize total
    semitone motion, then prefer voices moving in opposite directions.
    """
    if lo >= hi:
        raise ValueError(f"register needs lo < hi, got {lo}-{hi}")
    pool = target.pitches(lo, hi)
    if not pool:
        raise ValueError(f"no tones of {target} in register {lo}-{hi}")
    voicing = sorted(voicing)
    options = [sorted(pool, key=lambda q, p=p: (abs(q - p), q))[:4] for p in voicing]
    need = min(len(voicing), len(target.pcs))
    best = None
    for combo in itertools.product(*options):
        moves = [q - p for p, q in zip(voicing, combo, strict=True)]
        covered = len({pc(q) for q in combo})
        cost = sum(abs(m) for m in moves)
        contrary = sum(1 for a, b in itertools.combinations(moves, 2) if a * b < 0)
        key = (covered < need, cost, -contrary, tuple(sorted(combo)))
        if best is None or key < best[0]:
            best = (key, combo)
    return sorted(best[1])


# --- consonance -----------------------------------------------------------
def _plomp_levelt(f1: float, f2: float, a1: float, a2: float) -> float:
    """Dissonance of two sine partials (Plomp-Levelt curve, Sethares' fit)."""
    b1, b2, d_star, s1, s2 = 3.5, 5.75, 0.24, 0.0207, 18.96
    s = d_star / (s1 * min(f1, f2) + s2)
    d = abs(f2 - f1)
    return min(a1, a2) * (np.exp(-b1 * s * d) - np.exp(-b2 * s * d))


def roughness(pitches: Iterable[int], partials: int = 6) -> float:
    """Sensory dissonance of notes with harmonic overtones (Sethares 1993).

    Each note contributes partials k*f with amplitude 0.88^(k-1); every pair
    of partials adds its Plomp-Levelt dissonance. Lower means smoother.
    """
    comps = [
        (freq(p) * k, 0.88 ** (k - 1)) for p in pitches for k in range(1, partials + 1)
    ]
    return float(
        sum(
            _plomp_levelt(f1, f2, a1, a2)
            for (f1, a1), (f2, a2) in itertools.combinations(comps, 2)
        )
    )
