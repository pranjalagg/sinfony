"""Music theory as mathematics: pitch, scales, chords, voice leading, consonance."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

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
