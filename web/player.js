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
